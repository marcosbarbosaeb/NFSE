#!/usr/bin/env python3
"""
Cancela uma NFS-e ja emitida no Sistema Nacional NFS-e, enviando um Pedido de
Registro de Evento (evento e101101 - "Cancelamento de NFS-e").

Layout oficial confirmado no XSD publico (pedRegEvento_v1.0x.xsd /
tiposEventos_v1.0x.xsd, mesmo padrao sped.fazenda.gov.br/nfse usado na DPS):

    <pedRegEvento versao="1.00">
      <infPedReg Id="PRE<chave 50 digitos><101101>">
        <tpAmb>1|2</tpAmb>
        <verAplic>...</verAplic>
        <dhEvento>AAAA-MM-DDThh:mm:ss-03:00</dhEvento>
        <CNPJAutor>...</CNPJAutor>
        <chNFSe>...(50 digitos)...</chNFSe>
        <e101101>
          <xDesc>Cancelamento de NFS-e</xDesc>
          <cMotivo>1|2|9</cMotivo>   1=Erro na Emissao 2=Servico nao Prestado 9=Outros
          <xMotivo>texto (15-255 caracteres)</xMotivo>
        </e101101>
      </infPedReg>
      <Signature>...assinatura XMLDSig do infPedReg, MESMA receita da DPS...</Signature>
    </pedRegEvento>

Id do infPedReg = "PRE" + chave de acesso (50 digitos) + codigo do evento (6
digitos, "101101"). Assinatura: c14n EXCLUSIVO + RSA-SHA256 + SHA256, sem
prefixo de namespace (identico ao sign_dps.py, que ja foi validado contra a
API de producao).

Envio: POST {base}/nfse/{chaveAcesso}/eventos
  Body JSON: {"pedidoRegistroEventoXmlGZipB64": "<gzip do XML assinado, base64>"}
  Resposta sucesso (201): JSON com eventoXmlGZipB64.
  Resposta erro: JSON com "erros": [...].

Uso:
    python3 cancelar_nfse.py secretos\\raiana.pfx "SENHA" --chave 3106...3684 \\
        --cmotivo 1 --xmotivo "Emissao duplicada: nota reemitida manualmente..." \\
        --tpAmb 1
"""
import argparse
import base64
import datetime
import gzip
import hashlib
import json
import os
import tempfile

from lxml import etree
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
import requests

NS = "http://www.sped.fazenda.gov.br/nfse"
NSMAP = {None: NS}
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"

BASES = {
    "2": "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",  # homologacao
    "1": "https://sefin.nfse.gov.br/SefinNacional",  # producao
}

CODIGO_EVENTO = "101101"


def _el(tag, children=(), attrs=None, text=None):
    e = etree.Element(f"{{{NS}}}{tag}", nsmap=NSMAP)
    if attrs:
        for k, v in attrs.items():
            e.set(k, v)
    if text is not None:
        e.text = text
    for c in children:
        if c is not None:
            e.append(c)
    return e


def leaf(tag, text):
    e = etree.Element(f"{{{NS}}}{tag}", nsmap=NSMAP)
    e.text = str(text)
    return e


def build_evento_xml(chave: str, cnpj_autor: str, cmotivo: str, xmotivo: str, tpAmb: str):
    if len(chave) != 50 or not chave.isdigit():
        raise SystemExit(f"Chave de acesso invalida (precisa ter 50 digitos): {chave!r}")
    if len(xmotivo) < 15:
        raise SystemExit("xMotivo precisa ter pelo menos 15 caracteres (regra do schema)")

    now = datetime.datetime.now().astimezone()
    dhEvento = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    dhEvento = dhEvento[:-2] + ":" + dhEvento[-2:]

    id_pedreg = "PRE" + chave + CODIGO_EVENTO

    e101101 = _el("e101101", [
        leaf("xDesc", "Cancelamento de NFS-e"),
        leaf("cMotivo", cmotivo),
        leaf("xMotivo", xmotivo),
    ])

    infPedReg = _el(
        "infPedReg",
        [
            leaf("tpAmb", tpAmb),
            leaf("verAplic", "ClaudeNFSe-0.1"),
            leaf("dhEvento", dhEvento),
            leaf("CNPJAutor", cnpj_autor),
            leaf("chNFSe", chave),
            e101101,
        ],
        attrs={"Id": id_pedreg},
    )

    pedRegEvento = _el("pedRegEvento", [infPedReg], attrs={"versao": "1.00"})
    etree.cleanup_namespaces(pedRegEvento)
    return pedRegEvento


def c14n(el) -> bytes:
    return etree.tostring(el, method="c14n", exclusive=True, with_comments=False)


def build_signature(digest_b64: str, ref_id: str, cert_b64: str):
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
    el(sig, "SignatureValue")
    ki = el(sig, "KeyInfo")
    x = el(ki, "X509Data")
    el(x, "X509Certificate", cert_b64)
    etree.cleanup_namespaces(sig)
    return sig


def sign_evento(pedRegEvento_el, private_key, cert):
    infPedReg = pedRegEvento_el.find(f"{{{NS}}}infPedReg")
    ref_id = infPedReg.get("Id")

    digest = hashlib.sha256(c14n(infPedReg)).digest()
    digest_b64 = base64.b64encode(digest).decode("ascii")

    cert_b64 = base64.b64encode(cert.public_bytes(Encoding.DER)).decode("ascii")
    sig = build_signature(digest_b64, ref_id, cert_b64)
    pedRegEvento_el.append(sig)

    signed_info = sig.find(f"{{{DS}}}SignedInfo")
    signature = private_key.sign(c14n(signed_info), padding.PKCS1v15(), hashes.SHA256())
    sig.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(signature).decode("ascii")
    return pedRegEvento_el


def resumo(pedRegEvento_el):
    inf = pedRegEvento_el.find(f"{{{NS}}}infPedReg")
    def t(tag):
        x = inf.find(f"{{{NS}}}{tag}")
        return x.text if x is not None else "-"
    e = inf.find(f"{{{NS}}}e101101")
    def te(tag):
        x = e.find(f"{{{NS}}}{tag}")
        return x.text if x is not None else "-"
    amb = {"1": "*** PRODUCAO (cancelamento de verdade) ***", "2": "homologacao (teste)"}.get(t("tpAmb"), t("tpAmb"))
    print("=" * 78)
    print(f"{'AMBIENTE':30s} {amb}")
    print(f"{'Id do pedido de registro':30s} {inf.get('Id')}")
    print(f"{'Evento':30s} e101101 - {te('xDesc')}")
    print(f"{'Data/hora do evento':30s} {t('dhEvento')}")
    print(f"{'CNPJ autor':30s} {t('CNPJAutor')}")
    print(f"{'Chave da NFS-e a cancelar':30s} {t('chNFSe')}")
    print(f"{'Motivo (codigo)':30s} {te('cMotivo')} (1=Erro na Emissao 2=Servico nao Prestado 9=Outros)")
    print(f"{'Motivo (texto)':30s} {te('xMotivo')}")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfx_path")
    ap.add_argument("pfx_password")
    ap.add_argument("--chave", required=True, help="chave de acesso da NFS-e a cancelar (50 digitos)")
    ap.add_argument("--cnpj-autor", default="45172374000122", help="CNPJ do autor do evento (padrao: Raiana)")
    ap.add_argument("--cmotivo", default="1", choices=["1", "2", "9"])
    ap.add_argument("--xmotivo", required=True, help="texto do motivo (15-255 caracteres)")
    ap.add_argument("--tpAmb", default="1", choices=["1", "2"])
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--so-gerar", action="store_true", help="so gera e mostra o XML, nao assina nem envia")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    pedRegEvento_el = build_evento_xml(args.chave, args.cnpj_autor, args.cmotivo, args.xmotivo, args.tpAmb)
    resumo(pedRegEvento_el)

    unsigned_path = os.path.join(args.outdir, f"CANCELAMENTO_{args.chave}.xml")
    etree.ElementTree(pedRegEvento_el).write(unsigned_path, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    print(f"XML (nao assinado) gravado em: {unsigned_path}")

    if args.so_gerar:
        return

    with open(args.pfx_path, "rb") as f:
        pfx_data = f.read()
    private_key, cert, _extra = pkcs12.load_key_and_certificates(pfx_data, args.pfx_password.encode("utf-8"))

    # precisa reler sem pretty_print (senao a indentacao entra no c14n) - assina
    # direto a arvore em memoria antes de gravar bonito.
    pedRegEvento_el = build_evento_xml(args.chave, args.cnpj_autor, args.cmotivo, args.xmotivo, args.tpAmb)
    sign_evento(pedRegEvento_el, private_key, cert)

    signed_path = os.path.join(args.outdir, f"CANCELAMENTO_{args.chave}_assinado.xml")
    etree.ElementTree(pedRegEvento_el).write(signed_path, xml_declaration=True, encoding="UTF-8", pretty_print=False)
    print(f"XML assinado gravado em: {signed_path}")

    with open(signed_path, "rb") as f:
        xml_bytes = f.read()
    gz = gzip.compress(xml_bytes)
    b64 = base64.b64encode(gz).decode("ascii")

    tmp = tempfile.mkdtemp(prefix="nfse_cert_")
    cert_path = os.path.join(tmp, "cert.pem")
    key_path = os.path.join(tmp, "key.pem")
    open(cert_path, "wb").write(cert.public_bytes(Encoding.PEM))
    open(key_path, "wb").write(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    base = BASES[args.tpAmb]
    url = f"{base}/nfse/{args.chave}/eventos"
    print(f"POST {url}")
    try:
        resp = requests.post(url, json={"pedidoRegistroEventoXmlGZipB64": b64}, cert=(cert_path, key_path), timeout=40)
    except requests.exceptions.RequestException as e:
        print(f"ERRO DE CONEXAO/REDE: {e}")
        return
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print("Resposta nao-JSON:")
        print(resp.text[:2000])
        return

    if resp.status_code == 201:
        print("Evento de cancelamento REGISTRADO.")
        ev_b64 = data.get("eventoXmlGZipB64")
        if ev_b64:
            ev_xml = gzip.decompress(base64.b64decode(ev_b64))
            out_path = os.path.join(args.outdir, f"CANCELAMENTO_{args.chave}_RESPOSTA.xml")
            open(out_path, "wb").write(ev_xml)
            print(f"XML do evento (resposta) salvo em: {out_path}")
        if data.get("alertas"):
            print("Alertas:", json.dumps(data["alertas"], ensure_ascii=False, indent=2))
    else:
        print("ERRO no cancelamento:")
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
