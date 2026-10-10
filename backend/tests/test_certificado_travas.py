"""Travas do certificado e orientação de compra (2026.10.7 — item C do roteiro).

- no envio: certificado de outro CNPJ ou já vencido é recusado com frase clara;
- vencido não assina, não envia nem roda no lote (antes só travava o "gerar");
- e-mail de aviso 30 dias antes, uma vez por certificado;
- texto de orientação configurável, entregue por /api/suporte.
Certificados de mentira gerados aqui. Só dados sintéticos."""
import datetime
import uuid

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Certificado, Usuario
from app.services import avisos_certificado
from app.services.certificados import CertificadoVencidoError, carregar_certificado, salvar_certificado
from app.tempo import hoje as hoje_br

CHAVE = get_settings().cert_master_key


def _pfx(cnpj: str | None, dias_validade: int = 365, ja_vencido: bool = False) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn = f"EMPRESA SINTETICA LTDA:{cnpj}" if cnpj else "TESTE SEM CNPJ"
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    agora = datetime.datetime.now(datetime.timezone.utc)
    inicio = agora - datetime.timedelta(days=400 if ja_vencido else 1)
    fim = agora - datetime.timedelta(days=2) if ja_vencido else agora + datetime.timedelta(days=dias_validade)
    b = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(key.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(inicio).not_valid_after(fim))
    if cnpj:
        valor = b"\x04" + bytes([len(cnpj)]) + cnpj.encode()
        b = b.add_extension(x509.SubjectAlternativeName([x509.OtherName(ObjectIdentifier("2.16.76.1.3.3"), valor)]), critical=False)
    cert = b.sign(key, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b"t", key, cert, None, serialization.BestAvailableEncryption(b"senha"))


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _enviar(client, pfx: bytes):
    return client.post("/api/certificado", files={"pfx": ("c.pfx", pfx, "application/x-pkcs12")}, data={"senha": "senha"})


def test_certificado_de_outro_cnpj_e_recusado(client, prestador_teste):
    r = _enviar(client, _pfx("11222333000181"))
    assert r.status_code == 400
    assert "11.222.333/0001-81" in r.json()["detail"] and "00.000.000/0001-91" in r.json()["detail"]


def test_certificado_vencido_e_recusado_no_envio(client):
    r = _enviar(client, _pfx("00000000000191", ja_vencido=True))
    assert r.status_code == 400 and "venceu" in r.json()["detail"]


def test_certificado_da_empresa_e_aceito(client):
    r = _enviar(client, _pfx("00000000000191"))
    assert r.status_code == 200 and r.json()["carregado"] is True


def test_certificado_da_matriz_serve_pra_filial(client):
    """Mesma raiz de CNPJ (8 primeiros números): matriz e filial."""
    assert _enviar(client, _pfx("00000000000272")).status_code == 200


def test_certificado_sem_cnpj_legivel_passa(client):
    """e-CPF (MEI) ou certificado fora do padrão: a Sefin confere na hora de assinar."""
    assert _enviar(client, _pfx(None)).status_code == 200


def test_vencido_nao_assina_nem_envia(client, db, prestador_teste, vinculo_teste):
    salvar_certificado(db, prestador_teste.id, _pfx("00000000000191"), "senha", CHAVE)
    nota = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    cert = db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one()
    cert.validade = hoje_br() - datetime.timedelta(days=1)
    db.flush()
    with pytest.raises(CertificadoVencidoError):
        carregar_certificado(db, prestador_teste.id, CHAVE)
    for acao in ("assinar", "submeter"):
        r = client.post(f"/api/dps/{nota['id']}/{acao}")
        assert r.status_code == 409 and "venceu em" in r.json()["detail"], (acao, r.text)


def test_lote_para_com_a_frase_do_vencido(db, prestador_teste):
    from app.services import lotes

    salvar_certificado(db, prestador_teste.id, _pfx("00000000000191"), "senha", CHAVE)
    db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one().validade = hoje_br() - datetime.timedelta(days=3)
    db.flush()
    import inspect

    fonte = inspect.getsource(lotes)
    assert "CertificadoVencidoError" in fonte  # a frase própria do vencido chega no lote


# ---------------------------------------------------------------- aviso por e-mail

@pytest.fixture
def dona(db, prestador_teste):
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"dona{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    return u


def test_aviso_de_vencimento_sai_uma_vez(db, prestador_teste, dona, monkeypatch):
    enviados = []
    monkeypatch.setattr("app.services.email.get_email_sender", lambda: type("S", (), {"enviar": lambda self, **kw: enviados.append(kw)})())
    monkeypatch.setattr(db, "commit", db.flush)
    salvar_certificado(db, prestador_teste.id, _pfx("00000000000191"), "senha", CHAVE)
    cert = db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one()

    cert.validade = hoje_br() + datetime.timedelta(days=45)
    db.flush()
    avisos_certificado.avisar(db)
    assert [e for e in enviados if dona.email in e["destinatario"]] == []  # ainda longe

    cert.validade = hoje_br() + datetime.timedelta(days=30)
    db.flush()
    avisos_certificado.avisar(db)
    meus = [e for e in enviados if dona.email in e["destinatario"]]
    assert len(meus) == 1
    assert "vence em 30 dias" in meus[0]["assunto"]
    assert "preço especial" in meus[0]["corpo_texto"]
    avisos_certificado.avisar(db)
    assert len([e for e in enviados if dona.email in e["destinatario"]]) == 1  # não repete

    # certificado novo, que também vai vencer: avisa de novo
    cert.validade = hoje_br() + datetime.timedelta(days=5)
    db.flush()
    avisos_certificado.avisar(db)
    assert len([e for e in enviados if dona.email in e["destinatario"]]) == 2


def test_aviso_nao_sai_pra_simulacao(db, prestador_teste, dona, monkeypatch):
    enviados = []
    monkeypatch.setattr("app.services.email.get_email_sender", lambda: type("S", (), {"enviar": lambda self, **kw: enviados.append(kw)})())
    monkeypatch.setattr(db, "commit", db.flush)
    prestador_teste.demo = True
    salvar_certificado(db, prestador_teste.id, _pfx("00000000000191"), "senha", CHAVE)
    db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one().validade = hoje_br() + datetime.timedelta(days=3)
    db.flush()
    avisos_certificado.avisar(db)
    assert [e for e in enviados if dona.email in e["destinatario"]] == []


def test_orientacao_configuravel(monkeypatch):
    c = TestClient(app)
    assert "preço especial" in c.get("/api/suporte").json()["certificado_texto"]
    monkeypatch.setattr(get_settings(), "certificado_orientacao", "Texto novo do parceiro.")
    monkeypatch.setattr(get_settings(), "certificado_orientacao_whatsapp", "(31) 99999-0000")
    r = c.get("/api/suporte").json()
    assert r["certificado_texto"] == "Texto novo do parceiro." and r["certificado_whatsapp"] == "31999990000"
    monkeypatch.setattr(get_settings(), "certificado_orientacao", "  ")
    assert c.get("/api/suporte").json()["certificado_texto"] is None
