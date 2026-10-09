"""Registros (logs) com o nível certo no Railway (09/10/2026).

O Railway marca como "error" tudo o que sai no stderr. Sem configuração, o
Python e o uvicorn escrevem lá até mensagem normal ("Started server
process", "Application startup complete", o alembic, e avisos como "conta
... excluída"), e cada linha de um traceback virava um "error" separado.

Aqui (só quando roda no Railway, ou com LOG_JSON=1): uma linha JSON por
registro no stdout, com `level` (debug/info/warn/error) e `message` — o
formato estruturado que o Railway lê. O traceback vai inteiro dentro da
mensagem do próprio erro. Erro de verdade continua "error"; o resto não.
Fora do Railway (desenvolvimento e testes) nada muda.
"""
from __future__ import annotations

import json
import logging
import os
import sys

_NIVEIS = {logging.DEBUG: "debug", logging.INFO: "info", logging.WARNING: "warn", logging.ERROR: "error", logging.CRITICAL: "error"}


class FormatoRailway(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        mensagem = registro.getMessage()
        if registro.exc_info:
            mensagem += "\n" + self.formatException(registro.exc_info)
        nivel = _NIVEIS.get(registro.levelno) or ("error" if registro.levelno >= logging.ERROR else "info")
        return json.dumps({"level": nivel, "message": mensagem, "logger": registro.name}, ensure_ascii=False)


def ligado() -> bool:
    return bool(os.environ.get("LOG_JSON") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_ENVIRONMENT_ID"))


def configurar(forcar: bool = False) -> bool:
    """Liga o formato do Railway. Devolve se ligou."""
    if not (forcar or ligado()):
        return False
    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(FormatoRailway())
    raiz = logging.getLogger()
    raiz.handlers = [saida]
    raiz.setLevel(logging.INFO)
    # uvicorn traz handlers próprios (stderr): passam a usar o da raiz
    for nome in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(nome)
        lg.handlers = []
        lg.propagate = True
    return True
