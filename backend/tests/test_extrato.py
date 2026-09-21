"""Marco 15 (item 5): extrato bancário em PDF (ver
app/services/extrato_pdf.py e app/services/importacao_extrato.py).

O PDF de teste é gerado na hora via reportlab (nenhum extrato real da
Raiana é usado ou versionado) — simula um layout comum o bastante (data +
descrição + valor por linha) pro parser heurístico reconhecer.
"""
import io
from datetime import date
from decimal import Decimal

import pytest
from reportlab.pdfgen import canvas

from app.services.extrato_pdf import PdfInvalidoError, extrair_transacoes
from app.services.importacao_extrato import ItemExtrato, confirmar_importacao_extrato


def _gerar_pdf(linhas: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for linha in linhas:
        c.drawString(50, y, linha)
        y -= 20
    c.save()
    return buffer.getvalue()


LINHAS_EXTRATO = [
    "Extrato de conta corrente - Setembro/2026",
    "Data       Descrição                          Valor",
    "05/09/2026 PIX RECEBIDO JOAO SILVA              1.234,56",
    "06/09/2026 TARIFA MANUTENCAO CONTA                 -25,00",
    "07/09/2026 TED RECEBIDA EMPRESA XYZ LTDA           500,00 C",
    "08/09/2026 COMPRA CARTAO DEBITO MERCADO             89,90 D",
    "Saldo final: 1.619,66",
]


def test_extrair_transacoes_reconhece_creditos_e_debitos():
    pdf_bytes = _gerar_pdf(LINHAS_EXTRATO)
    transacoes = extrair_transacoes(pdf_bytes)

    creditos = [t for t in transacoes if t.credito]
    debitos = [t for t in transacoes if not t.credito]

    assert len(creditos) == 2
    assert len(debitos) == 2  # a "tarifa" (sinal de menos) e a "compra" (marcador D)

    pix = next(t for t in transacoes if "PIX" in t.descricao)
    assert pix.data == date(2026, 9, 5)
    assert pix.valor == Decimal("1234.56")
    assert pix.credito is True

    ted = next(t for t in transacoes if "TED" in t.descricao)
    assert ted.valor == Decimal("500.00")
    assert ted.credito is True

    tarifa = next(t for t in transacoes if "TARIFA" in t.descricao)
    assert tarifa.credito is False
    assert tarifa.valor == Decimal("25.00")  # valor absoluto, sinal só decide credito/debito


def test_extrair_transacoes_ignora_linhas_sem_data_ou_valor():
    pdf_bytes = _gerar_pdf(LINHAS_EXTRATO)
    transacoes = extrair_transacoes(pdf_bytes)
    # cabeçalho, título e linha de saldo (sem par data+valor reconhecível) somem
    assert len(transacoes) == 4


def test_extrair_transacoes_pdf_vazio_nao_quebra():
    pdf_bytes = _gerar_pdf(["Nenhuma transação aqui, só texto solto."])
    assert extrair_transacoes(pdf_bytes) == []


def test_extrair_transacoes_arquivo_invalido_da_erro():
    with pytest.raises(PdfInvalidoError):
        extrair_transacoes(b"isto nao e um pdf de verdade")


# --- confirmação (grava PagamentoRecebido de verdade) ---


def test_confirmar_importacao_extrato_sucesso(db, vinculo_teste):
    itens = [ItemExtrato(vinculo_id=vinculo_teste.id, competencia="2026-09", valor=1234.56, data_recebimento=date(2026, 9, 5))]
    resultados = confirmar_importacao_extrato(db, itens)
    assert len(resultados) == 1
    assert resultados[0].ok is True
    assert resultados[0].pagamento_id is not None


def test_confirmar_importacao_extrato_vinculo_invalido_nao_derruba_os_outros(db, vinculo_teste):
    import uuid

    itens = [
        ItemExtrato(vinculo_id=uuid.uuid4(), competencia="2026-09", valor=100.0),
        ItemExtrato(vinculo_id=vinculo_teste.id, competencia="2026-09", valor=200.0),
    ]
    resultados = confirmar_importacao_extrato(db, itens)
    assert resultados[0].ok is False
    assert resultados[1].ok is True


# --- nível HTTP ---


@pytest.fixture
def client(db, prestador_teste):
    from app.database import get_db
    from app.main import app, prestador_atual_id
    from fastapi.testclient import TestClient

    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_endpoint_extrair_extrato(client):
    pdf_bytes = _gerar_pdf(LINHAS_EXTRATO)
    resp = client.post("/api/recebimentos/extrato", files={"arquivo": ("extrato.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["total_transacoes"] == 4
    assert any(t["credito"] for t in corpo["transacoes"])


def test_endpoint_extrair_extrato_arquivo_invalido_da_400(client):
    resp = client.post("/api/recebimentos/extrato", files={"arquivo": ("extrato.pdf", b"lixo", "application/pdf")})
    assert resp.status_code == 400


def test_endpoint_confirmar_extrato(client, db, vinculo_teste):
    resp = client.post(
        "/api/recebimentos/extrato/confirmar",
        json={"itens": [{"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 500.0}]},
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["sucesso"] == 1
    assert corpo["erro"] == 0

    from app.services.listagens import listar_pagamentos

    pagamentos = listar_pagamentos(db, ano="2026")
    assert len(pagamentos) == 1
    assert pagamentos[0]["valor"] == 500.0


def test_endpoint_confirmar_extrato_item_invalido_da_erro_parcial(client):
    import uuid

    resp = client.post(
        "/api/recebimentos/extrato/confirmar",
        json={"itens": [{"vinculo_id": str(uuid.uuid4()), "competencia": "2026-09", "valor": 100.0}]},
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["sucesso"] == 0
    assert corpo["erro"] == 1
    assert corpo["itens"][0]["ok"] is False
