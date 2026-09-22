"""
Testes de app.services.google_oauth — `requests.post`/`requests.get`
sempre mockados (ver docstring do módulo: rede bloqueada nesta sandbox,
e mesmo com rede livre não teríamos credenciais reais pra testar contra a
Google de verdade).
"""
import pytest
import requests

from app.config import Settings
from app.services.google_oauth import (
    GoogleOAuthFalhaError,
    GoogleOAuthNaoConfiguradoError,
    gerar_state,
    montar_url_autorizacao,
    trocar_code_por_usuario,
)


class _RespostaFake:
    def __init__(self, status_code, corpo=None, quebra_json=False):
        self.status_code = status_code
        self._corpo = corpo
        self._quebra_json = quebra_json

    def json(self):
        if self._quebra_json:
            raise ValueError("não é JSON")
        return self._corpo


def _settings(**overrides):
    base = {"google_oauth_client_id": "", "google_oauth_client_secret": ""}
    base.update(overrides)
    return Settings(**base)


# --- montar_url_autorizacao ---


def test_gerar_state_devolve_valores_diferentes_a_cada_chamada():
    assert gerar_state() != gerar_state()


def test_montar_url_sem_credencial_configurada_da_erro():
    with pytest.raises(GoogleOAuthNaoConfiguradoError):
        montar_url_autorizacao(_settings(), "state123")


def test_montar_url_com_credencial_inclui_client_id_redirect_e_state():
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")
    url = montar_url_autorizacao(settings, "state123")
    assert "client_id=abc123" in url
    assert "state=state123" in url
    assert "accounts.google.com" in url
    assert "redirect_uri=" in url
    assert "scope=" in url


# --- trocar_code_por_usuario ---


def test_trocar_code_sem_credencial_configurada_da_erro_sem_chamar_rede(monkeypatch):
    def _nao_deveria_chamar(*a, **kw):
        raise AssertionError("não deveria ter chamado requests sem credencial configurada")

    monkeypatch.setattr(requests, "post", _nao_deveria_chamar)
    monkeypatch.setattr(requests, "get", _nao_deveria_chamar)
    with pytest.raises(GoogleOAuthNaoConfiguradoError):
        trocar_code_por_usuario(_settings(), "code-qualquer")


def test_trocar_code_caminho_feliz_devolve_dados_do_usuario(monkeypatch):
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")

    def _post_fake(url, data=None, timeout=None):
        assert data["code"] == "code-valido"
        assert data["client_id"] == "abc123"
        assert data["client_secret"] == "segredo"
        assert data["grant_type"] == "authorization_code"
        return _RespostaFake(200, {"access_token": "token-fake"})

    def _get_fake(url, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer token-fake"
        return _RespostaFake(
            200,
            {"sub": "1234567890", "email": "PESSOA@Exemplo.com", "email_verified": True, "name": "Fulana de Tal"},
        )

    monkeypatch.setattr(requests, "post", _post_fake)
    monkeypatch.setattr(requests, "get", _get_fake)

    info = trocar_code_por_usuario(settings, "code-valido")
    assert info.sub == "1234567890"
    assert info.email == "pessoa@exemplo.com"  # normalizado (mesmo padrão de autenticar())
    assert info.email_verificado is True
    assert info.nome == "Fulana de Tal"


def test_trocar_code_token_endpoint_recusa_da_erro(monkeypatch):
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _RespostaFake(400, {"error": "invalid_grant"}))
    with pytest.raises(GoogleOAuthFalhaError):
        trocar_code_por_usuario(settings, "code-invalido-ou-expirado")


def test_trocar_code_falha_de_rede_na_troca_de_token_da_erro(monkeypatch):
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")

    def _levanta(*a, **kw):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", _levanta)
    with pytest.raises(GoogleOAuthFalhaError):
        trocar_code_por_usuario(settings, "code-qualquer")


def test_trocar_code_userinfo_endpoint_recusa_da_erro(monkeypatch):
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _RespostaFake(200, {"access_token": "token-fake"}))
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _RespostaFake(401, {"error": "invalid_token"}))
    with pytest.raises(GoogleOAuthFalhaError):
        trocar_code_por_usuario(settings, "code-valido")


def test_trocar_code_resposta_sem_access_token_da_erro(monkeypatch):
    settings = _settings(google_oauth_client_id="abc123", google_oauth_client_secret="segredo")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _RespostaFake(200, {"algo_inesperado": True}))
    with pytest.raises(GoogleOAuthFalhaError):
        trocar_code_por_usuario(settings, "code-valido")
