"""Painel de gestão da plataforma (06/10/2026). Só dados sintéticos."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.main import app, exigir_gestor, prestador_atual_id
from app.models import Assinatura, Emissao, Prestador, Usuario
from app.services import gestao
from app.services.motor_emissao import criar_rascunho


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
    app.dependency_overrides.pop(exigir_gestor, None)


def _usuario(db, prestador, email, confirmado=True):
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador.id, email=email, senha_hash="scrypt$00$00", email_confirmado=confirmado)
    db.add(u)
    db.flush()
    return u


def test_gestao_so_abre_pra_quem_esta_em_admin_emails(client, db, prestador_teste, monkeypatch):
    # sem a variável: ninguém entra — nem a conta "cortesia"
    db.add(Assinatura(id=uuid.uuid4(), prestador_id=prestador_teste.id, status="cortesia"))
    db.flush()
    assert client.get("/api/gestao/acesso").json() == {"gestor": False, "configurado": False, "separada": False}
    assert client.get("/api/gestao").status_code == 403
    assert client.get("/api/gestao/guia").status_code == 403
    # com a variável, mas sem ser o login certo
    monkeypatch.setattr(get_settings(), "admin_emails", "dona@plataforma.com")
    assert client.get("/api/gestao/acesso").json() == {"gestor": False, "configurado": True, "separada": False}
    assert client.get("/api/gestao").status_code == 403


def test_painel_conta_o_uso_de_cada_empresa_sem_misturar(client, db, prestador_teste, vinculo_teste):
    _usuario(db, prestador_teste, "dono@empresa-a.com")
    nota = criar_rascunho(db, vinculo_teste, competencia="2026-10", valor=100)
    nota.estado = "confirmado"
    db.flush()
    # outra empresa, sem nota nenhuma e com e-mail por confirmar
    outra = Prestador(id=uuid.uuid4(), cpf_cnpj="00000000000353", razao_social="OUTRA EMPRESA LTDA", cod_municipio="3106200", modulos=["financeiro"])
    definir_prestador_atual(db, outra.id)
    db.add(outra)
    db.flush()
    _usuario(db, outra, "novo@empresa-b.com", confirmado=False)
    definir_prestador_atual(db, prestador_teste.id)

    painel = gestao.painel(db, prestador_teste.id, hoje=datetime.date.today())
    por_nome = {c["razao_social"]: c for c in painel["contas"]}
    a, b = por_nome[prestador_teste.razao_social], por_nome["OUTRA EMPRESA LTDA"]
    assert (a["notas_total"], a["tomadores"], a["email_confirmado"], a["certificado"]) == (1, 1, True, "falta")
    assert (b["notas_total"], b["tomadores"], b["email_confirmado"], b["modulos"]) == (0, 0, False, ["financeiro"])
    assert [l["email"] for l in b["logins"]] == ["novo@empresa-b.com"]
    # só números: nada de tomador, descrição ou valor de nota
    assert not any("TOMADOR DE TESTE" in str(v) or "Comissão de teste" in str(v) for v in a.values())
    notas = next(f for f in painel["ferramentas"] if f["id"] == "notas")
    assert notas["contas"] >= 1
    # o contexto volta pra empresa de quem chamou
    assert db.query(Emissao).count() == 1

    # pela rota (com o acesso liberado)
    app.dependency_overrides[exigir_gestor] = lambda: None
    r = client.get("/api/gestao")
    assert r.status_code == 200 and r.json()["resumo"]["contas"] >= 2
    guia = client.get("/api/gestao/guia")
    assert guia.status_code == 200 and "Agente Ana" in guia.text and "attachment" in guia.headers["content-disposition"]
