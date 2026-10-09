"""Formato de e-mail (09/10/2026).

Em 05/10 o aviso de fim de lote não saiu: o serviço de e-mail (Resend)
recusou com 422 "Invalid `to` field". A partir daqui o formato é conferido
num lugar só — na entrada (tomador, vendedor do relatório, conta) e antes de
qualquer envio — e e-mail inválido vira aviso claro, nunca exceção solta.

A regra é a que o provedor aceita na prática: parte local em ASCII (letras,
números e . _ % + - ' etc.), um @, e um domínio com ponto e terminação de
pelo menos duas letras. Sem espaço, acento, vírgula, ponto no começo/fim
nem dois pontos seguidos.
"""
from __future__ import annotations

import re

_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_DOMINIO = r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}"
_EMAIL = re.compile(rf"^{_LOCAL}@{_DOMINIO}$")
_SEPARADORES = re.compile(r"[,;\s]+")

DICA = "Confira se tem @, o domínio completo (ex.: gmail.com) e nada de espaço ou acento."


def normalizar(texto: str | None) -> str:
    """" Fulano <A@X.COM> " -> "a@x.com"; "mailto:a@x.com" -> "a@x.com"."""
    t = (texto or "").strip()
    m = re.search(r"<([^<>]+)>", t)
    if m:
        t = m.group(1)
    if t.lower().startswith("mailto:"):
        t = t[7:]
    return t.strip().rstrip(".").lower()


def email_valido(texto: str | None) -> bool:
    e = normalizar(texto)
    return 3 <= len(e) <= 254 and bool(_EMAIL.match(e))


def separar(texto: str | list[str] | None) -> tuple[list[str], list[str]]:
    """Uma lista digitada ("a@x.com; b@y.com, errado") -> (válidos sem
    repetir, inválidos como foram escritos)."""
    if isinstance(texto, list):
        partes = [p for item in texto for p in _SEPARADORES.split(item or "")]
    else:
        partes = _SEPARADORES.split(texto or "")
    validos: list[str] = []
    invalidos: list[str] = []
    for parte in partes:
        if not parte.strip():
            continue
        if email_valido(parte):
            e = normalizar(parte)
            if e not in validos:
                validos.append(e)
        else:
            invalidos.append(parte.strip())
    return validos, invalidos


def frase_invalido(email: str, onde: str | None = None) -> str:
    return f"“{email}” não é um e-mail válido{f' ({onde})' if onde else ''}. {DICA}"


def conferir_lista(texto: str | None, onde: str | None = None) -> str | None:
    """Pra validar campo de cadastro: devolve o texto como veio (ou None se
    vazio) e levanta ValueError com a frase pra pessoa se algum não vale."""
    if texto is None or not texto.strip():
        return None if texto is None else texto
    _, invalidos = separar(texto)
    if invalidos:
        raise ValueError(frase_invalido(invalidos[0], onde))
    return texto


def conferir_um(texto: str | None, onde: str | None = None) -> str | None:
    if texto is None or not texto.strip():
        return texto
    if not email_valido(texto):
        raise ValueError(frase_invalido(texto.strip(), onde))
    return texto
