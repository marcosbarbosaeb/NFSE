"""Nomenclatura Brasileira de Serviços (NBS 2.0) — lista pra busca.

Pedido do Marcos (06/10/2026): "no cadastro dos tomadores, conseguiríamos
deixar as NBS pesquisáveis?". Mesma ideia da lista de serviços
(app/services/servicos_nacionais.py): a tabela oficial fica embutida em
app/data/nbs.json (gerada por scripts/atualizar_nbs.py a partir do Anexo B
da NFS-e Nacional), sem chamada de rede.

A lista AJUDA a escolher; não é trava: um código de 9 dígitos que não está
nela continua aceito (a tabela oficial muda e a prefeitura é quem valida).
"""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_ARQUIVO = Path(__file__).resolve().parents[1] / "data" / "nbs.json"


def formatar(codigo: str) -> str:
    """101011100 -> 1.0101.11.00"""
    return f"{codigo[0]}.{codigo[1:5]}.{codigo[5:7]}.{codigo[7:]}" if len(codigo) == 9 else codigo


@lru_cache(maxsize=1)
def listar_nbs() -> list[dict]:
    dados = json.loads(_ARQUIVO.read_text(encoding="utf-8"))
    return [
        {"codigo": codigo, "descricao": descricao, "grupo": grupo, "formatado": formatar(codigo)}
        for codigo, descricao, grupo in dados["codigos"]
    ]


@lru_cache(maxsize=1)
def _por_codigo() -> dict[str, dict]:
    return {n["codigo"]: n for n in listar_nbs()}


def nbs_por_codigo(codigo: str | None) -> dict | None:
    return _por_codigo().get("".join(c for c in (codigo or "") if c.isdigit()))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def buscar_nbs(termo: str | None, limite: int = 50) -> list[dict]:
    """Por código (com ou sem pontos) ou por palavras, sem ligar pra acento."""
    termo_norm = _sem_acento((termo or "").strip())
    if not termo_norm:
        return listar_nbs()[:limite]
    digitos = "".join(c for c in termo_norm if c.isdigit())
    palavras = [p for p in termo_norm.replace(".", " ").split() if not p.isdigit()]
    achados = []
    for n in listar_nbs():
        if digitos and not n["codigo"].startswith(digitos) and digitos not in n["codigo"]:
            continue
        texto = _sem_acento(f'{n["descricao"]} {n["grupo"]}')
        if all(p in texto for p in palavras):
            achados.append(n)
    # quem começa pelo número digitado vem antes de quem só contém
    if digitos:
        achados.sort(key=lambda n: (not n["codigo"].startswith(digitos), n["codigo"]))
    return achados[:limite]
