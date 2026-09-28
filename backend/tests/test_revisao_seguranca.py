"""Revisão de segurança e bugs de 28/09/2026: limite de tentativas nas rotas
públicas, bloqueio de pedidos vindos de outros sites, cabeçalhos de
segurança, catálogo de tomadores protegido da simulação, descrição com
código desconhecido, competência inválida, pagamentos pelo ano em que caíram
e teto diário de e-mails."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import PagamentoRecebido, Tomador
from app.services.demo import apagar_conta_demo


@pytest.fixture
def client_publico(db):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


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


def test_login_tem_limite_de_tentativas(client_publico):
    codigos = [
        client_publico.post("/api/auth/login", json={"email": "ninguem@x.com", "senha": "errada123"}).status_code
        for _ in range(22)
    ]
    assert 429 in codigos and codigos[0] != 429


def test_pedido_de_outro_site_e_recusado_e_cabecalhos(client_publico):
    r = client_publico.post("/api/auth/login", json={"email": "a@x.com", "senha": "12345678"}, headers={"Origin": "https://malicioso.com"})
    assert r.status_code == 403
    r = client_publico.post("/api/auth/login", json={"email": "a@x.com", "senha": "12345678"}, headers={"Origin": "https://notas.agenteana.com.br"})
    assert r.status_code != 403
    r = client_publico.get("/api/suporte")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"


def test_simulacao_nao_planta_tomador_no_catalogo_nem_ve_sugestoes(client_publico, db):
    assert client_publico.post("/api/demo").status_code == 200
    novo = {
        "novo_tomador": {"cnpj": "11444777000161", "razao_social": "Empresa Inventada", "cod_municipio": "3550308"},
        "apelido": "Inventada", "cod_local_prestacao": "3550308", "cod_trib_nacional": "170601",
        "template_descricao": "Serviço {competencia_mm_aaaa}",
    }
    r = client_publico.post("/api/vinculos", json=novo)
    assert r.status_code == 200, r.text
    tomador = db.query(Tomador).filter_by(cnpj="11444777000161").one()
    assert tomador.status == "pendente"
    assert all(t["cnpj"] != "11444777000161" for t in client_publico.get("/api/tomadores").json())
    assert all(t["sug_template_descricao"] is None for t in client_publico.get("/api/tomadores").json())

    # apagar a simulação leva o tomador junto
    prestador_id = uuid.UUID(client_publico.get("/api/auth/me").json()["prestador_id"])
    apagar_conta_demo(db, prestador_id)
    assert db.query(Tomador).filter_by(cnpj="11444777000161").one_or_none() is None


def test_conta_real_assume_tomador_pendente_do_mesmo_cnpj(client, db):
    db.add(Tomador(id=uuid.uuid4(), cnpj="11444777000161", razao_social="Plantado", cod_municipio="3550308", status="pendente"))
    db.flush()
    r = client.post("/api/vinculos", json={
        "novo_tomador": {"cnpj": "11444777000161", "razao_social": "Nome Certo LTDA", "cod_municipio": "3106200"},
        "apelido": "Certo", "cod_local_prestacao": "3106200", "cod_trib_nacional": "170601",
        "template_descricao": "Serviço",
    })
    assert r.status_code == 200, r.text
    tomador = db.query(Tomador).filter_by(cnpj="11444777000161").one()
    assert tomador.status == "aprovado" and tomador.razao_social == "Nome Certo LTDA"


def test_dados_oficiais_ganham_do_digitado(client, db, monkeypatch):
    from app.services.cnpj_lookup import DadosCnpj

    oficial = DadosCnpj(
        razao_social="RAZAO OFICIAL SA", logradouro="Rua Oficial", numero="1", complemento=None, bairro="Centro",
        cep="01000000", municipio="São Paulo", uf="SP", cod_municipio_sugerido="3550308", situacao_cadastral="ATIVA",
    )
    monkeypatch.setattr("app.main._dados_oficiais_cnpj", lambda cnpj: oficial)
    r = client.post("/api/vinculos", json={
        "novo_tomador": {"cnpj": "22333444000181", "razao_social": "Qualquer Coisa", "cod_municipio": "3106200"},
        "apelido": "Oficial", "cod_local_prestacao": "3106200", "cod_trib_nacional": "170601",
        "template_descricao": "Serviço",
    })
    assert r.status_code == 200, r.text
    t = db.query(Tomador).filter_by(cnpj="22333444000181").one()
    assert t.razao_social == "RAZAO OFICIAL SA" and t.cod_municipio == "3550308"


def test_descricao_com_codigo_desconhecido_nao_derruba(client, vinculo_teste):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"template_descricao": "Comissão {cliente} { solto {mes}/{ano}"})
    assert r.status_code == 200
    r = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-05", "valor": 10})
    assert r.status_code == 200, r.text
    assert client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-13", "valor": 10}).status_code == 422
    assert client.get("/api/painel/resumo-mes?competencia=abcd-ef").status_code == 422
    assert client.get("/api/calendario?inicio=0001-01-01&fim=2026-01-01").status_code == 422


def test_pagamentos_pelo_ano_em_que_cairam(client, db, prestador_teste, vinculo_teste):
    db.add(PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id,
        competencia="2025-12", valor=100, data_recebimento=datetime.date(2026, 1, 10),
    ))
    db.flush()
    assert len(client.get("/api/pagamentos?ano=2026&por=recebimento").json()) == 1
    assert len(client.get("/api/pagamentos?ano=2025&por=recebimento").json()) == 0
    assert len(client.get("/api/pagamentos?ano=2025").json()) == 1


def test_upload_grande_demais_da_413(client):
    grande = b"%PDF" + b"0" * (10 * 1024 * 1024 + 10)
    r = client.post("/api/awin/ordem", files={"arquivo": ("o.pdf", grande, "application/pdf")})
    assert r.status_code == 413
