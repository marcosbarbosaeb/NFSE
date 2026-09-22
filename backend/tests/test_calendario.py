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
from app.services.calendario import (
    atualizar_evento_manual,
    buscar_evento_manual,
    criar_evento_manual,
    eventos_calendario,
    excluir_evento_manual,
)
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


# --- Lembrete de alíquota (Marco 16, item 5) ---


def test_revisar_aliquota_aparece_quando_nao_confirmada_no_mes(db, prestador_teste):
    hoje = datetime.date.today()
    eventos = eventos_calendario(db, prestador_teste.id, hoje.replace(day=1), hoje)
    revisar = [e for e in eventos if e["tipo"] == "revisar_aliquota"]
    assert len(revisar) == 1
    assert revisar[0]["data"] == hoje.replace(day=1)


def test_revisar_aliquota_some_apos_confirmar_no_mes(db, prestador_teste):
    hoje = datetime.date.today()
    prestador_teste.aliquota_atual = 6.0
    prestador_teste.aliquota_atualizada_em = hoje
    db.flush()

    eventos = eventos_calendario(db, prestador_teste.id, hoje.replace(day=1), hoje)
    assert [e for e in eventos if e["tipo"] == "revisar_aliquota"] == []


def test_revisar_aliquota_nao_aparece_fora_do_mes_corrente(db, prestador_teste):
    """Ligado ao calendário real, não à competência navegada — consultar
    agosto/2024 não deve trazer um lembrete de 'revisar agora'."""
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2024, 8, 1), datetime.date(2024, 8, 31))
    assert [e for e in eventos if e["tipo"] == "revisar_aliquota"] == []


def test_eventos_fora_do_intervalo_sao_descartados(db, prestador_teste, vinculo_teste):
    """O evento de prazo cai no dia 25 — pedir um intervalo que não cobre
    esse dia (mesmo dentro do mesmo mês) não deve trazer nada."""
    atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=25)
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 24))
    assert eventos == []


def test_vinculo_sem_prazo_nem_previsao_nao_gera_evento(db, prestador_teste, vinculo_teste):
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
    # o intervalo cobre o ano inteiro, então inclui o dia 1 do mês corrente
    # (ver 'revisar_aliquota' em app/services/calendario.py — não é o que
    # este teste quer verificar, então filtra fora daqui).
    eventos = [e for e in eventos if e["tipo"] != "revisar_aliquota"]
    assert eventos == []


# --- Eventos manuais (Marco 15 — 'gerenciar eventos' na tela de Calendário) ---


def test_criar_evento_manual_aparece_no_calendario(db, prestador_teste):
    evento = criar_evento_manual(db, prestador_teste.id, data=datetime.date(2026, 8, 15), titulo="Reunião com contador")

    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "manual"
    assert eventos[0]["titulo"] == "Reunião com contador"
    assert eventos[0]["id"] == evento.id
    assert eventos[0]["descricao"] is None


def test_evento_manual_com_descricao(db, prestador_teste):
    criar_evento_manual(
        db, prestador_teste.id, data=datetime.date(2026, 8, 15), titulo="Renovar certificado",
        descricao="Vence dia 20, não esquecer.",
    )
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert eventos[0]["descricao"] == "Vence dia 20, não esquecer."


def test_evento_manual_fora_do_intervalo_nao_aparece(db, prestador_teste):
    criar_evento_manual(db, prestador_teste.id, data=datetime.date(2026, 9, 1), titulo="Mês que vem")
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert eventos == []


def test_atualizar_evento_manual_muda_so_os_campos_passados(db, prestador_teste):
    evento = criar_evento_manual(db, prestador_teste.id, data=datetime.date(2026, 8, 15), titulo="Original")
    atualizar_evento_manual(db, evento, titulo="Renomeado")
    assert evento.titulo == "Renomeado"
    assert evento.data == datetime.date(2026, 8, 15)  # não mudou


def test_excluir_evento_manual_some_do_calendario(db, prestador_teste):
    evento = criar_evento_manual(db, prestador_teste.id, data=datetime.date(2026, 8, 15), titulo="Cancelado depois")
    excluir_evento_manual(db, evento)
    eventos = eventos_calendario(db, prestador_teste.id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert eventos == []


def test_buscar_evento_manual_de_outro_prestador_nao_acha_via_rls(db, prestador_teste):
    """RLS isola por prestador_id: um evento manual só é visível pela sessão
    do prestador dono, mesmo sabendo o id exato — mesma garantia testada
    pras outras tabelas de negócio (ver test_dois_usuarios... em test_auth.py)."""
    import uuid as uuid_mod

    from app.database import definir_prestador_atual
    from app.models import Prestador as PrestadorModel

    outro_id = uuid_mod.uuid4()
    definir_prestador_atual(db, outro_id)
    outro_prestador = PrestadorModel(
        id=outro_id, cpf_cnpj="33333333000188", razao_social="OUTRO PRESTADOR CALENDARIO", cod_municipio="3106200",
    )
    db.add(outro_prestador)
    db.flush()
    evento_do_outro = criar_evento_manual(db, outro_id, data=datetime.date(2026, 8, 15), titulo="Não é seu")

    definir_prestador_atual(db, prestador_teste.id)
    assert buscar_evento_manual(db, evento_do_outro.id) is None


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


# --- POST/PATCH/DELETE /api/calendario/eventos (Marco 15) ---


def test_endpoint_criar_evento_manual(client):
    resp = client.post("/api/calendario/eventos", json={"data": "2026-08-15", "titulo": "Reunião com contador"})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["tipo"] == "manual"
    assert dados["titulo"] == "Reunião com contador"
    assert dados["id"] is not None

    listagem = client.get("/api/calendario", params={"inicio": "2026-08-01", "fim": "2026-08-31"})
    assert len(listagem.json()["eventos"]) == 1


def test_endpoint_criar_evento_manual_titulo_vazio_da_422(client):
    resp = client.post("/api/calendario/eventos", json={"data": "2026-08-15", "titulo": ""})
    assert resp.status_code == 422


def test_endpoint_atualizar_evento_manual(client):
    criado = client.post("/api/calendario/eventos", json={"data": "2026-08-15", "titulo": "Original"}).json()
    resp = client.patch(f"/api/calendario/eventos/{criado['id']}", json={"titulo": "Renomeado"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["titulo"] == "Renomeado"
    assert resp.json()["data"] == "2026-08-15"  # não mudou


def test_endpoint_atualizar_evento_manual_inexistente_da_404(client):
    import uuid as uuid_mod

    resp = client.patch(f"/api/calendario/eventos/{uuid_mod.uuid4()}", json={"titulo": "X"})
    assert resp.status_code == 404


def test_endpoint_excluir_evento_manual(client):
    criado = client.post("/api/calendario/eventos", json={"data": "2026-08-15", "titulo": "Vai sumir"}).json()
    resp = client.delete(f"/api/calendario/eventos/{criado['id']}")
    assert resp.status_code == 200, resp.text

    listagem = client.get("/api/calendario", params={"inicio": "2026-08-01", "fim": "2026-08-31"})
    assert listagem.json()["eventos"] == []


def test_endpoint_excluir_evento_manual_inexistente_da_404(client):
    import uuid as uuid_mod

    resp = client.delete(f"/api/calendario/eventos/{uuid_mod.uuid4()}")
    assert resp.status_code == 404
