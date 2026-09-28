"""Limite de uso por IP nas rotas públicas (revisão de segurança,
28/09/2026): cadastro, login, reenvio de confirmação, simulação e
formulário de suporte podiam ser chamados sem parar — spam de e-mail
(gastando a cota do Resend), força bruta de senha, contas de simulação aos
milhares.

Em memória, por processo: o app roda num processo só no Railway. Se um dia
tiver vários, trocar por Redis.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class Limitador:
    def __init__(self) -> None:
        self._eventos: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, chave: str, maximo: int, janela_s: int) -> bool:
        agora = time.monotonic()
        with self._lock:
            fila = self._eventos[chave]
            while fila and agora - fila[0] > janela_s:
                fila.popleft()
            if len(fila) >= maximo:
                return False
            fila.append(agora)
            if len(self._eventos) > 50_000:  # não deixa crescer sem fim
                self._eventos.clear()
            return True

    def limpar(self) -> None:
        with self._lock:
            self._eventos.clear()


limitador = Limitador()


def ip_do_cliente(request: Request) -> str:
    """O Railway põe o IP real no fim do X-Forwarded-For (o começo pode ter
    sido inventado pelo cliente)."""
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def limite(nome: str, maximo: int, janela_s: int):
    """Dependência do FastAPI: `dependencies=[Depends(limite("login", 20, 600))]`."""

    def _dep(request: Request) -> None:
        if not limitador.permitir(f"{nome}:{ip_do_cliente(request)}", maximo, janela_s):
            raise HTTPException(status_code=429, detail="Muitas tentativas seguidas. Espere alguns minutos e tente de novo.")

    return _dep
