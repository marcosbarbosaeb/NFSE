"""
Tabela de municípios (código IBGE + nome + UF) — pedido do Marcos
(23/09/2026): "tire esse negócio de código IBGE, as pessoas nem sabem que
existe isso e vai confundir".

A NFS-e continua EXIGINDO o código IBGE de 7 dígitos (cMun, cLocPrestacao
— ver app/fiscal/dps.py), então o código não some do sistema: ele só deixa
de ser digitado/visto pela pessoa. A tela pede a CIDADE (autocomplete por
nome) e guarda o código por trás; onde antes aparecia "3106200", aparece
"Belo Horizonte/MG".

Fonte: app/data/municipios.json, gerado a partir da relação oficial do
IBGE (via github.com/kelvins/municipios-brasileiros, MIT) — 5.571
municípios, formato [[codigo, nome, uf], ...]. Embutida no repositório em
vez de consultar a API do IBGE ao vivo: é pequena (~180 KB), muda
raríssimamente (último município novo: Boa Esperança do Norte/MT) e não
deixa o cadastro dependente de um serviço externo estar no ar.
"""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "municipios.json"


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento — 'sao paulo' acha 'São Paulo'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.lower().replace("'", " ").replace("-", " ").split())


@lru_cache(maxsize=1)
def _tabela() -> tuple[list[dict], dict[str, dict]]:
    brutos = json.loads(_ARQUIVO.read_text(encoding="utf-8"))
    lista = [{"codigo": c, "nome": n, "uf": uf, "_busca": _normalizar(n)} for c, n, uf in brutos]
    por_codigo = {m["codigo"]: m for m in lista}
    return lista, por_codigo


def _publico(m: dict) -> dict:
    return {"codigo": m["codigo"], "nome": m["nome"], "uf": m["uf"], "rotulo": f"{m['nome']}/{m['uf']}"}


def buscar_municipios(termo: str, uf: str | None = None, limite: int = 10) -> list[dict]:
    """Autocomplete: primeiro quem COMEÇA com o termo, depois quem só
    contém — assim 'belo' traz Belo Horizonte antes de Porto Belo. Aceita
    'cidade/UF' ou 'cidade - UF' digitado direto (ex.: 'manaus/am')."""
    termo = (termo or "").strip()
    if "/" in termo or " - " in termo:
        partes = termo.replace(" - ", "/").rsplit("/", 1)
        if len(partes[1].strip()) == 2 and not uf:
            termo, uf = partes[0], partes[1].strip()
    alvo = _normalizar(termo)
    if len(alvo) < 2:
        return []
    uf = uf.upper() if uf else None
    lista, _ = _tabela()
    comeca, contem = [], []
    for m in lista:
        if uf and m["uf"] != uf:
            continue
        if m["_busca"].startswith(alvo):
            comeca.append(m)
        elif alvo in m["_busca"]:
            contem.append(m)
    return [_publico(m) for m in (comeca + contem)[:limite]]


def municipio_por_codigo(codigo: str | None) -> dict | None:
    if not codigo:
        return None
    _, por_codigo = _tabela()
    m = por_codigo.get(str(codigo).strip())
    return _publico(m) if m else None


def rotulo_municipio(codigo: str | None) -> str | None:
    """'3106200' -> 'Belo Horizonte/MG'. Código desconhecido volta como
    veio (melhor mostrar algo do que nada), None continua None."""
    if not codigo:
        return None
    m = municipio_por_codigo(codigo)
    return m["rotulo"] if m else str(codigo)


def codigo_por_nome(nome: str | None, uf: str | None) -> str | None:
    """Resolve 'Belo Horizonte' + 'MG' -> '3106200' (match exato, sem
    acento/caixa). Usado pra conferir a sugestão da consulta de CNPJ."""
    if not nome or not uf:
        return None
    alvo = _normalizar(nome)
    lista, _ = _tabela()
    for m in lista:
        if m["uf"] == uf.upper() and m["_busca"] == alvo:
            return m["codigo"]
    return None
