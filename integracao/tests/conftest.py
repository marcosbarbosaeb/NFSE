"""
Fixtures compartilhadas dos testes de regressão fiscal (Marco 2 do plano).

Objetivo do Marco 2: travar o comportamento HOJE correto de build_dps.py e
cancelar_nfse.py (já testados manualmente contra produção/homologação real)
antes do Marco 3 desacoplar esse código pra uma biblioteca importável
data-driven (lendo do Postgres em vez de FORNECEDORES hardcoded). Se o
refactor mudar um byte que importe no XML fiscal, esses testes quebram.

Nenhum teste aqui toca rede nem exige o certificado A1 real da Raiana: a
assinatura é testada com um certificado autoassinado descartável, gerado em
memória pela fixture `certificado_teste`. O que se verifica é a MECÂNICA da
assinatura (algoritmo, canonicalização, ausência de prefixo de namespace —
tudo isso foi descoberto empiricamente contra a API real e documentado em
sign_dps.py/cancelar_nfse.py) e a validade estrutural do XML contra o XSD
oficial, não a aceitação pela Sefin em si.
"""
import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


@pytest.fixture(scope="session")
def certificado_teste(tmp_path_factory):
    """Gera um par de chaves RSA + certificado autoassinado e um .pfx
    descartável, só pra exercitar sign_dps.py/cancelar_nfse.py sem precisar
    do certificado real da Raiana (que não existe neste sandbox)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TESTE REGRESSAO NFSE")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"teste",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"senha-teste"),
    )
    pfx_path = tmp_path_factory.mktemp("cert") / "teste.pfx"
    pfx_path.write_bytes(pfx_bytes)

    return {"path": str(pfx_path), "senha": "senha-teste", "private_key": key, "cert": cert}
