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
    assert importar_planilha.deslocamento(merc["valores"], nf["valores"]) == 1  # caiu em jan, nota em fev


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


def test_planilha_soma_linhas_do_mesmo_tomador(client, db, vinculo_teste):
    from app.models import PagamentoRecebido

    arquivo = {"arquivo": ("c.xlsx", planilha(), "application/octet-stream")}
    escolhas = {"receitas": [
        {"linha": 0, "acao": "vinculo", "vinculo_id": str(vinculo_teste.id), "deslocamento": 0},
        {"linha": 1, "acao": "vinculo", "vinculo_id": str(vinculo_teste.id), "deslocamento": 0},
    ], "despesas": False, "recorrentes": False, "retiradas": False, "rotinas": False}
    r = client.post("/api/importar/planilha", files=arquivo, data={"ano": "2026", "escolhas": json.dumps(escolhas)})
    assert r.status_code == 200 and r.json()["pagamentos"] == 7
    jan = db.query(PagamentoRecebido).filter_by(prestador_tomador_id=vinculo_teste.id, competencia="2026-01").all()
    assert sorted(float(p.valor) for p in jan) == [10, 100]
    assert client.post("/api/importar/planilha", files=arquivo, data={"ano": "2026", "escolhas": json.dumps(escolhas)}).json()["pagamentos"] == 0


def test_contas_fixas_e_lancamento_manual(client, db, prestador_teste, monkeypatch):
    import calendar

    hoje = datetime.date.today()
    monkeypatch.setattr("app.main.hoje_br", lambda: hoje)
    comp = f"{hoje.year:04d}-{hoje.month:02d}"
    r = client.post("/api/financeiro/contas-fixas", json={"nome": "Cartão Inter", "categoria": "Cartão", "dia_vencimento": 31})
    assert r.status_code == 200, r.text
    conta_id = r.json()["id"]
    mes = client.get(f"/api/financeiro/mes?competencia={comp}").json()
    cartao = next(c for c in mes["contas"] if c["descricao"] == "Cartão Inter")
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    assert cartao["vencimento"] == f"{comp}-{ultimo:02d}" and cartao["valor_a_definir"]
    # mês anterior à criação não ganha lançamento
    antes = client.get("/api/financeiro/mes?competencia=2025-01").json()
    assert all(c["descricao"] != "Cartão Inter" for c in antes["contas"])

    r = client.post("/api/despesas", json={"categoria": "Distribuição de lucros", "competencia": comp, "valor": 1000, "tipo": "retirada", "conta": "Inter"})
    assert r.status_code == 200 and r.json()["tipo"] == "retirada" and r.json()["pago"]
    assert client.delete(f"/api/despesas/{r.json()['id']}").status_code == 200

    assert client.delete(f"/api/financeiro/contas-fixas/{conta_id}").status_code == 200
    assert db.get(DespesaRecorrente, uuid.UUID(conta_id)).ativa is False
    assert db.query(Despesa).filter_by(recorrente_id=uuid.UUID(conta_id)).count() == 0

    r = client.post("/api/financeiro/rotinas", json={"nome": "Conferir PayPal"})
    assert r.status_code == 200 and db.query(RotinaMensal).count() == 1


def test_recebimento_sem_nota_e_gerar_nota_dele(client, db, prestador_teste, vinculo_teste, monkeypatch):
    """Mercado Livre/Amazon pagam antes da nota: o recebimento sem nota no
    mês vira aviso com "gerar nota", e a nota gerada dele fica no mês do
    recebimento (com a data de competência de hoje). Avisos podem ser
    ignorados."""
    from app.services.dashboard import proximos

    hoje = datetime.date(2026, 10, 1)
    monkeypatch.setattr("app.main.hoje_br", lambda: hoje)
    r = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 1234.5})
    assert r.status_code == 200 and r.json()["sem_nota"] is True
    pagamento_id = r.json()["id"]

    lista = client.get("/api/financeiro/recebimentos-sem-nota").json()
    assert [x["competencia"] for x in lista] == ["2026-09"] and lista[0]["valor"] == 1234.5
    p = proximos(db, prestador_teste.id, hoje)
    aviso = next(x for x in p["pendencias"] if x["tipo"] == "nota_recebimento")
    assert f"pagamento={pagamento_id}" in aviso["link"]

    # ignorar e voltar
    assert client.post("/api/painel/pendencias/ignorar", json={"chave": aviso["chave"]}).status_code == 200
    assert client.get("/api/financeiro/recebimentos-sem-nota").json() == []
    client.post("/api/painel/pendencias/ignorar", json={"chave": aviso["chave"], "ignorar": False})

    # gerar a nota do recebimento: fica em 09/2026, data de competência hoje
    r = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-10", "data_competencia": "2026-10-01",
        "valor": 1234.5, "pagamento_id": pagamento_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["competencia"] == "2026-09"
    assert client.get("/api/financeiro/recebimentos-sem-nota").json() == []
    from app.services import a_receber
    assert all(g["competencia"] != "2026-09" for g in a_receber.notas_em_aberto(db, hoje))

    # recebimento de um mês que já tem nota não avisa
    r = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 1})
    assert r.json()["sem_nota"] is False

    # planilha: pagamento de quem paga antes entra no mês da nota
    arquivo = {"arquivo": ("c.xlsx", planilha(), "application/octet-stream")}
    escolhas = {"receitas": [{"linha": 1, "acao": "vinculo", "vinculo_id": str(vinculo_teste.id), "deslocamento": 1}],
                "despesas": False, "recorrentes": False, "retiradas": False, "rotinas": False}
    assert client.post("/api/importar/planilha", files=arquivo, data={"ano": "2026", "escolhas": json.dumps(escolhas)}).status_code == 200
    from app.models import PagamentoRecebido
    comps = sorted(c for (c,) in db.query(PagamentoRecebido.competencia).filter_by(prestador_tomador_id=vinculo_teste.id))
    assert comps[:3] == ["2026-02", "2026-03", "2026-05"]


def test_vendedores_shopee_separados_e_sem_cobranca(client, db, prestador_teste, vinculo_teste):
    """Notas de vendedores da Shopee: aba própria e fora do "a receber" — a
    Shopee paga tudo junto na nota dela (01/10/2026)."""
    from app.services import a_receber
    from app.services.dashboard import resumo_mes as resumo_do_mes
    from app.services.motor_emissao import montar

    principal = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=100, tpAmb="2")
    montar(db, principal)
    for i in range(3):
        e = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=5, tpAmb="2", tomador_avulso={
            "documento": f"1122233300011{i}", "tipo_documento": "CNPJ", "razao_social": f"Loja {i}" if i else None,
            "email": None, "endereco": {}, "pais": "BR", "lojas": [],
        })
        montar(db, e)
    notas = client.get("/api/dps?grupo=notas").json()
    vend = client.get("/api/dps?grupo=vendedores").json()
    assert len(notas) == 1 and len(vend) == 3 and all(v["avulsa"] for v in vend)
    abertas = a_receber.notas_em_aberto(db, datetime.date(2026, 10, 1))
    assert [g["valor"] for g in abertas if g["vinculo_id"] == vinculo_teste.id] == [100.0]

    # Shopee pagou o total (100 + vendedores): a nota da Shopee fica paga
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 115})
    assert not [g for g in a_receber.notas_em_aberto(db, datetime.date(2026, 10, 1)) if g["vinculo_id"] == vinculo_teste.id]

    linhas = resumo_do_mes(db, prestador_teste.id, "2026-09")["emissoes"]
    assert sorted(l.get("vendedores", False) for l in linhas if l["vinculo_id"] == vinculo_teste.id) == [False, True]

    # apagar nota que não saiu
    assert client.delete(f"/api/dps/{principal.id}").status_code == 200
