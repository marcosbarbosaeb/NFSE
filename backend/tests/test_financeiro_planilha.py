"""Módulo financeiro (contas do mês com check, rotina, resumo com lucro e
retiradas) e importação da planilha de controle — planilha sintética com o
mesmo formato (blocos por nome, meses nas colunas)."""
import datetime
import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, DespesaRecorrente, PagamentoRecebido, PrestadorTomador, RotinaMensal, RotinaMensalFeita
from app.services import importar_planilha
from app.services.motor_emissao import criar_rascunho

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def planilha() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Pagamentos recebidos", *MESES, "Total"])
    ws.append(["Fornecedor Teste (x)", 100, 200, 300, 400, None, None, None, None, None, None, None, None, 1000])
    ws.append(["Mercado Teste", 10, 20, "-", 40])
    ws.append(["Parcerias", 0, "-", 1500])
    ws.append([None, 110, 220])
    ws.append(["NF Geradas", *MESES, "Total"])
    ws.append(["Fornecedor Teste", 100, 200, 300, 400])
    ws.append(["Mercado Teste", 5, 10, 20, "-", 40])
    ws.append([None, 1, 2])
    ws.append(["Despesas", *MESES, "Total"])
    ws.append(["Contabilidade (Pivot)", 550, 550, 550, 550, 550, 550, 550, 570, 570, 570, 570, 570])
    ws.append(["Simples Nacional", 800, 1000, 1500, 1200, 700, 900, 1800, 1850, 1600])
    ws.append(["-", "-", "-"])
    ws.append(["Manychat", 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90])
    ws.append([None, 1440, 1640])
    ws.append([None, None, None, None, None, None, None, None, None, None, None, None, None, "Total"])
    ws.append(["Lucro ", 1, 2])
    ws.append(["Margem de lucro", 0.9, 0.8])
    ws.append(["Distribuição de lucros Inter", 50, 60])
    ws.append(["ML", 0, 25])
    ws.append(["Total", 50, 85])
    ws.append([None, *MESES])
    ws.append(["Extrato Inter", "X", "x", None])
    ws.append(["NF Facebook", "X"])
    ws.append(["Dia da atualização"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


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


def test_leitura_da_planilha():
    blocos = importar_planilha.ler(planilha())
    assert [r["nome"] for r in blocos["recebidos"]] == ["Fornecedor Teste (x)", "Mercado Teste", "Parcerias"]
    assert [d["nome"] for d in blocos["despesas"]] == ["Contabilidade (Pivot)", "Simples Nacional", "Manychat"]
    assert [r["conta"] for r in blocos["retiradas"]] == ["Inter", "ML"]
    assert blocos["rotinas"] == [{"nome": "Extrato Inter", "feitos": [1, 2]}, {"nome": "NF Facebook", "feitos": [1]}]
    merc = blocos["recebidos"][1]
    nf = importar_planilha._achar_nf(merc["nome"], blocos["nf"])
    assert importar_planilha.deslocamento(merc["valores"], nf["valores"]) == 1  # pago em jan = nota de fev


def test_importar_planilha_e_financeiro(client, db, prestador_teste, vinculo_teste, monkeypatch):
    hoje = datetime.date(2026, 9, 28)
    monkeypatch.setattr("app.main.hoje_br", lambda: hoje)
    arquivo = {"arquivo": ("controle.xlsx", planilha(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/importar/planilha/previa", files=arquivo, data={"ano": "2026"})
    assert r.status_code == 200, r.text
    previa = r.json()
    receitas = {x["nome"]: x for x in previa["receitas"]}
    assert receitas["Fornecedor Teste (x)"]["vinculo_id"] == str(vinculo_teste.id)
    assert receitas["Mercado Teste"]["deslocamento"] == 1
    contab = next(d for d in previa["despesas"] if d["categoria"] == "Contabilidade")
    assert contab["recorrente"] and contab["valor_padrao"] == 570
    simples = next(d for d in previa["despesas"] if d["categoria"] == "Simples Nacional")
    assert simples["recorrente"] and simples["valor_padrao"] is None

    escolhas = {"receitas": [
        {"linha": 0, "acao": "vinculo", "vinculo_id": str(vinculo_teste.id), "deslocamento": 0},
        {"linha": 1, "acao": "ignorar"},
        {"linha": 2, "acao": "novo", "deslocamento": 0},
    ]}
    r = client.post("/api/importar/planilha", files=arquivo, data={"ano": "2026", "escolhas": json.dumps(escolhas)})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["pagamentos"] == 5 and res["tomadores_criados"] == 1 and res["contas_fixas"] == 3
    assert res["retiradas"] == 3 and res["rotinas"] == 2
    pag = db.query(PagamentoRecebido).filter_by(prestador_tomador_id=vinculo_teste.id).count()
    assert pag == 4
    parceria = db.query(PrestadorTomador).filter_by(apelido="Parcerias").one()
    assert parceria.sem_nota and parceria.tomador.status == "interno"
    # conta de outubro (futura) entrou "a pagar"
    out = db.query(Despesa).filter_by(competencia="2026-10", categoria="Contabilidade").one()
    assert out.pago is False and out.recorrente_id is not None
    assert db.query(RotinaMensalFeita).count() == 3

    # reimportar não duplica
    res2 = client.post("/api/importar/planilha", files=arquivo, data={"ano": "2026", "escolhas": json.dumps(escolhas)}).json()
    assert res2["pagamentos"] == 0 and res2["despesas"] == 0 and res2["retiradas"] == 0

    # contas do mês: outubro já tem os lançamentos importados, sem duplicar
    mes = client.get("/api/financeiro/mes?competencia=2026-10").json()
    nomes = [c["descricao"] for c in mes["contas"]]
    assert nomes.count("Contabilidade (Pivot)") == 1 and "Simples Nacional" in nomes
    simples_out = next(c for c in mes["contas"] if c["descricao"] == "Simples Nacional")
    assert simples_out["valor_a_definir"] and not simples_out["pago"]
    assert {r["nome"] for r in mes["rotinas"]} == {"Extrato Inter", "NF Facebook"}

    # ticar: pagou o Simples com o valor do mês; rotina feita
    r = client.patch(f"/api/despesas/{simples_out['id']}", json={"valor": 1700, "pago": True})
    assert r.status_code == 200 and r.json()["pago"] and r.json()["pago_em"]
    rotina = next(r for r in mes["rotinas"] if r["nome"] == "NF Facebook")
    assert client.post(f"/api/financeiro/rotinas/{rotina['id']}/check", json={"competencia": "2026-10", "feita": True}).status_code == 200
    mes = client.get("/api/financeiro/mes?competencia=2026-10").json()
    assert next(r for r in mes["rotinas"] if r["nome"] == "NF Facebook")["feita"]

    # resumo: lucro = recebido − despesas; retiradas à parte
    criar_rascunho(db, vinculo_teste, competencia="2026-02", valor=200, tpAmb="2")
    resumo = client.get("/api/financeiro/resumo?ano=2026").json()
    assert resumo["recebido"][0] == 100 and resumo["despesas"][0] == 550 + 800 + 90
    assert resumo["lucro"][0] == round(100 - 1440, 2)
    assert resumo["impostos"][0] == 800 and resumo["ferramentas"][0] == 90
    assert resumo["retiradas"][:2] == [50, 85]
    assert resumo["categorias"][0]["categoria"] in ("Simples Nacional", "Contabilidade")


def test_contas_fixas_e_lancamento_manual(client, db, prestador_teste, monkeypatch):
    monkeypatch.setattr("app.main.hoje_br", lambda: datetime.date(2026, 9, 10))
    r = client.post("/api/financeiro/contas-fixas", json={"nome": "Cartão Inter", "categoria": "Cartão", "dia_vencimento": 31})
    assert r.status_code == 200, r.text
    conta_id = r.json()["id"]
    mes = client.get("/api/financeiro/mes?competencia=2026-09").json()
    cartao = next(c for c in mes["contas"] if c["descricao"] == "Cartão Inter")
    assert cartao["vencimento"] == "2026-09-30" and cartao["valor_a_definir"]
    # mês anterior à criação não ganha lançamento
    antes = client.get("/api/financeiro/mes?competencia=2025-01").json()
    assert all(c["descricao"] != "Cartão Inter" for c in antes["contas"])

    r = client.post("/api/despesas", json={"categoria": "Distribuição de lucros", "competencia": "2026-09", "valor": 1000, "tipo": "retirada", "conta": "Inter"})
    assert r.status_code == 200 and r.json()["tipo"] == "retirada" and r.json()["pago"]
    assert client.delete(f"/api/despesas/{r.json()['id']}").status_code == 200

    assert client.delete(f"/api/financeiro/contas-fixas/{conta_id}").status_code == 200
    assert db.get(DespesaRecorrente, uuid.UUID(conta_id)).ativa is False
    assert db.query(Despesa).filter_by(recorrente_id=uuid.UUID(conta_id)).count() == 0

    r = client.post("/api/financeiro/rotinas", json={"nome": "Conferir PayPal"})
    assert r.status_code == 200 and db.query(RotinaMensal).count() == 1
