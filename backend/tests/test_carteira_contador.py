"""Carteira do contador (2026.10.7): números de cada cliente, cadastrar cliente
novo com convite pro dono e a contagem de clientes ativos por contador (base da
cobrança por cliente, que ainda não está ligada). Só dados sintéticos."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.deps import usuario_logado
from app.main import app
from app.models import AcessoContador, ConviteDono, Prestador, Usuario, UsuarioPrestador
from app.services import carteira


@pytest.fixture
def ambiente(db, monkeypatch, prestador_teste):
    monkeypatch.setattr(db, "commit", db.flush)
    enviados = []
    monkeypatch.setattr("app.contador.get_email_sender", lambda: type("S", (), {"enviar": lambda self, **kw: enviados.append(kw)})())

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield enviados
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(usuario_logado, None)
    definir_prestador_atual(db, prestador_teste.id)


def _contador(db):
    casa = Prestador(id=uuid.uuid4(), cpf_cnpj=f"CT{uuid.uuid4().hex[:10]}", razao_social="ESCRITORIO SINTETICO", cod_municipio="3106200", so_contador=True)
    definir_prestador_atual(db, casa.id)
    db.add(casa)
    db.flush()
    u = Usuario(id=uuid.uuid4(), prestador_id=casa.id, email=f"contador{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    return u


def _cliente(usuario):
    app.dependency_overrides[usuario_logado] = lambda: usuario
    return TestClient(app)


def _cnpj():
    base = "9" + uuid.uuid4().int.__str__()[:11]
    return base + "00"


NOVO = {"razao_social": "CLIENTE SINTETICO LTDA", "cod_municipio": "3106200", "email_dono": "dono.sintetico@exemplo.com.br"}


def test_contador_cadastra_cliente_e_o_dono_recebe_o_convite(db, ambiente):
    contador = _contador(db)
    c = _cliente(contador)
    cnpj = _cnpj()
    r = c.post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": cnpj})
    assert r.status_code == 200, r.text
    assert r.json()["email_enviado"] is True and ambiente[0]["destinatario"] == NOVO["email_dono"]
    assert "/convite/" in ambiente[0]["corpo_texto"]
    a = db.get(AcessoContador, uuid.UUID(r.json()["acesso_id"]))
    assert a.status == "ativo" and a.criado_pelo_contador and "documentos" not in a.permissoes and "emitir" in a.permissoes
    painel = c.get("/api/contador/atendimentos").json()
    cliente = next(x for x in painel["clientes"] if x["id"] == str(a.id))
    assert cliente["criado_pelo_contador"] is True and cliente["convite_dono"] == {"email": NOVO["email_dono"], "aceito": False, "vencido": False}
    assert painel["resumo"]["na_carteira"] >= 1 and painel["resumo"]["cadastrados_pelo_contador"] >= 1
    # CNPJ repetido
    assert c.post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": cnpj}).status_code == 409
    # reenviar o convite troca o link
    antigo = db.query(ConviteDono).filter_by(prestador_id=a.prestador_id).one().token
    assert c.post(f"/api/contador/clientes/{a.id}/reenviar-convite").status_code == 200
    assert db.query(ConviteDono).filter_by(prestador_id=a.prestador_id).one().token != antigo


def test_so_contador_cadastra_e_nunca_com_o_proprio_email(db, ambiente, prestador_teste):
    dono = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"dono{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(dono)
    db.flush()
    assert _cliente(dono).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj()}).status_code == 403
    contador = _contador(db)
    r = _cliente(contador).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj(), "email_dono": contador.email})
    assert r.status_code == 422


def test_dono_cria_a_conta_pelo_convite(db, ambiente):
    contador = _contador(db)
    r = _cliente(contador).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj(), "email_dono": "novo.dono@exemplo.com.br"})
    token = ambiente[0]["corpo_texto"].split("/convite/")[1].split()[0]
    publico = TestClient(app)
    app.dependency_overrides.pop(usuario_logado, None)
    info = publico.get(f"/api/convite-dono/{token}").json()
    assert info["tem_conta"] is False and info["email"] == "novo.dono@exemplo.com.br"
    assert publico.post(f"/api/convite-dono/{token}/criar-conta", json={"senha": "senha-boa-123", "whatsapp": "31999990000"}).status_code == 200
    u = db.query(Usuario).filter_by(email="novo.dono@exemplo.com.br").one()
    prestador_id = uuid.UUID(r.json()["prestador_id"])
    assert u.email_confirmado and u.prestador_id == prestador_id
    assert db.query(UsuarioPrestador).filter_by(usuario_id=u.id, prestador_id=prestador_id).count() == 1
    assert publico.get(f"/api/convite-dono/{token}").status_code == 409  # já usado


def test_dono_que_ja_tem_conta_aceita_logado(db, ambiente, prestador_teste):
    existente = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email="ja.tenho@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(existente)
    db.flush()
    contador = _contador(db)
    r = _cliente(contador).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj(), "email_dono": existente.email})
    token = ambiente[0]["corpo_texto"].split("/convite/")[1].split()[0]
    assert _cliente(contador).post(f"/api/convite-dono/{token}/aceitar").status_code == 403  # outro e-mail
    c = _cliente(existente)
    assert c.get(f"/api/convite-dono/{token}").json()["tem_conta"] is True
    assert c.post(f"/api/convite-dono/{token}/criar-conta", json={"senha": "senha-boa-123", "whatsapp": "31999990000"}).status_code == 409
    assert c.post(f"/api/convite-dono/{token}/aceitar").status_code == 200
    assert db.query(UsuarioPrestador).filter_by(usuario_id=existente.id, prestador_id=uuid.UUID(r.json()["prestador_id"])).count() == 1


def test_convite_vencido(db, ambiente):
    contador = _contador(db)
    r = _cliente(contador).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj()})
    convite = db.query(ConviteDono).filter_by(prestador_id=uuid.UUID(r.json()["prestador_id"])).one()
    convite.expira_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    db.flush()
    assert TestClient(app).get(f"/api/convite-dono/{convite.token}").status_code == 410


def test_regra_do_cliente_ativo_no_mes():
    hoje = datetime.date(2026, 10, 10)
    neste_mes = datetime.datetime(2026, 10, 2, tzinfo=datetime.timezone.utc)
    mes_passado = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)
    com_nota = {"situacao": {"motivo": "teste"}, "raio_x": {"notas_mes": 3}}
    sem_nota = {"situacao": {"motivo": "assinatura"}, "raio_x": {"notas_mes": 0}}
    assert carteira.ativo_no_mes(com_nota, None, hoje)
    assert carteira.ativo_no_mes(sem_nota, neste_mes, hoje)
    assert not carteira.ativo_no_mes(sem_nota, mes_passado, hoje)
    assert not carteira.ativo_no_mes({"situacao": {"motivo": "bloqueada", "bloqueado": True}, "raio_x": {"notas_mes": 5}}, neste_mes, hoje)
    assert not carteira.ativo_no_mes({"situacao": {"motivo": "teste_acabou"}, "raio_x": {"notas_mes": 5}}, neste_mes, hoje)


def test_gestao_conta_os_clientes_de_cada_contador(db, ambiente, prestador_teste):
    contador = _contador(db)
    c = _cliente(contador)
    for _ in range(2):
        assert c.post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj()}).status_code == 200
    linhas = carteira.resumo_gestao(db, prestador_teste.id)
    minha = next(x for x in linhas if x["email"] == contador.email)
    assert minha["na_carteira"] == 2 and minha["cadastrados_pelo_contador"] == 2 and minha["ativos_no_mes"] == 0


def test_cadastrar_cliente_sem_contexto_da_rls_no_pedido(db, ambiente):
    """Num pedido de verdade a variável da RLS começa vazia: a rota tem que
    definir o contexto antes de ler a empresa "de casa" (deu 500 no navegador)."""
    from sqlalchemy import text

    contador = _contador(db)
    db.info.pop("prestador_atual", None)
    db.execute(text("select set_config('app.current_prestador_id', '', true)"))
    r = _cliente(contador).post("/api/contador/clientes", json={**NOVO, "cpf_cnpj": _cnpj()})
    assert r.status_code == 200, r.text
