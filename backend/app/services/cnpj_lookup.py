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
import logging
from dataclasses import dataclass

import requests

from app.services.municipios import codigo_por_nome, municipio_por_codigo

_URL_BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
_TIMEOUT_SEGUNDOS = 8
log = logging.getLogger(__name__)


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
    # 07/10/2026 — "completar os dados da empresa pelo CNPJ": o que mais a
    # Receita sabe. `regime` já vem no código da nota (opSimpNac): "2" MEI,
    # "3" ME/EPP do Simples, "1" não optante; None quando a Receita não diz.
    nome_fantasia: str | None = None
    regime: str | None = None
    telefone: str | None = None
    email: str | None = None


def _limpar_cnpj(cnpj: str) -> str:
    return "".join(c for c in cnpj if c.isdigit())


def _no_formato_brasilapi_cnpjws(d: dict) -> dict:
    """CNPJ.ws (publica.cnpj.ws) → mesmos nomes de campo da BrasilAPI."""
    est = d.get("estabelecimento") or {}
    simples = d.get("simples") or {}
    cidade, estado = est.get("cidade") or {}, est.get("estado") or {}
    sim = lambda v: True if str(v).lower() == "sim" else False if str(v).lower() in ("não", "nao") else None
    logradouro = " ".join(x for x in (est.get("tipo_logradouro"), est.get("logradouro")) if x) or None
    return {
        "razao_social": d.get("razao_social"),
        "nome_fantasia": est.get("nome_fantasia"),
        "logradouro": logradouro,
        "numero": est.get("numero"),
        "complemento": est.get("complemento"),
        "bairro": est.get("bairro"),
        "cep": est.get("cep"),
        "municipio": cidade.get("nome"),
        "uf": estado.get("sigla"),
        "codigo_municipio_ibge": cidade.get("ibge_id"),
        "descricao_situacao_cadastral": (est.get("situacao_cadastral") or "").upper() or None,
        "opcao_pelo_mei": sim(simples.get("mei")) if simples else None,
        "opcao_pelo_simples": sim(simples.get("simples")) if simples else None,
        "ddd_telefone_1": f"{est.get('ddd1') or ''}{est.get('telefone1') or ''}",
        "email": est.get("email"),
    }


def _no_formato_brasilapi_receitaws(d: dict) -> dict:
    """ReceitaWS → mesmos nomes de campo da BrasilAPI. Ela responde 200 com
    status "ERROR" quando não conhece o CNPJ."""
    if str(d.get("status", "")).upper() == "ERROR":
        raise CnpjNaoEncontradoError(d.get("message") or "CNPJ não encontrado.")
    optante = lambda chave: (d.get(chave) or {}).get("optante") if isinstance(d.get(chave), dict) else None
    return {
        "razao_social": d.get("nome"),
        "nome_fantasia": d.get("fantasia"),
        "logradouro": d.get("logradouro"),
        "numero": d.get("numero"),
        "complemento": d.get("complemento"),
        "bairro": d.get("bairro"),
        "cep": d.get("cep"),
        "municipio": d.get("municipio"),
        "uf": d.get("uf"),
        "descricao_situacao_cadastral": d.get("situacao"),
        "opcao_pelo_mei": optante("simei"),
        "opcao_pelo_simples": optante("simples"),
        "ddd_telefone_1": (d.get("telefone") or "").split("/")[0],
        "email": d.get("email"),
    }


# 08/10/2026 — no ambiente de teste a BrasilAPI passou a recusar a consulta
# ("Não deu pra consultar o CNPJ agora", inclusive pro CNPJ da Shopee), enquanto
# a produção respondia normal: o bloqueio é por endereço de saída do servidor.
# Por isso há outras fontes públicas e gratuitas dos mesmos dados abertos da
# Receita, tentadas em ordem só quando a anterior está FORA (um "não existe"
# de verdade, 404, encerra a busca).
_FONTES = (
    ("BrasilAPI", _URL_BRASILAPI, None),
    ("CNPJ.ws", "https://publica.cnpj.ws/cnpj/{cnpj}", _no_formato_brasilapi_cnpjws),
    ("ReceitaWS", "https://receitaws.com.br/v1/cnpj/{cnpj}", _no_formato_brasilapi_receitaws),
)
_CABECALHOS = {"Accept": "application/json", "User-Agent": "AgenteAna/1.0 (+https://agenteana.com.br)"}


def _buscar(nome: str, url: str, converter) -> dict:
    try:
        resp = requests.get(url, timeout=_TIMEOUT_SEGUNDOS, headers=_CABECALHOS)
    except requests.RequestException as exc:
        raise ConsultaCnpjIndisponivelError(f"{nome}: sem resposta ({type(exc).__name__})") from exc
    if resp.status_code == 404:
        raise CnpjNaoEncontradoError("CNPJ não encontrado.")
    if resp.status_code != 200:
        raise ConsultaCnpjIndisponivelError(f"{nome}: respondeu {resp.status_code}")
    try:
        dados = resp.json()
    except ValueError as exc:
        raise ConsultaCnpjIndisponivelError(f"{nome}: resposta fora do formato") from exc
    if not isinstance(dados, dict):
        raise ConsultaCnpjIndisponivelError(f"{nome}: resposta fora do formato")
    return converter(dados) if converter else dados


def consultar_cnpj(cnpj: str) -> DadosCnpj:
    cnpj_limpo = _limpar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        raise CnpjInvalidoError("CNPJ precisa ter 14 dígitos.")

    falhas: list[str] = []
    dados = None
    for nome, url, converter in _FONTES:
        try:
            dados = _buscar(nome, url.format(cnpj=cnpj_limpo), converter)
            break
        except CnpjNaoEncontradoError:
            raise CnpjNaoEncontradoError(f"CNPJ {cnpj_limpo} não encontrado.")
        except ConsultaCnpjIndisponivelError as exc:
            falhas.append(str(exc))
    if dados is None:
        # o motivo vai pro log do servidor (pra saber qual fonte caiu e por quê)
        log.warning("consulta de CNPJ indisponível: %s", "; ".join(falhas))
        raise ConsultaCnpjIndisponivelError("Não foi possível consultar o CNPJ agora — tente de novo em instantes.")

    # Município: a BrasilAPI costuma trazer tanto o código quanto o nome —
    # cobrimos as variações de nome de campo já vistas em integrações
    # parecidas (ver comentário no topo do arquivo) sem quebrar se algum
    # deles não vier.
    cod_municipio = dados.get("codigo_municipio_ibge") or dados.get("codigo_municipio")
    cod_municipio_str = str(cod_municipio) if cod_municipio else None
    if cod_municipio_str and not cod_municipio_str.isdigit():
        cod_municipio_str = None
    # Confere contra a tabela oficial embutida (app/services/municipios.py):
    # um código que não existe nela é descartado e trocado pelo resolvido a
    # partir de nome+UF — a tela não mostra mais o código pra pessoa
    # corrigir, então ele precisa vir certo daqui.
    if not municipio_por_codigo(cod_municipio_str):
        cod_municipio_str = codigo_por_nome(dados.get("municipio"), dados.get("uf"))

    mei, simples = dados.get("opcao_pelo_mei"), dados.get("opcao_pelo_simples")
    regime = "2" if mei is True else "3" if simples is True else "1" if simples is False else None
    telefone = "".join(c for c in str(dados.get("ddd_telefone_1") or "") if c.isdigit()) or None

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
        nome_fantasia=(dados.get("nome_fantasia") or "").strip() or None,
        regime=regime,
        telefone=telefone,
        email=(dados.get("email") or "").strip().lower() or None,
    )
