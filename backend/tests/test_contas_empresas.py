"""Conta e empresas (29/09/2026): sessões no servidor, desconectar aparelho,
login por código no e-mail, vários CNPJs no mesmo login, dados do emitente
editáveis e excluir empresa/conta."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app
from app.models import Prestador, Sessao, Usuario, UsuarioPrestador
from app.services.usuarios import criar_usuario


@pytest.fixture
def cliente(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    usuario = criar_usuario(db, prestador_teste.id, "dono@empresa.com", "senha-forte-1")
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador_teste.id))
    db.flush()
    yield TestClient(app), usuario
    app.dependency_overrides.pop(get_db, None)


def _login(client):
    r = client.post("/api/auth/login", json={"email": "dono@empresa.com", "senha": "senha-forte-1"})
    assert r.status_code == 200, r.text


def test_sessoes_listar_e_desconectar_outro_aparelho(cliente, db):
    client, usuario = cliente
    _login(client)
    outro = TestClient(app)
    r = outro.post("/api/auth/login", json={"email": "dono@empresa.com", "senha": "senha-forte-1"}, headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari/605"})
    assert r.status_code == 200
    sessoes = client.get("/api/conta/sessoes").json()
    assert len(sessoes) == 2 and sum(s["atual"] for s in sessoes) == 1
    do_iphone = next(s for s in sessoes if not s["atual"])
    assert do_iphone["dispositivo"].startswith("iPhone")

    assert client.delete(f"/api/conta/sessoes/{do_iphone['id']}").status_code == 200
    assert outro.get("/api/auth/me").status_code == 401  # derrubado
    assert client.get("/api/auth/me").status_code == 200


def test_trocar_senha_derruba_os_outros(cliente):
    client, _ = cliente
    _login(client)
    outro = TestClient(app)
    outro.post("/api/auth/login", json={"email": "dono@empresa.com", "senha": "senha-forte-1"})
    r = client.post("/api/auth/trocar-senha", json={"senha_atual": "senha-forte-1", "senha_nova": "outra-senha-2"})
    assert r.status_code == 200
    assert outro.get("/api/vinculos").status_code == 401
    assert client.get("/api/vinculos").status_code == 200


def test_login_por_codigo(cliente, monkeypatch):
    client, _ = cliente
    enviados = []

    class Falso:
        def enviar(self, **kw):
            enviados.append(kw)

    monkeypatch.setattr("app.main.get_email_sender", lambda: Falso())
    assert client.post("/api/auth/codigo", json={"email": "ninguem@x.com"}).json() == {"ok": True}
    assert enviados == []  # sem conta: não manda, mas responde igual
    client.post("/api/auth/codigo", json={"email": "Dono@Empresa.com"})
    codigo = enviados[-1]["assunto"].split()[0]
    assert len(codigo) == 6
    assert client.post("/api/auth/codigo/entrar", json={"email": "dono@empresa.com", "codigo": "000000" if codigo != "000000" else "111111"}).status_code == 401
    r = client.post("/api/auth/codigo/entrar", json={"email": "dono@empresa.com", "codigo": codigo})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    # o código não vale duas vezes
    assert TestClient(app).post("/api/auth/codigo/entrar", json={"email": "dono@empresa.com", "codigo": codigo}).status_code == 401


def test_varios_cnpjs_no_mesmo_login(cliente, db, prestador_teste):
    client, usuario = cliente
    _login(client)
    r = client.post("/api/empresas", json={"cpf_cnpj": "11444777000161", "razao_social": "Segunda Empresa LTDA", "cod_municipio": "3106200"})
    assert r.status_code == 200, r.text
    nova_id = r.json()["id"]
    empresas = client.get("/api/empresas").json()
    assert len(empresas) == 2 and next(e for e in empresas if e["id"] == nova_id)["ativa"]
    # a empresa nova está vazia; a antiga continua com os dados dela
    assert client.get("/api/prestador").json()["razao_social"] == "Segunda Empresa LTDA"
    client.post(f"/api/empresas/{prestador_teste.id}/ativar")
    assert client.get("/api/prestador").json()["razao_social"] == prestador_teste.razao_social
    # CNPJ repetido
    assert client.post("/api/empresas", json={"cpf_cnpj": "11444777000161", "razao_social": "X", "cod_municipio": "3106200"}).status_code == 409


def test_editar_emitente(cliente):
    client, _ = cliente
    _login(client)
    r = client.patch("/api/prestador", json={"nome_fantasia": "Minha Loja", "telefone": "31999990000", "op_simples_nacional": "3", "cep": "30.140-093"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nome_fantasia"] == "Minha Loja" and corpo["cep"] == "30140093" and corpo["op_simples_nacional"] == "3"
    assert client.patch("/api/prestador", json={"op_simples_nacional": "9"}).status_code == 422


def test_excluir_empresa_e_conta(cliente, db, prestador_teste):
    client, usuario = cliente
    _login(client)
    nova = client.post("/api/empresas", json={"cpf_cnpj": "11444777000161", "razao_social": "Descartável", "cod_municipio": "3106200"}).json()
    assert client.request("DELETE", "/api/empresa", json={"confirmacao": "123"}).status_code == 422
    r = client.request("DELETE", "/api/empresa", json={"confirmacao": "11.444.777/0001-61"})
    assert r.status_code == 200 and r.json()["conta_excluida"] is False
    definir_prestador_atual(db, nova["id"])
    assert db.get(Prestador, nova["id"]) is None
    assert client.get("/api/auth/me").status_code == 200  # voltou pra empresa que sobrou

    assert client.request("DELETE", "/api/conta", json={"confirmacao": "sim"}).status_code == 422
    usuario_id = usuario.id
    assert client.request("DELETE", "/api/conta", json={"confirmacao": "excluir"}).status_code == 200
    assert db.get(Usuario, usuario_id) is None
    assert db.query(Sessao).filter_by(usuario_id=usuario_id).count() == 0


def test_conta_de_teste(db, monkeypatch):
    """Conta de teste: repete o CNPJ de uma conta real, nota sempre em
    homologação e e-mail de nota só pra quem testa."""
    import app.services.cadastro as cadastro
    import app.services.envio_direto as envio_direto
    from app.config import get_settings
    from app.models import Prestador, PrestadorTomador, Tomador, Usuario
    from app.services.motor_emissao import montar

    monkeypatch.setattr(cadastro, "_enviar_email_confirmacao", lambda *a, **k: None)
    real = cadastro.criar_cadastro(db, email="real@x.com", senha="12345678", razao_social="Real", cpf_cnpj="98765432000110", cod_municipio="3106200")
    teste = cadastro.criar_cadastro(
        db, email="teste@x.com", senha="12345678", razao_social="Teste", cpf_cnpj="98765432000110", cod_municipio="3106200", modo_teste=True,
    )
    assert teste.prestador_id != real.prestador_id

    from app.database import definir_prestador_atual
    definir_prestador_atual(db, teste.prestador_id)
    p = db.get(Prestador, teste.prestador_id)
    assert p.modo_teste and p.tp_amb_padrao == "2"

    db.commit = db.flush
    from app.main import app, prestador_atual_id
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: (yield db)
    app.dependency_overrides[prestador_atual_id] = lambda: teste.prestador_id
    try:
        client = TestClient(app)
        t = Tomador(
            # endereço inteiro: a conferência não deixa gerar nota com ele pela metade
            id=uuid.uuid4(), cnpj="11222333000181", razao_social="T", cod_municipio="3550308",
            cep="01311000", logradouro="Av Teste", numero="100", bairro="Centro",
        )
        db.add(t)
        db.flush()
        v = PrestadorTomador(
            id=uuid.uuid4(), prestador_id=teste.prestador_id, tomador_id=t.id, apelido="T", cod_local_prestacao="3106200",
            cod_trib_nacional="170601", template_descricao="Serviço", ativo=True, email_contato="tomador@real.com",
        )
        db.add(v)
        db.flush()
        r = client.post("/api/dps", json={"vinculo_id": str(v.id), "competencia": "2026-09", "valor": 10, "tpAmb": "1"})
        assert r.status_code == 200, r.text
        from app.models import Emissao
        e = db.get(Emissao, uuid.UUID(r.json()["id"]))
        assert e.tomador_snapshot["tpAmb"] == "2"
        assert client.patch("/api/prestador/preferencias", json={"tp_amb_padrao": "1"}).json()["tp_amb_padrao"] == "2"

        enviados = []

        class Falso:
            def enviar(self, **kw):
                enviados.append(kw)

        monkeypatch.setattr(envio_direto, "get_email_sender", lambda: Falso())
        monkeypatch.setattr(envio_direto, "motivo_email_desabilitado", lambda vinculo, destino=None: None)
        v.email_anexos = "xml"
        r = client.post(f"/api/dps/{e.id}/enviar-email", json={})
        assert r.status_code == 200, r.text
        assert enviados[-1]["destinatario"] == ["teste@x.com"] and enviados[-1]["assunto"].startswith("[TESTE]")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(prestador_atual_id, None)
