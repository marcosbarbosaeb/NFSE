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
    r"|\bpo\s*\d|pedido de compra|\bnf\s*\d|\bjob\b|projeto\s*:|@\w|\bid\b",
    re.IGNORECASE,
)
_NUMERO_LONGO = re.compile(r"\d[\d.\-/ ]{3,}\d")  # 5+ dígitos seguidos (com ou sem pontuação)
_MES_ANO = re.compile(r"\b(0[1-9]|1[0-2])\s*/\s*20\d\d\b")
# Sobrou data, ano ou valor: é texto de UMA nota, não modelo.
_DE_UMA_NOTA = re.compile(r"\b(19|20)\d\d\b|R\$|\b\d{1,2}/\d{1,2}\b")
_VARIAVEL = re.compile(r"\{[a-z_]+\}")
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
    nomes_limpos = sorted({n.strip() for n in nomes if n and len(n.strip()) >= 4}, key=len, reverse=True)
    partes = _SEPARADOR.split(texto)
    saida: list[str] = []
    cortou = False
    for i in range(0, len(partes), 2):
        trecho = _MES_ANO.sub("{competencia_mm_aaaa}", partes[i])
        separador = partes[i + 1] if i + 1 < len(partes) else ""
        for nome in nomes_limpos:
            if re.search(re.escape(nome), trecho, re.IGNORECASE):
                if trocar_nome_por:
                    trecho = re.sub(re.escape(nome), trocar_nome_por, trecho, flags=re.IGNORECASE)
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
