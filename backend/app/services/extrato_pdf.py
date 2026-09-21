"""
Extração automática de transações de um extrato bancário em PDF — Marco 15
(item 5 do pedido do Marcos: "Recebimentos" ganha upload de "extrato
bancário (várias transações)", opção que ele escolheu entre as
alternativas apresentadas).

Bancos exportam PDF em layouts bem diferentes entre si — não existe parser
universal confiável pra "qual desses números é o saldo, qual é uma
transação de verdade" sem entender o leiaute específico daquele banco.
Por isso a extração aqui é DELIBERADAMENTE heurística: por LINHA de texto
extraída do PDF (via pdfplumber), procura um padrão "data brasileira +
valor monetário brasileiro" e usa o resto da linha como descrição. Linhas
sem esse par (cabeçalho, saldo, rodapé, texto solto) são ignoradas.

Isto NUNCA grava nada no banco sozinho — devolve candidatos
(`TransacaoExtraida`) pro painel mostrar numa tela de revisão, onde a
pessoa escolhe quais são recebimentos de verdade e de qual vínculo (ver
app/services/importacao_extrato.py pra a etapa de confirmação, e os
endpoints /api/recebimentos/extrato + /api/recebimentos/extrato/confirmar
em app/main.py). Extração errada aqui na pior das hipóteses faz a pessoa
ignorar uma linha ruim na revisão — nunca cria um pagamento sozinha.
"""
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pdfplumber

# dd/mm/aaaa ou dd/mm/aa — a maioria dos extratos brasileiros usa um dos dois.
_RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{2,4})\b")

# Valor monetário brasileiro: milhares com ponto, centavos com vírgula
# (100,00 / 1.234,56), sinal de menos opcional na frente, "R$" opcional
# antes, e um marcador C/D opcional depois (alguns extratos marcam
# Crédito/Débito assim em vez de usar sinal).
_RE_VALOR = re.compile(r"(-)?\s*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*([CD])?\b")


class PdfInvalidoError(Exception):
    """Arquivo não é um PDF legível (corrompido, protegido por senha,
    formato errado) — diferente de "não achou nenhuma transação", que não é
    erro (ver docstring de extrair_transacoes)."""


@dataclass
class TransacaoExtraida:
    linha: int
    data: date | None
    descricao: str
    valor: Decimal
    credito: bool


def _parsear_data(bruto: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(bruto, fmt).date()
        except ValueError:
            continue
    return None


def _parsear_valor(bruto: str) -> Decimal | None:
    try:
        valor = Decimal(bruto.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return valor if valor != 0 else None


def extrair_transacoes(pdf_bytes: bytes) -> list[TransacaoExtraida]:
    """Devolve TODAS as linhas que parecem transação (crédito e débito) —
    filtrar só créditos (recebimentos de verdade) é decisão da tela de
    revisão, não deste parser: mostrar o débito também ajuda a pessoa a
    perceber quando o parser leu uma linha errada."""
    try:
        arquivo = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:  # pdfplumber/pypdf levantam tipos variados pra PDF corrompido/senha
        raise PdfInvalidoError("Não foi possível abrir o PDF — confira se o arquivo não está corrompido ou protegido por senha.") from exc

    transacoes: list[TransacaoExtraida] = []
    with arquivo as pdf:
        numero_linha = 0
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            for linha_bruta in texto.split("\n"):
                numero_linha += 1
                data_match = _RE_DATA.search(linha_bruta)
                valor_match = _RE_VALOR.search(linha_bruta)
                if not data_match or not valor_match:
                    continue

                valor = _parsear_valor(valor_match.group(2))
                if valor is None:
                    continue

                sinal_negativo = valor_match.group(1) == "-"
                marcador = valor_match.group(3)
                credito = marcador == "C" or (marcador != "D" and not sinal_negativo)

                descricao = linha_bruta.replace(data_match.group(1), "").replace(valor_match.group(0), "")
                descricao = re.sub(r"\s+", " ", descricao).strip(" -–—")

                transacoes.append(
                    TransacaoExtraida(
                        linha=numero_linha,
                        data=_parsear_data(data_match.group(1)),
                        descricao=descricao or "(sem descrição)",
                        valor=valor,
                        credito=credito,
                    )
                )
    return transacoes
