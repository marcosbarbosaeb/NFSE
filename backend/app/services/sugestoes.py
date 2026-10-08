"""Limpeza do que vai pro catálogo de tomadores (05/10/2026).

O catálogo (`tomador`) é compartilhado entre as contas: o jeito que uma
empresa fatura um tomador vira sugestão pra próxima. Pedido do Marcos:
"deixe pré-preenchido; troque apenas os dados pessoais, nomes, conta
bancária". Então NADA do que é de uma pessoa pode ir junto — conta
bancária, CNPJ/CPF, número de pedido, ID de afiliado, @ de rede social,
vencimento, valor ou mês de uma nota específica.

Módulo puro (sem banco): a migração que limpa o catálogo usa a mesma função.
"""
from __future__ import annotations

import re

# Pedaço que fala de dado bancário, documento ou identificador de alguém.
_PESSOAL = re.compile(
    r"banc|ag[êe]ncia|\bag\b|\bconta\b|\bcc\b|\bc/c\b|\bpix\b|d[ií]gito|cnpj|cpf|venciment|afiliad"
    r"|\bpo\s*\d|pedido de compra|\bnf\s*\d|\bjob\b|projeto\s*:|@\w|\bid\b"
    # 08/10/2026: cupom de desconto é de uma pessoa (ex.: "Cupom_ NOME10")
    r"|cupo[mn]|c[óo]digo promocional",
    re.IGNORECASE,
)
_NUMERO_LONGO = re.compile(r"\d[\d.\-/ ]{3,}\d")  # 5+ dígitos seguidos (com ou sem pontuação)
_MES_ANO = re.compile(r"\b(0[1-9]|1[0-2])\s*/\s*20\d\d\b")
# Sobrou data, ano ou valor: é texto de UMA nota, não modelo.
_DE_UMA_NOTA = re.compile(r"\b(19|20)\d\d\b|R\$|\b\d{1,2}/\d{1,2}\b")
_VARIAVEL = re.compile(r"\{[a-z_]+\}")
# Assinatura no fim do e-mail ("Atenciosamente, Fulana de Tal."): o que vem
# depois da despedida, na mesma linha, é o nome de alguém (08/10/2026 — o
# catálogo de produção tinha uma assinatura com nome de pessoa).
_ASSINATURA = re.compile(r"^(\s*(?:atenciosamente|att\.?|cordialmente|abra[çc]os?)\s*[,.!:-]*\s*)([^\W\d_].*?)\s*$", re.IGNORECASE)
# Palavras de razão social de empresa (o resto, num nome, é nome de gente).
_DE_EMPRESA = re.compile(
    r"\b(ltda|s/?a|eireli|me|epp|mei|comercio|com[ée]rcio|servi[çc]os|tecnologia|digital|marketing|"
    r"conte[uú]do|produ[çc][õo]es|ag[êe]ncia|consultoria|solu[çc][õo]es|grupo|holding|cia)\b",
    re.IGNORECASE,
)


def _variantes_de_nome(nomes) -> list[str]:
    """O nome inteiro e os pedaços que aparecem soltos num texto: cada dupla
    de palavras seguidas ("Raiana Diniz" de "RAIANA DINIZ REMORINI") e, num
    nome de pessoa (sem "LTDA", "serviços"...), o primeiro nome sozinho."""
    saida: set[str] = set()
    for nome in nomes:
        if not nome or len(nome.strip()) < 4:
            continue
        saida.add(nome.strip())
        palavras = [p for p in re.split(r"[\s.,/&-]+", nome) if len(p) >= 3 and p.isalpha()]
        saida.update(f"{a} {b}" for a, b in zip(palavras, palavras[1:]))
        if palavras and not _DE_EMPRESA.search(nome) and len(palavras[0]) >= 4:
            saida.add(palavras[0])
    return sorted(saida, key=len, reverse=True)
_SEPARADOR = re.compile(r"(\r?\n|\|)")


def _tem_numero_longo(trecho: str) -> bool:
    return any(sum(c.isdigit() for c in m.group()) >= 5 for m in _NUMERO_LONGO.finditer(trecho))


def limpar_texto(texto: str | None, nomes: tuple[str, ...] | list[str] = (), trocar_nome_por: str | None = None) -> str | None:
    """`texto` sem nada pessoal, ou None se não sobra um modelo aproveitável.

    - corta os pedaços (linhas ou trechos entre "|") com dado bancário,
      documento, número longo, @ ou o nome da empresa/pessoa (`nomes`);
      com `trocar_nome_por`, o nome vira essa variável (ex.: "{prestador}")
      em vez de derrubar o pedaço;
    - "06/2025" vira {competencia_mm_aaaa};
    - se ainda sobrar data, ano ou valor em reais, é texto de uma nota só;
    - se precisou cortar algo e não sobrou nenhuma variável, também é
      texto de um trabalho específico: não vira sugestão."""
    if not texto or not texto.strip():
        return None
    nomes_limpos = _variantes_de_nome(nomes)
    partes = _SEPARADOR.split(texto)
    saida: list[str] = []
    cortou = False
    for i in range(0, len(partes), 2):
        trecho = _MES_ANO.sub("{competencia_mm_aaaa}", partes[i])
        separador = partes[i + 1] if i + 1 < len(partes) else ""
        assinatura = _ASSINATURA.match(trecho)
        if assinatura and not _VARIAVEL.fullmatch(assinatura.group(2).strip(" .!")):
            trecho = assinatura.group(1).rstrip() + (" " + trocar_nome_por if trocar_nome_por else "")
        for nome in nomes_limpos:
            if re.search(r"(?<![\w{])" + re.escape(nome) + r"(?![\w}])", trecho, re.IGNORECASE):
                if trocar_nome_por:
                    trecho = re.sub(r"(?<![\w{])" + re.escape(nome) + r"(?![\w}])", trocar_nome_por, trecho, flags=re.IGNORECASE)
                else:
                    trecho = "\0"
        sem_variaveis = _VARIAVEL.sub("", trecho)
        if "\0" in trecho or _PESSOAL.search(sem_variaveis) or _tem_numero_longo(sem_variaveis):
            cortou = cortou or bool(trecho.strip())
            continue
        if not trecho.strip():
            # linha em branco entre parágrafos: mantém uma só
            if saida and separador.strip() == "" and not saida[-1].endswith("\n\n"):
                saida.append(separador)
            continue
        saida.append(trecho + separador)
    limpo = re.sub(r"\n{3,}", "\n\n", "".join(saida)).strip(" \t\r\n|-–—:;,")
    if not limpo:
        return None
    if _DE_UMA_NOTA.search(_VARIAVEL.sub("", limpo)):
        return None
    if cortou and not _VARIAVEL.search(limpo):
        return None
    return limpo
