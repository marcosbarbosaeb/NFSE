"""Leitura da ordem de pagamento da Awin (PDF) — pedido do Marcos de
28/09/2026: "segue o exemplo do pdf que recebemos da awin para extrair a
ordem de pagamento e o valor".

O PDF da Awin é um formulário (AcroForm): o texto fixo ("ORDEM DE PAGAMENTO
– Número:", "Total Bruto") fica na página e os VALORES ficam em campos do
formulário — por isso uma extração de texto comum volta os rótulos vazios.
Lemos em três camadas, da mais confiável pra menos:

1. Campos do formulário: `paymentOrderId`, `totalAmount`, `paymentOrderDate`,
   `currency`, `taxDetailsTaxNumber` (CNPJ do beneficiário) e
   `paymentDetailsTaxNumber` (CNPJ do titular da conta).
2. Texto da página (quando o PDF foi "impresso" de novo e os campos viraram
   texto): "Número: 15496516", "Total Bruto BRL 35951.41", "Data: 15/09/2026".
3. Nome do arquivo que a Awin usa: `2026-08-31_15496516-20260831-...pdf`
   (fim do período + número da ordem).

Competência: "normalmente a competência fica como a data de emissão da nota"
(Marcos, 28/09/2026) — então a sugestão é o mês de hoje (quando a nota vai
ser emitida), não o período das comissões. A tela deixa trocar antes de gerar.

Só leitura — nada vai pro banco aqui.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pdfplumber
from pdfminer.pdftypes import resolve1

CNPJ_AWIN = "14182871000188"


class OrdemAwinInvalidaError(Exception):
    """Arquivo não abre como PDF ou não tem cara de ordem de pagamento."""


@dataclass
class OrdemAwin:
    numero: str | None = None
    valor: Decimal | None = None
    data: date | None = None
    moeda: str | None = None
    competencia_sugerida: str | None = None
    cnpj_beneficiario: str | None = None
    cnpj_devedor: str | None = None
    fontes: list[str] = field(default_factory=list)


def _so_digitos(texto: str | None) -> str | None:
    if not texto:
        return None
    d = re.sub(r"\D", "", texto)
    return d or None


def parse_valor(texto: str | None) -> Decimal | None:
    """'35951.41', '35.951,41', '35,951.41', 'R$ 1.234,00' -> Decimal."""
    if not texto:
        return None
    t = re.sub(r"[^\d.,]", "", texto)
    if not t:
        return None
    if "," in t and "." in t:
        # o separador que aparece por último é o decimal
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        # "1.234.567" ou "1.234": ponto de milhar
        t = t.replace(".", "")
    try:
        valor = Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return valor if valor > 0 else None


def _parse_data(texto: str | None) -> date | None:
    if not texto:
        return None
    m = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", texto)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _decodificar(valor) -> str | None:
    valor = resolve1(valor)
    if valor is None:
        return None
    if isinstance(valor, bytes):
        if valor.startswith(b"\xfe\xff"):
            return valor[2:].decode("utf-16-be", errors="ignore").strip()
        return valor.decode("latin-1", errors="ignore").strip()
    if isinstance(valor, str):
        return valor.strip()
    # nomes (PSLiteral) e afins
    nome = getattr(valor, "name", None)
    return str(nome).strip() if nome is not None else None


def _campos_formulario(pdf) -> dict[str, str]:
    campos: dict[str, str] = {}
    try:
        acroform = resolve1(pdf.doc.catalog.get("AcroForm"))
        if not acroform:
            return campos
        pendentes = list(resolve1(acroform.get("Fields")) or [])
    except Exception:  # noqa: BLE001 — PDF sem formulário ou malformado: segue pro texto
        return campos
    while pendentes:
        campo = resolve1(pendentes.pop())
        if not isinstance(campo, dict):
            continue
        nome = _decodificar(campo.get("T"))
        valor = _decodificar(campo.get("V"))
        if nome and valor:
            campos[nome] = valor
        for filho in resolve1(campo.get("Kids")) or []:
            pendentes.append(filho)
    return campos


_RE_NUMERO = re.compile(r"(?:ORDEM DE PAGAMENTO\s*[–-]\s*N[úu]mero|N[úu]mero da ordem de pagamento)\s*:?\s*(\d{5,})", re.I)
_RE_TOTAL = re.compile(r"Total\s+Bruto\s*(?:([A-Z]{3})\s*)?(?:R\$\s*)?([\d.,]+)", re.I)
_RE_DATA = re.compile(r"\bData\s*:?\s*(\d{2}/\d{2}/\d{4})")
_RE_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_RE_NOME_ARQUIVO = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{5,})")


def ler_ordem_awin(conteudo: bytes, nome_arquivo: str | None = None, hoje: date | None = None) -> OrdemAwin:
    try:
        pdf = pdfplumber.open(io.BytesIO(conteudo))
    except Exception as exc:  # noqa: BLE001
        raise OrdemAwinInvalidaError(
            "Não foi possível abrir o PDF — confira se é a ordem de pagamento da Awin e se não está protegido por senha."
        ) from exc

    ordem = OrdemAwin()
    with pdf:
        campos = _campos_formulario(pdf)
        try:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:  # noqa: BLE001
            texto = ""

    # 1) campos do formulário
    if campos:
        ordem.numero = _so_digitos(campos.get("paymentOrderId"))
        ordem.valor = parse_valor(campos.get("totalAmount"))
        ordem.data = _parse_data(campos.get("paymentOrderDate"))
        ordem.moeda = campos.get("currency")
        ordem.cnpj_beneficiario = _so_digitos(campos.get("taxDetailsTaxNumber") or campos.get("paymentDetailsTaxNumber"))
        if ordem.numero or ordem.valor:
            ordem.fontes.append("formulario")

    # 2) texto da página
    if not ordem.numero and (m := _RE_NUMERO.search(texto)):
        ordem.numero = m.group(1)
        ordem.fontes.append("texto")
    if not ordem.valor and (m := _RE_TOTAL.search(texto)):
        ordem.valor = parse_valor(m.group(2))
        ordem.moeda = ordem.moeda or m.group(1)
        if "texto" not in ordem.fontes:
            ordem.fontes.append("texto")
    if not ordem.data and (m := _RE_DATA.search(texto)):
        ordem.data = _parse_data(m.group(1))
    cnpjs = [_so_digitos(c) for c in _RE_CNPJ.findall(texto)]
    if CNPJ_AWIN in cnpjs:
        ordem.cnpj_devedor = CNPJ_AWIN
    if not ordem.cnpj_beneficiario:
        outros = [c for c in cnpjs if c != CNPJ_AWIN]
        ordem.cnpj_beneficiario = outros[0] if outros else None

    # 3) nome do arquivo (só o número da ordem, se faltou)
    if not ordem.numero and nome_arquivo and (m := _RE_NOME_ARQUIVO.search(nome_arquivo)):
        ordem.numero = m.group(4)
        ordem.fontes.append("nome_arquivo")

    hoje = hoje or date.today()
    ordem.competencia_sugerida = f"{hoje.year:04d}-{hoje.month:02d}"

    parece_awin = ordem.cnpj_devedor == CNPJ_AWIN or "awin" in texto.lower() or bool(campos.get("paymentOrderId"))
    if not parece_awin and not (ordem.numero and ordem.valor):
        raise OrdemAwinInvalidaError(
            "Esse PDF não parece uma ordem de pagamento da Awin — não achei o número da ordem nem o valor."
        )
    return ordem
