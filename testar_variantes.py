#!/usr/bin/env python3
"""
Testa, em UMA rodada, varias variantes de assinatura da DPS contra a API Sefin
Nacional (homologacao), para descobrir qual o verificador deles aceita.
Cada variante e gerada, assinada, enviada, e a resposta resumida numa tabela.
Os XMLs e respostas ficam em output/variantes/.

Uso:
    python testar_variantes.py secretos\\raiana.pfx "SENHA" --competencia 2026-08 --valor 17654.40 --n-dps 91
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import tempfile

import requests
from lxml import etree
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import (
    pkcs12, Encoding, PrivateFormat, NoEncryption,
)

import build_dps

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N_INC = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
C14N_EXC = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
ALG = {
    "sha256": ("http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
               "http://www.w3.org/2001/04/xmlenc#sha256", hashlib.sha256, hashes.SHA256()),
    "sha1": ("http://www.w3.org/2000/09/xmldsig#rsa-sha1",
             "http://www.w3.org/2000/09/xmldsig#sha1", hashlib.sha1, hashes.SHA1()),
}
URL_HOMOLOG = "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/nfse"


def c14n(el, exclusive):
    return etree.tostring(el, method="c14n", exclusive=exclusive, with_comments=False)


def make_signature(digest_b64, ref_id, cert_b64, alg, c14n_uri):
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
    el(si, "CanonicalizationMethod", Algorithm=c14n_uri)
    el(si, "SignatureMethod", Algorithm=ALG[alg][0])
    ref = el(si, "Reference", URI=f"#{ref_id}")
    tr = el(ref, "Transforms")
    el(tr, "Transform", Algorithm=ENVELOPED)
    el(tr, "Transform", Algorithm=c14n_uri)
    el(ref, "DigestMethod", Algorithm=ALG[alg][1])
    el(ref, "DigestValue", digest_b64)
    el(sig, "SignatureValue")
    ki = el(sig, "KeyInfo")
    x = el(ki, "X509Data")
    el(x, "X509Certificate", cert_b64)
    etree.cleanup_namespaces(sig)
    return sig


def sign_variant(root, key, cert, *, alg="sha256", exclusive=False,
                 strip_xmlns_digest=False, sig_inside_infdps=False):
    infDPS = root.find(f"{{{NS}}}infDPS")
    ref_id = infDPS.get("Id")
    c14n_uri = C14N_EXC if exclusive else C14N_INC

    data = c14n(infDPS, exclusive)
    if strip_xmlns_digest:
        data = data.replace(f' xmlns="{NS}"'.encode(), b"", 1)
    digest_b64 = base64.b64encode(ALG[alg][2](data).digest()).decode()

    cert_b64 = base64.b64encode(cert.public_bytes(Encoding.DER)).decode()
    sig = make_signature(digest_b64, ref_id, cert_b64, alg, c14n_uri)
    (infDPS if sig_inside_infdps else root).append(sig)

    si = sig.find(f"{{{DS}}}SignedInfo")
    sv = key.sign(c14n(si, exclusive), padding.PKCS1v15(), ALG[alg][3])
    sig.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(sv).decode()
    return root


def serialize(root, *, pretty=False, double_quotes=False):
    # pretty ja foi aplicado em build(); aqui NUNCA reindentar (mudaria o digest)
    body = etree.tostring(root, encoding="UTF-8", pretty_print=False)
    decl = b'<?xml version="1.0" encoding="UTF-8"?>' if double_quotes else b"<?xml version='1.0' encoding='UTF-8'?>"
    return decl + b"\n" + body


def build(args, versao="1.00", pretty=False):
    root = build_dps.build_dps_xml("squad_epoca", args.competencia, args.valor, args.n_dps, "2")
    if versao != "1.00":
        root.set("versao", versao)
    if pretty:
        # indentacao passa a fazer parte do conteudo ASSINADO (como no emissor
        # Python de referencia, que assina o XML ja indentado)
        return etree.fromstring(etree.tostring(root, pretty_print=True))
    # compacto: sem espacos "de enfeite"
    return etree.fromstring(etree.tostring(root), etree.XMLParser(remove_blank_text=True))


VARIANTES = [
    # nome, opcoes de assinatura, opcoes de serializacao, versao
    ("A_exclusiva_sha256",         dict(exclusive=True),                      dict(),                                  "1.00"),
    ("B_digest_sem_xmlns_sha256",  dict(strip_xmlns_digest=True),             dict(),                                  "1.00"),
    ("C_indentado_v101_sha256",    dict(),                                    dict(pretty=True, double_quotes=True),   "1.01"),
    ("D_sig_dentro_infDPS_sha256", dict(sig_inside_infdps=True),              dict(),                                  "1.00"),
    ("E_exclusiva_sha1",           dict(exclusive=True, alg="sha1"),          dict(),                                  "1.00"),
    ("F_v101_compacto_sha256",     dict(),                                    dict(double_quotes=True),                "1.01"),
    ("G_baseline_inclusiva_sha256", dict(),                                   dict(),                                  "1.00"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfx_path")
    ap.add_argument("pfx_password")
    ap.add_argument("--competencia", required=True)
    ap.add_argument("--valor", required=True, type=float)
    ap.add_argument("--n-dps", type=int, required=True)
    ap.add_argument("--so", help="rodar so a variante com este prefixo (ex: A)")
    args = ap.parse_args()

    pfx = open(args.pfx_path, "rb").read()
    key, cert, _ = pkcs12.load_key_and_certificates(pfx, args.pfx_password.encode())
    tmp = tempfile.mkdtemp(prefix="nfse_cert_")
    cert_path, key_path = os.path.join(tmp, "cert.pem"), os.path.join(tmp, "key.pem")
    open(cert_path, "wb").write(cert.public_bytes(Encoding.PEM))
    open(key_path, "wb").write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    outdir = os.path.join("output", "variantes")
    os.makedirs(outdir, exist_ok=True)
    resumo = []
    for nome, sopts, wopts, versao in VARIANTES:
        if args.so and not nome.startswith(args.so):
            continue
        root = build(args, versao, pretty=wopts.get("pretty", False))
        signed = sign_variant(root, key, cert, **sopts)
        xml = serialize(signed, **wopts)
        open(os.path.join(outdir, f"{nome}.xml"), "wb").write(xml)

        body = {"dpsXmlGZipB64": base64.b64encode(gzip.compress(xml)).decode()}
        print(f"\n=== {nome} ===")
        try:
            r = requests.post(URL_HOMOLOG, json=body, cert=(cert_path, key_path), timeout=40)
            try:
                data = r.json()
            except ValueError:
                data = {"_raw": r.text[:500]}
            open(os.path.join(outdir, f"{nome}_resposta.json"), "w", encoding="utf-8").write(
                json.dumps(data, ensure_ascii=False, indent=2))
            erros = data.get("erros") or []
            cod = ", ".join(f"{e.get('Codigo')} {e.get('Descricao','')}" for e in erros) if erros else "-"
            chave = data.get("chaveAcesso")
            status = f"HTTP {r.status_code}" + (f"  SUCESSO chaveAcesso={chave}" if chave else f"  {cod}")
            if chave and data.get("nfseXmlGZipB64"):
                open(os.path.join(outdir, f"{nome}_NFSE.xml"), "wb").write(
                    gzip.decompress(base64.b64decode(data["nfseXmlGZipB64"])))
        except requests.exceptions.RequestException as e:
            status = f"ERRO DE REDE: {e}"
        print(status)
        resumo.append((nome, status))
        if "SUCESSO" in status:
            print(">>> Esta variante foi ACEITA. Parando aqui (as demais repetiriam o mesmo nDPS).")
            break

    print("\n================ RESUMO ================")
    for nome, status in resumo:
        print(f"{nome:32s} {status}")
    print("(XMLs e respostas em output\\variantes\\)")


if __name__ == "__main__":
    main()
