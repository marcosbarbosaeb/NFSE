"""
Consulta pública de CNPJ — Marco 16, item 2 do pedido do Marcos: "ninguém
sabe o número do IBGE do município, o ideal seria [a pessoa] digitar o
CNPJ e a gente puxar tudo".

Usa a BrasilAPI (https://brasilapi.com.br/api/cnpj/v1/{cnpj}) — espelho
público e gratuito dos dados abertos de CNPJ da Receita Federal, sem chave
nem contrato (ao contrário do Integra Contador da SERPRO, que é pago e
teria sentido só pra alguma coisa como o item 5 — geração de DAS, não pra
uma simples consulta de cadastro). NÃO precisa de credencial pra trocar
depois (diferente do padrão Resend/Stripe do Marco 15).

IMPORTANTE (ver docstring do módulo de e-mail pra um paralelo): esta
sandbox tem o egress bloqueado por política da organização pra qualquer
host fora de uma lista curta (registros de pacote, API da Anthropic) — não
dá pra testar esta chamada de rede de verdade daqui. Os testes deste
módulo usam `requests.get` mockado; a validação ao vivo só acontece quando
isto estiver rodando num ambiente com rede aberta.

Ponto de atenção fiscal (por isso o autopreenchimento é só um PONTO DE
PARTIDA, nunca a palavra final): o campo de município que a BrasilAPI
devolve vem dos dados abertos da Receita Federal, que usa uma tabela de
códigos de município PRÓPRIA (às vezes chamada de "código TOM"), não
necessariamente idêntica ao código IBGE de 7 dígitos que a nota fiscal
nacional exige (`cMun` no XML da DPS — ver app/fiscal/dps.py). Sem
conseguir validar isso ao vivo contra a tabela oficial do IBGE, o campo
`cod_municipio_sugerido` devolvido aqui é só uma SUGESTÃO pré-preenchida
num campo que continua editável — o cadastro público nunca aceita esse
valor sem a pessoa poder conferir/corrigir antes de enviar.
"""
from dataclasses import dataclass

import requests

_URL_BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
_TIMEOUT_SEGUNDOS = 8


class CnpjInvalidoError(Exception):
    """CNPJ não tem 14 dígitos — nem vale a pena chamar a API externa."""


class CnpjNaoEncontradoError(Exception):
    """A Receita/BrasilAPI não conhece esse CNPJ (404 de verdade, não
    problema de rede)."""


class ConsultaCnpjIndisponivelError(Exception):
    """Rede fora do ar, timeout, ou a API respondeu algo inesperado — nunca
    deve travar o cadastro: quem chama isto cai pro preenchimento manual."""


@dataclass
class DadosCnpj:
    razao_social: str
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cep: str | None
    municipio: str
    uf: str
    cod_municipio_sugerido: str | None
    situacao_cadastral: str | None


def _limpar_cnpj(cnpj: str) -> str:
    return "".join(c for c in cnpj if c.isdigit())


def consultar_cnpj(cnpj: str) -> DadosCnpj:
    cnpj_limpo = _limpar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        raise CnpjInvalidoError("CNPJ precisa ter 14 dígitos.")

    try:
        resp = requests.get(_URL_BRASILAPI.format(cnpj=cnpj_limpo), timeout=_TIMEOUT_SEGUNDOS)
    except requests.RequestException as exc:
        raise ConsultaCnpjIndisponivelError(f"Não foi possível consultar o CNPJ agora: {exc}") from exc

    if resp.status_code == 404:
        raise CnpjNaoEncontradoError(f"CNPJ {cnpj_limpo} não encontrado.")
    if resp.status_code != 200:
        raise ConsultaCnpjIndisponivelError(f"Consulta de CNPJ respondeu {resp.status_code} — tente de novo em instantes.")

    try:
        dados = resp.json()
    except ValueError as exc:
        raise ConsultaCnpjIndisponivelError("Resposta da consulta de CNPJ veio num formato inesperado.") from exc

    # Município: a BrasilAPI costuma trazer tanto o código quanto o nome —
    # cobrimos as variações de nome de campo já vistas em integrações
    # parecidas (ver comentário no topo do arquivo) sem quebrar se algum
    # deles não vier.
    cod_municipio = dados.get("codigo_municipio_ibge") or dados.get("codigo_municipio")
    cod_municipio_str = str(cod_municipio) if cod_municipio else None
    if cod_municipio_str and not cod_municipio_str.isdigit():
        cod_municipio_str = None

    return DadosCnpj(
        razao_social=(dados.get("razao_social") or dados.get("nome") or "").strip(),
        logradouro=dados.get("logradouro") or None,
        numero=dados.get("numero") or None,
        complemento=dados.get("complemento") or None,
        bairro=dados.get("bairro") or None,
        cep=(dados.get("cep") or "").replace("-", "").replace(".", "") or None,
        municipio=(dados.get("municipio") or "").strip(),
        uf=(dados.get("uf") or "").strip().upper(),
        cod_municipio_sugerido=cod_municipio_str,
        situacao_cadastral=dados.get("descricao_situacao_cadastral"),
    )
