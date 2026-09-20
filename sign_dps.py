#!/usr/bin/env python3
"""
Assina uma DPS (XML) com o certificado A1 (.pfx), no padrao XMLDSig
enveloped exigido pelo Sistema Nacional NFS-e:
  - CanonicalizationMethod e Transform: c14n EXCLUSIVO (xml-exc-c14n#)
  - SignatureMethod: RSA-SHA256   - DigestMethod: SHA256
  DESCOBERTO EMPIRICAMENTE em 09/09/2026 (testar_variantes.py): a API Sefin
  Nacional so aceitou a assinatura com canonicalizacao EXCLUSIVA. Com a
  inclusiva (REC-xml-c14n-20010315) - que e a "fixada" pelo xmldsig-core-schema
  v1.00 da pasta schemas/ - ela devolve E0714 "Arquivo enviado com erro na
  assinatura", mesmo com a assinatura criptograficamente valida. Aquele XSD
  esta desatualizado tambem quanto ao SHA1: a API aceita SHA-256.
  - Reference URI="#<Id do infDPS>", transforms: enveloped-signature + c14n
  - KeyInfo/X509Data/X509Certificate: SO o certificado do titular (o schema
    oficial aceita um unico X509Certificate)

Implementacao manual (lxml + cryptography), SEM a biblioteca signxml.
Motivo: a API Sefin Nacional rejeita qualquer prefixo de namespace no XML
(erro E1228 "Xml declarado com prefixo de namespace"), inclusive o "ds:" da
assinatura. O signxml, quando configurado para namespace padrao (sem prefixo),
tem um bug que grava Transforms/DigestMethod/DigestValue FORA do namespace
xmldsig, e a assinatura fica invalida. Assinando a mao, o XML sai exatamente
como o padrao NF-e/NFS-e espera:
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#"> ... </Signature>

Uso:
    python3 sign_dps.py output/DPS_squad_epoca_2026-08.xml secretos/raiana.pfx 'SENHA'
"""
import base64
import hashlib
import sys

from lxml import etree
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"


def c14n(el) -> bytes:
    return etree.tostring(el, method="c14n", exclusive=True, with_comments=False)


def build_signature(digest_b64: str, ref_id: str, cert_b64: str):
    """Monta <Signature> no namespace PADRAO (nenhum prefixo)."""
    nsmap = {None: DS}

    def el(parent, tag, text=None, **attrs):
        e = etree.SubElement(parent, f"{{{DS}}}{tag}", nsmap=nsmap)
        for k, v in attrs.items():
            e.set(k, v)
        if text is not None:
            e.text = text
        return e

    sig = etree.Element(f"{{{DS}}}Signature", nsmap=nsmap)
    si = el(sig, "SignedInfo")
    el(si, "CanonicalizationMethod", Algorithm=C14N)
    el(si, "SignatureMethod", Algorithm=RSA_SHA256)
    ref = el(si, "Reference", URI=f"#{ref_id}")
    tr = el(ref, "Transforms")
    el(tr, "Transform", Algorithm=ENVELOPED)
    el(tr, "Transform", Algorithm=C14N)
    el(ref, "DigestMethod", Algorithm=SHA256)
    el(ref, "DigestValue", digest_b64)
    el(sig, "SignatureValue")  # preenchido depois
    ki = el(sig, "KeyInfo")
    x = el(ki, "X509Data")
    el(x, "X509Certificate", cert_b64)
    etree.cleanup_namespaces(sig)
    return sig


def sign(xml_path: str, pfx_path: str, pfx_password: str, out_path: str):
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()
    private_key, cert, _extra = pkcs12.load_key_and_certificates(
        pfx_data, pfx_password.encode("utf-8")
    )

    # remove_blank_text: evita que espacos/quebras de linha "de enfeite" entrem
    # no calculo do digest de um jeito e sejam serializados de outro.
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()  # <DPS>
    infDPS = root.find(f"{{{NS}}}infDPS")
    if infDPS is None:
        raise RuntimeError("Elemento infDPS nao encontrado")
    ref_id = infDPS.get("Id")
    if not ref_id:
        raise RuntimeError("infDPS sem atributo Id")

    # 1) Digest SHA256 do infDPS canonicalizado (a assinatura ainda nao existe
    #    na arvore, entao o transform enveloped-signature e trivialmente satisfeito)
    digest = hashlib.sha256(c14n(infDPS)).digest()
    digest_b64 = base64.b64encode(digest).decode("ascii")

    # 2) Monta <Signature> e anexa apos o infDPS (posicao exigida pelo schema)
    cert_b64 = base64.b64encode(cert.public_bytes(Encoding.DER)).decode("ascii")
    sig = build_signature(digest_b64, ref_id, cert_b64)
    root.append(sig)

    # 3) Assina o SignedInfo canonicalizado JA DENTRO da arvore (c14n inclusivo
    #    leva em conta os namespaces em escopo)
    signed_info = sig.find(f"{{{DS}}}SignedInfo")
    signature = private_key.sign(c14n(signed_info), padding.PKCS1v15(), hashes.SHA256())
    sig.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(signature).decode("ascii")

    etree.ElementTree(root).write(
        out_path, xml_declaration=True, encoding="UTF-8", pretty_print=False
    )
    print(f"DPS assinada gravada em: {out_path}")
    return out_path


if __name__ == "__main__":
    xml_path, pfx_path, pfx_password = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = xml_path.replace(".xml", "_assinada.xml")
    sign(xml_path, pfx_path, pfx_password, out_path)
