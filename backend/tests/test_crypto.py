"""app.crypto — cifra/decifra em repouso do certificado (Marco 4)."""
import pytest

from app.crypto import (
    ChaveInvalidaError,
    DescriptografiaFalhouError,
    criptografar,
    descriptografar,
    gerar_chave_local,
)


def test_roundtrip():
    chave = gerar_chave_local()
    original = b"conteudo binario qualquer, inclusive um .pfx de verdade \x00\x01\xff"
    cifrado = criptografar(original, chave)
    assert cifrado != original
    assert descriptografar(cifrado, chave) == original


def test_chave_invalida_recusada():
    with pytest.raises(ChaveInvalidaError):
        criptografar(b"dado", "isso-nao-e-uma-chave-fernet-valida")


def test_chave_errada_na_descriptografia_falha_alto():
    chave1 = gerar_chave_local()
    chave2 = gerar_chave_local()
    cifrado = criptografar(b"segredo", chave1)
    with pytest.raises(DescriptografiaFalhouError):
        descriptografar(cifrado, chave2)


def test_duas_chaves_diferentes_produzem_ciphertexts_diferentes():
    dado = b"mesmo conteudo"
    c1 = criptografar(dado, gerar_chave_local())
    c2 = criptografar(dado, gerar_chave_local())
    assert c1 != c2  # nonce/IV do Fernet garante isso mesmo com a mesma chave, mais ainda com chaves diferentes
