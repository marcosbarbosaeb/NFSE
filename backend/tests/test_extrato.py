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

from app.financeiro.extrato_pdf import PdfInvalidoError, extrair_transacoes
from app.financeiro.importacao_extrato import ItemExtrato, confirmar_importacao_extrato


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

    from app.financeiro.listas import listar_pagamentos

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


# --- Revisão de 28/09/2026: leiautes reais de bancos + OFX/CSV ---------------

from app.financeiro.extrato_pdf import extrair_de_texto, extrair_extrato  # noqa: E402


def _resumo(transacoes):
    return [(t.data, t.valor, t.credito) for t in transacoes]


def test_nubank_data_no_cabecalho_e_totais_ignorados():
    linhas = [
        "Extrato de 01 SET 2026 a 30 SET 2026",
        "01 SET 2026 Total de entradas + 1.500,00",
        "Transferência recebida pelo Pix 1.000,00",
        "AWIN LTDA - 12.345.678/0001-90",
        "Transferência enviada pelo Pix 200,00",
        "02 SET 2026 Total de saídas - 50,00",
        "Compra no débito Mercado 50,00",
    ]
    assert _resumo(extrair_de_texto(linhas)) == [
        (date(2026, 9, 1), Decimal("1000.00"), True),
        (date(2026, 9, 1), Decimal("200.00"), False),
        (date(2026, 9, 2), Decimal("50.00"), False),
    ]


def test_inter_data_por_extenso_valor_com_rs_e_saldo_na_mesma_linha():
    linhas = [
        "1 de Setembro de 2026 Saldo do dia: R$ 2.000,00",
        'Pix recebido: "Cp :60746948-AWIN" R$ 800,00 R$ 2.800,00',
        'Pix enviado: "Fulano" -R$ 100,00 R$ 2.700,00',
    ]
    assert _resumo(extrair_de_texto(linhas)) == [
        (date(2026, 9, 1), Decimal("800.00"), True),
        (date(2026, 9, 1), Decimal("100.00"), False),
    ]


def test_itau_data_sem_ano_e_menos_no_fim():
    linhas = ["Extrato conta corrente - 2026", "01/09 PIX TRANSF AWIN LTDA 1.234,56", "02/09 SISPAG FORNECEDORES 300,00-", "03/09 SALDO DO DIA 5.000,00"]
    assert _resumo(extrair_de_texto(linhas)) == [
        (date(2026, 9, 1), Decimal("1234.56"), True),
        (date(2026, 9, 2), Decimal("300.00"), False),
    ]


def test_mercado_pago_data_com_traco():
    linhas = [
        "01-09-2026 Transferência Pix recebida Lomadee R$ 500,00 R$ 1.500,00",
        "02-09-2026 Pagamento com QR Pix Padaria R$ -30,00 R$ 1.470,00",
    ]
    assert _resumo(extrair_de_texto(linhas)) == [
        (date(2026, 9, 1), Decimal("500.00"), True),
        (date(2026, 9, 2), Decimal("30.00"), False),
    ]


def test_ofx():
    ofx = b"""OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260905120000[-3:BRT]<TRNAMT>950.00<FITID>1<MEMO>PIX RECEBIDO AWIN
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260906<TRNAMT>-120.00<FITID>2<MEMO>BOLETO CEMIG
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    resultado = extrair_extrato(ofx, "extrato.ofx")
    assert resultado.formato == "ofx"
    assert _resumo(resultado.transacoes) == [
        (date(2026, 9, 5), Decimal("950.00"), True),
        (date(2026, 9, 6), Decimal("120.00"), False),
    ]
    assert resultado.transacoes[0].descricao == "PIX RECEBIDO AWIN"


def test_csv_com_cabecalho():
    conteudo = "Data;Descrição;Valor\n05/09/2026;Pix recebido AWIN;950,00\n06/09/2026;Boleto;-120,00\n".encode("cp1252")
    resultado = extrair_extrato(conteudo, "extrato.csv")
    assert resultado.formato == "csv"
    assert _resumo(resultado.transacoes) == [
        (date(2026, 9, 5), Decimal("950.00"), True),
        (date(2026, 9, 6), Decimal("120.00"), False),
    ]


def test_formato_desconhecido_da_erro_claro():
    with pytest.raises(PdfInvalidoError):
        extrair_extrato(b"\x89PNG\r\n\x1a\n\x00\x00", "foto.png")
