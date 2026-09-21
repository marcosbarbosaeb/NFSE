"""
Login multiusuário (Marco 10) — hash de senha, serviço de autenticação, e
o fluxo HTTP completo via cookie de sessão (login -> rota protegida ->
logout), SEM sobrescrever `prestador_atual_id` (as outras suítes
sobrescrevem de propósito pra testar rota/serviço isolado da autenticação —
aqui é o contrário: é a autenticação em si que está sendo testada).
"""
import uuid

import pytest

from app.auth import hash_senha, verificar_senha
from app.services.usuarios import (
    EmailJaCadastradoError,
    SenhaAtualIncorretaError,
    autenticar,
    criar_usuario,
    trocar_senha,
)


# --- app/auth.py ---


def test_hash_senha_gera_valores_diferentes_pro_mesmo_texto():
    """Salt aleatório por chamada — dois hashes da MESMA senha não podem
    ser iguais (senão dois usuários com a mesma senha teriam o mesmo hash
    no banco, um vazamento de informação)."""
    h1 = hash_senha("minhasenha123")
    h2 = hash_senha("minhasenha123")
    assert h1 != h2
    assert verificar_senha("minhasenha123", h1)
    assert verificar_senha("minhasenha123", h2)


def test_verificar_senha_errada_falha():
    h = hash_senha("senhacerta123")
    assert verificar_senha("senhaerrada123", h) is False


def test_verificar_senha_hash_malformado_nao_quebra():
    assert verificar_senha("qualquer", "lixo-nao-e-um-hash") is False
    assert verificar_senha("qualquer", "scrypt$naoehex$naoehex") is False


def test_hash_senha_vazia_recusa():
    with pytest.raises(ValueError):
        hash_senha("")


# --- app/services/usuarios.py ---


def test_criar_usuario_e_autenticar(db, prestador_teste):
    usuario = criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    achado = autenticar(db, "raiana@exemplo.com", "senhaforte123")
    assert achado is not None
    assert achado.id == usuario.id


def test_autenticar_email_normalizado_case_insensitive(db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "Raiana@Exemplo.com", "senhaforte123")
    assert autenticar(db, "raiana@exemplo.com", "senhaforte123") is not None
    assert autenticar(db, "RAIANA@EXEMPLO.COM", "senhaforte123") is not None


def test_autenticar_senha_errada_devolve_none(db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    assert autenticar(db, "raiana@exemplo.com", "senhaerrada") is None


def test_autenticar_email_inexistente_devolve_none(db, prestador_teste):
    assert autenticar(db, "ninguem@exemplo.com", "qualquer123") is None


def test_criar_usuario_email_duplicado_da_erro(db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    with pytest.raises(EmailJaCadastradoError):
        criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "outrasenha123")


def test_autenticar_usuario_inativo_devolve_none(db, prestador_teste):
    usuario = criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    usuario.ativo = False
    db.flush()
    assert autenticar(db, "raiana@exemplo.com", "senhaforte123") is None


# --- trocar_senha (Marco 15 — tela de Configurações) ---


def test_trocar_senha_sucesso_permite_login_com_a_nova(db, prestador_teste):
    usuario = criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    trocar_senha(db, usuario.id, "senhaoriginal123", "senhanova456")
    assert autenticar(db, "raiana@exemplo.com", "senhaoriginal123") is None
    assert autenticar(db, "raiana@exemplo.com", "senhanova456") is not None


def test_trocar_senha_atual_errada_recusa_e_nao_muda_nada(db, prestador_teste):
    usuario = criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    with pytest.raises(SenhaAtualIncorretaError):
        trocar_senha(db, usuario.id, "senhaerrada", "senhanova456")
    assert autenticar(db, "raiana@exemplo.com", "senhaoriginal123") is not None


def test_trocar_senha_usuario_inativo_recusa(db, prestador_teste):
    usuario = criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    usuario.ativo = False
    db.flush()
    with pytest.raises(SenhaAtualIncorretaError):
        trocar_senha(db, usuario.id, "senhaoriginal123", "senhanova456")


# --- scripts/criar_usuario.py (a função de negócio, sem subprocess) ---


def test_script_criar_usuario_cria_e_depois_atualiza_senha(db, prestador_teste):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from criar_usuario import criar_ou_atualizar  # noqa: E402

    criar_ou_atualizar(db, email="raiana@exemplo.com", senha="senhaoriginal123", prestador_id=prestador_teste.id)
    assert autenticar(db, "raiana@exemplo.com", "senhaoriginal123") is not None

    criar_ou_atualizar(db, email="raiana@exemplo.com", senha="senhanova456", prestador_id=prestador_teste.id)
    assert autenticar(db, "raiana@exemplo.com", "senhaoriginal123") is None  # senha antiga não funciona mais
    assert autenticar(db, "raiana@exemplo.com", "senhanova456") is not None

    # continua havendo só UM usuário com esse e-mail (upsert, não duplicou)
    from app.models import Usuario
    assert db.query(Usuario).filter_by(email="raiana@exemplo.com").count() == 1


# --- Fluxo HTTP completo (login real, sem overridar prestador_atual_id) ---


@pytest.fixture
def client_sem_login(db, prestador_teste):
    """Diferente do fixture `client` das outras suítes: aqui só o `get_db`
    é sobrescrito — `prestador_atual_id` fica intacto, então a autenticação
    de verdade (cookie de sessão) precisa acontecer pra rota protegida
    funcionar."""
    from app.database import get_db
    from app.main import app

    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    from fastapi.testclient import TestClient
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_rota_protegida_sem_login_da_401(client_sem_login):
    resp = client_sem_login.get("/api/vinculos")
    assert resp.status_code == 401


def test_me_sem_login_da_401(client_sem_login):
    resp = client_sem_login.get("/api/auth/me")
    assert resp.status_code == 401


def test_login_com_senha_errada_da_401(client_sem_login, db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    resp = client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "errada"})
    assert resp.status_code == 401


def test_login_com_email_inexistente_da_401(client_sem_login):
    resp = client_sem_login.post("/api/auth/login", json={"email": "ninguem@exemplo.com", "senha": "qualquer123"})
    assert resp.status_code == 401


def test_login_sucesso_libera_rota_protegida_e_isola_pelo_prestador_certo(client_sem_login, db, prestador_teste, vinculo_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    login = client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaforte123"})
    assert login.status_code == 200, login.text
    assert login.json()["prestador_id"] == str(prestador_teste.id)

    me = client_sem_login.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "raiana@exemplo.com"

    vinculos = client_sem_login.get("/api/vinculos")
    assert vinculos.status_code == 200
    assert len(vinculos.json()) == 1
    assert vinculos.json()[0]["apelido"] == "Fornecedor Teste"


def test_logout_derruba_a_sessao(client_sem_login, db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaforte123"})
    assert client_sem_login.get("/api/auth/me").status_code == 200

    resp = client_sem_login.post("/api/auth/logout")
    assert resp.status_code == 200
    assert client_sem_login.get("/api/auth/me").status_code == 401
    assert client_sem_login.get("/api/vinculos").status_code == 401


def test_dois_usuarios_de_prestadores_diferentes_nao_veem_dados_um_do_outro(client_sem_login, db, prestador_teste, vinculo_teste):
    """O teste que mais importa aqui: login resolve prestador_id no
    SERVIDOR a partir de quem logou — usuários de prestadores diferentes
    continuam isolados pela RLS de sempre, agora por trás de sessão real."""
    import uuid as uuid_mod

    from app.database import definir_prestador_atual
    from app.models import Prestador as PrestadorModel

    outro_prestador_id = uuid_mod.uuid4()
    definir_prestador_atual(db, outro_prestador_id)
    outro_prestador = PrestadorModel(
        id=outro_prestador_id, cpf_cnpj="22222222000199", razao_social="OUTRO PRESTADOR TESTE", cod_municipio="3106200",
    )
    db.add(outro_prestador)
    db.flush()
    criar_usuario(db, outro_prestador_id, "outro@exemplo.com", "senhaforte123")
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")

    resp = client_sem_login.post("/api/auth/login", json={"email": "outro@exemplo.com", "senha": "senhaforte123"})
    assert resp.status_code == 200
    assert resp.json()["prestador_id"] == str(outro_prestador_id)

    # este usuário está logado como o OUTRO prestador — não deve ver o vínculo do prestador_teste
    vinculos = client_sem_login.get("/api/vinculos")
    assert vinculos.status_code == 200
    assert vinculos.json() == []


# --- POST /api/auth/trocar-senha (Marco 15) ---


def test_trocar_senha_sem_login_da_401(client_sem_login):
    resp = client_sem_login.post(
        "/api/auth/trocar-senha", json={"senha_atual": "qualquer123", "senha_nova": "outraqualquer456"}
    )
    assert resp.status_code == 401


def test_trocar_senha_via_http_sucesso_permite_login_com_a_nova(client_sem_login, db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaoriginal123"})

    resp = client_sem_login.post(
        "/api/auth/trocar-senha", json={"senha_atual": "senhaoriginal123", "senha_nova": "senhanova456"}
    )
    assert resp.status_code == 200, resp.text

    # a sessão atual continua valendo (não desloga ao trocar)
    assert client_sem_login.get("/api/auth/me").status_code == 200

    client_sem_login.post("/api/auth/logout")
    login_com_senha_antiga = client_sem_login.post(
        "/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaoriginal123"}
    )
    assert login_com_senha_antiga.status_code == 401
    login_com_senha_nova = client_sem_login.post(
        "/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhanova456"}
    )
    assert login_com_senha_nova.status_code == 200


def test_trocar_senha_via_http_atual_errada_da_400(client_sem_login, db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaoriginal123"})

    resp = client_sem_login.post(
        "/api/auth/trocar-senha", json={"senha_atual": "senhaerrada", "senha_nova": "senhanova456"}
    )
    assert resp.status_code == 400

    login_com_senha_original = client_sem_login.post(
        "/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaoriginal123"}
    )
    assert login_com_senha_original.status_code == 200


def test_trocar_senha_nova_curta_demais_da_422(client_sem_login, db, prestador_teste):
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaoriginal123")
    client_sem_login.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaoriginal123"})

    resp = client_sem_login.post(
        "/api/auth/trocar-senha", json={"senha_atual": "senhaoriginal123", "senha_nova": "curta"}
    )
    assert resp.status_code == 422
