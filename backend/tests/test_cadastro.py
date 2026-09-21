"""
Cadastro público self-service — Marco 15, item 4 (ver
app/services/cadastro.py). `EmailSenderConsole` é o sender ativo nestes
testes (RESEND_API_KEY não configurada no ambiente de teste — ver
app/services/email.py), então nenhum teste aqui depende de rede.
"""
import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Prestador, Usuario
from app.services.cadastro import (
    EmailJaCadastradoError,
    PrestadorJaCadastradoError,
    TokenInvalidoOuExpiradoError,
    confirmar_email,
    criar_cadastro,
    reenviar_confirmacao,
)
from app.services.usuarios import autenticar


def test_criar_cadastro_cria_prestador_e_usuario_nao_confirmado(db):
    usuario = criar_cadastro(
        db, email="nova@exemplo.com", senha="senhaforte123", razao_social="EMPRESA NOVA LTDA",
        cpf_cnpj="12345678000199", cod_municipio="3106200",
    )
    assert usuario.email_confirmado is False
    assert usuario.token_confirmacao is not None

    prestador = db.query(Prestador).filter_by(id=usuario.prestador_id).one()
    assert prestador.razao_social == "EMPRESA NOVA LTDA"
    assert prestador.cpf_cnpj == "12345678000199"


def test_criar_cadastro_normaliza_email_e_limpa_cnpj(db):
    usuario = criar_cadastro(
        db, email="Maiuscula@Exemplo.com", senha="senhaforte123", razao_social="X",
        cpf_cnpj="12.345.678/0001-99", cod_municipio="3106200",
    )
    assert usuario.email == "maiuscula@exemplo.com"
    prestador = db.query(Prestador).filter_by(id=usuario.prestador_id).one()
    assert prestador.cpf_cnpj == "12345678000199"


def test_criar_cadastro_email_duplicado_recusa(db):
    criar_cadastro(db, email="dup@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="11111111000111", cod_municipio="3106200")
    with pytest.raises(EmailJaCadastradoError):
        criar_cadastro(db, email="dup@exemplo.com", senha="outrasenha123", razao_social="Y", cpf_cnpj="22222222000122", cod_municipio="3106200")


def test_criar_cadastro_cnpj_duplicado_recusa(db):
    criar_cadastro(db, email="um@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="33333333000133", cod_municipio="3106200")
    with pytest.raises(PrestadorJaCadastradoError):
        criar_cadastro(db, email="dois@exemplo.com", senha="senhaforte123", razao_social="Y", cpf_cnpj="33333333000133", cod_municipio="3106200")


def test_usuario_nao_confirmado_nao_consegue_logar_pelo_autenticar_isolado(db):
    """`autenticar` sozinho não checa email_confirmado (é responsabilidade
    do endpoint, ver test_endpoint_login_recusa_antes_de_confirmar abaixo)
    — este teste documenta que o usuário existe e a senha bate, só pra
    deixar claro que o bloqueio é uma camada A MAIS, não uma falha de
    autenticar."""
    criar_cadastro(db, email="pendente@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="44444444000144", cod_municipio="3106200")
    usuario = autenticar(db, "pendente@exemplo.com", "senhaforte123")
    assert usuario is not None
    assert usuario.email_confirmado is False


def test_confirmar_email_com_token_valido(db):
    usuario = criar_cadastro(db, email="confirma@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="55555555000155", cod_municipio="3106200")
    token = usuario.token_confirmacao

    confirmado = confirmar_email(db, token)
    assert confirmado.email_confirmado is True
    assert confirmado.token_confirmacao is None


def test_confirmar_email_token_invalido_recusa(db):
    with pytest.raises(TokenInvalidoOuExpiradoError):
        confirmar_email(db, "token-que-nao-existe")


def test_confirmar_email_token_expirado_recusa(db):
    usuario = criar_cadastro(db, email="expirado@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="66666666000166", cod_municipio="3106200")
    usuario.token_confirmacao_expira_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    db.flush()
    with pytest.raises(TokenInvalidoOuExpiradoError):
        confirmar_email(db, usuario.token_confirmacao)


def test_reenviar_confirmacao_gera_token_novo(db):
    usuario = criar_cadastro(db, email="reenvio@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="77777777000177", cod_municipio="3106200")
    token_original = usuario.token_confirmacao

    reenviar_confirmacao(db, "reenvio@exemplo.com")
    db.refresh(usuario)
    assert usuario.token_confirmacao != token_original

    # o token novo confirma; o antigo não vale mais
    with pytest.raises(TokenInvalidoOuExpiradoError):
        confirmar_email(db, token_original)
    confirmar_email(db, usuario.token_confirmacao)


def test_reenviar_confirmacao_email_inexistente_nao_da_erro(db):
    reenviar_confirmacao(db, "ninguem@exemplo.com")  # não levanta, não faz nada


def test_reenviar_confirmacao_email_ja_confirmado_nao_gera_token_novo(db):
    usuario = criar_cadastro(db, email="jaconfirmado@exemplo.com", senha="senhaforte123", razao_social="X", cpf_cnpj="88888888000188", cod_municipio="3106200")
    confirmar_email(db, usuario.token_confirmacao)
    reenviar_confirmacao(db, "jaconfirmado@exemplo.com")
    db.refresh(usuario)
    assert usuario.token_confirmacao is None  # continua confirmado, sem token novo


# --- Camada HTTP ---


@pytest.fixture
def client_publico(db):
    """Sem overridar prestador_atual_id de propósito — as rotas de cadastro
    são públicas (get_db puro), igual login."""
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_endpoint_cadastro_sucesso(client_publico):
    resp = client_publico.post(
        "/api/cadastro",
        json={
            "email": "http@exemplo.com", "senha": "senhaforte123", "razao_social": "EMPRESA HTTP LTDA",
            "cpf_cnpj": "99999999000199", "cod_municipio": "3106200",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "http@exemplo.com"


def test_endpoint_cadastro_email_invalido_ou_senha_curta_da_422(client_publico):
    resp = client_publico.post(
        "/api/cadastro",
        json={"email": "x@exemplo.com", "senha": "curta", "razao_social": "X", "cpf_cnpj": "12345678000199", "cod_municipio": "3106200"},
    )
    assert resp.status_code == 422


def test_endpoint_cadastro_cnpj_com_pontuacao_da_422(client_publico):
    """O schema exige só dígitos (ver CadastroRequest) — pontuação vai na
    tela, não no payload."""
    resp = client_publico.post(
        "/api/cadastro",
        json={
            "email": "x@exemplo.com", "senha": "senhaforte123", "razao_social": "X",
            "cpf_cnpj": "12.345.678/0001-99", "cod_municipio": "3106200",
        },
    )
    assert resp.status_code == 422


def test_endpoint_cadastro_email_duplicado_da_409(client_publico):
    payload = {
        "email": "dupe@exemplo.com", "senha": "senhaforte123", "razao_social": "X",
        "cpf_cnpj": "10101010000110", "cod_municipio": "3106200",
    }
    client_publico.post("/api/cadastro", json=payload)
    payload2 = dict(payload, cpf_cnpj="20202020000120")
    resp = client_publico.post("/api/cadastro", json=payload2)
    assert resp.status_code == 409


def test_endpoint_login_recusa_antes_de_confirmar(client_publico):
    client_publico.post(
        "/api/cadastro",
        json={
            "email": "semconfirmar@exemplo.com", "senha": "senhaforte123", "razao_social": "X",
            "cpf_cnpj": "30303030000130", "cod_municipio": "3106200",
        },
    )
    resp = client_publico.post("/api/auth/login", json={"email": "semconfirmar@exemplo.com", "senha": "senhaforte123"})
    assert resp.status_code == 403


def test_endpoint_confirmar_email_loga_direto(client_publico, db):
    client_publico.post(
        "/api/cadastro",
        json={
            "email": "confirmahttp@exemplo.com", "senha": "senhaforte123", "razao_social": "X",
            "cpf_cnpj": "40404040000140", "cod_municipio": "3106200",
        },
    )
    usuario = db.query(Usuario).filter_by(email="confirmahttp@exemplo.com").one()
    token = usuario.token_confirmacao

    resp = client_publico.post("/api/cadastro/confirmar", json={"token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "confirmahttp@exemplo.com"

    # sessão já ficou ativa (confirmar loga direto)
    me = client_publico.get("/api/auth/me")
    assert me.status_code == 200

    # login normal também passa a funcionar
    logout = client_publico.post("/api/auth/logout")
    assert logout.status_code == 200
    login = client_publico.post("/api/auth/login", json={"email": "confirmahttp@exemplo.com", "senha": "senhaforte123"})
    assert login.status_code == 200


def test_endpoint_confirmar_email_token_invalido_da_400(client_publico):
    resp = client_publico.post("/api/cadastro/confirmar", json={"token": "lixo"})
    assert resp.status_code == 400


def test_endpoint_reenviar_confirmacao_sempre_200(client_publico):
    resp = client_publico.post("/api/cadastro/reenviar-confirmacao", json={"email": "ninguem-de-verdade@exemplo.com"})
    assert resp.status_code == 200
