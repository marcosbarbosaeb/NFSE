"""
Carregamento de certificado A1 (.pfx) e extração de PEM temporário para mTLS.

A extração cert+key em arquivos .pem temporários estava copiada de forma
praticamente idêntica em integracao/submit_dps.py, consultar_dps.py,
consultar_nfse.py e cancelar_nfse.py (cada um com seu próprio
`tempfile.mkdtemp` sem limpeza automática). Consolidado aqui como um
context manager que limpa o diretório temporário ao sair — os originais
nunca limpavam.

NADA aqui decide onde o .pfx/senha ficam guardados em repouso — isso é
`certificado.pfx_criptografado`/`senha_criptografada` no banco (ver
app/models.py e a nota sobre KMS no Marco 4). Este módulo só sabe abrir um
.pfx já em mãos (bytes ou path) e devolver algo utilizável pro `requests`.
"""
import contextlib
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)


def carregar_pfx(pfx: bytes | str, senha: str):
    """Aceita bytes do .pfx ou um path. Retorna (private_key, cert)."""
    dados = pfx if isinstance(pfx, bytes) else Path(pfx).read_bytes()
    private_key, cert, _extra = pkcs12.load_key_and_certificates(dados, senha.encode("utf-8"))
    if private_key is None or cert is None:
        raise ValueError("Não foi possível extrair chave privada/certificado do .pfx — senha errada?")
    return private_key, cert


@contextlib.contextmanager
def pem_temporario(private_key, cert):
    """Grava cert.pem/key.pem num diretório temporário (para `requests`
    fazer mTLS, que exige arquivos em disco) e apaga tudo ao sair do `with`.

    Uso:
        private_key, cert = carregar_pfx(pfx_bytes, senha)
        with pem_temporario(private_key, cert) as (cert_path, key_path):
            requests.post(url, cert=(cert_path, key_path), ...)
    """
    tmpdir = tempfile.mkdtemp(prefix="nfse_cert_")
    try:
        cert_path = str(Path(tmpdir) / "cert.pem")
        key_path = str(Path(tmpdir) / "key.pem")
        Path(cert_path).write_bytes(cert.public_bytes(Encoding.PEM))
        Path(key_path).write_bytes(
            private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
        yield cert_path, key_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
