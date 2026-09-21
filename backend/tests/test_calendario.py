"""
Calendário de prazos e previsão de recebimento — Marco 13 (ver
app/services/calendario.py). Mesmo padrão real-Postgres-com-rollback das
demais suítes.
"""
import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.services.calendario import eventos_calendario
from app.services.motor_emissao import criar_rascunho, montar
from app.services.pagamentos import registrar_pagamento
from app.services.vinculos import atualizar_vinculo


def test_prazo_emissao_so_aparece_se_ainda_nao_emitiu(db, prestador_teste, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=25)

    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "prazo_emissao"
    assert eventos[0]["data"] == datetime.date(2026, 8, 25)
    assert eventos[0]["apelido"] == "Fornecedor Teste"

    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    eventos_depois = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert eventos_depois == []


def test_prazo_emissao_ajusta_dia_alto_pro_ultimo_dia_do_mes(db, prestador_teste, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=31)

    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 2, 1), datetime.date(2026, 2, 28))
    assert len(eventos) == 1
    assert eventos[0]["data"] == datetime.date(2026, 2, 28)  # fevereiro não tem dia 31


def test_recebimento_previsto_soma_dias_apos_emissao(db, prestador_teste, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, dias_para_recebimento=10)
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=200.0))
    data_esperada = emissao.criado_em.date() + datetime.timedelta(days=10)

    eventos = eventos_calendario(db, prestador_teste.id, data_esperada, data_esperada)
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "recebimento_previsto"
    assert eventos[0]["valor"] == 200.0


def test_recebimento_previsto_some_quando_pagamento_e_registrado(db, prestador_teste, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, dias_para_recebimento=10)
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=200.0))
    data_esperada = emissao.criado_em.date() + datetime.timedelta(days=10)

    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=200.0)

    eventos = eventos_calendario(db, prestador_teste.id, data_esperada, data_esperada)
    assert eventos == []


def test_recebimento_confirmado_aparece_com_data_de_recebimento(db, prestador_teste, vinculo_teste):
    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=150.0, data_recebimento=datetime.date(2026, 8, 12))

    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "recebimento_confirmado"
    assert eventos[0]["data"] == datetime.date(2026, 8, 12)
    assert eventos[0]["valor"] == 150.0


def test_eventos_fora_do_intervalo_sao_descartados(db, prestador_teste, vinculo_teste):
    """O evento de prazo cai no dia 25 — pedir um intervalo que não cobre
    esse dia (mesmo dentro do mesmo mês) não deve trazer nada."""
    atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=25)
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 24))
    assert eventos == []


def test_vinculo_sem_prazo_nem_previsao_nao_gera_evento(db, prestador_teste, vinculo_teste):
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
    assert eventos == []


# --- Camada HTTP ---


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


def test_endpoint_calendario(client, db, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=25)
    resp = client.get("/api/calendario", params={"inicio": "2026-08-01", "fim": "2026-08-31"})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["eventos"][0]["tipo"] == "prazo_emissao"
    assert dados["eventos"][0]["data"] == "2026-08-25"


def test_endpoint_calendario_datas_malformadas_da_422(client):
    resp = client.get("/api/calendario", params={"inicio": "01-08-2026", "fim": "2026-08-31"})
    assert resp.status_code == 422


def test_endpoint_calendario_fim_antes_de_inicio_da_422(client):
    resp = client.get("/api/calendario", params={"inicio": "2026-08-31", "fim": "2026-08-01"})
    assert resp.status_code == 422
