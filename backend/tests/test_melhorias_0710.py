"""Melhorias de 07/10/2026: completar a empresa pelo CNPJ, desfazer
importações (extrato, planilha, Emissor Nacional) e os e-mails de exemplo
da Gestão. Só dados sintéticos."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, LancamentoBancario, PagamentoRecebido, PrestadorTomador
from app.services import completar_empresa, importar_adn
from app.services.cnpj_lookup import ConsultaCnpjIndisponivelError, DadosCnpj

from tests.test_importar_nacional import nfse


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


def _receita(**extra) -> DadosCnpj:
    base = dict(
        razao_social="EMPRESA SINTETICA LTDA", logradouro="RUA DAS FLORES", numero="100", complemento="SALA 2", bairro="CENTRO",
        cep="30130-000", municipio="BELO HORIZONTE", uf="MG", cod_municipio_sugerido="3106200", situacao_cadastral="ATIVA",
        nome_fantasia="SINTETICA", regime="3", telefone="3133334444", email="contato@sintetica.example",
    )
    return DadosCnpj(**{**base, **extra})


# --- completar pelo CNPJ ------------------------------------------------------


def test_completar_preenche_so_o_que_esta_em_branco(client, db, prestador_teste, monkeypatch):
    p = prestador_teste
    p.cep = p.logradouro = p.numero = p.bairro = p.complemento = None
    p.op_simples_nacional = p.regime_apuracao_sn = None
    p.nome_fantasia = "Meu Nome de Sempre"
    p.telefone = None
    db.flush()
    monkeypatch.setattr(completar_empresa, "consultar_cnpj", lambda cnpj: _receita())

    r = client.post("/api/prestador/completar-pelo-cnpj")
    assert r.status_code == 200, r.text
    assert r.json()["preenchidos"][:2] == ["endereço", "regime tributário"] and "nome fantasia" not in r.json()["preenchidos"]
    db.refresh(p)
    assert (p.cep, p.logradouro, p.numero, p.bairro) == ("30130000", "RUA DAS FLORES", "100", "CENTRO")
    assert p.op_simples_nacional == "3" and p.regime_apuracao_sn == "1"
    assert p.nome_fantasia == "Meu Nome de Sempre"  # o que a pessoa escreveu fica
    # ME/EPP do Simples: a alíquota a Receita não sabe — continua faltando
    assert [f["campo"] for f in r.json()["faltam"]] == (["aliquota"] if p.aliquota_atual is None else [])


def test_completar_mei_e_receita_fora_do_ar(client, db, prestador_teste, monkeypatch):
    p = prestador_teste
    p.op_simples_nacional = None
    p.cep = None
    db.flush()

    def fora(cnpj):
        raise ConsultaCnpjIndisponivelError("timeout")

    monkeypatch.setattr(completar_empresa, "consultar_cnpj", fora)
    assert client.post("/api/prestador/completar-pelo-cnpj").status_code == 503
    db.refresh(p)
    assert p.op_simples_nacional is None

    monkeypatch.setattr(completar_empresa, "consultar_cnpj", lambda cnpj: _receita(regime="2"))
    r = client.post("/api/prestador/completar-pelo-cnpj")
    assert r.status_code == 200 and "regime tributário" in r.json()["preenchidos"]
    db.refresh(p)
    assert p.op_simples_nacional == "2" and r.json()["faltam"] == []


def test_regime_vem_da_receita(monkeypatch):
    from app.services import cnpj_lookup

    class Resp:
        status_code = 200

        def __init__(self, corpo):
            self._corpo = corpo

        def json(self):
            return self._corpo

    base = {"razao_social": "X LTDA", "municipio": "BELO HORIZONTE", "uf": "MG", "codigo_municipio_ibge": 3106200}
    for corpo, esperado in (
        ({"opcao_pelo_mei": True, "opcao_pelo_simples": True}, "2"),
        ({"opcao_pelo_mei": False, "opcao_pelo_simples": True}, "3"),
        ({"opcao_pelo_mei": False, "opcao_pelo_simples": False}, "1"),
        ({"opcao_pelo_mei": None, "opcao_pelo_simples": None}, None),
    ):
        monkeypatch.setattr(cnpj_lookup.requests, "get", lambda url, timeout, c=corpo, **kw: Resp({**base, **c}))
        assert cnpj_lookup.consultar_cnpj("00000000000191").regime == esperado


# --- desfazer importação do extrato -------------------------------------------


def _nota(db, vinculo, competencia, valor, n):
    e = Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="78", n_dps=n, estado="confirmado", valor=Decimal(valor), origem="ana", tomador_snapshot={"apelido": vinculo.apelido},
    )
    db.add(e)
    db.flush()
    return e


def test_desfazer_extrato_apaga_o_que_ele_criou_e_reabre_o_resto(client, db, prestador_teste, vinculo_teste):
    nota = _nota(db, vinculo_teste, "2026-09", "500.00", 8801)
    # o que a pessoa lançou à mão: nunca é tocado
    manual = Despesa(id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="Internet", competencia="2026-09", valor=Decimal("99.90"), pago=True)
    conta = Despesa(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="Contador", descricao="Honorários", competencia="2026-09",
        valor=Decimal("300.00"), pago=False,
    )
    db.add_all([manual, conta])
    db.flush()

    r = client.post("/api/recebimentos/extrato/confirmar", json={
        "arquivo": "extrato-setembro.pdf",
        "itens": [{
            "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 500.0, "data_recebimento": "2026-09-10",
            "descricao": "PIX RECEBIDO TOMADOR", "emissao_id": str(nota.id),
        }],
        "despesas": [{"categoria": "Software", "competencia": "2026-09", "valor": 59.9, "descricao": "ASSINATURA APP", "data": "2026-09-11", "tipo": "despesa"}],
        "pendentes": [{"data": "2026-09-12", "descricao": "PAGTO BOLETO CONTADOR", "valor": 300.0, "credito": False}],
    })
    assert r.status_code == 200, r.text
    # a linha que ficou pendente paga a conta que já existia
    pendente = next(l for l in client.get("/api/conciliacao").json()["lancamentos"] if l["descricao"] == "PAGTO BOLETO CONTADOR")
    assert client.post(f"/api/conciliacao/{pendente['id']}/despesa", json={"despesa_id": str(conta.id)}).status_code == 200
    db.refresh(conta)
    assert conta.pago is True

    lista = client.get("/api/financeiro/importacoes").json()["importacoes"]
    assert len(lista) == 1 and lista[0]["tipo"] == "extrato" and lista[0]["titulo"] == "extrato-setembro.pdf"
    assert lista[0]["resumo"] == "3 linhas, 1 recebimento, 2 despesas"

    r = client.post("/api/financeiro/importacoes/desfazer", json={"tipo": "extrato", "quando": lista[0]["quando"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"linhas": 3, "recebimentos": 1, "despesas": 1, "contas_reabertas": 1}
    db.expire_all()
    assert db.query(LancamentoBancario).count() == 0
    assert db.query(PagamentoRecebido).count() == 0  # a nota volta a ficar a receber
    assert {d.categoria: d.pago for d in db.query(Despesa)} == {"Internet": True, "Contador": False}
    assert client.get("/api/financeiro/importacoes").json()["importacoes"] == []
    assert client.post("/api/financeiro/importacoes/desfazer", json={"tipo": "extrato", "quando": lista[0]["quando"]}).status_code == 404


def test_desfazer_planilha_nao_toca_no_que_e_manual(client, db, prestador_teste, vinculo_teste):
    db.add_all([
        PagamentoRecebido(
            id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-03",
            valor=Decimal("10.00"), origem="planilha", mes_inteiro=True,
        ),
        PagamentoRecebido(
            id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-04",
            valor=Decimal("20.00"), origem="manual",
        ),
        Despesa(id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="Aluguel", competencia="2026-03", valor=Decimal("1.00"), origem="planilha"),
        Despesa(id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="Luz", competencia="2026-03", valor=Decimal("2.00")),
    ])
    db.flush()
    lista = client.get("/api/financeiro/importacoes").json()["importacoes"]
    assert [i["tipo"] for i in lista] == ["planilha"]
    r = client.post("/api/financeiro/importacoes/desfazer", json={"tipo": "planilha", "quando": lista[0]["quando"]})
    assert r.status_code == 200 and r.json()["recebimentos"] == 1 and r.json()["despesas"] == 1
    db.expire_all()
    assert [p.origem for p in db.query(PagamentoRecebido)] == ["manual"]
    assert [d.categoria for d in db.query(Despesa)] == ["Luz"]


# --- desfazer importação do Emissor Nacional -----------------------------------


def test_desfazer_importacao_do_emissor_nacional(client, db, prestador_teste, vinculo_teste, monkeypatch):
    monkeypatch.setattr(importar_adn, "PAUSA_S", 0)
    da_ana = _nota(db, vinculo_teste, "2026-03", "40.00", 8901)
    antiga = Emissao(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, prestador_tomador_id=vinculo_teste.id, competencia="2025-12",
        serie="900", n_dps=77, estado="confirmado", valor=Decimal("5.00"), origem="importada", tomador_snapshot={"importada": True},
    )
    db.add(antiga)
    db.flush()
    a1, _ = nfse(1, "11222333000181", "TOMADOR", "2026-01", "100.00")
    novo, _ = nfse(3, "44555666000199", "Empresa Nova SA", "2026-02", "300.00")
    paginas = [[{"nsu": 1, "tipo": "NFSE", "xml": a1}, {"nsu": 2, "tipo": "NFSE", "xml": novo}], []]

    def pagina_falsa(cliente, cnpj, nsu):
        pagina = paginas.pop(0)
        return pagina, (max(d["nsu"] for d in pagina) if pagina else None)

    monkeypatch.setattr(importar_adn, "ler_pagina", pagina_falsa)
    monkeypatch.setattr("app.main._cliente_producao", lambda db, p: object())
    importar_adn._buscas.pop(prestador_teste.id, None)
    assert client.post("/api/importar/nacional/buscar", json={"desde": "2025-01"}).status_code == 200
    r = client.post("/api/importar/nacional", json={"mapeamento": [
        {"documento": "11222333000181", "acao": "vinculo", "vinculo_id": str(vinculo_teste.id)},
        {"documento": "44555666000199", "acao": "novo"},
    ]})
    assert r.status_code == 200 and r.json()["importadas"] == 2 and r.json()["vinculos_criados"] == 1
    assert db.query(PrestadorTomador).count() == 2
    db.refresh(prestador_teste)
    assert prestador_teste.adn_ultimo_nsu == 2

    lista = client.get("/api/importar/nacional/importacoes").json()["importacoes"]
    assert [(i["titulo"], i["notas"]) for i in lista] == [("Importação do Emissor Nacional", 2), ("Importações anteriores", 1)]
    assert lista[0]["periodo"] == "2026-01 a 2026-02"

    r = client.post("/api/importar/nacional/desfazer", json={"importacao": lista[0]["id"]})
    assert r.status_code == 200 and r.json() == {"notas": 2, "tomadores": 1}
    db.expire_all()
    # ficam a nota da Ana e a importada de antes; o tomador criado some
    assert {e.id for e in db.query(Emissao)} == {da_ana.id, antiga.id}
    assert [v.id for v in db.query(PrestadorTomador)] == [vinculo_teste.id]
    assert db.get(type(prestador_teste), prestador_teste.id).adn_ultimo_nsu == 0

    assert client.post("/api/importar/nacional/desfazer", json={"importacao": lista[0]["id"]}).status_code == 404
    r = client.post("/api/importar/nacional/desfazer", json={"importacao": "anteriores"})
    assert r.status_code == 200 and r.json()["notas"] == 1
    db.expire_all()
    assert [e.id for e in db.query(Emissao)] == [da_ana.id]
