"""
Lista oficial de códigos de tributação nacional (cTribNac) da NFS-e —
pedido do Marcos (28/09/2026): "coloque a relação de código com um
pesquisar para a pessoa buscar o código e não criar códigos novos".

Fonte: Anexo B (Lista de Serviços Nacional) da documentação técnica da
NFS-e Nacional (gov.br/nfse), embutido em app/data/servicos_nacionais.json
— mesmo padrão da tabela de municípios (app/services/municipios.py): sem
chamada de rede em tempo de execução.
"""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_ARQUIVO = Path(__file__).resolve().parents[1] / "data" / "servicos_nacionais.json"


@lru_cache(maxsize=1)
def _dados() -> dict:
    return json.loads(_ARQUIVO.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def listar_servicos() -> list[dict]:
    grupos = _dados()["grupos"]
    return [
        {"codigo": codigo, "descricao": descricao, "grupo": grupos.get(str(item), "")}
        for codigo, descricao, item in _dados()["codigos"]
    ]


@lru_cache(maxsize=1)
def _por_codigo() -> dict[str, dict]:
    return {s["codigo"]: s for s in listar_servicos()}


def normalizar_codigo(codigo: str | None) -> str:
    """Aceita "17.06.01", "170601" ou "17061" (sem o zero à esquerda, como a
    planilha oficial guarda) e devolve sempre 6 dígitos."""
    digitos = "".join(c for c in (codigo or "") if c.isdigit())
    return digitos.zfill(6) if digitos else ""


def servico_por_codigo(codigo: str | None) -> dict | None:
    return _por_codigo().get(normalizar_codigo(codigo))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def buscar_servicos(termo: str, limite: int = 30) -> list[dict]:
    termo_norm = _sem_acento(termo.strip())
    if not termo_norm:
        return listar_servicos()[:limite]
    digitos = "".join(c for c in termo_norm if c.isdigit())
    palavras = [p for p in termo_norm.replace(".", " ").split() if not p.isdigit()]
    achados = []
    for s in listar_servicos():
        if digitos and digitos not in s["codigo"]:
            continue
        texto = _sem_acento(f'{s["descricao"]} {s["grupo"]}')
        if all(p in texto for p in palavras):
            achados.append(s)
        if len(achados) >= limite:
            break
    return achados
