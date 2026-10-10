"""Gestão num subdomínio próprio (2026.10.7 — decisão do Marcos em 10/10/2026).

Com GESTAO_HOST preenchida, a Gestão só existe em gestao.<domínio>: no app das
notas as rotas dão 404, o menu não mostra e /app/gestao leva pro subdomínio;
no subdomínio, as outras telas levam pra /app/gestao. Sem a variável, nada muda."""
import base64
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.config import get_settings
from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Gestor, Usuario
from app.services import gestores

GESTAO = "gestao.agenteana.com.br"


@pytest.fixture
def gestor(db, prestador_teste, monkeypatch):
    monkeypatch.setattr(gestores, "_da_tabela", lambda sessao: {e for (e,) in sessao.query(Gestor.email).all()})
    monkeypatch.setattr(get_settings(), "admin_emails", "")
    monkeypatch.setattr(db, "commit", db.flush)
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email="gestora@plataforma.example", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.add(Gestor(email=u.email))
    db.flush()

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    dados = base64.b64encode(json.dumps({"usuario_id": str(u.id), "prestador_id": str(prestador_teste.id)}).encode())
    cookie = TimestampSigner(get_settings().session_secret_key).sign(dados).decode()

    def cliente(host):
        c = TestClient(app, base_url=f"http://{host}", follow_redirects=False)
        c.cookies.set("session", cookie)
        return c

    yield cliente
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_sem_a_variavel_a_gestao_fica_no_app(gestor, monkeypatch):
    monkeypatch.setattr(get_settings(), "gestao_host", "")
    c = gestor("notas.agenteana.com.br")
    assert c.get("/api/gestao/acesso").json()["gestor"] is True
    assert c.get("/api/gestao/gestores").status_code == 200


def test_no_app_das_notas_a_gestao_nao_existe(gestor, monkeypatch):
    monkeypatch.setattr(get_settings(), "gestao_host", GESTAO)
    c = gestor("notas.agenteana.com.br")
    acesso = c.get("/api/gestao/acesso").json()
    assert acesso["gestor"] is False and acesso["separada"] is True  # o menu some
    for rota in ("/api/gestao/gestores", "/api/gestao/perfis", "/api/parceiros"):
        assert c.get(rota).status_code == 404, rota
    r = c.get("/app/gestao?aba=contas")
    assert r.status_code == 302 and r.headers["location"].endswith(f"{GESTAO}/app/gestao?aba=contas")


def test_no_subdominio_so_a_gestao(gestor, monkeypatch):
    monkeypatch.setattr(get_settings(), "gestao_host", GESTAO)
    c = gestor(GESTAO)
    assert c.get("/api/gestao/acesso").json()["gestor"] is True
    assert c.get("/api/gestao/gestores").status_code == 200
    for caminho in ("/", "/app", "/app/nfse", "/cadastro", "/simulacao"):
        r = c.get(caminho)
        assert r.status_code == 302 and r.headers["location"] == "/app/gestao", caminho
    for caminho in ("/app/gestao", "/entrar", "/privacidade"):
        assert c.get(caminho).status_code in (200, 404), caminho  # 404 só quando o build do frontend não existe
        assert "location" not in c.get(caminho).headers
    # pedido que muda dado vindo do próprio subdomínio não é barrado pela regra de origem
    r = c.post("/api/gestao/gestores", json={"email": "outra@plataforma.example"}, headers={"origin": f"https://{GESTAO}"})
    assert r.status_code != 403
