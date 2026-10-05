"""Ajuda / FAQ: a rota só devolve o endereço da IA gratuita configurada em
AJUDA_IA_URL (05/10/2026). Só dados sintéticos."""
import pytest
from fastapi.testclient import TestClient

import app.ajuda as ajuda_mod
from app.config import Settings
from app.database import get_db
from app.main import app, prestador_atual_id

URL = "/api/ajuda"


@pytest.fixture
def client(db, prestador_teste):
    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _configurar(monkeypatch, valor: str):
    monkeypatch.setattr(ajuda_mod, "get_settings", lambda: Settings(ajuda_ia_url=valor))


def test_sem_link_configurado_devolve_null(client, monkeypatch):
    _configurar(monkeypatch, "")
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"ia_url": None}


def test_com_link_https_devolve_o_link(client, monkeypatch):
    _configurar(monkeypatch, "  https://notebooklm.google.com/notebook/exemplo-sintetico  ")
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"ia_url": "https://notebooklm.google.com/notebook/exemplo-sintetico"}


@pytest.mark.parametrize(
    "valor",
    [
        "http://exemplo.test/sem-https",
        "javascript:alert(1)",
        "notebooklm.google.com/notebook/x",
        "https://",
        "https://exemplo.test/com espaco",
    ],
)
def test_link_invalido_devolve_null(client, monkeypatch, valor):
    _configurar(monkeypatch, valor)
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"ia_url": None}


def test_vale_pra_qualquer_modulo(client, monkeypatch, prestador_teste, db):
    """Não exige módulo: quem tem só o financeiro também vê a Ajuda."""
    prestador_teste.modulos = ["financeiro"]
    db.flush()
    _configurar(monkeypatch, "https://exemplo.test/ia")
    assert client.get(URL).json() == {"ia_url": "https://exemplo.test/ia"}


def test_exige_login():
    r = TestClient(app).get(URL)
    assert r.status_code == 401


def test_padrao_da_configuracao_e_vazio(monkeypatch):
    monkeypatch.delenv("AJUDA_IA_URL", raising=False)
    assert Settings(_env_file=None).ajuda_ia_url == ""
    monkeypatch.setenv("AJUDA_IA_URL", "https://exemplo.test/ia")
    assert Settings(_env_file=None).ajuda_ia_url == "https://exemplo.test/ia"
