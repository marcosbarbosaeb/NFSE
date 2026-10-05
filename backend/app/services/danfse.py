"""DANFSe gerado aqui (05/10/2026).

A API do governo que devolvia o PDF oficial (ADN, /danfse/{chave}) foi
suspensa em 03/08/2026 pela Nota Técnica SE/CGNFS-e nº 008/2026: desde
então quem emite é que gera o DANFSe, a partir do XML da NFS-e autorizada.
Por isso "Baixar PDF" tinha parado de funcionar.

O documento segue os blocos da NT 008 (identificação, emitente, tomador,
intermediário, serviço, tributação municipal e federal, valor total,
totais aproximados de tributos, informações complementares), com o QR Code
da consulta pública pela chave de acesso. Tudo sai do XML que a Sefin
devolveu (`xml_resposta`); o que o XML não traz vem do cadastro/snapshot.
"""
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from lxml import etree
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.models import Emissao
from app.services.municipios import rotulo_municipio

URL_CONSULTA = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave={chave}"

MARGEM = 10 * mm
LARGURA, ALTURA = A4
UTIL = LARGURA - 2 * MARGEM
CINZA = colors.Color(0.45, 0.45, 0.45)
LINHA = colors.Color(0.7, 0.7, 0.7)
FUNDO = colors.Color(0.93, 0.93, 0.93)

TRIB_ISSQN = {"1": "Operação tributável", "2": "Imunidade", "3": "Exportação de serviço", "4": "Não incidência"}
RET_ISSQN = {"1": "Não retido", "2": "Retido pelo tomador", "3": "Retido pelo intermediário"}
REGIME_SN = {"1": "Não optante", "2": "Optante — MEI", "3": "Optante — ME/EPP"}


class DanfseIndisponivelError(Exception):
    pass


# --- leitura do XML (sem depender do prefixo/namespace) ---


def _filho(no, nome):
    if no is None:
        return None
    for f in no:
        if isinstance(f.tag, str) and etree.QName(f).localname == nome:
            return f
    return None


def _no(no, caminho: str):
    for parte in caminho.split("/"):
        no = _filho(no, parte)
        if no is None:
            return None
    return no


def _t(no, caminho: str) -> str | None:
    alvo = _no(no, caminho)
    texto = (alvo.text or "").strip() if alvo is not None else ""
    return texto or None


def _achar(raiz, nome):
    if raiz is None:
        return None
    for el in raiz.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == nome:
            return el
    return None


# --- formatação ---


def _brl(valor) -> str:
    if valor in (None, ""):
        return "-"
    try:
        v = Decimal(str(valor))
    except InvalidOperation:
        return str(valor)
    inteiro, _, centavos = f"{v:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def _pct(valor) -> str:
    if valor in (None, ""):
        return "-"
    try:
        return f"{Decimal(str(valor)):.2f}".replace(".", ",") + "%"
    except InvalidOperation:
        return str(valor)


def _doc(numero: str | None) -> str:
    d = "".join(c for c in (numero or "") if c.isalnum())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return numero or "-"


def _cep(cep: str | None) -> str:
    d = "".join(c for c in (cep or "") if c.isdigit())
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else (cep or "-")


def _data_hora(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return iso


def _data(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _municipio(codigo: str | None) -> str:
    if not codigo:
        return "-"
    try:
        return rotulo_municipio(codigo) or codigo
    except Exception:  # noqa: BLE001 — só o rótulo
        return codigo


def _cod_servico(codigo: str | None) -> str:
    d = "".join(c for c in (codigo or "") if c.isdigit())
    return f"{d[:2]}.{d[2:4]}.{d[4:]}" if len(d) == 6 else (codigo or "-")


def _endereco(lgr, nro, cpl, bairro) -> str:
    partes = [p for p in (lgr, nro, cpl, bairro) if p]
    return ", ".join(partes) if partes else "-"


# --- dados ---


def dados_do_danfse(emissao: Emissao) -> dict:
    """Tudo o que o DANFSe mostra, já em texto."""
    if emissao.estado not in ("confirmado", "cancelada", "substituida") or not emissao.chave_acesso:
        raise DanfseIndisponivelError("O PDF da nota só existe depois que a prefeitura confirma a nota.")
    bruto = emissao.xml_resposta or emissao.xml_assinado or emissao.xml_dps
    raiz = etree.fromstring(bruto.encode("utf-8")) if bruto else None
    inf = _achar(raiz, "infNFSe")
    dps = _achar(raiz, "infDPS")
    snap = emissao.tomador_snapshot or {}
    prestador = emissao.vinculo.prestador if emissao.vinculo is not None else None

    emit = _filho(inf, "emit")
    ender_emit = _filho(emit, "enderNac")
    toma = _filho(dps, "toma")
    end_toma = _filho(toma, "end")
    end_nac = _filho(end_toma, "endNac")
    interm = _filho(dps, "interm")
    end_snap = snap.get("endereco") or {}
    cod_mun_prest = _t(ender_emit, "cMun") or (prestador.cod_municipio if prestador else None)
    cod_mun_toma = _t(end_nac, "cMun") or end_snap.get("cMun")

    v_serv = _t(dps, "valores/vServPrest/vServ") or str(emissao.valor)
    v_liq = _t(inf, "valores/vLiq") or v_serv
    trib_mun = _no(dps, "valores/trib/tribMun")
    tot_trib = _no(dps, "valores/trib/totTrib")
    p_sn = _t(tot_trib, "pTotTribSN")
    aprox = "-"
    if p_sn:
        try:
            aprox = f"{_brl(Decimal(v_serv) * Decimal(p_sn) / 100)} ({_pct(p_sn)}) — Simples Nacional"
        except InvalidOperation:
            aprox = f"{_pct(p_sn)} — Simples Nacional"
    elif _no(tot_trib, "vTotTrib") is not None:
        aprox = " · ".join(
            f"{rot} {_brl(_t(tot_trib, f'vTotTrib/{tag}'))}"
            for rot, tag in (("Federais", "vTotTribFed"), ("Estaduais", "vTotTribEst"), ("Municipais", "vTotTribMun"))
        )

    return {
        "chave": emissao.chave_acesso,
        "url_consulta": URL_CONSULTA.format(chave=emissao.chave_acesso),
        "homologacao": (_t(dps, "tpAmb") or snap.get("tpAmb") or "1") == "2",
        "situacao": {"cancelada": "CANCELADA", "substituida": "SUBSTITUÍDA"}.get(emissao.estado),
        "municipio_emissor": _t(inf, "xLocEmi") or _municipio(cod_mun_prest),
        "identificacao": [
            ("Número da NFS-e", _t(inf, "nNFSe") or "-"),
            ("Competência da NFS-e", _data(_t(dps, "dCompet")) if _t(dps, "dCompet") else emissao.competencia),
            ("Data e hora da emissão da NFS-e", _data_hora(_t(inf, "dhProc"))),
            ("Número da DPS", str(_t(dps, "nDPS") or emissao.n_dps)),
            ("Série da DPS", str(_t(dps, "serie") or emissao.serie)),
            ("Data e hora da emissão da DPS", _data_hora(_t(dps, "dhEmi"))),
        ],
        "emitente": [
            ("Nome / Nome empresarial", _t(emit, "xNome") or (prestador.razao_social if prestador else "-")),
            ("CNPJ / CPF", _doc(_t(emit, "CNPJ") or _t(emit, "CPF") or (prestador.cpf_cnpj if prestador else None))),
            ("Inscrição municipal", _t(emit, "IM") or (prestador.inscricao_municipal if prestador else None) or "-"),
            ("Telefone", _t(emit, "fone") or (prestador.telefone if prestador else None) or "-"),
            ("Endereço", _endereco(
                _t(ender_emit, "xLgr") or (prestador.logradouro if prestador else None),
                _t(ender_emit, "nro") or (prestador.numero if prestador else None),
                _t(ender_emit, "xCpl") or (prestador.complemento if prestador else None),
                _t(ender_emit, "xBairro") or (prestador.bairro if prestador else None),
            )),
            ("Município", _municipio(cod_mun_prest)),
            ("CEP", _cep(_t(ender_emit, "CEP") or (prestador.cep if prestador else None))),
            ("E-mail", _t(emit, "email") or (prestador.email if prestador else None) or "-"),
            ("Simples Nacional na data de competência", REGIME_SN.get(_t(dps, "prest/regTrib/opSimpNac") or "", "-")),
        ],
        "tomador": [
            ("Nome / Nome empresarial", _t(toma, "xNome") or snap.get("razao_social") or "-"),
            ("CNPJ / CPF / NIF", _doc(_t(toma, "CNPJ") or _t(toma, "CPF") or _t(toma, "NIF") or snap.get("cnpj"))),
            ("Inscrição municipal", _t(toma, "IM") or "-"),
            ("Telefone", _t(toma, "fone") or "-"),
            ("Endereço", _endereco(
                _t(end_toma, "xLgr") or end_snap.get("xLgr"), _t(end_toma, "nro") or end_snap.get("nro"),
                _t(end_toma, "xCpl") or end_snap.get("xCpl"), _t(end_toma, "xBairro") or end_snap.get("xBairro"),
            )),
            ("Município", _municipio(cod_mun_toma) if cod_mun_toma else (_t(end_toma, "endExt/xCidade") or "-")),
            ("CEP", _cep(_t(end_nac, "CEP") or end_snap.get("CEP"))),
            ("E-mail", _t(toma, "email") or "-"),
        ],
        "intermediario": [
            ("Nome / Nome empresarial", _t(interm, "xNome") or "-"),
            ("CNPJ / CPF / NIF", _doc(_t(interm, "CNPJ") or _t(interm, "CPF") or _t(interm, "NIF"))),
        ] if interm is not None else None,
        "servico": [
            ("Código de tributação nacional", " — ".join(p for p in (_cod_servico(_t(dps, "serv/cServ/cTribNac")), _t(inf, "xTribNac")) if p and p != "-") or "-"),
            ("Código de tributação municipal", " — ".join(p for p in (_t(dps, "serv/cServ/cTribMun"), _t(inf, "xTribMun")) if p) or "-"),
            ("Local da prestação", _t(inf, "xLocPrestacao") or _municipio(_t(dps, "serv/locPrest/cLocPrestacao"))),
            ("Código NBS", _t(dps, "serv/cServ/cNBS") or "-"),
        ],
        "descricao": _t(dps, "serv/cServ/xDescServ") or snap.get("descricao_renderizada") or "-",
        "municipal": [
            ("Tributação do ISSQN", TRIB_ISSQN.get(_t(trib_mun, "tribISSQN") or "", "-")),
            ("Município de incidência do ISSQN", _t(inf, "xLocIncid") or _municipio(_t(inf, "cLocIncid")) if (_t(inf, "xLocIncid") or _t(inf, "cLocIncid")) else "-"),
            ("Retenção do ISSQN", RET_ISSQN.get(_t(trib_mun, "tpRetISSQN") or "", "-")),
            ("Valor do serviço", _brl(v_serv)),
            ("Base de cálculo do ISSQN", _brl(_t(inf, "valores/vBC"))),
            ("Alíquota aplicada", _pct(_t(inf, "valores/pAliqAplic") or _t(trib_mun, "pAliq"))),
            ("ISSQN apurado", _brl(_t(inf, "valores/vISSQN"))),
        ],
        "federal": [
            ("IRRF", _brl(_t(dps, "valores/trib/tribFed/vRetIRRF"))),
            ("CSLL", _brl(_t(dps, "valores/trib/tribFed/vRetCSLL"))),
            ("Contribuição previdenciária", _brl(_t(dps, "valores/trib/tribFed/vRetCP"))),
            ("PIS", _brl(_t(dps, "valores/trib/tribFed/piscofins/vPis"))),
            ("COFINS", _brl(_t(dps, "valores/trib/tribFed/piscofins/vCofins"))),
        ],
        "totais": [
            ("Valor do serviço", _brl(v_serv)),
            ("Desconto incondicionado", _brl(_t(dps, "valores/vDescCondIncond/vDescIncond"))),
            ("Desconto condicionado", _brl(_t(dps, "valores/vDescCondIncond/vDescCond"))),
            ("Total de retenções", _brl(_t(inf, "valores/vTotalRet"))),
        ],
        "valor_liquido": _brl(v_liq),
        "tributos_aproximados": aprox,
        "complementares": " ".join(p for p in (_t(dps, "serv/infoCompl/xInfComp"), _t(inf, "valores/xOutInf")) if p) or "-",
    }


# --- desenho ---


class _Pagina:
    def __init__(self, c: canvas.Canvas):
        self.c = c
        self.y = ALTURA - MARGEM

    def titulo(self, texto: str):
        c = self.c
        self.y -= 2.2 * mm
        c.setFillColor(FUNDO)
        c.rect(MARGEM, self.y - 4.6 * mm, UTIL, 4.6 * mm, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(MARGEM + 1.5 * mm, self.y - 3.4 * mm, texto.upper())
        self.y -= 4.6 * mm

    def campos(self, campos: list[tuple[str, str]], colunas: int = 3):
        """Rótulo pequeno em cima, valor embaixo, em N colunas; valor longo
        quebra em linhas e a faixa cresce junto."""
        c = self.c
        largura = UTIL / colunas
        for inicio in range(0, len(campos), colunas):
            faixa = campos[inicio : inicio + colunas]
            quebras = [simpleSplit(str(valor or "-"), "Helvetica", 8.5, largura - 3 * mm)[:3] or ["-"] for _, valor in faixa]
            altura = 4.2 * mm + max(len(q) for q in quebras) * 3.7 * mm
            for i, ((rotulo, _), linhas) in enumerate(zip(faixa, quebras)):
                x = MARGEM + i * largura + 1.5 * mm
                c.setFillColor(CINZA)
                c.setFont("Helvetica", 6.2)
                c.drawString(x, self.y - 3.2 * mm, rotulo)
                c.setFillColor(colors.black)
                c.setFont("Helvetica", 8.5)
                for n, linha in enumerate(linhas):
                    c.drawString(x, self.y - 7 * mm - n * 3.7 * mm, linha)
            self.y -= altura
        self.linha()

    def texto(self, texto: str, max_linhas: int = 9):
        c = self.c
        linhas = []
        for paragrafo in str(texto or "-").splitlines() or ["-"]:
            linhas.extend(simpleSplit(paragrafo, "Helvetica", 8.5, UTIL - 3 * mm) or [""])
        if len(linhas) > max_linhas:
            linhas = linhas[:max_linhas]
            linhas[-1] = linhas[-1][:-3] + "..."
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8.5)
        for n, linha in enumerate(linhas):
            c.drawString(MARGEM + 1.5 * mm, self.y - 4.2 * mm - n * 3.7 * mm, linha)
        self.y -= 2.5 * mm + len(linhas) * 3.7 * mm
        self.linha()

    def linha(self):
        self.c.setStrokeColor(LINHA)
        self.c.setLineWidth(0.4)
        self.c.line(MARGEM, self.y, MARGEM + UTIL, self.y)


def gerar_danfse(emissao: Emissao) -> bytes:
    d = dados_do_danfse(emissao)
    saida = io.BytesIO()
    c = canvas.Canvas(saida, pagesize=A4)
    c.setTitle(f"DANFSe {d['chave']}")
    c.setAuthor("Agente Ana")
    p = _Pagina(c)

    # Cabeçalho: marca NFS-e, título, município emissor, chave e QR Code.
    topo = p.y
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.Color(0.0, 0.35, 0.2))
    c.drawString(MARGEM, topo - 8 * mm, "NFS-e")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 6.5)
    c.drawString(MARGEM, topo - 11.5 * mm, "Nota Fiscal de Serviço eletrônica")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(LARGURA / 2, topo - 5.5 * mm, "DANFSe v2.0")
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(LARGURA / 2, topo - 9.5 * mm, "Documento Auxiliar da NFS-e")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(LARGURA / 2, topo - 13.5 * mm, f"Município: {d['municipio_emissor']}")
    if d["homologacao"]:
        c.setFillColor(colors.red)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(LARGURA / 2, topo - 18 * mm, "NFS-e SEM VALIDADE JURÍDICA")
        c.setFillColor(colors.black)

    lado = 24 * mm  # a NT pede no mínimo 1,52 cm
    qr = QrCodeWidget(d["url_consulta"], barLevel="M")
    x0, y0, x1, y1 = qr.getBounds()
    desenho = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
    desenho.add(qr)
    renderPDF.draw(desenho, c, MARGEM + UTIL - lado, topo - lado)

    p.y = topo - max(lado, 20 * mm) - 1 * mm
    p.linha()
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.2)
    c.drawString(MARGEM + 1.5 * mm, p.y - 3.2 * mm, "Chave de acesso da NFS-e")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(MARGEM + 1.5 * mm, p.y - 7.2 * mm, d["chave"])
    c.setFont("Helvetica", 6.2)
    c.setFillColor(CINZA)
    c.drawString(
        MARGEM + 1.5 * mm, p.y - 10.4 * mm,
        "A autenticidade desta NFS-e pode ser verificada pela leitura do QR Code ou pela consulta da chave de acesso no Portal Nacional da NFS-e (nfse.gov.br/ConsultaPublica).",
    )
    p.y -= 12 * mm
    p.linha()

    p.campos(d["identificacao"], colunas=3)
    p.titulo("Emitente da NFS-e (prestador do serviço)")
    p.campos(d["emitente"], colunas=3)
    p.titulo("Tomador do serviço")
    p.campos(d["tomador"], colunas=3)
    p.titulo("Intermediário do serviço")
    if d["intermediario"]:
        p.campos(d["intermediario"], colunas=2)
    else:
        p.texto("Não identificado na NFS-e")
    p.titulo("Serviço prestado")
    p.campos(d["servico"], colunas=2)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.2)
    c.drawString(MARGEM + 1.5 * mm, p.y - 3.2 * mm, "Descrição do serviço")
    p.y -= 2.4 * mm
    p.texto(d["descricao"])
    p.titulo("Tributação municipal")
    p.campos(d["municipal"], colunas=4)
    p.titulo("Tributação federal")
    p.campos(d["federal"], colunas=5)
    p.titulo("Valor total da NFS-e")
    p.campos(d["totais"], colunas=4)
    # Valor líquido em destaque (a NT pede o campo sombreado).
    c.setFillColor(FUNDO)
    c.rect(MARGEM, p.y - 9 * mm, UTIL, 9 * mm, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGEM + 1.5 * mm, p.y - 5.8 * mm, "VALOR LÍQUIDO DA NFS-e")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(MARGEM + UTIL - 1.5 * mm, p.y - 6.2 * mm, d["valor_liquido"])
    p.y -= 9 * mm
    p.linha()
    p.titulo("Totais aproximados dos tributos (Lei nº 12.741/2012)")
    p.texto(d["tributos_aproximados"], max_linhas=2)
    p.titulo("Informações complementares")
    p.texto(d["complementares"], max_linhas=5)

    # Moldura e rodapé.
    c.setStrokeColor(LINHA)
    c.setLineWidth(0.6)
    c.rect(MARGEM, p.y, UTIL, (ALTURA - MARGEM) - p.y, stroke=1, fill=0)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6)
    c.drawString(MARGEM, 6 * mm, "DANFSe gerado pelo emitente a partir do XML da NFS-e autorizada (NT SE/CGNFS-e nº 008/2026).")
    c.drawRightString(MARGEM + UTIL, 6 * mm, "Agente Ana · agenteana.com.br")

    if d["situacao"]:
        c.saveState()
        c.translate(LARGURA / 2, ALTURA / 2)
        c.rotate(45)
        c.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.22))
        c.setFont("Helvetica-Bold", 72)
        c.drawCentredString(0, 0, d["situacao"])
        c.restoreState()

    c.showPage()
    c.save()
    return saida.getvalue()
