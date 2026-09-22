"""
Listagens por linha (Marco 14) — GET /api/dps, /api/pagamentos, /api/despesas
e /api/prestador. Mesmo padrão real-Postgres-com-rollback das demais suítes
(ver conftest.py e docstring de app/services/listagens.py).
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id


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


# --- GET /api/dps (lista) ---


def test_listar_dps_vazio_sem_nenhuma_emissao(client, prestador_teste):
    resp = client.get("/api/dps")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_dps_devolve_as_criadas_mais_recente_primeiro(client, vinculo_teste):
    e1 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    e2 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 200.0}).json()

    resp = client.get("/api/dps")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 2
    assert dados[0]["id"] == e2["id"]  # mais recente primeiro
    assert dados[1]["id"] == e1["id"]
    assert dados[0]["apelido"] == "Fornecedor Teste"
    assert dados[0]["tomador_razao_social"] == "TOMADOR DE TESTE LTDA"
    assert dados[0]["estado_label"] == "Emitida"
    assert dados[0]["vinculo_id"] == str(vinculo_teste.id)


def test_listar_dps_filtra_por_ano(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2025-12", "valor": 100.0})
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-01", "valor": 200.0})

    resp = client.get("/api/dps", params={"ano": "2026"})
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["competencia"] == "2026-01"


def test_listar_dps_filtra_por_vinculo_e_estado(client, vinculo_teste, db, prestador_teste):
    from app.models import PrestadorTomador, Tomador

    tomador2 = Tomador(
        id=uuid.uuid4(), cnpj="22333444000199", razao_social="OUTRO TOMADOR LTDA",
        cod_municipio="3550308",
    )
    db.add(tomador2)
    db.flush()
    vinculo2 = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador2.id,
        apelido="Outro Fornecedor", cod_local_prestacao=prestador_teste.cod_municipio,
        cod_trib_nacional="170601", template_descricao="Comissão - {competencia_mm_aaaa}",
        serie="1", ativo=True,
    )
    db.add(vinculo2)
    db.flush()

    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    client.post("/api/dps", json={"vinculo_id": str(vinculo2.id), "competencia": "2026-08", "valor": 300.0})

    resp = client.get("/api/dps", params={"vinculo_id": str(vinculo2.id)})
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["apelido"] == "Outro Fornecedor"

    resp2 = client.get("/api/dps", params={"estado": "montado"})
    assert len(resp2.json()) == 2  # ambas nasceram 'montado'
    resp3 = client.get("/api/dps", params={"estado": "assinado"})
    assert resp3.json() == []


def test_listar_dps_ano_malformado_da_422(client, prestador_teste):
    resp = client.get("/api/dps", params={"ano": "abcd"})
    assert resp.status_code == 422


# --- Marco 16 (item 3): confronto emitidas x pagas ---


def test_listar_dps_marca_pagamento_recebido_quando_ha_pagamento_pro_mesmo_vinculo_e_competencia(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})

    resp = client.get("/api/dps")
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["pagamento_recebido"] is True


def test_listar_dps_pagamento_recebido_false_sem_pagamento_correspondente(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    # pagamento de OUTRA competência não deve contar
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-07", "valor": 100.0})

    resp = client.get("/api/dps")
    dados = resp.json()
    assert dados[0]["pagamento_recebido"] is False


def test_listar_dps_filtra_pagamento_recebido(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 200.0})
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})

    recebidas = client.get("/api/dps", params={"pagamento": "recebido"}).json()
    assert len(recebidas) == 1
    assert recebidas[0]["competencia"] == "2026-08"

    pendentes = client.get("/api/dps", params={"pagamento": "pendente"}).json()
    assert len(pendentes) == 1
    assert pendentes[0]["competencia"] == "2026-09"


def test_listar_dps_pagamento_invalido_da_422(client, prestador_teste):
    resp = client.get("/api/dps", params={"pagamento": "quitada"})
    assert resp.status_code == 422


# --- GET /api/pagamentos (lista) ---


def test_listar_pagamentos_vazio(client, prestador_teste):
    resp = client.get("/api/pagamentos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_pagamentos_devolve_com_apelido_e_filtra_por_ano(client, vinculo_teste):
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2025-12", "valor": 50.0})
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 150.0})

    resp = client.get("/api/pagamentos", params={"ano": "2026"})
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["apelido"] == "Fornecedor Teste"
    assert dados[0]["valor"] == 150.0


def test_listar_pagamentos_ano_malformado_da_422(client, prestador_teste):
    resp = client.get("/api/pagamentos", params={"ano": "20"})
    assert resp.status_code == 422


# --- GET /api/despesas (lista) ---


def test_listar_despesas_vazio(client, prestador_teste):
    resp = client.get("/api/despesas")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_despesas_filtra_por_ano(client, prestador_teste):
    client.post("/api/despesas", json={"categoria": "Pro Labore", "competencia": "2025-12", "valor": 1000.0})
    client.post("/api/despesas", json={"categoria": "INSS", "competencia": "2026-08", "valor": 300.0})

    resp = client.get("/api/despesas", params={"ano": "2026"})
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["categoria"] == "INSS"


# --- GET /api/prestador ---


def test_ver_prestador(client, prestador_teste):
    resp = client.get("/api/prestador")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["razao_social"] == prestador_teste.razao_social
    assert dados["cpf_cnpj"] == prestador_teste.cpf_cnpj
    assert dados["cod_municipio"] == prestador_teste.cod_municipio
    assert dados["aliquota_atual"] is None
    assert dados["aliquota_atualizada_em"] is None


# --- PATCH /api/prestador/aliquota (Marco 16, item 5) ---


def test_atualizar_aliquota(client, prestador_teste):
    import datetime

    resp = client.patch("/api/prestador/aliquota", json={"aliquota": 6.5})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["aliquota_atual"] == 6.5
    assert dados["aliquota_atualizada_em"] == datetime.date.today().isoformat()


def test_atualizar_aliquota_fora_do_intervalo_da_422(client, prestador_teste):
    resp = client.patch("/api/prestador/aliquota", json={"aliquota": 150})
    assert resp.status_code == 422

    resp = client.patch("/api/prestador/aliquota", json={"aliquota": -1})
    assert resp.status_code == 422
