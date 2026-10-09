"""Níveis dos registros no Railway (09/10/2026): mensagem normal saía como
"error" (stderr). Ver app/registro.py."""
import configparser
import io
import sys
import json
import logging
from pathlib import Path

from app import registro


def _registrar(nivel, mensagem, exc=False):
    saida = io.StringIO()
    h = logging.StreamHandler(saida)
    h.setFormatter(registro.FormatoRailway())
    lg = logging.getLogger("teste.registro")
    lg.handlers, lg.propagate = [h], False
    lg.setLevel(logging.DEBUG)
    if exc:
        try:
            raise ValueError("quebrou")
        except ValueError:
            lg.exception(mensagem)
    else:
        lg.log(nivel, mensagem)
    return [json.loads(l) for l in saida.getvalue().splitlines()]


def test_cada_nivel_sai_com_o_rotulo_certo():
    assert _registrar(logging.INFO, "Started server process [1]")[0]["level"] == "info"
    assert _registrar(logging.WARNING, "cota do e-mail")[0]["level"] == "warn"
    assert _registrar(logging.ERROR, "falhou")[0]["level"] == "error"


def test_traceback_vai_inteiro_numa_linha_so():
    linhas = _registrar(logging.ERROR, "Exception in ASGI application", exc=True)
    assert len(linhas) == 1 and linhas[0]["level"] == "error" and "ValueError: quebrou" in linhas[0]["message"]


def test_no_railway_tudo_vai_pro_stdout_e_o_uvicorn_usa_o_mesmo_formato(monkeypatch):
    raiz = logging.getLogger()
    antes = (list(raiz.handlers), raiz.level)
    uv = {n: (list(logging.getLogger(n).handlers), logging.getLogger(n).propagate) for n in ("uvicorn", "uvicorn.error", "uvicorn.access")}
    try:
        assert registro.configurar(forcar=True)
        assert len(raiz.handlers) == 1 and raiz.handlers[0].stream is sys.stdout
        assert all(logging.getLogger(n).handlers == [] and logging.getLogger(n).propagate for n in uv)
    finally:
        raiz.handlers, _ = antes[0], raiz.setLevel(antes[1])
        for n, (hs, prop) in uv.items():
            logging.getLogger(n).handlers, logging.getLogger(n).propagate = hs, prop


def test_fora_do_railway_nao_mexe(monkeypatch):
    for v in ("LOG_JSON", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT_ID"):
        monkeypatch.delenv(v, raising=False)
    assert registro.configurar() is False


def test_migracoes_saem_no_stdout():
    ini = configparser.ConfigParser()
    ini.read(Path(__file__).resolve().parents[1] / "alembic.ini")
    assert ini["handler_console"]["args"].strip() == "(sys.stdout,)"


def test_exclusao_de_conta_pela_gestao_e_registro_de_rotina():
    fonte = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert 'logger.info("Gestão: conta %s (%s) excluída' in fonte
