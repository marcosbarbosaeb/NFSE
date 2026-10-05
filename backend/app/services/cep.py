"""Conserto de CEP (05/10/2026) — "sobre falhas de CEP, vamos tentar
encontrar o CEP e corrigir no cadastro, por meio do endereço informado".

A Receita recusa a nota (E0240) quando o CEP do tomador não existe ou não é
da cidade informada. No relatório da Shopee isso aparece em 1 ou 2 notas a
cada centenas: o vendedor digitou o CEP errado. Aqui a Ana procura o CEP
certo no ViaCEP (https://viacep.com.br, público e gratuito, sem chave):

1. o CEP informado existe e é de outra cidade -> procura a rua na cidade
   informada; se não achar, fica com a cidade do CEP (quem errou foi a
   cidade);
2. o CEP não existe -> procura pela rua + cidade + UF e usa o CEP achado;
3. nada achado -> a nota sai sem o endereço do tomador (o endereço é
   opcional na NFS-e; documento e nome continuam indo).

Nunca levanta exceção de rede: sem resposta do ViaCEP, devolve None e a
nota fica como está (recusada, com o motivo na tela).
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote

import requests

from app.services.municipios import municipio_por_codigo

logger = logging.getLogger("agenteana.cep")

_URL = "https://viacep.com.br/ws"
_TIMEOUT_S = 6
# Códigos de recusa da Receita que falam do CEP/endereço do tomador.
RECUSAS_DE_CEP = ("E0240",)

_TIPOS_LOGRADOURO = {
    "r", "rua", "av", "avenida", "al", "alameda", "tv", "travessa", "rod", "rodovia", "estr", "estrada",
    "pc", "pca", "praca", "lg", "largo", "vl", "vila", "qd", "quadra", "cj", "conjunto", "est",
}


@dataclass
class Correcao:
    endereco: dict | None  # None = tirar o endereço da nota
    explicacao: str


def _norm(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", sem_acento.lower()).strip()


def _get(url: str):
    try:
        resp = requests.get(url, timeout=_TIMEOUT_S)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def consultar_cep(cep: str | None) -> dict | None:
    """{"cep", "ibge", "logradouro", "bairro", "cidade", "uf"} ou None
    (não existe). Levanta LookupError se o serviço não respondeu."""
    digitos = re.sub(r"\D", "", cep or "")
    if len(digitos) != 8:
        return None
    dados = _get(f"{_URL}/{digitos}/json/")
    if dados is None:
        raise LookupError("ViaCEP indisponível")
    if not isinstance(dados, dict) or dados.get("erro"):
        return None
    return _linha(dados)


def _linha(dados: dict) -> dict:
    return {
        "cep": re.sub(r"\D", "", str(dados.get("cep") or "")),
        "ibge": str(dados.get("ibge") or ""),
        "logradouro": dados.get("logradouro") or "",
        "bairro": dados.get("bairro") or "",
        "cidade": dados.get("localidade") or "",
        "uf": dados.get("uf") or "",
    }


def _termos_da_rua(logradouro: str | None) -> list[str]:
    """Do mais específico pro mais solto: o nome sem o tipo ("R", "Av"), e
    depois a palavra mais comprida (o ViaCEP exige 3+ letras e casa por
    trecho do nome)."""
    palavras = [p for p in _norm(logradouro).split() if not p.isdigit()]
    while palavras and palavras[0] in _TIPOS_LOGRADOURO:
        palavras = palavras[1:]
    fortes = [p for p in palavras if len(p) >= 3]
    termos: list[str] = []
    if len(" ".join(fortes)) >= 3:
        termos.append(" ".join(fortes))
    if len(fortes) > 1:
        termos.append(max(fortes, key=len))
    return termos


def buscar_por_endereco(uf: str, cidade: str, logradouro: str | None) -> list[dict]:
    """CEPs da rua naquela cidade ([] se não achou). LookupError se o
    serviço não respondeu em nenhuma tentativa."""
    if not uf or not cidade:
        return []
    respondeu = False
    for termo in _termos_da_rua(logradouro):
        dados = _get(f"{_URL}/{quote(uf)}/{quote(cidade)}/{quote(termo)}/json/")
        if dados is None:
            continue
        respondeu = True
        if isinstance(dados, list) and dados:
            return [_linha(d) for d in dados if isinstance(d, dict)]
    if not respondeu and _termos_da_rua(logradouro):
        raise LookupError("ViaCEP indisponível")
    return []


def _melhor(candidatos: list[dict], bairro: str | None) -> dict | None:
    if not candidatos:
        return None
    alvo = _norm(bairro)
    if alvo:
        for c in candidatos:
            if _norm(c["bairro"]) == alvo:
                return c
        for c in candidatos:
            b = _norm(c["bairro"])
            if b and (b in alvo or alvo in b):
                return c
    ceps = {c["cep"] for c in candidatos}
    # Sem bairro batendo: só serve se a rua tem um CEP só (senão é chute).
    return candidatos[0] if len(ceps) == 1 else None


def corrigir_endereco(endereco: dict | None) -> Correcao | None:
    """Endereço da nota (cMun, CEP, xLgr, nro, xCpl, xBairro) consertado, ou
    None quando não há o que fazer (endereço já coerente, ou o ViaCEP não
    respondeu)."""
    if not endereco or not endereco.get("cMun"):
        return None
    cmun = str(endereco["cMun"])
    municipio = municipio_por_codigo(cmun)
    try:
        do_cep = consultar_cep(endereco.get("CEP"))
        if do_cep and do_cep["ibge"] == cmun:
            return None  # CEP e cidade batem: a recusa não é por isso
        candidatos = buscar_por_endereco(municipio["uf"], municipio["nome"], endereco.get("xLgr")) if municipio else []
    except LookupError:
        logger.warning("ViaCEP não respondeu — CEP não conferido")
        return None
    candidatos = [c for c in candidatos if c["ibge"] == cmun and len(c["cep"]) == 8]
    achado = _melhor(candidatos, endereco.get("xBairro"))
    if achado:
        novo = {**endereco, "CEP": achado["cep"]}
        return Correcao(novo, f"CEP corrigido de {endereco.get('CEP') or 'vazio'} para {achado['cep']} (achado pelo endereço).")
    if do_cep and municipio_por_codigo(do_cep["ibge"]):
        novo = {**endereco, "cMun": do_cep["ibge"]}
        return Correcao(novo, f"Cidade corrigida para {do_cep['cidade']}/{do_cep['uf']}, que é a do CEP {do_cep['cep']}.")
    return Correcao(None, "Não achei o CEP certo pelo endereço — a nota foi sem o endereço do tomador.")
