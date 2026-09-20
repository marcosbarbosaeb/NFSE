#!/usr/bin/env python3
"""
Mostra, em linguagem de gente, os campos de uma DPS (XML) para conferencia
antes do envio. Nao altera nada.

Uso:  python resumo_dps.py output\\DPS_squad_epoca_2026-08.xml
"""
import sys
from lxml import etree

NS = "http://www.sped.fazenda.gov.br/nfse"


def t(el, path):
    x = el.find("/".join(f"{{{NS}}}{p}" for p in path.split("/")))
    return x.text if x is not None and x.text is not None else "-"


def brl(v):
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return v


def cnpj(v):
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}" if len(v) == 14 else v


def main():
    root = etree.parse(sys.argv[1]).getroot()
    inf = root.find(f"{{{NS}}}infDPS")
    amb = t(inf, "tpAmb")
    amb_txt = {"1": "*** PRODUCAO (nota de verdade) ***", "2": "homologacao (teste)"}.get(amb, amb)
    tot = inf.find(f"{{{NS}}}valores/{{{NS}}}trib/{{{NS}}}totTrib")
    tot_txt = "-"
    if tot is not None and len(tot):
        c = tot[0]
        nome = etree.QName(c).localname
        tot_txt = {"pTotTribSN": f"aliquota do Simples Nacional {c.text}%",
                   "indTotTrib": "nao informado (indTotTrib=0)"}.get(nome, f"{nome}={c.text}")
    desc = t(inf, "serv/cServ/xDescServ")

    linhas = [
        ("AMBIENTE", amb_txt),
        ("Id da DPS", inf.get("Id")),
        ("Serie / numero DPS", f"{t(inf, 'serie')} / {t(inf, 'nDPS')}"),
        ("Emissao (dhEmi)", t(inf, "dhEmi")),
        ("Competencia (dCompet)", t(inf, "dCompet")),
        ("Municipio emissor", t(inf, "cLocEmi")),
        ("", ""),
        ("PRESTADOR", t(inf, "prest/xNome")),
        ("  CNPJ / IM", f"{cnpj(t(inf, 'prest/CNPJ'))} / {t(inf, 'prest/IM')}"),
        ("  Endereco", f"{t(inf, 'prest/end/xLgr')}, {t(inf, 'prest/end/nro')} - {t(inf, 'prest/end/xBairro')} - mun {t(inf, 'prest/end/endNac/cMun')} CEP {t(inf, 'prest/end/endNac/CEP')}"),
        ("  Fone / e-mail", f"{t(inf, 'prest/fone')} / {t(inf, 'prest/email')}"),
        ("  Simples Nacional", f"opSimpNac={t(inf, 'prest/regTrib/opSimpNac')} regApTribSN={t(inf, 'prest/regTrib/regApTribSN')} regEspTrib={t(inf, 'prest/regTrib/regEspTrib')}"),
        ("", ""),
        ("TOMADOR", t(inf, "toma/xNome")),
        ("  CNPJ", cnpj(t(inf, "toma/CNPJ"))),
        ("  Endereco", f"{t(inf, 'toma/end/xLgr')}, {t(inf, 'toma/end/nro')} {t(inf, 'toma/end/xCpl')} - {t(inf, 'toma/end/xBairro')} - mun {t(inf, 'toma/end/endNac/cMun')} CEP {t(inf, 'toma/end/endNac/CEP')}"),
        ("", ""),
        ("SERVICO", ""),
        ("  Cod. trib. nacional / municipal", f"{t(inf, 'serv/cServ/cTribNac')} / {t(inf, 'serv/cServ/cTribMun')}"),
        ("  Local da prestacao", t(inf, "serv/locPrest/cLocPrestacao")),
        ("  Descricao", desc),
        ("", ""),
        ("VALORES", ""),
        ("  Valor do servico", brl(t(inf, "valores/vServPrest/vServ"))),
        ("  ISSQN", f"tribISSQN={t(inf, 'valores/trib/tribMun/tribISSQN')} (1=tributavel) retencao={t(inf, 'valores/trib/tribMun/tpRetISSQN')} (1=nao retido); aliquota ISS: parametrizada pelo municipio"),
        ("  Total tributos", tot_txt),
    ]
    print("=" * 78)
    for k, v in linhas:
        print(f"{k:34s} {v}" if k or v else "")
    print("=" * 78)


if __name__ == "__main__":
    main()
