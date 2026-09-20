"""
Hash de senha — Marco 10 (login multiusuário). Usa `hashlib.scrypt`
(stdlib, sem dependência nova — mesma filosofia do resto do projeto:
`app/crypto.py` também ficou com uma lib já usada em vez de somar mais
uma). scrypt é uma KDF de senha reconhecida (memory-hard, resiste bem a
ataque por GPU/ASIC), não um hash genérico tipo sha256 — não dá pra trocar
por `hashlib.sha256(senha)` sem reabrir essa decisão.

Formato armazenado: "scrypt$<salt em hex>$<hash em hex>" — o salt vai
junto do hash (é assim que verificar_senha sabe qual salt usar; salt não é
segredo, só precisa ser único por usuário, e `os.urandom` garante isso).
"""
import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1  # parâmetros do scrypt — custo computacional deliberado (não mude sem medir o impacto em login)
_TAMANHO_SALT = 16
_TAMANHO_HASH = 32


def hash_senha(senha: str) -> str:
    if not senha:
        raise ValueError("senha vazia")
    salt = os.urandom(_TAMANHO_SALT)
    derivado = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_TAMANHO_HASH)
    return f"scrypt${salt.hex()}${derivado.hex()}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, salt_hex, hash_hex = hash_armazenado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    calculado = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=len(esperado))
    return hmac.compare_digest(calculado, esperado)  # tempo constante — evita timing attack no login
