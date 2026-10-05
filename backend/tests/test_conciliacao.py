"""Conciliação do extrato, recebimento sem nota e troca de nota não enviada
(05/10/2026). Dados sintéticos."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, LancamentoBancario, PagamentoRecebido, PrestadorTomador
from app.financeiro import a_receber


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


def _nota(db, vinculo, competencia, valor, n, estado="confirmado"):
    e = Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="77", n_dps=n, estado=estado, valor=Decimal(valor), origem="importada",
        tomador_snapshot={"apelido": vinculo.apelido},
    )
    db.add(e)
    db.flush()
    return e


def test_quem_paga_antes_nao_cai_na_nota_ja_paga(client, db, prestador_teste, vinculo_teste):
    """Amazon: a nota de setembro já está paga (histórico); o dinheiro que cai
    em setembro é da nota de outubro — fica como recebimento sem nota."""
    setembro = _nota(db, vinculo_teste, "2026-09", "44409.35", 9501)
    db.add(PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-09",
        valor=Decimal("44409.35"), origem="planilha", mes_inteiro=True,
    ))
    db.flush()
    r = client.post("/api/pagamentos", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 70701.53, "data_recebimento": "2026-09-29",
    }).json()
    assert r["sem_nota"] is True and r["emissao_id"] is None
    assert [x["valor"] for x in client.get("/api/financeiro/recebimentos-sem-nota").json()] == [70701.53]
    lista = client.get("/api/pagamentos?ano=2026").json()
    assert next(p for p in lista if p["id"] == r["id"])["pode_gerar_nota"] is True

    # já existe a nota de outubro, ainda não enviada: avisa em vez de travar...
    outubro = _nota(db, vinculo_teste, "2026-10", "70701.53", 9502, estado="montado")
    dup = client.get(f"/api/dps/verificar-duplicata?vinculo_id={vinculo_teste.id}&competencia=2026-10").json()
    assert dup["pode_substituir"] is True and dup["valor"] == 70701.53
    corpo = {"vinculo_id": str(vinculo_teste.id), "competencia": "2026-10", "data_competencia": "2026-10-04",
             "valor": 70701.53, "pagamento_id": r["id"]}
    recusa = client.post("/api/dps", json=corpo)
    assert recusa.status_code == 409 and "ainda não foi enviada" in recusa.json()["detail"]

    # ...e dá pra ligar o recebimento à nota que já existe
    ligado = client.patch(f"/api/pagamentos/{r['id']}", json={"emissao_id": str(outubro.id)}).json()
    assert ligado["competencia"] == "2026-10" and ligado["emissao_id"] == str(outubro.id)
    assert a_receber.notas_em_aberto(db) == [] and client.get("/api/financeiro/recebimentos-sem-nota").json() == []

    # ou gerar outra no lugar: a antiga some e o recebimento passa pra nova
    nova = client.post("/api/dps", json={**corpo, "pagamento_id": None, "valor": 70000, "substituir": True})
    assert nova.status_code == 200, nova.text
    assert db.get(Emissao, outubro.id) is None
    assert str(db.get(PagamentoRecebido, uuid.UUID(r["id"])).emissao_id) == nova.json()["id"]

    # nota já emitida no mês: não substitui
    assert client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 10, "substituir": True,
    }).status_code == 409
    assert db.get(Emissao, setembro.id) is not None


def test_importar_guarda_tudo_e_conciliar_depois(client, db, prestador_teste, vinculo_teste):
    nota = _nota(db, vinculo_teste, "2026-09", "410.73", 9601)
    conta = Despesa(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="Contador", descricao="Contabilidade", competencia="2026-09",
        valor=Decimal("350.00"), pago=False, origem="recorrente",
    )
    db.add(conta)
    db.flush()

    pendentes = [
        {"data": "2026-09-08", "descricao": "Pix recebido TOMADOR DE TESTE LTDA", "valor": 410.73, "credito": True},
        {"data": "2026-09-10", "descricao": "Pix enviado ESCRITORIO CONTABIL", "valor": 350.0, "credito": False},
        {"data": "2026-09-11", "descricao": "Pix enviado LOJA DE MOVEIS", "valor": 900.0, "credito": False},
        {"data": "2026-09-12", "descricao": "Aplicacao CDB", "valor": 5000.0, "credito": False},
        {"data": "2026-09-13", "descricao": "Pix recebido CLIENTE NOVO", "valor": 200.0, "credito": True},
    ]
    r = client.post("/api/recebimentos/extrato/confirmar", json={"pendentes": pendentes, "arquivo": "extrato.ofx"})
    assert r.status_code == 200, r.text
    assert r.json()["pendentes"] == 5 and db.query(PagamentoRecebido).count() == 0
    # reimportar o mesmo arquivo não duplica
    assert client.post("/api/recebimentos/extrato/confirmar", json={"pendentes": pendentes}).json()["pendentes"] == 5
    pendencias = client.get("/api/financeiro/pendencias").json()
    assert any(p["tipo"] == "conciliar" and p["titulo"].startswith("5 ") for p in pendencias)
    # ...e a Visão geral do emissor não fala disso
    assert all(p["tipo"] != "conciliar" for p in client.get("/api/painel/proximos").json()["pendencias"])

    painel = client.get("/api/conciliacao").json()
    por_valor = {l["valor"]: l for l in painel["lancamentos"]}
    assert por_valor[410.73]["emissao_id"] == str(nota.id) and por_valor[410.73]["nota_exata"] is True
    assert por_valor[350.0]["despesa_id"] == str(conta.id)  # conta a pagar do mesmo valor
    assert [c["id"] for c in painel["contas_a_pagar"]] == [str(conta.id)]

    # 1) entrada com nota do mesmo valor: de uma vez
    assert client.post("/api/conciliacao/automatico").json() == {"conciliados": 1}
    assert a_receber.notas_em_aberto(db) == []
    # 2) saída paga a conta que estava em aberto
    assert client.post(f"/api/conciliacao/{por_valor[350.0]['id']}/despesa", json={"despesa_id": str(conta.id)}).status_code == 200
    db.refresh(conta)
    assert conta.pago is True and str(conta.pago_em) == "2026-09-10"
    # 3) saída sem conta prevista: vira despesa nova da categoria escolhida
    r = client.post(f"/api/conciliacao/{por_valor[900.0]['id']}/despesa", json={"categoria": "Móveis"})
    assert r.status_code == 200 and db.query(Despesa).filter_by(categoria="Móveis").one().valor == 900
    # 4) movimentação que não é do negócio: ignorar
    assert client.post(f"/api/conciliacao/{por_valor[5000.0]['id']}/ignorar").status_code == 200
    assert [x["valor"] for x in client.get("/api/conciliacao/ignorados").json()] == [5000.0]
    # 5) entrada sem nota: recebimento do tomador, com a opção de gerar a nota
    r = client.post(f"/api/conciliacao/{por_valor[200.0]['id']}/receita", json={"vinculo_id": str(vinculo_teste.id)}).json()
    assert r["pode_gerar_nota"] is True and r["emissao_id"] is None and r["competencia"] == "2026-09"

    assert client.get("/api/conciliacao").json()["lancamentos"] == []
    # conciliar duas vezes não passa
    assert client.post(f"/api/conciliacao/{por_valor[200.0]['id']}/receita", json={"vinculo_id": str(vinculo_teste.id)}).status_code == 422
    # apagar o recebimento devolve o lançamento pra lista
    db.query(PagamentoRecebido).filter(PagamentoRecebido.id == uuid.UUID(r["pagamento_id"])).delete()
    db.flush()
    db.expire_all()
    assert [l["valor"] for l in client.get("/api/conciliacao").json()["lancamentos"]] == [200.0]


def test_classificado_na_importacao_ja_fica_conciliado(client, db, vinculo_teste):
    r = client.post("/api/recebimentos/extrato/confirmar", json={
        "itens": [{"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 100, "data_recebimento": "2026-09-02",
                   "descricao": "Pix recebido FULANO"}],
        "despesas": [{"categoria": "Tarifas bancárias", "competencia": "2026-09", "valor": 12.5, "data": "2026-09-03",
                      "descricao": "Tarifa pacote"}],
        "pendentes": [{"data": "2026-09-04", "descricao": "TED recebida SICLANO", "valor": 77, "credito": True}],
    })
    assert r.status_code == 200 and r.json()["pendentes"] == 1
    estados = {float(l.valor): l.status for l in db.query(LancamentoBancario)}
    assert estados == {100.0: "conciliado", 12.5: "conciliado", 77.0: "pendente"}
    # próxima leitura do mesmo extrato: as já conciliadas vêm como "já lançado"
    arquivo = "Data;Descrição;Valor\n02/09/2026;Pix recebido FULANO;100,00\n04/09/2026;TED recebida SICLANO;77,00\n".encode()
    t = client.post("/api/recebimentos/extrato", files={"arquivo": ("e.csv", arquivo, "text/csv")}).json()["transacoes"]
    assert [x["ja_lancado"] for x in t] == [True, False]


def test_irmao_com_nota_do_mesmo_valor_ganha_da_regra_lembrada(client, db, prestador_teste, vinculo_teste):
    """AWIN x AWIN Rchlo: mesma descrição no extrato, a regra lembra "AWIN" —
    mas os R$ 553,74 são da nota da Rchlo."""
    irmao = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido="Programa B",
        cod_local_prestacao="3106200", cod_trib_nacional="100101", template_descricao="x", ativo=True,
    )
    db.add(irmao)
    db.flush()
    _nota(db, vinculo_teste, "2026-09", "35951.41", 9701)
    nota_b = _nota(db, irmao, "2026-09", "553.74", 9702)
    from app.financeiro import classificar_extrato

    classificar_extrato.lembrar(db, prestador_teste.id, "Transferencia recebida REDE DE AFILIADOS", credito=True, vinculo_id=vinculo_teste.id)
    arquivo = ("Data;Descrição;Valor\n24/09/2026;Transferencia recebida REDE DE AFILIADOS;35951,41\n"
               "24/09/2026;Transferencia recebida REDE DE AFILIADOS;553,74\n").encode()
    t = client.post("/api/recebimentos/extrato", files={"arquivo": ("e.csv", arquivo, "text/csv")}).json()["transacoes"]
    assert t[0]["vinculo_id"] == str(vinculo_teste.id)
    assert t[1]["vinculo_id"] == str(irmao.id) and t[1]["emissao_id"] == str(nota_b.id)


def test_ordem_da_rotina(client, db):
    ids = [client.post("/api/financeiro/rotinas", json={"nome": n}).json()["id"] for n in ("A", "B", "C")]
    assert client.put("/api/financeiro/rotinas/ordem", json={"ids": [ids[2], ids[0], ids[1]]}).status_code == 200
    db.expire_all()
    assert [r["nome"] for r in client.get("/api/financeiro/rotinas").json()] == ["C", "A", "B"]
