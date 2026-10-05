"""Emissor e financeiro como produtos separados (05/10/2026)."""
import pathlib
import re
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Emissao, PagamentoRecebido

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "app"


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


def test_emissor_nao_importa_o_financeiro():
    """A regra da separação: nada do emissor (nem do cadastro geral) importa
    `app.financeiro`. Só app/main.py, que monta o sistema, inclui as rotas."""
    culpados = []
    for arquivo in RAIZ.rglob("*.py"):
        relativo = arquivo.relative_to(RAIZ).as_posix()
        if relativo.startswith("financeiro/") or relativo == "main.py":
            continue
        if re.search(r"^\s*(from|import)\s+app\.financeiro\b|from app import .*\bfinanceiro\b", arquivo.read_text(), re.M):
            culpados.append(relativo)
    assert culpados == []
    # e em main.py o financeiro só aparece no bloco que inclui o módulo
    principal = (RAIZ / "main.py").read_text()
    assert len(re.findall(r"^from app\.financeiro", principal, re.M)) == 2


def test_financeiro_so_usa_do_emissor_o_que_e_ponto_de_integracao():
    """O financeiro não importa serviços do emissor — só o cadastro comum
    de clientes (vinculos) e o barramento de eventos."""
    permitidos = {"app.services.vinculos"}
    usados = set()
    for arquivo in (RAIZ / "financeiro").glob("*.py"):
        usados |= set(re.findall(r"^\s*from (app\.services\.\w+) import", arquivo.read_text(), re.M))
        assert "from app.services import" not in arquivo.read_text()
        assert "from app.main" not in arquivo.read_text() and "import app.main" not in arquivo.read_text()
    assert usados <= permitidos, usados - permitidos


def test_modulo_desligado_fecha_as_rotas_do_financeiro(client, db, prestador_teste, vinculo_teste):
    prestador_teste.modulos = ["emissor"]
    db.flush()
    for metodo, rota in (
        ("get", "/api/pagamentos?ano=2026"), ("get", "/api/despesas"), ("get", "/api/financeiro/resumo?ano=2026"),
        ("get", "/api/conciliacao"), ("get", "/api/notas-a-receber"), ("get", "/api/financeiro/pendencias"),
    ):
        r = getattr(client, metodo)(rota)
        assert r.status_code == 403 and "Financeiro" in r.json()["detail"], rota
    assert client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 1}).status_code == 403

    # o emissor segue inteiro, sem nenhuma palavra sobre pagamento
    nota = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 100})
    assert nota.status_code == 200, nota.text
    lista = client.get("/api/dps").json()
    assert len(lista) == 1 and not any("pag" in chave or "receb" in chave for chave in lista[0])
    resumo = client.get("/api/painel/resumo-mes?competencia=2026-09").json()
    assert not any("receb" in chave or "pagamento" in chave for chave in resumo)
    tipos = {p["tipo"] for p in client.get("/api/painel/proximos").json()["pendencias"]}
    assert not tipos & {"receber", "nota_recebimento", "conciliar"}
    agenda = client.get("/api/calendario?inicio=2026-09-01&fim=2026-09-30")
    assert agenda.status_code == 200 and all("recebimento" not in e["tipo"] for e in agenda.json().get("eventos", agenda.json()))

    # ligar de novo devolve tudo (nada foi apagado)
    r = client.put("/api/empresa/modulos", json={"modulos": ["financeiro", "emissor"]})
    assert r.status_code == 200 and r.json() == {"modulos": ["emissor", "financeiro"]}
    assert client.get("/api/notas-a-receber").status_code == 200
    assert client.put("/api/empresa/modulos", json={"modulos": []}).status_code == 422


def test_calendario_so_traz_recebimento_com_o_financeiro_ligado(client, db, prestador_teste, vinculo_teste):
    db.add(PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-09",
        valor=Decimal("10"), data_recebimento=__import__("datetime").date(2026, 9, 10),
    ))
    db.flush()

    def tipos():
        corpo = client.get("/api/calendario?inicio=2026-09-01&fim=2026-09-30").json()
        return {e["tipo"] for e in (corpo.get("eventos", corpo) if isinstance(corpo, dict) else corpo)}

    assert "recebimento_confirmado" in tipos()
    prestador_teste.modulos = ["emissor"]
    db.flush()
    assert "recebimento_confirmado" not in tipos()


def test_nota_pedida_pelo_financeiro_volta_ligada_ao_recebimento(client, db, vinculo_teste):
    """O ponto de integração: o financeiro pede a nota de um recebimento
    passando uma `origem` que o emissor não interpreta — só devolve no evento."""
    pag = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 500}).json()
    nota = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-10", "valor": 500, "origem": f"fin:pagamento:{pag['id']}",
    })
    assert nota.status_code == 200, nota.text
    assert str(db.get(PagamentoRecebido, uuid.UUID(pag["id"])).emissao_id) == nota.json()["id"]
    # origem que o financeiro não reconhece: a nota não sai
    ruim = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-11", "valor": 1, "origem": f"fin:pagamento:{uuid.uuid4()}",
    })
    assert ruim.status_code == 422 and db.query(Emissao).filter_by(competencia="2026-11").count() == 0
    # origem de outro módulo qualquer: o financeiro ignora
    assert client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-12", "valor": 1, "origem": "outro:coisa:1",
    }).status_code == 200

    # nota que já existia atende um recebimento novo
    pag2 = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-12", "valor": 1}).json()
    existente = db.query(Emissao).filter_by(competencia="2026-12").one()
    db.query(PagamentoRecebido).filter(PagamentoRecebido.id == uuid.UUID(pag2["id"])).update({"emissao_id": None})
    r = client.post(f"/api/dps/{existente.id}/origem", json={"origem": f"fin:pagamento:{pag2['id']}"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(PagamentoRecebido, uuid.UUID(pag2["id"])).emissao_id == existente.id


def test_so_financeiro_fecha_o_emissor_e_funciona_sozinho(client, db, prestador_teste):
    """Empresa que comprou só o financeiro: não emite nota, mas lança
    receita (com cliente próprio), despesa e concilia extrato."""
    prestador_teste.modulos = ["financeiro"]
    db.flush()
    assert client.get("/api/dps").status_code == 403
    assert client.get("/api/painel/resumo-mes").status_code == 403
    assert "Notas" in client.post("/api/dps", json={"vinculo_id": str(uuid.uuid4()), "competencia": "2026-09", "valor": 1}).json()["detail"]

    cliente = client.post("/api/vinculos/controle", json={"nome": "Cliente Sem Nota"}).json()
    assert client.post("/api/pagamentos", json={
        "vinculo_id": cliente["id"], "competencia": "2026-09", "valor": 250, "data_recebimento": "2026-09-10",
    }).status_code == 200
    assert client.post("/api/despesas", json={"categoria": "Aluguel", "competencia": "2026-09", "valor": 100}).status_code == 200
    resumo = client.get("/api/financeiro/resumo?ano=2026").json()
    assert resumo["totais"]["recebido"] == 250 and resumo["totais"]["despesas"] == 100
    # cliente só de controle não vira pendência de "gerar nota"
    assert client.get("/api/financeiro/recebimentos-sem-nota").json() == []
    assert client.get("/api/notas-a-receber").json() == []
    r = client.post("/api/recebimentos/extrato/confirmar", json={"pendentes": [
        {"data": "2026-09-12", "descricao": "Pix recebido CLIENTE SEM NOTA", "valor": 80, "credito": True},
    ]})
    assert r.status_code == 200 and r.json()["pendentes"] == 1
    painel = client.get("/api/conciliacao").json()
    assert painel["notas_abertas"] == [] and painel["lancamentos"][0]["vinculo_id"] == cliente["id"]
