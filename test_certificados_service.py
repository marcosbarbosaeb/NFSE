"""
app.services.certificados — integração real contra o Postgres local
(nfse_saas), pelo role de runtime (nfse_dev, sujeito a RLS). Prova três
coisas ao mesmo tempo: o certificado guardado não é legível como texto puro
(criptografia em repouso funciona), o roundtrip devolve algo realmente
utilizável pra assinar, e a RLS continua isolando por prestador mesmo
passando pela camada de serviço nova.
"""
import uuid

import pytest

from app.database import definir_prestador_atual
from app.fiscal.xmldsig import assinar_elemento, c14n
from app.models import Certificado
from app.services.certificados import (
    CertificadoNaoEncontradoError,
    carregar_certificado,
    certificado_vencido,
    salvar_certificado,
)

CHAVE_MESTRA_TESTE = "VMQ063EE7ooDE2PpkdzF0zezlh7RcbR6sXlAKW4W9mY="  # mesma forma da de dev, só que isolada do config real


def test_salvar_certificado_nao_guarda_texto_puro(db, prestador_teste, certificado_teste):
    registro = salvar_certificado(
        db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], CHAVE_MESTRA_TESTE
    )
    assert registro.pfx_criptografado != certificado_teste["pfx_bytes"]
    assert certificado_teste["senha"].encode() not in registro.senha_criptografada
    # bytes crus do .pfx (formato ASN.1/PKCS12 tem marcadores reconhecíveis)
    # não podem aparecer dentro do blob cifrado:
    assert certificado_teste["pfx_bytes"][:20] not in registro.pfx_criptografado


def test_salvar_e_carregar_certificado_roundtrip_e_utilizavel(db, prestador_teste, certificado_teste):
    salvar_certificado(
        db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], CHAVE_MESTRA_TESTE
    )

    private_key, cert = carregar_certificado(db, prestador_teste.id, CHAVE_MESTRA_TESTE)

    assert cert.serial_number == certificado_teste["cert"].serial_number

    # utilizável de verdade: assina algo e confere.
    import lxml.etree as etree
    elemento = etree.Element("teste", Id="x1")
    raiz = etree.Element("raiz")
    raiz.append(elemento)
    assinar_elemento(raiz, elemento, private_key, cert)
    assert raiz.find("{http://www.w3.org/2000/09/xmldsig#}Signature") is not None


def test_senha_errada_falha_cedo_sem_gravar_nada(db, prestador_teste, certificado_teste):
    with pytest.raises(Exception):
        salvar_certificado(db, prestador_teste.id, certificado_teste["pfx_bytes"], "senha-errada-com-certeza", CHAVE_MESTRA_TESTE)
    assert db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one_or_none() is None


def test_upsert_substitui_certificado_anterior(db, prestador_teste, certificado_teste):
    salvar_certificado(db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], CHAVE_MESTRA_TESTE)
    total_antes = db.query(Certificado).filter_by(prestador_id=prestador_teste.id).count()
    salvar_certificado(db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], CHAVE_MESTRA_TESTE)
    total_depois = db.query(Certificado).filter_by(prestador_id=prestador_teste.id).count()
    assert total_antes == total_depois == 1


def test_carregar_certificado_inexistente_leva_erro_claro(db, prestador_teste):
    with pytest.raises(CertificadoNaoEncontradoError):
        carregar_certificado(db, prestador_teste.id, CHAVE_MESTRA_TESTE)


def test_rls_bloqueia_acesso_de_outro_prestador(db, prestador_teste, certificado_teste):
    salvar_certificado(db, prestador_teste.id, certificado_teste["pfx_bytes"], certificado_teste["senha"], CHAVE_MESTRA_TESTE)

    # troca o "usuário autenticado" da sessão pra outro prestador (que nem
    # existe) — a RLS tem que negar a visão do certificado do primeiro.
    definir_prestador_atual(db, uuid.uuid4())
    with pytest.raises(CertificadoNaoEncontradoError):
        carregar_certificado(db, prestador_teste.id, CHAVE_MESTRA_TESTE)


def test_certificado_vencido():
    import datetime
    from unittest.mock import MagicMock

    cert_ok = MagicMock(validade=datetime.date.today() + datetime.timedelta(days=30))
    cert_vencido = MagicMock(validade=datetime.date.today() - datetime.timedelta(days=1))
    cert_sem_validade = MagicMock(validade=None)

    assert certificado_vencido(cert_ok) is False
    assert certificado_vencido(cert_vencido) is True
    assert certificado_vencido(cert_sem_validade) is False
