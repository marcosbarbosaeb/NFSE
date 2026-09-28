"""
Extração automática de transações de um extrato bancário — Marco 15 (item
5 do pedido do Marcos: "Recebimentos" ganha upload de "extrato bancário
(várias transações)").

Revisto em 28/09/2026 ("a importação do extrato bancário não está
funcionando"): a primeira versão só entendia linhas no formato
"dd/mm/aaaa descrição valor" — é o leiaute de poucos bancos. Os extratos
reais que chegam aqui variam muito:

- Nubank: a data vem num CABEÇALHO ("01 SET 2026 Total de entradas + ...")
  e as transações do dia vêm nas linhas de baixo, só com descrição e valor;
- Inter: "1 de Setembro de 2026 Saldo do dia: ..." como cabeçalho, e o
  valor com "R$" e sinal ("-R$ 50,00");
- Itaú/Bradesco: "01/09 PIX TRANSF ..." — dia/mês sem ano;
- Mercado Pago/PicPay: "01-09-2026 ..." com traço, e duas colunas de valor
  (valor da transação e saldo);
- Banco do Brasil/Caixa: marcador "C"/"D" depois do valor, ou "-" no fim.

Por isso a leitura agora: aceita esses formatos de data (com e sem ano,
numérico ou por extenso/abreviado), "herda" a data do último cabeçalho
quando a linha só tem valor, ignora linhas de saldo/total, usa o PRIMEIRO
valor da linha quando há dois (o segundo costuma ser o saldo), e decide
crédito/débito pelo sinal, pelo marcador C/D ou, na falta deles, pelas
palavras da descrição ("recebido", "enviado", "pagamento", ...).

Além de PDF, aceita os dois formatos que praticamente todo banco exporta
e que não dependem de leiaute: OFX (Money/Quicken) e CSV.

Continua valendo a regra original: isto NUNCA grava nada no banco sozinho
— devolve candidatos pra uma tela de revisão, onde a pessoa escolhe quais
são recebimentos de verdade e de qual fornecedor (ver
app/services/importacao_extrato.py e os endpoints /api/recebimentos/extrato
em app/main.py).
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pdfplumber

_MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
    # inglês — alguns bancos digitais exportam assim
    "feb": 2, "apr": 4, "may": 5, "aug": 8, "sep": 9, "oct": 10, "dec": 12,
}

# dd/mm/aaaa, dd-mm-aaaa, dd.mm.aaaa, dd/mm/aa
_RE_DATA_NUM = re.compile(r"(?<![\d,])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})(?![\d,])")
# aaaa-mm-dd (CSV/ISO)
_RE_DATA_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
# dd/mm sem ano (Itaú, Bradesco) — não pode ser pedaço de valor (vírgula)
_RE_DATA_CURTA = re.compile(r"(?<![\d,./-])(\d{2})/(\d{2})(?![\d/,])")
# "01 SET 2026", "1 de setembro de 2026", "01 set", "05/set"
_RE_DATA_EXTENSO = re.compile(
    r"(?<!\d)(\d{1,2})(?:\s+de\s+|\s+|/|-)"
    r"(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|feb|apr|may|aug|sep|oct|dec)[a-zç]*\.?"
    r"(?:(?:\s+de\s+|\s+|/|-)(\d{4}))?(?![a-z])",
    re.IGNORECASE,
)

# Valor monetário brasileiro: sinal opcional (+, -, − ou –) antes ou
# depois do "R$", milhar com ponto ou sem separador, centavos com vírgula,
# e marcador C/D ou "-" opcional depois.
_RE_VALOR = re.compile(
    r"(?:(?P<sinal>[+\-−–])(?=\s*R\$|\d))?(?:\s*R\$\s*)?(?P<sinal2>[+\-−–])?"
    r"(?P<numero>\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})(?!\d)"
    r"(?P<sufixo>\s*[CD](?![A-Za-z])|-)?"
)

_PALAVRAS_IGNORAR = (
    "saldo", "total de entradas", "total de saidas", "total de saídas", "totais",
    "limite", "rendimento acumulado", "saldo anterior", "saldo do dia", "saldo final",
    "saldo disponivel", "saldo disponível", "valor bloqueado",
)
_PALAVRAS_CREDITO = (
    "recebid", "recebimento", "credito", "crédito", "deposito", "depósito", "estorno",
    "rendimento", "resgate", "devolucao", "devolução", "entrada", "transf recebida",
    "pix receb", "ted receb", "doc receb", "cred ",
)
_PALAVRAS_DEBITO = (
    "enviad", "pagamento", "pagto", "pgto", "compra", "debito", "débito", "saque", "tarifa",
    "boleto", "fatura", "aplicacao", "aplicação", "saida", "saída", "iof", "juros",
    "pix envi", "ted envi", "transf envi", "deb ",
)

TAMANHO_MAXIMO = 15 * 1024 * 1024


class PdfInvalidoError(Exception):
    """Arquivo não é um extrato legível (PDF corrompido/com senha, formato
    desconhecido) — diferente de "não achou nenhuma transação", que não é
    erro."""


@dataclass
class TransacaoExtraida:
    linha: int
    data: date | None
    descricao: str
    valor: Decimal
    credito: bool


@dataclass
class ResultadoExtrato:
    transacoes: list[TransacaoExtraida] = field(default_factory=list)
    formato: str = "pdf"
    linhas_lidas: int = 0


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _data_valida(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _ano_de(bruto: str | None, ano_padrao: int) -> int:
    if not bruto:
        return ano_padrao
    ano = int(bruto)
    return ano + 2000 if ano < 100 else ano


def _achar_data(linha: str, ano_padrao: int) -> tuple[date | None, str | None]:
    """Devolve (data, trecho que casou) — o trecho é removido da descrição."""
    m = _RE_DATA_NUM.search(linha)
    if m:
        d = _data_valida(_ano_de(m.group(3), ano_padrao), int(m.group(2)), int(m.group(1)))
        if d:
            return d, m.group(0)
    m = _RE_DATA_ISO.search(linha)
    if m:
        d = _data_valida(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d, m.group(0)
    m = _RE_DATA_EXTENSO.search(linha)
    if m:
        mes = _MESES.get(m.group(2).lower()[:3])
        if mes:
            d = _data_valida(_ano_de(m.group(3), ano_padrao), mes, int(m.group(1)))
            if d:
                return d, m.group(0)
    m = _RE_DATA_CURTA.search(linha)
    if m:
        d = _data_valida(ano_padrao, int(m.group(2)), int(m.group(1)))
        if d:
            return d, m.group(0)
    return None, None


def _parsear_valor(bruto: str) -> Decimal | None:
    try:
        valor = Decimal(bruto.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return valor if valor != 0 else None


def _eh_credito(sinal: str | None, sufixo: str | None, descricao: str) -> bool:
    sufixo = (sufixo or "").strip().upper()
    if sufixo == "D" or sufixo == "-":
        return False
    if sufixo == "C":
        return True
    if sinal and sinal in "-−–":
        return False
    if sinal == "+":
        return True
    texto = _sem_acento(descricao) + " "
    if any(_sem_acento(p) in texto for p in _PALAVRAS_DEBITO):
        return False
    if any(_sem_acento(p) in texto for p in _PALAVRAS_CREDITO):
        return True
    return True


def _inferir_ano(texto: str) -> int:
    """Ano "da vez" pra datas sem ano (dd/mm, "01 set"): o primeiro ano de 4
    dígitos que aparece no documento (cabeçalho "Período: 01/09/2026 a
    ..."), ou o ano corrente."""
    m = re.search(r"\b(20\d{2})\b", texto)
    return int(m.group(1)) if m else date.today().year


def _linha_para_transacao(linha: str, numero: int, data: date | None) -> TransacaoExtraida | None:
    valores = list(_RE_VALOR.finditer(linha))
    if not valores:
        return None
    # Dois valores na linha = transação + saldo (o saldo vem por último).
    m = valores[0]
    valor = _parsear_valor(m.group("numero"))
    if valor is None:
        return None
    descricao = linha
    for v in valores:
        descricao = descricao.replace(v.group(0), " ")
    descricao = re.sub(r"\bR\$\s*", " ", descricao)
    descricao = re.sub(r"\s+", " ", descricao).strip(" -–—:|")
    sinal = m.group("sinal") or m.group("sinal2")
    return TransacaoExtraida(
        linha=numero,
        data=data,
        descricao=descricao or "(sem descrição)",
        valor=valor,
        credito=_eh_credito(sinal, m.group("sufixo"), descricao),
    )


def extrair_de_texto(linhas: list[str]) -> list[TransacaoExtraida]:
    """Coração do parser, separado da leitura do PDF pra ser testável com
    linhas de texto puras (uma por leiaute de banco nos testes)."""
    ano_padrao = _inferir_ano("\n".join(linhas))
    transacoes: list[TransacaoExtraida] = []
    data_corrente: date | None = None
    for numero, linha_bruta in enumerate(linhas, start=1):
        linha = linha_bruta.strip()
        if not linha:
            continue
        data, trecho = _achar_data(linha, ano_padrao)
        resto = linha.replace(trecho, " ", 1) if trecho else linha
        if data:
            data_corrente = data
        texto = _sem_acento(resto)
        if any(_sem_acento(p) in texto for p in _PALAVRAS_IGNORAR):
            continue
        if data is None and data_corrente is None:
            continue  # cabeçalho do documento, antes de qualquer data
        transacao = _linha_para_transacao(resto, numero, data or data_corrente)
        if transacao is not None:
            transacoes.append(transacao)
    return transacoes


def _extrair_pdf(conteudo: bytes) -> ResultadoExtrato:
    try:
        arquivo = pdfplumber.open(io.BytesIO(conteudo))
    except Exception as exc:  # pdfplumber/pypdf levantam tipos variados pra PDF corrompido/senha
        raise PdfInvalidoError(
            "Não foi possível abrir o PDF — confira se o arquivo não está corrompido ou protegido por senha."
        ) from exc
    linhas: list[str] = []
    try:
        with arquivo as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text(x_tolerance=2, y_tolerance=3) or ""
                linhas.extend(texto.split("\n"))
    except Exception as exc:
        raise PdfInvalidoError("Não foi possível ler o conteúdo do PDF.") from exc
    return ResultadoExtrato(transacoes=extrair_de_texto(linhas), formato="pdf", linhas_lidas=sum(1 for l in linhas if l.strip()))


def _decodificar(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("utf-8", errors="replace")


def _extrair_ofx(texto: str) -> ResultadoExtrato:
    """OFX (SGML ou XML): cada <STMTTRN> tem TRNAMT (com sinal), DTPOSTED
    (AAAAMMDD...) e MEMO/NAME. Não depende de leiaute nenhum."""
    transacoes = []
    blocos = re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", texto, re.S | re.I)

    def campo(bloco: str, nome: str) -> str | None:
        m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
        return m.group(1).strip() if m else None

    for indice, bloco in enumerate(blocos, start=1):
        bruto = (campo(bloco, "TRNAMT") or "").replace(",", ".")
        try:
            valor = Decimal(bruto)
        except InvalidOperation:
            continue
        if valor == 0:
            continue
        dt = campo(bloco, "DTPOSTED") or ""
        data = _data_valida(int(dt[:4]), int(dt[4:6]), int(dt[6:8])) if len(dt) >= 8 and dt[:8].isdigit() else None
        descricao = " ".join(filter(None, [campo(bloco, "NAME"), campo(bloco, "MEMO")])) or "(sem descrição)"
        transacoes.append(TransacaoExtraida(linha=indice, data=data, descricao=descricao, valor=abs(valor), credito=valor > 0))
    return ResultadoExtrato(transacoes=transacoes, formato="ofx", linhas_lidas=len(blocos))


def _extrair_csv(texto: str) -> ResultadoExtrato:
    """CSV de banco: acha as colunas de data, descrição e valor pelo nome do
    cabeçalho (ou, sem cabeçalho reconhecível, trata cada linha como texto)."""
    amostra = texto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
    linhas = list(csv.reader(io.StringIO(texto), dialeto))
    linhas = [l for l in linhas if any(c.strip() for c in l)]
    if not linhas:
        return ResultadoExtrato(formato="csv")

    cabecalho = [_sem_acento(c) for c in linhas[0]]

    def coluna(*nomes: str) -> int | None:
        for i, c in enumerate(cabecalho):
            if any(n in c for n in nomes):
                return i
        return None

    i_data = coluna("data", "date")
    i_valor = coluna("valor", "value", "amount", "quantia", "montante")
    i_desc = coluna("descri", "historico", "lancamento", "title", "memo", "identificador", "detalhe")
    if i_data is None or i_valor is None:
        # Sem cabeçalho útil: cai no parser de texto, uma linha por vez.
        return ResultadoExtrato(
            transacoes=extrair_de_texto([" ".join(l) for l in linhas]), formato="csv", linhas_lidas=len(linhas)
        )

    ano_padrao = _inferir_ano(texto)
    transacoes = []
    for numero, l in enumerate(linhas[1:], start=2):
        if max(i_data, i_valor) >= len(l):
            continue
        data, _ = _achar_data(l[i_data], ano_padrao)
        bruto = l[i_valor].strip().replace("R$", "").replace(" ", "")
        negativo = bruto.startswith(("-", "−", "–")) or bruto.endswith("-")
        bruto = bruto.strip("+-−–")
        # "1.234,56" (BR) ou "1234.56" (exportações em inglês)
        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        try:
            valor = Decimal(bruto)
        except InvalidOperation:
            continue
        if valor == 0:
            continue
        descricao = l[i_desc].strip() if i_desc is not None and i_desc < len(l) else ""
        transacoes.append(
            TransacaoExtraida(linha=numero, data=data, descricao=descricao or "(sem descrição)", valor=valor, credito=not negativo)
        )
    return ResultadoExtrato(transacoes=transacoes, formato="csv", linhas_lidas=len(linhas) - 1)


def extrair_extrato(conteudo: bytes, nome_arquivo: str | None = None) -> ResultadoExtrato:
    """Detecta o formato pelo conteúdo (não só pela extensão — muito banco
    exporta OFX com extensão .txt) e extrai as transações."""
    if not conteudo:
        raise PdfInvalidoError("O arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise PdfInvalidoError("Arquivo grande demais (máximo 15 MB).")
    if conteudo.lstrip()[:5] == b"%PDF-":
        return _extrair_pdf(conteudo)
    texto = _decodificar(conteudo)
    if re.search(r"<OFX>|OFXHEADER|<STMTTRN>", texto[:20000], re.I):
        return _extrair_ofx(texto)
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".pdf"):
        return _extrair_pdf(conteudo)  # extensão .pdf sem o cabeçalho: deixa o pdfplumber dar o erro claro
    if nome.endswith((".csv", ".txt")) or ";" in texto[:2000] or "," in texto[:2000]:
        return _extrair_csv(texto)
    raise PdfInvalidoError("Formato não reconhecido. Envie o extrato em PDF, OFX ou CSV.")


def extrair_transacoes(pdf_bytes: bytes) -> list[TransacaoExtraida]:
    """Compatibilidade com quem só precisa da lista (testes antigos)."""
    return extrair_extrato(pdf_bytes, "extrato.pdf").transacoes
