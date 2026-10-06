"""Regrava app/data/nbs.json a partir do Anexo B da NFS-e Nacional.

Uso:  python scripts/atualizar_nbs.py CAMINHO/ANEXO_B-NBS2-LISTA_SERVICO_NACIONAL-SNNFSe.xlsx

A planilha (aba "LISTA.NBS_v2.0") vem do Portal da NFS-e (gov.br/nfse ›
Biblioteca › Documentação técnica). Entram só os códigos completos, de 9
dígitos (1.0101.11.00); os títulos de capítulo/posição viram o "grupo" de
cada código, que ajuda na busca por palavra. A planilha NÃO vai pro
repositório — só o json gerado.
"""
import datetime
import json
import sys
from pathlib import Path

import openpyxl

DESTINO = Path(__file__).resolve().parents[1] / "app" / "data" / "nbs.json"


def gerar(caminho: str) -> dict:
    pasta = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    aba = next(a for a in pasta.worksheets if "NBS" in a.title.upper())
    codigos: list[list[str]] = []
    vistos: set[str] = set()
    titulos: dict[str, str] = {}  # dígitos do título -> descrição
    for i, (codigo, descricao, *_resto) in enumerate(aba.iter_rows(values_only=True)):
        if i == 0 or codigo is None or descricao is None:
            continue
        digitos = "".join(c for c in str(codigo) if c.isdigit())
        descricao = " ".join(str(descricao).split())
        if len(digitos) == 9:
            if digitos in vistos:
                continue
            vistos.add(digitos)
            # o título mais próximo acima: a posição (5 dígitos) a que o código pertence
            grupo = titulos.get(digitos[:5], "")
            codigos.append([digitos, descricao, grupo if grupo != descricao else ""])
        else:
            titulos[digitos] = descricao
    codigos.sort()
    return {
        "fonte": Path(caminho).name,
        "gerado_em": datetime.date.today().isoformat(),
        "codigos": codigos,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dados = gerar(sys.argv[1])
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(dados['codigos'])} códigos NBS gravados em {DESTINO}")
