"""
Fixtures da suíte de testes da biblioteca fiscal (app/fiscal/) — Marco 3.

Dá acesso, via sys.path, ao integracao/ original (onde FORNECEDORES e os
scripts fonte ainda moram intactos) — usado pelos testes de equivalência
que comparam a saída da nova biblioteca com a dos scripts originais.

Desde a preparação pra deploy (Marco 10+), `integracao/` mora DENTRO deste
mesmo repositório (nfse-saas/integracao/ — só o código, sem os arquivos de
saída reais da Raiana, que nunca foram versionados de propósito), então o
caminho é relativo ao repo e funciona em qualquer máquina que clonar o
projeto, não só nesta sessão.
"""
import datetime
import sys
import uuid
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

INTEGRACAO_DIR = Path(__file__).resolve().parents[2] / "integracao"
if str(INTEGRACAO_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRACAO_DIR))

from app.database import SessionLocal, definir_prestador_atual  # noqa: E402
from app.models import Prestador, PrestadorTomador, Tomador  # noqa: E402


@pytest.fixture(scope="session")
def certificado_teste(tmp_path_factory):
    """Mesmo certificado autoassinado descartável usado em
    integracao/tests/conftest.py — nunca o certificado real da Raiana."""
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
    return {"path": str(pfx_path), "pfx_bytes": pfx_bytes, "senha": "senha-teste", "private_key": key, "cert": cert}


@pytest.fixture
def db():
    """Sessão contra o Postgres local de dev (nfse_saas), pelo role de
    RUNTIME da app (nfse_dev — sujeito a RLS, sem bypass). Rollback no fim
    de cada teste: nenhum teste de integração deixa lixo no banco."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def prestador_teste(db):
    """Cria um Prestador descartável pra testes que precisam de uma linha
    real (certificado, prestador_tomador, ...). Some no rollback do fixture
    `db` — nunca fica no banco entre execuções de teste."""
    prestador_id = uuid.uuid4()
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        id=prestador_id,
        cpf_cnpj="00000000000191",
        razao_social="PRESTADOR DE TESTE (nunca deveria sobreviver a um teste)",
        cod_municipio="3106200",
    )
    db.add(prestador)
    db.flush()
    return prestador


@pytest.fixture
def vinculo_teste(db, prestador_teste):
    """Um vínculo (fornecedor) descartável, com um tomador próprio — usado
    tanto pelos testes do painel (Marco 5) quanto do motor de emissão
    (Marco 6). Some no rollback do fixture `db`."""
    tomador = Tomador(
        id=uuid.uuid4(), cnpj="11222333000181", razao_social="TOMADOR DE TESTE LTDA",
        cod_municipio="3550308", cep="01311000", logradouro="Av Teste", numero="100", bairro="Centro",
    )
    db.add(tomador)
    db.flush()

    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador.id,
        apelido="Fornecedor Teste", cod_local_prestacao=prestador_teste.cod_municipio,
        cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="Comissão de teste - {competencia_mm_aaaa}",
        serie="1", requer_revisao=True, ativo=True,
    )
    db.add(vinculo)
    db.flush()
    return vinculo
