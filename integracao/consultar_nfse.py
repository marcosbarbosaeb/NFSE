#!/usr/bin/env python3
"""
Consulta uma NFS-e emitida pela chave de acesso na API Sefin Nacional e baixa
o DANFSe (PDF). Nao emite nem altera nada.

  GET {base}/nfse/{chaveAcesso}   -> JSON com a NFS-e (nfseXmlGZipB64)
  GET {base}/DANFSe/{chaveAcesso} -> PDF do DANFSe

Uso:
    python consultar_nfse.py secretos\\raiana.pfx "SENHA" --chave 3106... --tpAmb 1
    python consultar_nfse.py secretos\\raiana.pfx "SENHA" --xml output\\..._NFSE_RESPOSTA.xml   (le a chave do XML)
"""
import argparse
import base64
import gzip
import json
import os
import tempfile

import requests
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

NS = "http://www.sped.fazenda.gov.br/nfse"
BASES = {
    "2": "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",
    "1": "https://sefin.nfse.gov.br/SefinNacional",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfx_path")
    ap.add_argument("pfx_password")
    ap.add_argument("--tpAmb", default="1", choices=["1", "2"])
    ap.add_argument("--chave", help="chave de acesso (50 digitos)")
    ap.add_argument("--xml", help="XML da NFS-e (le a chave do Id do infNFSe)")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    chave = args.chave
    if not chave and args.xml:
        root = etree.parse(args.xml).getroot()
        inf = root.find(f".//{{{NS}}}infNFSe")
        chave = inf.get("Id")[3:] if inf is not None else None
    if not chave:
        raise SystemExit("Informe --chave ou --xml")

    key, cert, _ = pkcs12.load_key_and_certificates(open(args.pfx_path, "rb").read(), args.pfx_password.encode())
    tmp = tempfile.mkdtemp(prefix="nfse_cert_")
    cp, kp = os.path.join(tmp, "cert.pem"), os.path.join(tmp, "key.pem")
    open(cp, "wb").write(cert.public_bytes(Encoding.PEM))
    open(kp, "wb").write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    base = BASES[args.tpAmb]
    print(f"Ambiente: {'PRODUCAO' if args.tpAmb == '1' else 'homologacao'}")
    print(f"Chave: {chave}")

    n_nfse = None
    # 1) a nota existe?
    r = requests.get(f"{base}/nfse/{chave}", cert=(cp, kp), timeout=40)
    print(f"GET /nfse/{{chave}} -> HTTP {r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
        except ValueError:
            data = {}
        b64 = data.get("nfseXmlGZipB64")
        if b64:
            xml = gzip.decompress(base64.b64decode(b64))
            root = etree.fromstring(xml)
            inf = root.find(f".//{{{NS}}}infNFSe")
            def t(p):
                x = inf.find("/".join(f"{{{NS}}}{s}" for s in p.split("/")))
                return x.text if x is not None else "-"
            n_nfse = t('nNFSe')
            print(f"  NFS-e n. {t('nNFSe')} | cStat {t('cStat')} | processada em {t('dhProc')} | emitente {t('emit/xNome')} | vLiq {t('valores/vLiq')}")
            ev = data.get("eventos") or []
            if ev:
                print("  Eventos vinculados:", json.dumps(ev, ensure_ascii=False)[:500])
        else:
            print("  Resposta sem XML:", json.dumps(data, ensure_ascii=False)[:500])
    else:
        print("  ", r.text[:500])

    # 2) DANFSe (PDF). O endpoint /DANFSe da Sefin devolve 501 (nao implementado);
    #    o servico de DANFSe e do ADN. Tentamos os candidatos conhecidos, em ordem.
    adn = "https://adn.nfse.gov.br" if args.tpAmb == "1" else "https://adn.producaorestrita.nfse.gov.br"
    candidatos = [
        f"{adn}/danfse/{chave}",
        f"{adn}/contribuintes/danfse/{chave}",
        f"{adn}/contribuintes/DANFSe/{chave}",
        f"{adn}/danfse/nfse/{chave}",
        f"{base}/DANFSe/{chave}",
    ]
    os.makedirs(args.outdir, exist_ok=True)
    for url in candidatos:
        try:
            r = requests.get(url, cert=(cp, kp), timeout=60, headers={"Accept": "application/pdf, */*"})
        except requests.exceptions.RequestException as e:
            print(f"GET {url} -> ERRO DE REDE: {e}")
            continue
        ct = r.headers.get("content-type")
        print(f"GET {url} -> HTTP {r.status_code} ({ct})")
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            out = os.path.join(args.outdir, f"DANFSe_NFSe_{n_nfse or chave}.pdf")
            open(out, "wb").write(r.content)
            print(f"  PDF salvo em: {out}")
            break
        if r.status_code == 200 and "json" in (ct or ""):
            # algumas respostas trazem o PDF em base64 dentro de JSON
            try:
                data = r.json()
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 1000:
                        raw = base64.b64decode(v)
                        if raw[:4] == b"%PDF":
                            out = os.path.join(args.outdir, f"DANFSe_NFSe_{n_nfse or chave}.pdf")
                            open(out, "wb").write(raw)
                            print(f"  PDF (campo {k}) salvo em: {out}")
                            break
            except Exception:
                pass
        else:
            print("  ", r.text[:300].replace("\n", " "))
    else:
        print("Nenhum endpoint devolveu o PDF.")


if __name__ == "__main__":
    main()
