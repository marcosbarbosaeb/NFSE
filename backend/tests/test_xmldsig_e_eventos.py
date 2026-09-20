"""
Verificação criptográfica ponta a ponta de app.fiscal.xmldsig (assinatura da
DPS e do evento de cancelamento) + equivalência com integracao/sign_dps.py e
integracao/cancelar_nfse.py. Certificado sempre de teste, descartável.
"""
import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from app.fiscal.dps import assinar_dps, montar_dps_xml
from app.fiscal.eventos import assinar_evento, montar_evento_cancelamento

import sign_dps  # noqa: E402  (via sys.path em conftest.py, o script original)
from cancelar_nfse import build_evento_xml  # noqa: E402

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N_EXCLUSIVO = "http://www.w3.org/2001/10/xml-exc-c14n#"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"


def _assert_assinatura_valida(signature_el, elemento_referenciado_antes, cert):
    assert signature_el.tag == f"{{{DS}}}Signature"
    assert signature_el.prefix is None

    signed_info = signature_el.find(f"{{{DS}}}SignedInfo")
    assert signed_info.find(f"{{{DS}}}CanonicalizationMethod").get("Algorithm") == C14N_EXCLUSIVO
    assert signed_info.find(f"{{{DS}}}SignatureMethod").get("Algorithm") == RSA_SHA256

    reference = signed_info.find(f"{{{DS}}}Reference")
    key_info = signature_el.find(f"{{{DS}}}KeyInfo")
    assert len(key_info.findall(f".//{{{DS}}}X509Certificate")) == 1

    digest_esperado = hashlib.sha256(
        etree.tostring(elemento_referenciado_antes, method="c14n", exclusive=True, with_comments=False)
    ).digest()
    digest_no_xml = base64.b64decode(reference.find(f"{{{DS}}}DigestValue").text)
    assert digest_esperado == digest_no_xml

    signed_info_bytes = etree.tostring(signed_info, method="c14n", exclusive=True, with_comments=False)
    signature_value = base64.b64decode(signature_el.find(f"{{{DS}}}SignatureValue").text)
    cert.public_key().verify(signature_value, signed_info_bytes, padding.PKCS1v15(), hashes.SHA256())


def test_assinar_dps_e_valida(certificado_teste):
    dps_el = montar_dps_xml(
        prest={"CNPJ": "45172374000122", "IM": "13665300010", "cMun": "3106200",
               "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"},
        toma={"CNPJ": "01239313000160", "xNome": "TESTE LTDA", "cMun": "3304557",
              "CEP": "20011000", "xLgr": "Rua X", "nro": "1", "xBairro": "Centro"},
        serv={"cLocPrestacao": "3106200", "cTribNac": "170601", "cTribMun": "001", "descricao": "Teste"},
        serie="1", n_dps=1, valor=100.0, tpAmb="1", aliq_sn=12.5, dcompet="2026-09-10",
    )
    infDPS_antes = etree.fromstring(etree.tostring(dps_el)).find(f"{{{NS}}}infDPS")

    assinado = assinar_dps(dps_el, certificado_teste["private_key"], certificado_teste["cert"])
    signature_el = assinado.find(f"{{{DS}}}Signature")
    assert signature_el is not None
    _assert_assinatura_valida(signature_el, infDPS_antes, certificado_teste["cert"])


def test_sign_dps_script_original_e_app_fiscal_produzem_assinatura_equivalente(tmp_path, certificado_teste):
    """Mesmo XML assinado pelas duas implementações tem que ser válido pelas
    mesmas regras — não precisa dar bytes idênticos (SignatureValue pode
    variar por padding/timing), mas a MECÂNICA tem que bater."""
    dps_el = montar_dps_xml(
        prest={"CNPJ": "45172374000122", "IM": "13665300010", "cMun": "3106200",
               "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"},
        toma={"CNPJ": "01239313000160", "xNome": "TESTE LTDA", "cMun": "3304557",
              "CEP": "20011000", "xLgr": "Rua X", "nro": "1", "xBairro": "Centro"},
        serv={"cLocPrestacao": "3106200", "cTribNac": "170601", "cTribMun": "001", "descricao": "Teste"},
        serie="1", n_dps=1, valor=100.0, tpAmb="1", aliq_sn=12.5, dcompet="2026-09-10",
    )
    xml_path = tmp_path / "dps.xml"
    etree.ElementTree(dps_el).write(str(xml_path), xml_declaration=True, encoding="UTF-8")

    out_path = tmp_path / "dps_assinada_original.xml"
    sign_dps.sign(str(xml_path), certificado_teste["path"], certificado_teste["senha"], str(out_path))
    assinado_original = etree.parse(str(out_path)).getroot()

    infDPS_antes = etree.fromstring(etree.tostring(dps_el)).find(f"{{{NS}}}infDPS")
    _assert_assinatura_valida(
        assinado_original.find(f"{{{DS}}}Signature"), infDPS_antes, certificado_teste["cert"]
    )


def test_montar_evento_cancelamento_bate_com_original():
    chave = "31062002245172374000122000000000094726097112223684"
    xmotivo = "Emissao duplicada: nota reemitida manualmente apos falha de rede."

    original = build_evento_xml(chave, "45172374000122", "1", xmotivo, "1")
    novo = montar_evento_cancelamento(chave, "45172374000122", "1", xmotivo, "1")

    def normaliza(el):
        clone = etree.fromstring(etree.tostring(el))
        dh = clone.find(f".//{{{NS}}}dhEvento")
        if dh is not None:
            dh.text = "NORMALIZADO"
        return etree.tostring(clone, method="c14n")

    assert normaliza(original) == normaliza(novo)


def test_assinar_evento_e_valido(certificado_teste):
    chave = "31062002245172374000122000000000094726097112223684"
    evento_el = montar_evento_cancelamento(
        chave, "45172374000122", "1",
        "Emissao duplicada: nota reemitida manualmente apos falha de rede.", "1",
    )
    infPedReg_antes = etree.fromstring(etree.tostring(evento_el)).find(f"{{{NS}}}infPedReg")

    assinado = assinar_evento(evento_el, certificado_teste["private_key"], certificado_teste["cert"])
    signature_el = assinado.find(f"{{{DS}}}Signature")
    assert signature_el is not None
    _assert_assinatura_valida(signature_el, infPedReg_antes, certificado_teste["cert"])
