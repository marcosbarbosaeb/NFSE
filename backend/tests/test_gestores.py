"""Gestão com usuários próprios (2026.10.7 — item F do roteiro).

A tabela `gestor` decide quem entra na Gestão (ADMIN_EMAILS continua valendo
junto, como reserva). A migração já cria a conta do Marcos. Só dados
sintéticos (fora o e-mail do Marcos, que é o gestor de verdade)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Gestor, Usuario
from app.services import gestores


@pytest.fixture
def tabela_de_verdade(monkeypatch, db):
    monkeypatch.setattr(gestores, "_da_tabela", lambda sessao: {e for (e,) in sessao.query(Gestor.email).all()})
    monkeypatch.setattr(get_settings(), "admin_emails", "")
    monkeypatch.setattr(db, "commit", db.flush)


@pytest.fixture
def entrar(db, prestador_teste):
    """Cliente logado como `email` (sessão de verdade não é preciso: a rota lê o usuário pela sessão)."""
    def _entrar(email):
        u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=email, senha_hash="x", email_confirmado=True)
        db.add(u)
        db.flush()

        def _get_db():
            yield db

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
        c = TestClient(app)

        # injeta a sessão: o middleware de sessão lê do cookie assinado
        from itsdangerous import TimestampSigner
        import base64
        import json

        dados = base64.b64encode(json.dumps({"usuario_id": str(u.id), "prestador_id": str(prestador_teste.id)}).encode())
        cookie = TimestampSigner(get_settings().session_secret_key).sign(dados).decode()
        c.cookies.set("session", cookie)
        return c, u

    yield _entrar
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_migracao_criou_a_conta_do_marcos(db, tabela_de_verdade):
    assert "marcosbarbosaeb@gmail.com" in gestores.emails(db)


def test_gestor_pela_tabela_entra_e_cuida_dos_gestores(db, tabela_de_verdade, entrar):
    gestores.adicionar(db, "Gestora@Plataforma.Example", "marcosbarbosaeb@gmail.com")
    c, _ = entrar("gestora@plataforma.example")
    assert c.get("/api/gestao/acesso").json() == {"gestor": True, "configurado": True, "separada": False}
    lista = c.get("/api/gestao/gestores").json()["gestores"]
    assert {g["email"] for g in lista} >= {"gestora@plataforma.example", "marcosbarbosaeb@gmail.com"}
    r = c.post("/api/gestao/gestores", json={"email": "novo@plataforma.example"})
    assert r.status_code == 200 and any(g["email"] == "novo@plataforma.example" for g in r.json()["gestores"])
    assert c.post("/api/gestao/gestores", json={"email": "sem-arroba"}).status_code == 422
    # não tira a si mesma
    assert c.delete("/api/gestao/gestores/gestora@plataforma.example").status_code == 422
    assert c.delete("/api/gestao/gestores/novo@plataforma.example").status_code == 200
    assert "novo@plataforma.example" not in gestores.emails(db)


def test_quem_nao_e_gestor_nao_entra(db, tabela_de_verdade, entrar):
    c, _ = entrar("cliente@empresa.example")
    assert c.get("/api/gestao/acesso").json() == {"gestor": False, "configurado": True, "separada": False}
    assert c.get("/api/gestao/gestores").status_code == 403
    assert c.post("/api/gestao/gestores", json={"email": "eu@empresa.example"}).status_code == 403


def test_variavel_continua_valendo_como_reserva(db, tabela_de_verdade, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_emails", "reserva@plataforma.example")
    assert "reserva@plataforma.example" in gestores.emails(db)
    with pytest.raises(gestores.GestorError, match="ADMIN_EMAILS"):
        gestores.remover(db, "reserva@plataforma.example", "marcosbarbosaeb@gmail.com")
