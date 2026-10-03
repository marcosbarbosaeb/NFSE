"""Revisão do extrato (03/10/2026): descrição inteira, saldo fora, receita x
despesa, sugestão de tomador (nome, valor da nota em aberto) e classificação
lembrada. Dados sintéticos."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, PagamentoRecebido, PrestadorTomador, RegraExtrato
from app.services import classificar_extrato
from app.services.extrato_pdf import extrair_de_texto


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _nota(db, vinculo, competencia, valor, n):
    e = Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="77", n_dps=n, estado="confirmado", valor=Decimal(valor), origem="importada",
        tomador_snapshot={"apelido": vinculo.apelido},
    )
    db.add(e)
    db.flush()
    return e


def _csv(*linhas):
    return ("Data;Descrição;Valor\n" + "\n".join(linhas) + "\n").encode()


def test_saldo_sem_texto_fica_de_fora_e_recebido_ganha_do_nome():
    linhas = [
        "01/09/2026 149.475,82",  # saldo anterior, sem a palavra "saldo"
        '02/09/2026 Pix recebido: "Cp :123-PAGAR ME PAGAMENTOS SA" 500,00',
        '03/09/2026 Pix enviado: "Cp :456-CREDITO FACIL" 80,00',
    ]
    t = extrair_de_texto(linhas)
    assert [(x.valor, x.credito) for x in t] == [(Decimal("500.00"), True), (Decimal("80.00"), False)]


def test_linha_de_baixo_com_o_nome_entra_na_descricao():
    linhas = [
        "01 SET 2026 Total de entradas + 1.500,00",
        "Transferência recebida pelo Pix 1.000,00",
        "LOJA EXEMPLO LTDA - 11.222.333/0001-81",
        "Página 1 de 2",
        "Transferência enviada pelo Pix 200,00",
    ]
    t = extrair_de_texto(linhas)
    assert t[0].descricao == "Transferência recebida pelo Pix LOJA EXEMPLO LTDA - 11.222.333/0001-81"
    assert t[1].descricao == "Transferência enviada pelo Pix"


def test_chave_ignora_numeros_e_palavras_genericas():
    a = classificar_extrato.chave_da_descricao('Pix recebido: "Cp :90400888-EXI IMPORTACAO E COMERCIO"')
    b = classificar_extrato.chave_da_descricao('PIX RECEBIDO "cp :11111111-Exi Importação e Comércio" 09/10')
    assert a == b == "exi importacao comercio"
    assert classificar_extrato.chave_da_descricao("Pix recebido 123") == ""


def test_sugestao_por_nome_desempata_pela_nota_em_aberto(client, db, prestador_teste, vinculo_teste):
    # dois tomadores com o mesmo CNPJ (programa A e programa B), como AWIN e AWIN Rchlo
    vinculo_teste.apelido = "Programa A"
    irmao = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido="Programa B",
        cod_local_prestacao="3106200", cod_trib_nacional="100101", template_descricao="x", ativo=True,
    )
    db.add(irmao)
    db.flush()
    _nota(db, vinculo_teste, "2026-08", "3500.10", 9001)
    _nota(db, irmao, "2026-08", "55.37", 9002)
    arquivo = _csv(
        "10/09/2026;Transferencia recebida 341 7307 TOMADOR DE TESTE LTDA;3500,10",
        "11/09/2026;Pix recebido de alguem sem nome conhecido;55,37",
        "12/09/2026;Cambio Recebimento - remessa internacional;607,51",
    )
    r = client.post("/api/recebimentos/extrato", files={"arquivo": ("e.csv", arquivo, "text/csv")})
    assert r.status_code == 200, r.text
    t = r.json()["transacoes"]
    # nome bate nos dois: fica com o que tem nota em aberto daquele valor, no mês DA NOTA
    assert t[0]["vinculo_id"] == str(vinculo_teste.id) and t[0]["competencia"] == "2026-08" and t[0]["nota"]["exata"]
    # sem nome: única nota em aberto com o valor exato
    assert t[1]["vinculo_id"] == str(irmao.id) and t[1]["origem_sugestao"] == "valor"
    assert t[2]["vinculo_id"] is None and t[2]["credito"] is True
    assert "Outras despesas" in r.json()["categorias"]


def test_confirmar_lembra_e_na_proxima_ja_vem_classificado(client, db, prestador_teste, vinculo_teste):
    novo = client.post("/api/vinculos/controle", json={"nome": "Remessa internacional"})
    assert novo.status_code == 200, novo.text
    fonte = novo.json()
    assert fonte["sem_nota"] is True
    # mesmo nome de novo não duplica
    assert client.post("/api/vinculos/controle", json={"nome": "remessa internacional"}).json()["id"] == fonte["id"]

    r = client.post("/api/recebimentos/extrato/confirmar", json={
        "itens": [{"vinculo_id": fonte["id"], "competencia": "2026-09", "valor": 607.51, "data_recebimento": "2026-09-02",
                   "descricao": "Cambio Recebimento - remessa internacional"}],
        "despesas": [
            {"categoria": "Tráfego pago", "competencia": "2026-09", "valor": 300, "data": "2026-09-05",
             "descricao": 'Pix enviado: "Cp :1-AGENCIA DE ANUNCIOS XYZ"'},
            # "Pix recebido" que na verdade é saída (estorno de uma retirada): a pessoa escolhe o tipo
            {"categoria": "Distribuição de lucros", "tipo": "retirada", "competencia": "2026-09", "valor": 1000,
             "data": "2026-09-06", "descricao": 'Pix recebido: "Cp :2-FULANA SOCIA"'},
        ],
    })
    assert r.status_code == 200, r.text
    assert r.json()["sucesso"] == 1 and r.json()["despesas_registradas"] == 2
    assert db.query(RegraExtrato).count() == 3
    pagamento = db.query(PagamentoRecebido).filter_by(prestador_tomador_id=uuid.UUID(fonte["id"])).one()
    assert pagamento.origem == "extrato"
    despesa = db.query(Despesa).filter_by(categoria="Tráfego pago").one()
    assert despesa.origem == "extrato" and despesa.pago_em == date(2026, 9, 5) and "AGENCIA" in despesa.descricao
    assert db.query(Despesa).filter_by(categoria="Distribuição de lucros").one().tipo == "retirada"

    # mês seguinte: mesmas descrições (com números diferentes) já vêm classificadas
    arquivo = _csv(
        "03/10/2026;Cambio Recebimento - remessa internacional;450,00",
        '06/10/2026;Pix enviado: "Cp :9-AGENCIA DE ANUNCIOS XYZ";-310,00',
        '07/10/2026;Pix recebido: "Cp :8-FULANA SOCIA";1200,00',
        "02/09/2026;Cambio Recebimento - remessa internacional;607,51",
    )
    resp = client.post("/api/recebimentos/extrato", files={"arquivo": ("e.csv", arquivo, "text/csv")}).json()
    t = resp["transacoes"]
    assert t[0]["vinculo_id"] == fonte["id"] and t[0]["origem_sugestao"] == "lembrado" and not t[0]["ja_lancado"]
    assert t[1]["credito"] is False and t[1]["categoria"] == "Tráfego pago"
    assert t[2]["credito"] is False and t[2]["tipo_despesa"] == "retirada" and t[2]["categoria"] == "Distribuição de lucros"
    assert t[3]["ja_lancado"] is True  # o mesmo lançamento do extrato anterior
    assert "Tráfego pago" in resp["categorias"] and resp["categorias_retirada"] == ["Distribuição de lucros"]
