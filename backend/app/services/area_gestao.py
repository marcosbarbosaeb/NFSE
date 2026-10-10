"""Gestão num subdomínio próprio (2026.10.7, decisão do Marcos em 10/10/2026).

Com `GESTAO_HOST` (ex.: gestao.agenteana.com.br) preenchida:
- as rotas da Gestão e das parceiras (`exigir_gestor`/`exigir_admin`) só
  respondem nesse host — no app das notas elas dão 404;
- no app das notas, /app/gestao leva para o subdomínio e o menu não mostra a
  Gestão; no subdomínio, qualquer outra tela leva para /app/gestao;
- o login é separado: o cookie de sessão é de cada host.

Sem a variável, tudo continua como antes (Gestão dentro do app).
"""
from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request

from app.config import get_settings


def host_gestao() -> str:
    return (getattr(get_settings(), "gestao_host", "") or "").strip().lower().rstrip("/")


def separada() -> bool:
    return bool(host_gestao())


def host_do_pedido(request: Request) -> str:
    return (request.url.hostname or "").lower()


def na_gestao(request: Request) -> bool:
    return separada() and host_do_pedido(request) == host_gestao()


def fora_da_gestao(request: Request) -> bool:
    """Gestão separada e o pedido veio do app das notas (ou de outro host)."""
    return separada() and not na_gestao(request)


def url(caminho: str = "/app/gestao") -> str:
    esquema = "https" if get_settings().app_base_url.startswith("https://") else (urlparse(get_settings().app_base_url).scheme or "https")
    return f"{esquema}://{host_gestao()}{caminho}"


# Telas que existem no subdomínio da Gestão (fora do /app): entrar e as páginas legais.
TELAS_NA_GESTAO = {"entrar", "confirmar-email", "privacidade", "termos"}
