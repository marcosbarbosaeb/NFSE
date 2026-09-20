#!/usr/bin/env python3
"""
Consulta na API Sefin Nacional se uma DPS (pelo Id) ja foi processada, e
descobre o PROXIMO nDPS livre para a serie configurada. Nao emite nada.

GET {base}/dps/{IdDPS}   -> 200 se existe NFS-e para essa DPS, 404 se nao.

Uso:
    python consultar_dps.py secretos\\raiana.pfx "SENHA" --tpAmb 1          # producao
    python consultar_dps.py secretos\\raiana.pfx "SENHA" --tpAmb 2          # homologacao
    python consultar_dps.py ... --n-dps 5                                   # consulta um numero especifico
"""
import argparse
import os
import tempfile

import requests
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

import build_dps

BASES = {
    "2": "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",
    "1": "https://sefin.nfse.gov.br/SefinNacional",
}


def dps_id(fornecedor: str, n_dps: int) -> str:
    cfg = build_dps.FORNECEDORES[fornecedor]
    return ("DPS" + cfg["prest"]["cMun"].zfill(7) + "2" + cfg["prest"]["CNPJ"].zfill(14)
            + cfg["serie"].zfill(5) + str(n_dps).zfill(15))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfx_path")
    ap.add_argument("pfx_password")
    ap.add_argument("--tpAmb", default="2", choices=["1", "2"])
    ap.add_argument("--fornecedor", default="squad_epoca")
    ap.add_argument("--n-dps", type=int, help="consultar so este numero")
    ap.add_argument("--max", type=int, default=50, help="ate quantos numeros varrer procurando o proximo livre")
    ap.add_argument("--next-file", help="grava o proximo nDPS livre neste arquivo (para uso em .bat)")
    args = ap.parse_args()

    key, cert, _ = pkcs12.load_key_and_certificates(open(args.pfx_path, "rb").read(), args.pfx_password.encode())
    tmp = tempfile.mkdtemp(prefix="nfse_cert_")
    cp, kp = os.path.join(tmp, "cert.pem"), os.path.join(tmp, "key.pem")
    open(cp, "wb").write(cert.public_bytes(Encoding.PEM))
    open(kp, "wb").write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    base = BASES[args.tpAmb]
    serie = build_dps.FORNECEDORES[args.fornecedor]["serie"]
    print(f"Ambiente: {'PRODUCAO' if args.tpAmb == '1' else 'homologacao'} | serie {serie}")

    def existe(n):
        r = requests.get(f"{base}/dps/{dps_id(args.fornecedor, n)}", cert=(cp, kp), timeout=30)
        return r.status_code, r

    if args.n_dps:
        st, r = existe(args.n_dps)
        print(f"nDPS {args.n_dps}: HTTP {st} -> {'EXISTE' if st == 200 else 'nao existe' if st == 404 else r.text[:300]}")
        return

    for n in range(1, args.max + 1):
        st, r = existe(n)
        if st == 404:
            print(f"nDPS {n}: livre  -> PROXIMO nDPS = {n}")
            if args.next_file:
                open(args.next_file, "w").write(str(n))
            return
        if st == 200:
            print(f"nDPS {n}: ja usado")
            continue
        print(f"nDPS {n}: resposta inesperada HTTP {st}: {r.text[:300]}")
        return
    print(f"Todos os {args.max} primeiros numeros estao usados; aumente --max.")


if __name__ == "__main__":
    main()
