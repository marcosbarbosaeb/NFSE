"""Pedidos do Marcos de 28/09/2026: ordem de pagamento da Awin em PDF, e-mail
da nota configurável, notas a receber (todos os meses), próximos passos da
Visão geral, formulário de suporte, ambiente das notas na conta e programa de
indicação. Nenhum PDF real é versionado: os PDFs aqui são gerados na hora,
com dados fictícios."""
import datetime
import io
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import Assinatura, CodigoIndicacao, Indicacao, PagamentoRecebido, Prestador
from app.services import mensagens
from app.services.a_receber import avisos_abertas_ha_muito, notas_em_aberto, totais
from app.services.dashboard import proximos
from app.services.envio_direto import modelo_email, previa_email
from app.services.indicacao import (
    atualizar_status_indicado,
    codigo_do_prestador,
    desconto_para,
    registrar_indicacao,
    resumo,
)
from app.services.motor_emissao import criar_rascunho, montar
from app.services.ordem_awin import OrdemAwinInvalidaError, ler_ordem_awin, parse_valor


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


# --- Ordem de pagamento da Awin ---------------------------------------------


def _pdf_formulario(campos: dict[str, str]) -> bytes:
    """PDF com campos de formulário, como o da Awin (valores nos campos, não
    no texto da página)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 800, "ORDEM DE PAGAMENTO – Número:")
    c.drawString(50, 780, "Total Bruto")
    c.drawString(50, 760, "CNPJ: 14.182.871/0001-88")
    y = 700
    for nome, valor in campos.items():
        c.acroForm.textfield(name=nome, value=valor, x=300, y=y, width=200, height=16)
        y -= 20
    c.save()
    return buf.getvalue()


def _pdf_texto(linhas: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for linha in linhas:
        c.drawString(50, y, linha)
        y -= 18
    c.save()
    return buf.getvalue()


def test_ordem_awin_pelos_campos_do_formulario():
    pdf = _pdf_formulario({
        "paymentOrderId": "12345678", "totalAmount": "1234.56", "paymentOrderDate": "15/09/2026",
        "currency": "BRL", "taxDetailsTaxNumber": "11.222.333/0001-81",
    })
    ordem = ler_ordem_awin(pdf, "ordem.pdf", hoje=datetime.date(2026, 9, 28))
    assert ordem.numero == "12345678"
    assert ordem.valor == Decimal("1234.56")
    assert ordem.data == datetime.date(2026, 9, 15)
    assert ordem.moeda == "BRL"
    assert ordem.cnpj_beneficiario == "11222333000181"
    assert ordem.cnpj_devedor == "14182871000188"
    assert ordem.competencia_sugerida == "2026-09"  # mês de emissão da nota (hoje)


def test_ordem_awin_pelo_texto_e_numero_pelo_nome_do_arquivo():
    pdf = _pdf_texto([
        "Awin Veiculação de Publicidade na Internet Ltda.",
        "Data: 15/09/2026",
        "ORDEM DE PAGAMENTO – Número: 87654321",
        "Total Bruto BRL 35.951,41",
    ])
    ordem = ler_ordem_awin(pdf, "2026-07-31_87654321-20260731-1-BRL-201.pdf", hoje=datetime.date(2026, 10, 2))
    assert ordem.numero == "87654321"
    assert ordem.valor == Decimal("35951.41")
    assert ordem.competencia_sugerida == "2026-10"
    sem_numero = ler_ordem_awin(_pdf_texto(["Awin Ltda", "Total Bruto BRL 10,00"]), "2026-07-31_11112222-x.pdf")
    assert sem_numero.numero == "11112222"


def test_ordem_awin_recusa_pdf_que_nao_e_da_awin():
    with pytest.raises(OrdemAwinInvalidaError):
        ler_ordem_awin(_pdf_texto(["Extrato bancário", "Saldo 10,00"]), "extrato.pdf")
    with pytest.raises(OrdemAwinInvalidaError):
        ler_ordem_awin(b"nao e pdf", "x.pdf")


def test_parse_valor_formatos():
    assert parse_valor("35951.41") == Decimal("35951.41")
    assert parse_valor("35.951,41") == Decimal("35951.41")
    assert parse_valor("35,951.41") == Decimal("35951.41")
    assert parse_valor("R$ 1.234") == Decimal("1234.00")
    assert parse_valor("0") is None


def test_endpoint_ordem_awin_avisa_cnpj_diferente_e_ordem_ja_usada(client, db, vinculo_teste):
    pdf = _pdf_formulario({"paymentOrderId": "555", "totalAmount": "10.00", "paymentOrderDate": "01/09/2026", "taxDetailsTaxNumber": "99999999000191"})
    resp = client.post("/api/awin/ordem", files={"arquivo": ("o.pdf", pdf, "application/pdf")})
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["numero"] == "555" and corpo["valor"] == 10.0
    assert any("outro CNPJ" in a for a in corpo["avisos"])
    assert corpo["ja_usada"] is None

    vinculo_teste.template_descricao = "Ordem {ordem}"
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=10, ordem="555")
    resp = client.post("/api/awin/ordem", files={"arquivo": ("o.pdf", pdf, "application/pdf")})
    assert resp.json()["ja_usada"]["emissao_id"] == str(emissao.id)


# --- E-mail da nota configurável -------------------------------------------


def test_modelo_do_tomador_ganha_do_padrao(db, prestador_teste, vinculo_teste):
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=1234.5, ordem=None)
    montar(db, emissao)
    padrao = modelo_email(db, emissao, "https://x")
    assert padrao["assunto"] == mensagens.email_assunto(mensagens.DadosMensagem(
        prestador_nome=prestador_teste.razao_social, fornecedor_apelido="", descricao="", competencia="2026-09",
        valor=0, n_dps=0, chave_acesso=None, link="",
    ))
    assert padrao["anexos"] == "pdf_xml"

    prestador_teste.email_assunto_padrao = "NF {competencia} - {prestador}"
    assert modelo_email(db, emissao, "https://x")["assunto"] == f"NF 09/2026 - {prestador_teste.razao_social}"

    vinculo_teste.email_assunto = "Nota {tomador} {mes}/{ano} — {valor}"
    vinculo_teste.email_mensagem = "Oi!\n\nSegue a nota {numero_nota}.\n{link}"
    vinculo_teste.email_anexos = "xml"
    vinculo_teste.email_copia = "a@x.com; b@y.com, invalido"
    db.flush()
    modelo = modelo_email(db, emissao, "https://x")
    assert modelo["assunto"] == f"Nota {vinculo_teste.apelido} Setembro/2026 — R$ 1.234,50"
    assert modelo["texto"].startswith("Oi!") and str(emissao.n_dps) in modelo["texto"]
    assert modelo["copia"] == ["a@x.com", "b@y.com"]
    assert "<a href=" in modelo["html"]
    previa = previa_email(db, emissao, "https://x")
    assert previa["arquivos"] == [f"nfse_{emissao.n_dps}_2026-09.xml"]


def test_codigo_desconhecido_fica_como_esta():
    d = mensagens.DadosMensagem("P", "T", "d", "2026-01", 1, 1, None, "l")
    assert mensagens.renderizar_modelo("{nada} {tomador}", d) == "{nada} T"


def test_patch_vinculo_e_preferencias(client, vinculo_teste):
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"email_assunto": "  Assunto X  ", "email_anexos": "pdf"})
    assert resp.status_code == 200
    assert resp.json()["email_assunto"] == "Assunto X" and resp.json()["email_anexos"] == "pdf"
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"email_assunto": ""})
    assert resp.json()["email_assunto"] is None
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"email_anexos": "zip"}).status_code == 422

    resp = client.patch("/api/prestador/preferencias", json={"tp_amb_padrao": "2", "email_mensagem_padrao": "Olá {tomador}"})
    assert resp.status_code == 200
    assert resp.json()["tp_amb_padrao"] == "2" and resp.json()["email_mensagem_padrao"] == "Olá {tomador}"
    modelo = client.get("/api/email-modelo").json()
    assert any(c["codigo"] == "ordem" for c in modelo["codigos"])


def test_nota_nova_usa_o_ambiente_da_conta(client, db, prestador_teste, vinculo_teste):
    prestador_teste.tp_amb_padrao = "2"
    db.flush()
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-05", "valor": 10}).json()
    assert client.get(f"/api/dps/{criada['id']}/nota").json()["ambiente"] == "2"


# --- Notas a receber / Visão geral ---------------------------------------------


def test_notas_em_aberto_totais_e_alerta_de_dois_meses(db, prestador_teste, vinculo_teste):
    antiga = criar_rascunho(db, vinculo_teste, competencia="2026-05", valor=100)
    montar(db, antiga)
    paga = criar_rascunho(db, vinculo_teste, competencia="2026-06", valor=50)
    montar(db, paga)
    db.add(PagamentoRecebido(id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-06", valor=50, mes_inteiro=True))
    db.flush()

    hoje = datetime.date.today()
    abertas = notas_em_aberto(db, hoje)
    assert [g["competencia"] for g in abertas] == ["2026-05"]
    t = totais(db)
    assert t["a_receber_total"] == 100 and t["notas_a_receber"] == 1
    assert t["recebido_total"] == 50 and t["notas_recebidas"] == 1

    assert avisos_abertas_ha_muito(db, hoje) == []  # emitida hoje
    daqui_3_meses = hoje + datetime.timedelta(days=90)
    avisos = avisos_abertas_ha_muito(db, daqui_3_meses)
    assert len(avisos) == 1 and avisos[0]["tipo"] == "nota_aberta_antiga"


def test_proximos_traz_pendencias_mesmo_sem_eventos(db, prestador_teste, vinculo_teste):
    hoje = datetime.date.today()
    dados = proximos(db, prestador_teste.id, hoje)
    assert any(p["tipo"] == "gerar" for p in dados["pendencias"])
    emissao = criar_rascunho(db, vinculo_teste, competencia=f"{hoje.year:04d}-{hoje.month:02d}", valor=10)
    montar(db, emissao)
    dados = proximos(db, prestador_teste.id, hoje)
    tipos = [p["tipo"] for p in dados["pendencias"]]
    assert "assinar" in tipos and "gerar" not in tipos and "receber" in tipos


def test_endpoints_painel(client, vinculo_teste):
    assert client.get("/api/painel/proximos").status_code == 200
    assert client.get("/api/notas-a-receber").json() == []
    resumo_mes = client.get("/api/painel/resumo-mes").json()
    assert "a_receber_total" in resumo_mes and "notas_recebidas" in resumo_mes
    lista = client.get("/api/dps").json()
    assert lista == [] or "envio_status" in lista[0]


# --- Suporte -------------------------------------------------------------------


def test_suporte_formulario(client, monkeypatch):
    enviados = []

    class Falso:
        def enviar(self, **kw):
            enviados.append(kw)

    monkeypatch.setattr("app.main.get_email_sender", lambda: Falso())
    monkeypatch.setattr("app.main.get_settings", lambda: type("S", (), {"resend_api_key": "x", "email_suporte": "suporte@x.com", "suporte_whatsapp": "(92) 99999-0000"})())
    assert client.get("/api/suporte").json()["whatsapp"] == "92999990000"
    assert client.post("/api/suporte", json={"assunto": "Oi", "mensagem": "Preciso de ajuda"}).status_code == 400
    resp = client.post("/api/suporte", json={"assunto": "Oi", "mensagem": "Preciso de ajuda", "email": "fulano@ex.com"})
    assert resp.status_code == 200
    assert enviados[0]["destinatario"] == "suporte@x.com" and enviados[0]["responder_para"] == "fulano@ex.com"
    # robô preenche o campo escondido: nada é enviado
    client.post("/api/suporte", json={"assunto": "Oi", "mensagem": "spam spam", "email": "a@b.com", "site": "x"})
    assert len(enviados) == 1


# --- Indicação -----------------------------------------------------------------


def test_desconto_10_por_indicado_ate_100():
    assert [desconto_para(n) for n in (0, 1, 3, 10, 14)] == [0, 10, 30, 100, 100]


def _novo_prestador(db, nome):
    pid = uuid.uuid4()
    definir_prestador_atual(db, pid)
    db.add(Prestador(id=pid, cpf_cnpj=str(uuid.uuid4().int)[:14], razao_social=nome, cod_municipio="3106200"))
    db.flush()
    db.add(Assinatura(id=uuid.uuid4(), prestador_id=pid, status="trial"))
    db.flush()
    return pid


def test_fluxo_de_indicacao(db, prestador_teste):
    definir_prestador_atual(db, prestador_teste.id)
    codigo = codigo_do_prestador(db, prestador_teste.id)
    assert codigo_do_prestador(db, prestador_teste.id) == codigo

    indicados = []
    for i in range(3):
        pid = _novo_prestador(db, f"Fulana {i} Silva")
        assert registrar_indicacao(db, codigo.lower(), pid, f"Fulana {i} Silva") is True
        indicados.append(pid)
    # código inválido ou o próprio dono: ignorado
    assert registrar_indicacao(db, "NAOEXISTE", indicados[0], "x") is False

    for pid in indicados[:2]:
        definir_prestador_atual(db, pid)
        atualizar_status_indicado(db, pid, "ativa")

    definir_prestador_atual(db, prestador_teste.id)
    dados = resumo(db, prestador_teste.id)
    assert dados["ativos"] == 2 and dados["total"] == 3 and dados["desconto_pct"] == 20
    assert dados["indicados"][0]["nome"].startswith("Fulana")
    assert dados["link"].endswith(f"?ref={codigo}")

    # indicado cancelou: o desconto cai
    definir_prestador_atual(db, indicados[0])
    atualizar_status_indicado(db, indicados[0], "cancelada")
    definir_prestador_atual(db, prestador_teste.id)
    assert resumo(db, prestador_teste.id)["desconto_pct"] == 10
    # o indicador não enxerga dados de outros prestadores além da indicação
    assert db.query(Indicacao).count() == 3
    assert db.get(CodigoIndicacao, codigo).prestador_id == prestador_teste.id


def test_endpoints_de_previa_e_prestador(client, db, vinculo_teste):
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-04", valor=10)
    montar(db, emissao)
    resp = client.get(f"/api/dps/{emissao.id}/email-previa")
    assert resp.status_code == 200 and "assunto" in resp.json()
    assert "municipio_rotulo" in client.get("/api/prestador").json()


def test_destinatario_configuravel_copia_propria_e_troca_na_hora(client, db, prestador_teste, vinculo_teste, monkeypatch):
    enviados = []

    class Falso:
        def enviar(self, **kw):
            enviados.append(kw)

    monkeypatch.setattr("app.services.envio_direto.get_email_sender", lambda: Falso())
    monkeypatch.setattr("app.services.envio_direto.motivo_email_desabilitado",
                        lambda vinculo, destino=None: None if destino else "sem destino")
    vinculo_teste.email_contato = "contato@tomador.com"
    vinculo_teste.email_para = "fin@tomador.com; ap@tomador.com"
    vinculo_teste.email_copia = "gerente@tomador.com, fin@tomador.com"
    prestador_teste.email_copia_padrao = "eu@minhaempresa.com"
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-03", valor=10)
    montar(db, emissao)

    previa = client.get(f"/api/dps/{emissao.id}/email-previa").json()
    assert previa["destinos"] == ["fin@tomador.com", "ap@tomador.com"]
    assert previa["copia"] == ["gerente@tomador.com", "eu@minhaempresa.com"]  # sem repetir destinatário

    assert client.post(f"/api/dps/{emissao.id}/enviar-email").json()["status"] == "enviado"
    assert enviados[-1]["destinatario"] == ["fin@tomador.com", "ap@tomador.com"]
    assert enviados[-1]["copia"] == ["gerente@tomador.com", "eu@minhaempresa.com"]

    # só neste envio: outro destinatário, sem cópia
    r = client.post(f"/api/dps/{emissao.id}/enviar-email", json={"para": ["outro@x.com", "lixo"], "copia": []})
    assert r.json()["status"] == "enviado"
    assert enviados[-1]["destinatario"] == ["outro@x.com"] and enviados[-1]["copia"] is None

    # sem "Para" configurado, volta pro e-mail de contato
    vinculo_teste.email_para = None
    db.flush()
    assert client.get(f"/api/dps/{emissao.id}/email-previa").json()["destinos"] == ["contato@tomador.com"]


def test_teto_diario_nao_vale_pra_nota_autorizada_da_shopee(client, db, prestador_teste, vinculo_teste, monkeypatch):
    import app.services.envio_direto as envio_direto
    from app.services.motor_emissao import criar_rascunho as _criar

    enviados = []

    class Falso:
        def enviar(self, **kw):
            enviados.append(kw)

    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: Falso())
    monkeypatch.setattr(envio_direto, "motivo_email_desabilitado", lambda vinculo, destino=None: None if destino else "sem destino")
    monkeypatch.setattr(envio_direto, "LIMITE_EMAILS_DIA", 1)
    vinculo_teste.email_contato = "contato@tomador.com"
    vinculo_teste.email_anexos = "xml"  # sem PDF oficial no teste

    comum = _criar(db, vinculo_teste, competencia="2026-01", valor=10)
    montar(db, comum)
    assert client.post(f"/api/dps/{comum.id}/enviar-email").json()["status"] == "enviado"
    # a segunda nota comum bate no teto
    comum2 = _criar(db, vinculo_teste, competencia="2026-02", valor=10)
    montar(db, comum2)
    assert client.post(f"/api/dps/{comum2.id}/enviar-email").status_code == 400

    # nota da Shopee já autorizada: passa, e sempre pro e-mail do vendedor
    avulsa = _criar(db, vinculo_teste, competencia="2026-02", valor=5, tomador_avulso={
        "documento": "11222333000181", "tipo_documento": "CNPJ", "razao_social": "Loja X",
        "email": "vendedor@loja.com", "endereco": {}, "pais": "BR", "lojas": ["x"],
    })
    montar(db, avulsa)
    avulsa.estado = "confirmado"
    db.flush()
    r = client.post(f"/api/dps/{avulsa.id}/enviar-email", json={"para": ["outro@spam.com"]})
    assert r.status_code == 200 and r.json()["status"] == "enviado"
    assert enviados[-1]["destinatario"] == ["vendedor@loja.com"]
