"""Baixa por nota (03/10/2026): duas notas do mesmo tomador no mesmo mês são
recebidas separadamente; o histórico sem nota continua valendo pro mês."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Emissao, PagamentoRecebido
from app.services import a_receber


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


def _abertas(db):
    return {n["emissao_id"]: n["valor"] for n in a_receber.notas_em_aberto(db)}


def test_recebimento_paga_so_a_nota_dele(client, db, vinculo_teste):
    menor = _nota(db, vinculo_teste, "2026-09", "3574.14", 9101)
    maior = _nota(db, vinculo_teste, "2026-09", "14000.00", 9102)
    assert _abertas(db) == {menor.id: 3574.14, maior.id: 14000.0}

    # sem dizer a nota, o valor decide: paga a de 3.574,14 e a de 14.000 continua em aberto
    r = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 3574.14})
    assert r.status_code == 200, r.text
    assert _abertas(db) == {maior.id: 14000.0}
    assert a_receber.totais(db)["a_receber_total"] == 14000.0

    lista = {x["id"]: x["pagamento_recebido"] for x in client.get("/api/dps?ano=2026").json()}
    assert lista[str(menor.id)] is True and lista[str(maior.id)] is False
    painel = client.get("/api/painel/resumo-mes?competencia=2026-09")
    assert painel.status_code == 200, painel.text
    linhas = {l["emissao_id"]: l for l in painel.json()["emissoes"]}
    assert linhas[str(menor.id)]["pagamento_recebido"] is True and linhas[str(maior.id)]["pagamento_recebido"] is False
    proximos = client.get("/api/painel/proximos").json()["pendencias"]
    assert [p["valor"] for p in proximos if p["tipo"] == "receber"] == [14000.0]

    # dizendo a nota
    r = client.post("/api/pagamentos", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-10", "valor": 13900, "emissao_id": str(maior.id),
    })
    assert r.status_code == 200 and r.json()["competencia"] == "2026-09"  # fica no mês da nota
    assert _abertas(db) == {}

    # desfazer é por nota
    assert client.delete(f"/api/pagamentos?emissao_id={menor.id}").json() == {"removidos": 1}
    assert _abertas(db) == {menor.id: 3574.14}


def test_historico_sem_nota_vale_pro_mes_e_desfazer_uma_nao_abre_a_outra(client, db, prestador_teste, vinculo_teste):
    a = _nota(db, vinculo_teste, "2026-03", "100.00", 9201)
    b = _nota(db, vinculo_teste, "2026-03", "250.00", 9202)
    db.add(PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-03",
        valor=Decimal("350.00"), origem="planilha", mes_inteiro=True,
    ))
    db.flush()
    assert _abertas(db) == {}
    recebido = a_receber.totais(db)["recebido_total"]

    assert client.delete(f"/api/pagamentos?emissao_id={a.id}").status_code == 200
    assert _abertas(db) == {a.id: 100.0}  # só a que foi desfeita volta
    assert a_receber.totais(db)["recebido_total"] == recebido  # o dinheiro lançado não muda
    assert db.query(PagamentoRecebido).filter_by(emissao_id=b.id).count() == 1


def test_conciliar_e_recebimento_sem_nota(client, db, vinculo_teste):
    a = _nota(db, vinculo_teste, "2026-02", "80.00", 9301)
    r = client.post("/api/financeiro/conciliar", json={"ate": "2026-02"})
    assert r.status_code == 200 and r.json()["conciliadas"] == 1
    assert db.query(PagamentoRecebido).filter_by(emissao_id=a.id).one().valor == 0

    # dinheiro que cai sem nota no mês fica sem nota (e aparece no aviso)
    p = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 500}).json()
    assert p["sem_nota"] is True
    assert db.get(PagamentoRecebido, uuid.UUID(p["id"])).emissao_id is None
    assert [x["competencia"] for x in a_receber.recebimentos_sem_nota(db)] == ["2026-08"]


def test_extrato_sugere_e_grava_a_nota(client, db, vinculo_teste):
    menor = _nota(db, vinculo_teste, "2026-09", "3574.14", 9401)
    maior = _nota(db, vinculo_teste, "2026-09", "14000.00", 9402)
    arquivo = "Data;Descrição;Valor\n23/09/2026;Pix recebido TOMADOR DE TESTE LTDA;3574,14\n".encode()
    resp = client.post("/api/recebimentos/extrato", files={"arquivo": ("e.csv", arquivo, "text/csv")}).json()
    t = resp["transacoes"][0]
    assert t["emissao_id"] == str(menor.id) and t["vinculo_id"] == str(vinculo_teste.id)
    assert {n["emissao_id"] for n in resp["notas_abertas"]} == {str(menor.id), str(maior.id)}

    r = client.post("/api/recebimentos/extrato/confirmar", json={"itens": [{
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 3574.14, "data_recebimento": "2026-09-23",
        "descricao": "Pix recebido TOMADOR DE TESTE LTDA", "emissao_id": str(menor.id),
    }]})
    assert r.status_code == 200 and r.json()["sucesso"] == 1
    assert _abertas(db) == {maior.id: 14000.0}
