"""Família de erro "invalid input syntax for type uuid: ''" (05/10/2026).

Em produção, o commit encerra a transação e, com ela, a variável da RLS
(`app.current_prestador_id`, que vale só na transação). Qualquer leitura
depois do commit — um atributo que o banco preencheu (`atualizado_em`,
`xml_assinado`...), um `db.refresh`, uma consulta nova — abria outra
transação sem a variável e dava 500 (POST /api/dps e /dps/{id}/submeter).

O resto da suíte NÃO pega isso: ela troca `db.commit` por `db.flush`, então
tudo roda numa transação só. Por isso aqui:

1. o mecanismo com commit DE VERDADE: depois do commit a mesma sessão
   continua lendo as tabelas com RLS (e, sem o conserto, quebra igual a
   produção — o teste prova que a armadilha existe);
2. um passeio pelas rotas que gravam, com commits de verdade (sem trocar o
   banco da rota), numa conta de simulação descartável;
3. uma trava de código: a variável da RLS só é definida por
   `definir_prestador_atual` e toda sessão sai de `SessionLocal` — é isso que
   faz o conserto valer em QUALQUER rota.
"""
import datetime
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import DBAPIError

from app import database
from app.database import SessionLocal, definir_prestador_atual
from app.main import app
from app.models import Emissao, PrestadorTomador
from app.services.demo import apagar_conta_demo, criar_conta_demo
from app.tempo import hoje

APP = Path(__file__).resolve().parents[1] / "app"


def _apagar(prestador_id):
    with SessionLocal() as s:
        apagar_conta_demo(s, prestador_id)
        s.commit()


@pytest.fixture
def conta_com_commit_de_verdade():
    """Conta de simulação gravada de verdade (commit), apagada no fim."""
    with SessionLocal() as s:
        usuario = criar_conta_demo(s, "beleza")
        prestador_id = usuario.prestador_id
        s.commit()
    try:
        yield prestador_id
    finally:
        _apagar(prestador_id)


def test_depois_do_commit_a_sessao_continua_na_mesma_empresa(conta_com_commit_de_verdade):
    with SessionLocal() as s:
        definir_prestador_atual(s, conta_com_commit_de_verdade)
        nota = s.query(Emissao).filter_by(prestador_id=conta_com_commit_de_verdade).first()
        nota.erro_detalhe = None
        s.commit()
        # o que deu 500 em produção: reler o objeto e consultar de novo depois do commit
        s.refresh(nota)
        assert nota.atualizado_em is not None
        assert s.query(PrestadorTomador).filter_by(prestador_id=conta_com_commit_de_verdade).count() == 3


def test_sem_o_conserto_a_armadilha_aparece(conta_com_commit_de_verdade):
    """Garante que o teste acima mede a coisa certa: tirando o conserto, a
    mesma leitura pós-commit quebra com o erro de produção."""
    event.remove(SessionLocal, "after_begin", database._reaplicar_prestador_atual)
    try:
        with SessionLocal() as s:
            definir_prestador_atual(s, conta_com_commit_de_verdade)
            s.query(Emissao).filter_by(prestador_id=conta_com_commit_de_verdade).first()
            s.commit()
            with pytest.raises(DBAPIError, match="invalid input syntax for type uuid"):
                s.query(Emissao).filter_by(prestador_id=conta_com_commit_de_verdade).count()
            s.rollback()
    finally:
        event.listen(SessionLocal, "after_begin", database._reaplicar_prestador_atual)


def test_rotas_que_gravam_funcionam_com_commit_de_verdade():
    """Sem trocar o banco da rota: cada requisição dá commit de verdade."""
    cliente = TestClient(app)
    assert cliente.post("/api/demo?cenario=beleza").status_code == 200
    prestador_id = uuid.UUID(cliente.get("/api/auth/me").json()["prestador_id"])
    mes = hoje().strftime("%Y-%m")
    try:
        vinculos = cliente.get("/api/vinculos?todos=true").json()
        bella = next(v for v in vinculos if v["apelido"] == "Bella Beauty")

        respostas = {}
        nota = cliente.post("/api/dps", json={"vinculo_id": bella["id"], "competencia": mes, "valor": 3920.0, "aliq_sn": 6.0})
        respostas["POST /api/dps"] = nota
        nota_id = nota.json()["id"]
        respostas["assinar"] = cliente.post(f"/api/dps/{nota_id}/assinar")
        respostas["submeter"] = cliente.post(f"/api/dps/{nota_id}/submeter")
        respostas["enviar-email"] = cliente.post(f"/api/dps/{nota_id}/enviar-email", json={})
        respostas["marcar-enviada"] = cliente.post(f"/api/dps/{nota_id}/marcar-enviada", json={"forma": "portal"})
        respostas["GET nota"] = cliente.get(f"/api/dps/{nota_id}")
        respostas["pagamento"] = cliente.post("/api/pagamentos", json={
            "vinculo_id": bella["id"], "competencia": mes, "valor": 3920.0, "emissao_id": nota_id,
        })
        respostas["despesa"] = cliente.post("/api/despesas", json={"categoria": "Contador", "competencia": mes, "valor": 380.0})
        respostas["conta fixa"] = cliente.post("/api/financeiro/contas-fixas", json={"nome": "Internet", "valor_padrao": 120.0, "dia_vencimento": 10})
        respostas["evento"] = cliente.post("/api/calendario/eventos", json={
            "data": (hoje() + datetime.timedelta(days=2)).isoformat(), "categoria": "lembrete", "titulo": "Gravar vídeo",
        })
        respostas["editar tomador"] = cliente.patch(f"/api/vinculos/{bella['id']}", json={"dia_limite_emissao": 12})
        respostas["resumo do mês"] = cliente.get("/api/painel/resumo-mes")

        erros = {nome: (r.status_code, r.text[:200]) for nome, r in respostas.items() if r.status_code >= 400}
        assert not erros, erros
        assert respostas["submeter"].json()["estado"] == "confirmado"
    finally:
        _apagar(prestador_id)


def test_a_variavel_da_rls_so_e_definida_num_lugar():
    """Quem definir a variável da RLS por fora de `definir_prestador_atual`
    escapa do conserto (a próxima transação não a herda)."""
    padrao = re.compile(r"set_config\(\s*'app\.current_prestador_id'")
    permitidos = {APP / "database.py", APP / "services" / "lotes.py"}
    fora = [str(p.relative_to(APP)) for p in APP.rglob("*.py") if p not in permitidos and padrao.search(p.read_text(encoding="utf-8"))]
    assert not fora, f"defina a empresa com definir_prestador_atual: {fora}"


def test_toda_sessao_sai_de_sessionlocal():
    padrao = re.compile(r"\bsessionmaker\(|\bSession\(\s*(bind|engine)")
    fora = [str(p.relative_to(APP)) for p in APP.rglob("*.py") if p.name != "database.py" and padrao.search(p.read_text(encoding="utf-8"))]
    assert not fora, f"sessão criada fora de SessionLocal: {fora}"
