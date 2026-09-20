"""
Assinatura XMLDSig — Marco 3 do plano (desacoplar build_dps/sign_dps/
submit_dps/consultar_dps/cancelar_nfse/consultar_nfse numa biblioteca
importável).

Esta é a MESMA receita de assinatura usada em integracao/sign_dps.py e
integracao/cancelar_nfse.py — os dois arquivos originais tinham cópias
idênticas de `c14n`/`build_signature` (uma pra assinar a DPS, outra pra
assinar o evento de cancelamento). Consolidado aqui num único lugar: as
regras abaixo foram descobertas EMPIRICAMENTE contra a API real de produção
(ver integracao/sign_dps.py para o histórico) e não podem divergir entre os
dois usos.

    - CanonicalizationMethod e Transform: c14n EXCLUSIVO (xml-exc-c14n#) —
      não o inclusivo "fixado" pelo XSD oficial (esse XSD está desatualizado
      nesse ponto; a API rejeita com E0714 se usar o inclusivo).
    - SignatureMethod: RSA-SHA256. DigestMethod: SHA256 (o XSD oficial
      sugere SHA1; a API aceita SHA256 e foi o que validou em produção).
    - <Signature> SEM prefixo de namespace (a API rejeita qualquer prefixo,
      inclusive "ds:", com erro E1228).
    - KeyInfo/X509Data/X509Certificate: só o certificado do titular (o
      schema oficial só aceita um único X509Certificate).

O teste de regressão que verifica isso (backend/tests/test_xmldsig.py)
reexecuta a verificação criptográfica ponta a ponta com um certificado de
teste descartável — nunca com o certificado real da Raiana.
"""
import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import Certificate
from lxml import etree

DS = "http://www.w3.org/2000/09/xmldsig#"
C14N_EXCLUSIVO = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256_ALG = "http://www.w3.org/2001/04/xmlenc#sha256"


def c14n(elemento) -> bytes:
    """Canonicalização exclusiva (c14n-exc), sem comentários — a forma
    canônica sobre a qual digest e assinatura são calculados."""
    return etree.tostring(elemento, method="c14n", exclusive=True, with_comments=False)


def _montar_elemento_signature(digest_b64: str, ref_id: str, cert_b64: str):
    """Monta <Signature> no namespace PADRÃO (sem prefixo) — ver módulo."""
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
    el(si, "CanonicalizationMethod", Algorithm=C14N_EXCLUSIVO)
    el(si, "SignatureMethod", Algorithm=RSA_SHA256)
    ref = el(si, "Reference", URI=f"#{ref_id}")
    tr = el(ref, "Transforms")
    el(tr, "Transform", Algorithm=ENVELOPED)
    el(tr, "Transform", Algorithm=C14N_EXCLUSIVO)
    el(ref, "DigestMethod", Algorithm=SHA256_ALG)
    el(ref, "DigestValue", digest_b64)
    el(sig, "SignatureValue")  # preenchido depois
    ki = el(sig, "KeyInfo")
    x = el(ki, "X509Data")
    el(x, "X509Certificate", cert_b64)
    etree.cleanup_namespaces(sig)
    return sig


def assinar_elemento(raiz, elemento_referenciado, private_key: RSAPrivateKey, cert: Certificate):
    """Assina `elemento_referenciado` (precisa ter atributo Id) e anexa a
    <Signature> resultante como último filho de `raiz`.

    Usado tanto para assinar o infDPS de uma DPS (raiz=<DPS>) quanto o
    infPedReg de um evento de cancelamento (raiz=<pedRegEvento>) — mesma
    receita, dois usos, ver docstring do módulo.

    Retorna `raiz` (mutada in place, pra encadear a chamada).
    """
    ref_id = elemento_referenciado.get("Id")
    if not ref_id:
        raise ValueError("elemento referenciado precisa ter atributo Id")

    # Digest calculado ANTES da assinatura existir na árvore — o transform
    # enveloped-signature fica trivialmente satisfeito nesse momento.
    digest = hashlib.sha256(c14n(elemento_referenciado)).digest()
    digest_b64 = base64.b64encode(digest).decode("ascii")

    cert_b64 = base64.b64encode(cert.public_bytes(Encoding.DER)).decode("ascii")
    sig = _montar_elemento_signature(digest_b64, ref_id, cert_b64)
    raiz.append(sig)

    # SignedInfo é assinado JÁ DENTRO da árvore (c14n exclusivo considera os
    # namespaces em escopo no ponto onde o elemento está).
    signed_info = sig.find(f"{{{DS}}}SignedInfo")
    assinatura = private_key.sign(c14n(signed_info), padding.PKCS1v15(), hashes.SHA256())
    sig.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(assinatura).decode("ascii")

    return raiz
