"""
Relatório mensal de comissões da Shopee (programa de afiliados) — pedido
do Marcos (28/09/2026): "esse é o modelo da Shopee... estou te mandando
esse modelo apenas para você aprender a ler" + "a intenção é não salvar
essa lista toda de tomadores quando ela gerar".

Diferente dos outros tomadores, na Shopee a nota não vai pra Shopee: vai
pra CADA VENDEDOR que pagou comissão no mês (centenas por mês, a maioria de
poucos reais). O relatório ("MonthlyReport_*.csv", exportado no painel de
afiliados) traz uma linha por loja:

    Mês de conclusão, Nome da loja, ID da Loja, Comissão Total do Vendedor,
    CNPJ do Vendedor, CPF do Vendedor, Identificação Fiscal Estrangeira,
    Razão social do vendedor, Endereço do Vendedor, País do Vendedor,
    Inscrição Estadual, E-mail

Regras de leitura:
- o mesmo vendedor (mesmo CNPJ/CPF) pode ter várias lojas no mês — vira
  UMA nota, somando as comissões;
- "Aug 2026" -> competência 2026-08;
- o endereço vem numa string só ("Rua X, 10, Apto 2 - Bairro, Cidade -
  Estado, 01234567") e é quebrado nos campos da nota; se não der pra
  entender, a nota sai sem endereço (é opcional pro tomador na DPS);
- vendedor estrangeiro (país != BR, só com identificação fiscal
  estrangeira) fica marcado: nota pra fora do país é exportação de serviço
  e tem regra própria de ISS — não entra por padrão.

Nada aqui grava tomador no catálogo nem cria vínculo: os dados do vendedor
vão só no snapshot da própria nota (ver `tomador_avulso` em
app/services/motor_emissao.py).
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.services.municipios import codigo_por_nome

_MESES_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

_UF_POR_ESTADO = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}

_COLUNAS = {
    "mes": ("mes de conclusao", "mes"),
    "loja": ("nome da loja",),
    "valor": ("comissao total do vendedor", "comissao total", "comissao"),
    "cnpj": ("cnpj do vendedor", "cnpj"),
    "cpf": ("cpf do vendedor", "cpf"),
    "nif": ("identificacao fiscal estrangeira",),
    "razao_social": ("razao social do vendedor", "razao social"),
    "endereco": ("endereco do vendedor", "endereco"),
    "pais": ("pais do vendedor", "pais"),
    "email": ("e-mail", "email"),
}


class RelatorioShopeeInvalidoError(Exception):
    """O arquivo não é o relatório mensal da Shopee (colunas faltando)."""


def _norm(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").strip().lower()) if unicodedata.category(c) != "Mn")


def _digitos(texto: str | None) -> str:
    return "".join(c for c in (texto or "") if c.isdigit())


def parsear_competencia(bruto: str) -> str | None:
    """'Aug 2026' / 'ago 2026' / '08/2026' / '2026-08' -> '2026-08'."""
    t = _norm(bruto)
    m = re.match(r"^([a-z]{3})[a-z]*\.?[\s/-]+(\d{4})$", t)
    if m:
        mes = _MESES_EN.get(m.group(1)) or _MESES_PT.get(m.group(1))
        return f"{m.group(2)}-{mes:02d}" if mes else None
    m = re.match(r"^(\d{1,2})[/-](\d{4})$", t)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{4})-(\d{2})$", t)
    return t if m else None


def parsear_valor(bruto: str) -> Decimal | None:
    t = (bruto or "").replace("R$", "").replace(" ", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def parsear_endereco(bruto: str) -> dict | None:
    """'R Joaquim M Leite, 425, Cond 4 AP 236 - Jardim Interlagos,
    Hortolândia - São Paulo, 13186642' -> campos da DPS. None se não der."""
    partes = [p.strip() for p in (bruto or "").split(",")]
    if len(partes) < 4:
        return None
    cep = _digitos(partes[-1])
    if len(cep) != 8 or " - " not in partes[-2]:
        return None
    cidade, estado = (s.strip() for s in partes[-2].rsplit(" - ", 1))
    uf = _UF_POR_ESTADO.get(_norm(estado)) or (estado.upper() if len(estado) == 2 else None)
    cod_municipio = codigo_por_nome(cidade, uf) if uf else None
    if not cod_municipio:
        return None
    logradouro = partes[0]
    resto = ", ".join(partes[1:-2])
    if " - " in resto:
        antes, bairro = (s.strip(" ,") for s in resto.rsplit(" - ", 1))
    else:
        antes, bairro = resto, ""
    numero, _, complemento = antes.partition(",")
    return {
        "cMun": cod_municipio,
        "CEP": cep,
        "xLgr": logradouro[:255] or "Não informado",
        "nro": (numero.strip() or "S/N")[:60],
        "xCpl": complemento.strip()[:156] or None,
        "xBairro": (bairro or "Não informado")[:60],
        "cidade": cidade,
        "uf": uf,
    }


@dataclass
class VendedorShopee:
    """Um tomador (vendedor) de um mês — já somando todas as lojas dele."""

    competencia: str
    documento: str
    tipo_documento: str  # 'CNPJ' | 'CPF' | 'NIF'
    razao_social: str
    lojas: list[str]
    valor: Decimal
    pais: str
    email: str | None
    endereco: dict | None
    endereco_bruto: str
    estrangeiro: bool = False
    avisos: list[str] = field(default_factory=list)


@dataclass
class RelatorioShopee:
    vendedores: list[VendedorShopee]
    linhas_lidas: int
    linhas_ignoradas: list[str]


def ler_relatorio(conteudo: bytes) -> RelatorioShopee:
    texto = None
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise RelatorioShopeeInvalidoError("Não consegui ler o arquivo.")
    amostra = texto[:4096]
    delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=delimitador)
    try:
        cabecalho = [_norm(c) for c in next(leitor)]
    except StopIteration:
        raise RelatorioShopeeInvalidoError("O arquivo está vazio.")

    indice: dict[str, int] = {}
    for chave, nomes in _COLUNAS.items():
        for i, c in enumerate(cabecalho):
            if c in nomes:
                indice[chave] = i
                break
    faltando = {"mes", "valor", "razao_social"} - indice.keys()
    if faltando or not ({"cnpj", "cpf"} & indice.keys()):
        raise RelatorioShopeeInvalidoError(
            "Esse arquivo não parece o relatório mensal da Shopee (faltam as colunas de mês, comissão, razão social ou CNPJ)."
        )

    def col(linha: list[str], chave: str) -> str:
        i = indice.get(chave)
        return linha[i].strip() if i is not None and i < len(linha) else ""

    agrupados: dict[tuple[str, str], VendedorShopee] = {}
    ignoradas: list[str] = []
    lidas = 0
    for numero, linha in enumerate(leitor, start=2):
        if not any(c.strip() for c in linha):
            continue
        lidas += 1
        competencia = parsear_competencia(col(linha, "mes"))
        valor = parsear_valor(col(linha, "valor"))
        loja = col(linha, "loja") or col(linha, "razao_social")
        if not competencia or valor is None:
            ignoradas.append(f"Linha {numero} ({loja}): mês ou valor não reconhecido.")
            continue
        if valor <= 0:
            continue
        cnpj, cpf, nif = _digitos(col(linha, "cnpj")), _digitos(col(linha, "cpf")), col(linha, "nif")
        pais = (col(linha, "pais") or "BR").upper()
        if len(cnpj) == 14:
            documento, tipo = cnpj, "CNPJ"
        elif len(cpf) == 11:
            documento, tipo = cpf, "CPF"
        elif nif:
            documento, tipo = nif[:40], "NIF"
        else:
            ignoradas.append(f"Linha {numero} ({loja}): vendedor sem CNPJ, CPF ou identificação fiscal.")
            continue

        chave = (competencia, documento)
        if chave in agrupados:
            v = agrupados[chave]
            v.valor += valor
            if loja not in v.lojas:
                v.lojas.append(loja)
            continue

        estrangeiro = pais != "BR" or tipo == "NIF"
        endereco_bruto = col(linha, "endereco")
        endereco = None if estrangeiro else parsear_endereco(endereco_bruto)
        avisos = []
        if estrangeiro:
            avisos.append("Vendedor de fora do Brasil: a nota sai com a identificação fiscal estrangeira e o país dele.")
        elif endereco is None:
            avisos.append("Endereço não reconhecido — a nota sai sem o endereço do tomador.")
        agrupados[chave] = VendedorShopee(
            competencia=competencia, documento=documento, tipo_documento=tipo,
            razao_social=(col(linha, "razao_social") or loja)[:300], lojas=[loja], valor=valor, pais=pais,
            email=col(linha, "email") or None, endereco=endereco, endereco_bruto=endereco_bruto,
            estrangeiro=estrangeiro, avisos=avisos,
        )
    return RelatorioShopee(vendedores=list(agrupados.values()), linhas_lidas=lidas, linhas_ignoradas=ignoradas)


def tomador_avulso(v: VendedorShopee) -> dict:
    """Formato que `criar_rascunho(tomador_avulso=...)` espera — o tomador
    vai só no snapshot da nota, nunca pro catálogo."""
    return {
        "documento": v.documento,
        "tipo_documento": v.tipo_documento,
        "razao_social": v.razao_social,
        "endereco": v.endereco,
        "pais": v.pais,
        "email": v.email,
        "lojas": v.lojas,
    }


@dataclass
class ResultadoGeracao:
    geradas: int
    ja_existiam: int
    puladas: int
    total: Decimal
    erros: list[str]


def gerar_notas(
    db,
    vinculo,
    relatorio: RelatorioShopee,
    *,
    competencia: str,
    dcompet: str | None = None,
    valor_minimo: Decimal = Decimal("0"),
    incluir_estrangeiros: bool = False,
    aliq_sn: float | None = None,
    tpAmb: str = "2",
) -> ResultadoGeracao:
    """Uma nota (rascunho -> montada) por vendedor da competência. Não dá
    commit; cada vendedor roda no seu SAVEPOINT (um erro não derruba o
    lote). Quem já tem nota ativa nessa competência é pulado — dá pra
    reenviar o mesmo relatório sem duplicar nada."""
    from app.fiscal.dps import DescricaoIncompletaError
    from app.services.motor_emissao import EmissaoJaExisteError, criar_rascunho, montar

    geradas = ja_existiam = puladas = 0
    total = Decimal("0")
    erros: list[str] = []
    for v in relatorio.vendedores:
        if v.competencia != competencia:
            continue
        if v.valor < valor_minimo or (v.estrangeiro and not incluir_estrangeiros):
            puladas += 1
            continue
        savepoint = db.begin_nested()
        try:
            emissao = criar_rascunho(
                db, vinculo, competencia=competencia, valor=float(v.valor), aliq_sn=aliq_sn, tpAmb=tpAmb,
                tomador_avulso=tomador_avulso(v), dcompet=dcompet,
            )
            montar(db, emissao)
        except EmissaoJaExisteError:
            savepoint.rollback()
            ja_existiam += 1
        except (DescricaoIncompletaError, ValueError, KeyError) as exc:
            savepoint.rollback()
            erros.append(f"{v.razao_social}: {exc}")
        else:
            savepoint.commit()
            geradas += 1
            total += v.valor
    return ResultadoGeracao(geradas=geradas, ja_existiam=ja_existiam, puladas=puladas, total=total, erros=erros)
