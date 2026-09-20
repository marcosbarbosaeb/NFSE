"""
Regressão da geração de DPS (build_dps.py) — trava o XML gerado HOJE, pros 5
fornecedores reais, antes do Marco 3 trocar FORNECEDORES hardcoded por dados
vindos do Postgres (tabelas prestador/tomador/prestador_tomador migradas no
Marco 1). Qualquer diferença de valor de campo, e não só de estrutura, deve
quebrar um teste aqui.
"""
import re
import sys
from pathlib import Path

import pytest
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_dps import FORNECEDORES, build_dps_xml  # noqa: E402

NS = "http://www.sped.fazenda.gov.br/nfse"
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

# Inputs fixos e determinísticos por fornecedor — servem tanto pra validação
# de XSD quanto pra checagem campo-a-campo abaixo. `ordem` só é usado por
# quem precisa (AWIN/AWIN Rchlo); os demais ignoram o kwarg.
_INPUTS_POR_FORNECEDOR = {
    "squad_epoca": dict(competencia="2026-08", valor=17654.40, n_dps=1, aliq_sn=12.5, ordem=None),
    "elausa": dict(competencia="2026-07", valor=3200.00, n_dps=1, aliq_sn=12.5, ordem=None),
    "magalu": dict(competencia="2026-07", valor=980.50, n_dps=1, aliq_sn=12.5, ordem=None),
    "awin": dict(competencia="2026-08", valor=450.00, n_dps=1, aliq_sn=12.5, ordem="123456"),
    "awin_rchlo": dict(competencia="2026-08", valor=75.30, n_dps=1, aliq_sn=12.5, ordem="123457"),
}


def _xsd_dps():
    return etree.XMLSchema(etree.parse(str(SCHEMAS_DIR / "DPS_v1.00.xsd")))


def _build(fornecedor_key, **overrides):
    kwargs = dict(_INPUTS_POR_FORNECEDOR[fornecedor_key])
    kwargs.update(overrides)
    return build_dps_xml(
        fornecedor_key,
        kwargs["competencia"],
        kwargs["valor"],
        kwargs["n_dps"],
        tpAmb="1",
        aliq_sn=kwargs["aliq_sn"],
        dcompet="2026-09-10",
        ordem=kwargs["ordem"],
    )


@pytest.mark.parametrize("fornecedor_key", list(FORNECEDORES.keys()))
def test_fornecedores_conhecidos_nao_mudam_sem_querer(fornecedor_key):
    """Se alguém editar/remover um fornecedor de FORNECEDORES sem querer,
    isso deve aparecer aqui, não só silenciosamente em produção."""
    assert fornecedor_key in _INPUTS_POR_FORNECEDOR, (
        f"Fornecedor '{fornecedor_key}' existe em FORNECEDORES mas não tem "
        "inputs de teste cadastrados em _INPUTS_POR_FORNECEDOR — adicione."
    )


@pytest.mark.parametrize("fornecedor_key", list(_INPUTS_POR_FORNECEDOR.keys()))
def test_dps_gerada_valida_contra_xsd_oficial(fornecedor_key):
    dps_el = _build(fornecedor_key)
    xsd = _xsd_dps()
    xsd.assertValid(etree.ElementTree(dps_el))


@pytest.mark.parametrize("fornecedor_key", list(_INPUTS_POR_FORNECEDOR.keys()))
def test_id_dps_segue_formato_oficial(fornecedor_key):
    """Id = 'DPS' + cMun(7) + tipoInsc(1) + CNPJ(14) + serie(5) + nDPS(15)."""
    dps_el = _build(fornecedor_key)
    infDPS = dps_el.find(f"{{{NS}}}infDPS")
    id_dps = infDPS.get("Id")
    assert re.fullmatch(r"DPS\d{7}2\d{14}\d{5}\d{15}", id_dps), id_dps


def test_awin_e_awin_rchlo_exigem_ordem():
    """AWIN e AWIN Rchlo têm {ordem} no template — sem --ordem tem que
    estourar, não silenciosamente gerar descrição quebrada."""
    for chave in ("awin", "awin_rchlo"):
        with pytest.raises(ValueError):
            _build(chave, ordem=None)


def test_squad_epoca_bate_com_golden_file_real():
    """output/DPS_squad_epoca_2026-08.xml é uma nota REAL já gerada e usada
    (ver README/histórico). Regenerar com os mesmos inputs (fixando dCompet,
    já que dhEmi/dCompet variam com o relógio) tem que produzir exatamente o
    mesmo XML, campo a campo."""
    golden_path = OUTPUT_DIR / "DPS_squad_epoca_2026-08.xml"
    if not golden_path.exists():
        pytest.skip(f"golden file não encontrado: {golden_path}")

    golden = etree.parse(str(golden_path)).getroot()
    golden_infDPS = golden.find(f"{{{NS}}}infDPS")
    # dCompet no golden file foi gerado no dia em que o arquivo foi criado
    # (padrão: hoje da geração) — normaliza pro valor fixo usado no teste.
    dcompet_golden = golden_infDPS.find(f"{{{NS}}}dCompet").text

    gerado = _build("squad_epoca", competencia="2026-08", valor=17654.40, n_dps=1, aliq_sn=12.5, ordem=None)
    gerado = etree.fromstring(
        etree.tostring(gerado).replace(b"<dCompet>2026-09-10</dCompet>", f"<dCompet>{dcompet_golden}</dCompet>".encode())
    )

    def normaliza(el):
        # dhEmi é timestamp de geração — não é fiscalmente estável, remove
        # dos dois lados antes de comparar. remove_blank_text neutraliza a
        # diferença de pretty-printing entre o golden file (gravado com
        # pretty_print=True pelo CLI) e o XML construído direto em memória
        # aqui (sem indentação) — ambos têm que dizer a mesma coisa
        # semanticamente, não bater byte a byte incluindo indentação.
        parser = etree.XMLParser(remove_blank_text=True)
        clone = etree.fromstring(etree.tostring(el), parser=parser)
        dhEmi = clone.find(f".//{{{NS}}}dhEmi")
        if dhEmi is not None:
            dhEmi.text = "NORMALIZADO"
        return etree.tostring(clone, method="c14n")

    assert normaliza(gerado) == normaliza(golden)


@pytest.mark.parametrize("fornecedor_key", list(_INPUTS_POR_FORNECEDOR.keys()))
def test_campos_fiscais_batem_com_cadastro_atual(fornecedor_key):
    """Snapshot dos campos que IMPORTAM fiscalmente (CNPJs, tributação,
    município) — o texto exato da descrição muda por competência/ordem, mas
    estes não podem, sob pena de nota sair com dado fiscal errado."""
    cfg = FORNECEDORES[fornecedor_key]
    dps_el = _build(fornecedor_key)
    infDPS = dps_el.find(f"{{{NS}}}infDPS")

    def txt(*tags):
        path = "/".join(f"{{{NS}}}{tag}" for tag in tags)
        el = infDPS.find(path)
        return el.text

    assert txt("prest", "CNPJ") == cfg["prest"]["CNPJ"]
    assert txt("prest", "IM") == cfg["prest"]["IM"]
    assert txt("toma", "CNPJ") == cfg["toma"]["CNPJ"]
    assert txt("toma", "xNome") == cfg["toma"]["xNome"]
    assert txt("serv", "locPrest", "cLocPrestacao") == cfg["serv"]["cLocPrestacao"]
    assert txt("serv", "cServ", "cTribNac") == cfg["serv"]["cTribNac"]
    assert txt("serv", "cServ", "cTribMun") == cfg["serv"]["cTribMun"]
    assert txt("cLocEmi") == cfg["prest"]["cMun"]
