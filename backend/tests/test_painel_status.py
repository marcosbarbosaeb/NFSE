"""
Painel de status completo (Marco 8) — testes de serviço
(app/services/painel_status.py, pagamentos.py, despesas.py) e da camada
HTTP por cima, mesmo padrão real-Postgres-com-rollback das demais suítes.
"""
import uuid

import pytest

from app.services.despesas import registrar_despesa
from app.services.motor_emissao import criar_rascunho, montar
from app.services.pagamentos import registrar_pagamento
from app.services.painel_status import (
    painel_status_completo,
    status_despesas,
    status_notas_geradas,
    status_pagamentos_recebidos,
)


def test_notas_geradas_agrupa_por_vinculo_e_mes(db, vinculo_teste):
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=250.5))

    linhas = status_notas_geradas(db, "2026")
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["rotulo"] == "Fornecedor Teste"
    assert linha["meses"][7] == 100.0  # agosto = índice 7 (jan=0)
    assert linha["meses"][8] == 250.5
    assert linha["meses"][0] == 0.0  # janeiro sem lançamento
    assert linha["total"] == pytest.approx(350.5)


def test_notas_geradas_ignora_emissao_cancelada(db, vinculo_teste):
    e1 = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    e1.estado = "cancelada"
    db.flush()

    linhas = status_notas_geradas(db, "2026")
    assert linhas[0]["total"] == 0.0


def test_notas_geradas_filtra_por_ano_nao_mistura_anos_diferentes(db, vinculo_teste):
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2025-12", valor=999.0))
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-01", valor=50.0))

    linhas_2026 = status_notas_geradas(db, "2026")
    assert linhas_2026[0]["total"] == 50.0

    linhas_2025 = status_notas_geradas(db, "2025")
    assert linhas_2025[0]["total"] == 999.0


def test_pagamentos_recebidos_agrupa_por_vinculo_e_mes(db, vinculo_teste):
    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=80.0)
    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=20.0)  # dois recebimentos no mesmo mês somam

    linhas = status_pagamentos_recebidos(db, "2026")
    assert linhas[0]["meses"][7] == 100.0
    assert linhas[0]["total"] == 100.0


def test_despesas_agrupa_por_categoria_nao_por_fornecedor(db, prestador_teste):
    registrar_despesa(db, prestador_teste.id, categoria="Pro Labore", competencia="2026-08", valor=1000.0)
    registrar_despesa(db, prestador_teste.id, categoria="Contabilidade", competencia="2026-08", valor=300.0)
    registrar_despesa(db, prestador_teste.id, categoria="Pro Labore", competencia="2026-09", valor=1000.0)

    linhas = status_despesas(db, prestador_teste.id, "2026")
    rotulos = {l["rotulo"] for l in linhas}
    assert rotulos == {"Pro Labore", "Contabilidade"}
    pro_labore = next(l for l in linhas if l["rotulo"] == "Pro Labore")
    assert pro_labore["meses"][7] == 1000.0
    assert pro_labore["meses"][8] == 1000.0
    assert pro_labore["total"] == 2000.0


def test_painel_status_completo_junta_as_tres_secoes(db, vinculo_teste, prestador_teste):
    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=90.0)
    registrar_despesa(db, prestador_teste.id, categoria="INSS", competencia="2026-08", valor=50.0)

    painel = painel_status_completo(db, prestador_teste.id, "2026")
    assert painel["ano"] == "2026"
    assert painel["notas_geradas"][0]["total"] == 100.0
    assert painel["pagamentos_recebidos"][0]["total"] == 90.0
    assert painel["despesas"][0]["total"] == 50.0


def test_vinculo_sem_nenhum_lancamento_aparece_com_zeros(db, vinculo_teste):
    """Um fornecedor ativo mas sem nenhuma nota/pagamento no ano ainda
    aparece na tabela (com zeros) — igual a uma linha vazia na planilha,
    não some da lista."""
    linhas = status_notas_geradas(db, "2026")
    assert len(linhas) == 1
    assert linhas[0]["total"] == 0.0
    assert linhas[0]["meses"] == [0.0] * 12


# --- Camada HTTP ---


@pytest.fixture
def client(db, prestador_teste):
    from app.database import get_db
    from app.main import app, prestador_atual_id

    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    from fastapi.testclient import TestClient
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_endpoint_registrar_pagamento(client, vinculo_teste):
    resp = client.post("/api/pagamentos", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 123.45,
    })
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["apelido"] == "Fornecedor Teste"
    assert dados["valor"] == 123.45
    assert dados["data_recebimento"] is None


def test_endpoint_registrar_pagamento_com_data(client, vinculo_teste):
    resp = client.post("/api/pagamentos", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 50.0, "data_recebimento": "2026-08-15",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["data_recebimento"] == "2026-08-15"


def test_endpoint_registrar_pagamento_vinculo_inexistente_da_404(client, prestador_teste):
    resp = client.post("/api/pagamentos", json={
        "vinculo_id": str(uuid.uuid4()), "competencia": "2026-08", "valor": 100.0,
    })
    assert resp.status_code == 404


def test_endpoint_registrar_despesa(client, prestador_teste):
    resp = client.post("/api/despesas", json={"categoria": "Telefones", "competencia": "2026-08", "valor": 89.9})
    assert resp.status_code == 200, resp.text
    assert resp.json()["categoria"] == "Telefones"


def test_endpoint_status_junta_tudo(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 90.0})
    client.post("/api/despesas", json={"categoria": "INSS", "competencia": "2026-08", "valor": 50.0})

    resp = client.get("/api/painel/status", params={"ano": "2026"})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["notas_geradas"][0]["total"] == 100.0
    assert dados["pagamentos_recebidos"][0]["total"] == 90.0
    assert dados["despesas"][0]["total"] == 50.0


def test_endpoint_status_ano_malformado_da_422(client, vinculo_teste):
    resp = client.get("/api/painel/status", params={"ano": "abcd"})
    assert resp.status_code == 422


def test_endpoint_status_sem_parametro_ano_da_422(client, vinculo_teste):
    resp = client.get("/api/painel/status")
    assert resp.status_code == 422


# --- Marco 12: /api/painel/resumo-mes (ver app/services/dashboard.py) ---


def test_resumo_mes_separa_emitidas_de_aguardando(db, prestador_teste, vinculo_teste):
    """Um vínculo ativo sem emissão na competência conta como 'aguardando';
    com emissão ativa (não cancelada), conta como 'emitida'."""
    from app.services.dashboard import resumo_mes

    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["total_vinculos"] == 1
    assert resumo["aguardando"] == 1
    assert resumo["emitidas"] == 0
    assert resumo["emissoes"] == []

    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=150.0))
    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["emitidas"] == 1
    assert resumo["aguardando"] == 0
    assert resumo["emissoes"][0]["apelido"] == "Fornecedor Teste"
    assert resumo["emissoes"][0]["valor"] == 150.0
    assert resumo["emissoes"][0]["envio_status"] is None


def test_resumo_mes_emissao_cancelada_conta_como_aguardando(db, prestador_teste, vinculo_teste):
    from app.services.dashboard import resumo_mes

    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=150.0))
    emissao.estado = "cancelada"
    db.flush()

    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["aguardando"] == 1
    assert resumo["emitidas"] == 0


def test_resumo_mes_a_receber_soma_so_emissoes_sem_pagamento(db, prestador_teste, vinculo_teste):
    from app.services.dashboard import resumo_mes

    montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=150.0))
    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["a_receber"] == 150.0
    assert resumo["pagamentos_pendentes"] == 1
    assert resumo["emissoes"][0]["pagamento_recebido"] is False

    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=150.0)
    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["a_receber"] == 0.0
    assert resumo["pagamentos_pendentes"] == 0
    assert resumo["emissoes"][0]["pagamento_recebido"] is True


def test_resumo_mes_recebido_no_mes_e_delta_vs_anterior(db, prestador_teste, vinculo_teste):
    from app.services.dashboard import resumo_mes

    registrar_pagamento(db, vinculo_teste, competencia="2026-07", valor=100.0)
    registrar_pagamento(db, vinculo_teste, competencia="2026-08", valor=150.0)

    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["recebido_no_mes"] == 150.0
    assert resumo["recebido_mes_anterior"] == 100.0
    assert resumo["delta_recebimentos_pct"] == pytest.approx(50.0)
    assert len(resumo["serie_recebimentos"]) == 6
    assert resumo["serie_recebimentos"][-1] == {"competencia": "2026-08", "valor": 150.0}
    assert resumo["serie_recebimentos"][-2] == {"competencia": "2026-07", "valor": 100.0}


def test_resumo_mes_sem_competencia_usa_mes_corrente(db, prestador_teste):
    import datetime

    from app.services.dashboard import resumo_mes

    resumo = resumo_mes(db, prestador_teste.id)
    hoje = datetime.date.today()
    assert resumo["competencia"] == f"{hoje.year:04d}-{hoje.month:02d}"


def test_resumo_mes_alerta_certificado_vencendo(db, prestador_teste):
    """A validade do alerta só depende do campo `Certificado.validade` —
    monta a linha direto (sem passar por salvar_certificado, que extrairia
    a validade de um .pfx de verdade) pra testar só a janela de alerta de
    app/services/dashboard.py (<=30 dias), sem depender de gerar um
    certificado com vencimento próximo."""
    import datetime
    import uuid

    from app.models import Certificado
    from app.services.dashboard import resumo_mes

    db.add(Certificado(
        id=uuid.uuid4(), prestador_id=prestador_teste.id,
        pfx_criptografado=b"x", senha_criptografada=b"y",
        validade=datetime.date.today() + datetime.timedelta(days=5),
    ))
    db.flush()

    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert len(resumo["atencao"]) == 1
    assert resumo["atencao"][0]["tipo"] == "certificado_vencendo"
    assert "Certificado" in resumo["atencao"][0]["titulo"]


def test_resumo_mes_sem_alerta_quando_certificado_longe_do_vencimento(db, prestador_teste, certificado_teste):
    from app.services.certificados import salvar_certificado
    from app.services.dashboard import resumo_mes
    from app.config import get_settings

    salvar_certificado(db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], get_settings().cert_master_key)
    resumo = resumo_mes(db, prestador_teste.id, competencia="2026-08")
    assert resumo["atencao"] == []


def test_endpoint_resumo_mes(client, vinculo_teste):
    client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    resp = client.get("/api/painel/resumo-mes", params={"competencia": "2026-08"})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["competencia"] == "2026-08"
    assert dados["emitidas"] == 1
    assert dados["emissoes"][0]["valor"] == 100.0


def test_endpoint_resumo_mes_competencia_malformada_da_422(client, vinculo_teste):
    resp = client.get("/api/painel/resumo-mes", params={"competencia": "202608"})
    assert resp.status_code == 422
