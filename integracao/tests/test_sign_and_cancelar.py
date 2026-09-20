"""
Regressão da MECÂNICA de assinatura (sign_dps.py) e do evento de cancelamento
(cancelar_nfse.py) — trava as regras descobertas empiricamente contra a API
real (ver comentários em sign_dps.py): c14n EXCLUSIVO, RSA-SHA256, SHA256,
Signature SEM prefixo de namespace, um único X509Certificate. Um refactor
(Marco 3) que reintroduza um prefixo "ds:" ou troque pra c14n inclusivo, por
exemplo, quebra a assinatura silenciosamente em produção — e quebra aqui
primeiro.

Usa um certificado autoassinado descartável (fixture `certificado_teste`),
nunca o certificado real da Raiana.
"""
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_dps import build_dps_xml  # noqa: E402
from cancelar_nfse import build_evento_xml, c14n as c14n_evento, sign_evento  # noqa: E402
import sign_dps  # noqa: E402

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N_EXCLUSIVO = "http://www.w3.org/2001/10/xml-exc-c14n#"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256_ALG = "http://www.w3.org/2001/04/xmlenc#sha256"


def _assert_signature_valida(signature_el, referenced_el_before_signature, private_key, cert):
    """Reexecuta a verificação criptográfica ponta a ponta: recalcula o
    digest do elemento referenciado, confere contra DigestValue, e valida a
    SignatureValue contra o SignedInfo canonicalizado — exatamente o que a
    Sefin faz do lado dela."""
    assert signature_el.tag == f"{{{DS}}}Signature"
    # Sem prefixo: a raiz do elemento não pode ter outro prefixo declarado.
    assert signature_el.prefix is None, "Signature não pode ter prefixo de namespace (ver E1228 em cancelar_nfse.py)"

    signed_info = signature_el.find(f"{{{DS}}}SignedInfo")
    canon_method = signed_info.find(f"{{{DS}}}CanonicalizationMethod").get("Algorithm")
    sig_method = signed_info.find(f"{{{DS}}}SignatureMethod").get("Algorithm")
    assert canon_method == C14N_EXCLUSIVO
    assert sig_method == RSA_SHA256

    reference = signed_info.find(f"{{{DS}}}Reference")
    digest_method = reference.find(f"{{{DS}}}DigestMethod").get("Algorithm")
    assert digest_method == SHA256_ALG

    key_info = signature_el.find(f"{{{DS}}}KeyInfo")
    certs = key_info.findall(f".//{{{DS}}}X509Certificate")
    assert len(certs) == 1, "schema oficial só aceita um X509Certificate"

    import base64
    import hashlib

    digest_esperado = hashlib.sha256(
        etree.tostring(referenced_el_before_signature, method="c14n", exclusive=True, with_comments=False)
    ).digest()
    digest_no_xml = base64.b64decode(reference.find(f"{{{DS}}}DigestValue").text)
    assert digest_esperado == digest_no_xml, "DigestValue não bate com o digest recalculado do elemento referenciado"

    signed_info_bytes = etree.tostring(signed_info, method="c14n", exclusive=True, with_comments=False)
    signature_value = base64.b64decode(signature_el.find(f"{{{DS}}}SignatureValue").text)
    cert.public_key().verify(
        signature_value, signed_info_bytes, padding.PKCS1v15(), hashes.SHA256()
    )  # levanta InvalidSignature se não bater


def test_assinatura_da_dps_e_estruturalmente_e_criptograficamente_valida(tmp_path, certificado_teste):
    dps_el = build_dps_xml("squad_epoca", "2026-08", 17654.40, 1, tpAmb="1", aliq_sn=12.5, dcompet="2026-09-10")

    xml_path = tmp_path / "dps.xml"
    etree.ElementTree(dps_el).write(str(xml_path), xml_declaration=True, encoding="UTF-8")

    # digest é calculado sobre o infDPS ANTES da assinatura existir na árvore
    infDPS_antes = etree.fromstring(etree.tostring(dps_el)).find(f"{{{NS}}}infDPS")

    out_path = tmp_path / "dps_assinada.xml"
    sign_dps.sign(str(xml_path), certificado_teste["path"], certificado_teste["senha"], str(out_path))

    assinado = etree.parse(str(out_path)).getroot()
    signature_el = assinado.find(f"{{{DS}}}Signature")
    assert signature_el is not None, "assinatura não foi anexada à raiz <DPS>"

    _assert_signature_valida(
        signature_el, infDPS_antes, certificado_teste["private_key"], certificado_teste["cert"]
    )


def test_evento_cancelamento_estrutura_e_assinatura(certificado_teste):
    chave = "31062002245172374000122000000000094726097112223684"
    evento_el = build_evento_xml(
        chave=chave,
        cnpj_autor="45172374000122",
        cmotivo="1",
        xmotivo="Emissao duplicada: nota reemitida manualmente apos falha de rede.",
        tpAmb="1",
    )

    infPedReg_antes = etree.fromstring(etree.tostring(evento_el)).find(f"{{{NS}}}infPedReg")
    assert infPedReg_antes.get("Id") == f"PRE{chave}101101"

    sign_evento(evento_el, certificado_teste["private_key"], certificado_teste["cert"])
    signature_el = evento_el.find(f"{{{DS}}}Signature")
    assert signature_el is not None

    _assert_signature_valida(
        signature_el, infPedReg_antes, certificado_teste["private_key"], certificado_teste["cert"]
    )


def test_evento_cancelamento_valida_entradas():
    import pytest

    with pytest.raises(SystemExit):
        build_evento_xml("chave-curta-demais", "45172374000122", "1", "motivo qualquer com mais de 15 caracteres", "1")
    with pytest.raises(SystemExit):
        build_evento_xml("3" * 50, "45172374000122", "1", "curto", "1")  # xMotivo < 15 chars
