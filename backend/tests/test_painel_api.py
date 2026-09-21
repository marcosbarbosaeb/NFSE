"""
Testes de integração do painel (Marco 5/6) — batem na API de verdade
(fastapi.testclient) contra o Postgres local, usando um vínculo real criado
no teste (nunca os dados de produção da Raiana).

`db_sessao` do app usa `settings.prestador_ativo_id` fixo (sem login) — pra
testar isolado sem depender/poluir o prestador real, sobrescrevemos essa
dependency via `app.dependency_overrides` apontando pro prestador de teste.

A partir do Marco 6, POST /api/dps PERSISTE (cria rascunho + monta) — os
testes de nDPS automático e da máquina de estados de verdade vivem em
tests/test_motor_emissao.py; aqui é só a camada HTTP por cima disso.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import PrestadorTomador, Tomador

# vinculo_teste vem de conftest.py (compartilhado com test_motor_emissao.py)


@pytest.fixture
def client(db, prestador_teste):
    # api_salvar_certificado dá commit() de propósito (senão o certificado
    # não sobreviveria ao fim do request, em uso real). Aqui, `db` é a MESMA
    # sessão/transação da fixture `prestador_teste` — um commit() de verdade
    # vazaria o prestador de teste pro banco permanentemente, já que o
    # rollback() do teardown vira no-op depois de um commit. flush() já
    # basta pra o próprio teste enxergar a escrita (mesma transação).
    db.commit = db.flush

    def _get_db_override():
        # precisa ser generator function de verdade (yield, não um
        # iterator já pronto) — é assim que o FastAPI reconhece e aplica o
        # mesmo protocolo de cleanup da dependency original (get_db).
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_listar_vinculos_vazio_sem_nenhum_cadastrado(client, prestador_teste):
    resp = client.get("/api/vinculos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_vinculos_devolve_o_criado(client, vinculo_teste):
    resp = client.get("/api/vinculos")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["apelido"] == "Fornecedor Teste"
    assert dados[0]["tomador_cnpj"] == "11222333000181"


def test_status_certificado_sem_certificado(client, prestador_teste):
    resp = client.get("/api/certificado/status")
    assert resp.status_code == 200
    assert resp.json() == {"carregado": False, "validade": None, "vencido": False}


def test_upload_certificado_e_status_reflete(client, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        resp = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": certificado_teste["senha"]},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["carregado"] is True

    resp2 = client.get("/api/certificado/status")
    assert resp2.json()["carregado"] is True


def test_upload_certificado_com_senha_errada_da_400(client, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        resp = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": "senha-errada"},
        )
    assert resp.status_code == 400


def test_criar_dps_persiste_com_ndps_automatico(client, vinculo_teste):
    resp = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0, "tpAmb": "2",
    })
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "montado"
    assert dados["n_dps"] == 1  # atribuído sozinho — sem campo n_dps no request
    assert "<DPS" in dados["xml"]
    assert "Signature" not in dados["xml"]
    assert dados["tomador"] == "TOMADOR DE TESTE LTDA"
    assert "08/2026" in dados["descricao"]

    # persistiu de verdade: uma segunda emissão pega o próximo nDPS.
    resp2 = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 50.0, "tpAmb": "2",
    })
    assert resp2.json()["n_dps"] == 2


def test_criar_dps_vinculo_inexistente_da_404(client, prestador_teste):
    resp = client.post("/api/dps", json={
        "vinculo_id": str(uuid.uuid4()), "competencia": "2026-08", "valor": 100.0,
    })
    assert resp.status_code == 404


def test_criar_dps_duplicada_mesma_competencia_da_409(client, vinculo_teste):
    r1 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    assert r1.status_code == 200
    r2 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 200.0})
    assert r2.status_code == 409


def test_ver_dps_por_id(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.get(f"/api/dps/{criada['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == criada["id"]


def test_assinar_dps_sem_certificado_da_409(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/assinar")
    assert resp.status_code == 409


def test_assinar_dps_com_certificado_carregado(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        r = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": certificado_teste["senha"]},
        )
    assert r.status_code == 200

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/assinar")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "assinado"
    assert "<Signature" in dados["xml"]


def test_assinar_dps_duas_vezes_da_409_na_segunda(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    r1 = client.post(f"/api/dps/{criada['id']}/assinar")
    assert r1.status_code == 200
    r2 = client.post(f"/api/dps/{criada['id']}/assinar")
    assert r2.status_code == 409  # já está assinado, não pode assinar de novo


def test_criar_dps_com_template_de_ordem_sem_ordem_da_422(client, db, prestador_teste):
    tomador = Tomador(
        id=uuid.uuid4(), cnpj="99888777000166", razao_social="AWIN TESTE",
        cod_municipio="3550308", cep="01311000", logradouro="Rua X", numero="1", bairro="Centro",
    )
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador.id,
        apelido="AWIN Teste", cod_local_prestacao=prestador_teste.cod_municipio,
        cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="Ordem número: {ordem}", serie="1", ativo=True,
    )
    db.add(vinculo)
    db.flush()

    resp = client.post("/api/dps", json={
        "vinculo_id": str(vinculo.id), "competencia": "2026-08", "valor": 100.0,
    })
    assert resp.status_code == 422


def test_pagina_inicial_carrega(client):
    """Marco 12: `/` agora serve o SPA novo (React/Vite, frontend/dist) —
    o backend só entrega o index.html gerado pelo `npm run build`; o
    conteúdo de verdade é montado no navegador, então o teste checa só a
    casca (`id="root"`), não texto de UI (que mudaria a cada ajuste
    visual sem relação nenhuma com este endpoint)."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="root"' in resp.text


# --- Marco 11: /api/dps/{id}/nota — máscara visual (ver app/services/nota_visual.py) ---


def test_nota_visual_apos_montar_traz_prestador_tomador_e_servico(client, vinculo_teste, prestador_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 150.0}).json()

    resp = client.get(f"/api/dps/{criada['id']}/nota")
    assert resp.status_code == 200, resp.text
    nota = resp.json()

    assert nota["estado"] == "montado"
    assert nota["serie"] == vinculo_teste.serie
    assert nota["n_dps"] == criada["n_dps"]
    assert nota["competencia"] == "2026-08"
    assert nota["ambiente"] == "2"  # default de GerarDpsRequest.tpAmb
    assert nota["xml_disponivel"] is True
    assert nota["id_dps"]  # nasce na montagem

    # PRESTADOR vem do banco (Prestador), não do XML — a DPS deliberadamente
    # não leva nome/endereço do prestador (ver docstring de app/fiscal/dps.py,
    # erro E0121) — é por isso que este endpoint existe em vez de só reler o XML.
    assert nota["prestador"]["razao_social"] == prestador_teste.razao_social
    assert "00.000.000/0001-91" == nota["prestador"]["cnpj"]

    # TOMADOR vem do snapshot congelado no rascunho, não do catálogo ao vivo.
    assert nota["tomador"]["razao_social"] == "TOMADOR DE TESTE LTDA"
    assert "11.222.333/0001-81" == nota["tomador"]["cnpj"]

    assert nota["servico"]["codigo_tributacao_nacional"] == "170601"
    assert "08/2026" in nota["servico"]["descricao"]

    assert nota["valores"]["valor_servico"] == 150.0


def test_nota_visual_reflete_estado_apos_assinar(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    client.post(f"/api/dps/{criada['id']}/assinar")

    resp = client.get(f"/api/dps/{criada['id']}/nota")
    assert resp.status_code == 200
    nota = resp.json()
    assert nota["estado"] == "assinado"
    assert nota["estado_label"].startswith("Assinada")


def test_nota_visual_emissao_inexistente_da_404(client, prestador_teste):
    resp = client.get(f"/api/dps/{uuid.uuid4()}/nota")
    assert resp.status_code == 404
