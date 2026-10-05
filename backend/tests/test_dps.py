"""
Equivalência entre app.fiscal.dps (novo, decouplado) e integracao/build_dps.py
(original, com FORNECEDORES hardcoded) — prova que o Marco 3 (desacoplar em
biblioteca importável) não mudou nenhum byte de comportamento fiscal.

O adaptador `_montar_via_biblioteca_nova` abaixo é SÓ de teste: converte uma
entrada de FORNECEDORES pro formato de dicts que app.fiscal.dps.montar_dps_xml
espera. Isso não existe na biblioteca nova de propósito — ela não deveria
saber que FORNECEDORES existe; é o Marco 6 que vai montar esses dicts a
partir do Postgres.
"""
from pathlib import Path

import pytest
from lxml import etree

from app.fiscal.dps import DescricaoIncompletaError, montar_dps_xml, montar_id_dps, renderizar_descricao

from build_dps import FORNECEDORES, build_dps_xml  # noqa: E402  (via sys.path em conftest.py)

NS = "http://www.sped.fazenda.gov.br/nfse"
SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "integracao" / "schemas"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "integracao" / "output"

_INPUTS = {
    "squad_epoca": dict(competencia="2026-08", valor=17654.40, n_dps=1, aliq_sn=12.5, ordem=None),
    "elausa": dict(competencia="2026-07", valor=3200.00, n_dps=1, aliq_sn=12.5, ordem=None),
    "magalu": dict(competencia="2026-07", valor=980.50, n_dps=1, aliq_sn=12.5, ordem=None),
    "awin": dict(competencia="2026-08", valor=450.00, n_dps=1, aliq_sn=12.5, ordem="123456"),
    "awin_rchlo": dict(competencia="2026-08", valor=75.30, n_dps=1, aliq_sn=12.5, ordem="123457"),
}


def _montar_original(fornecedor_key, **overrides):
    kwargs = dict(_INPUTS[fornecedor_key])
    kwargs.update(overrides)
    return build_dps_xml(
        fornecedor_key, kwargs["competencia"], kwargs["valor"], kwargs["n_dps"],
        tpAmb="1", aliq_sn=kwargs["aliq_sn"], dcompet="2026-09-10", ordem=kwargs["ordem"],
    )


def _montar_via_biblioteca_nova(fornecedor_key, **overrides):
    kwargs = dict(_INPUTS[fornecedor_key])
    kwargs.update(overrides)
    cfg = FORNECEDORES[fornecedor_key]

    descricao = renderizar_descricao(
        cfg["serv"]["descricao_template"], kwargs["competencia"],
        ordem=kwargs["ordem"], dados_bancarios=cfg.get("dados_bancarios"),
    )
    serv = {**cfg["serv"], "descricao": descricao}

    return montar_dps_xml(
        prest=cfg["prest"], toma=cfg["toma"], serv=serv,
        serie=cfg["serie"], n_dps=kwargs["n_dps"], valor=kwargs["valor"],
        tpAmb="1", aliq_sn=kwargs["aliq_sn"], dcompet="2026-09-10",
    )


def _normaliza(el):
    parser = etree.XMLParser(remove_blank_text=True)
    clone = etree.fromstring(etree.tostring(el), parser=parser)
    dhEmi = clone.find(f".//{{{NS}}}dhEmi")
    if dhEmi is not None:
        dhEmi.text = "NORMALIZADO"
    return etree.tostring(clone, method="c14n")


@pytest.mark.parametrize("fornecedor_key", list(_INPUTS.keys()))
def test_biblioteca_nova_produz_xml_identico_ao_original(fornecedor_key):
    original = _montar_original(fornecedor_key)
    novo = _montar_via_biblioteca_nova(fornecedor_key)
    assert _normaliza(novo) == _normaliza(original)


@pytest.mark.parametrize("fornecedor_key", list(_INPUTS.keys()))
def test_biblioteca_nova_valida_contra_xsd_oficial(fornecedor_key):
    xsd = etree.XMLSchema(etree.parse(str(SCHEMAS_DIR / "DPS_v1.00.xsd")))
    novo = _montar_via_biblioteca_nova(fornecedor_key)
    xsd.assertValid(etree.ElementTree(novo))


def test_montar_id_dps_bate_com_original():
    for fornecedor_key, cfg in FORNECEDORES.items():
        esperado = ("DPS" + cfg["prest"]["cMun"].zfill(7) + "2" + cfg["prest"]["CNPJ"].zfill(14)
                    + cfg["serie"].zfill(5) + "1".zfill(15))
        assert montar_id_dps(cfg["prest"]["cMun"], cfg["prest"]["CNPJ"], cfg["serie"], 1) == esperado


def test_renderizar_descricao_exige_ordem_quando_template_pede():
    with pytest.raises(DescricaoIncompletaError):
        renderizar_descricao("Ordem: {ordem}", "2026-08", ordem=None)
    # não deve levantar quando ordem é dada:
    assert renderizar_descricao("Ordem: {ordem}", "2026-08", ordem="123") == "Ordem: 123"


def test_squad_epoca_bate_com_golden_file_real():
    golden_path = OUTPUT_DIR / "DPS_squad_epoca_2026-08.xml"
    if not golden_path.exists():
        pytest.skip(f"golden file não encontrado: {golden_path}")
    golden = etree.parse(str(golden_path)).getroot()
    dcompet_golden = golden.find(f".//{{{NS}}}dCompet").text

    novo = _montar_via_biblioteca_nova("squad_epoca")
    novo = etree.fromstring(
        etree.tostring(novo).replace(b"<dCompet>2026-09-10</dCompet>", f"<dCompet>{dcompet_golden}</dCompet>".encode())
    )
    assert _normaliza(novo) == _normaliza(golden)


def test_tomador_estrangeiro_sai_com_endereco_no_exterior_e_comercio_exterior():
    """Vendedor de fora (NIF): a mesma receita das notas já autorizadas pela
    Receita pra vendedores estrangeiros — endExt só com o país, grupo comExt
    e ISS tributável aqui. E o XML continua válido no XSD oficial."""
    from app.fiscal.dps import NS, montar_dps_xml

    dps = montar_dps_xml(
        prest={"CNPJ": "11222333000181", "IM": "123", "cMun": "3106200", "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"},
        toma={"NIF": "91440300MA5XYZ", "xNome": "SHENZHEN LOJA CO., LIMITED", "cPais": "cn", "cMun": None, "CEP": None, "xLgr": None, "nro": None, "xBairro": None},
        serv={"cLocPrestacao": "3106200", "cTribNac": "170601", "cTribMun": "001", "descricao": "Comissão", "cNBS": "114062000"},
        serie="900", n_dps=7, valor=2.83, tpAmb="2", aliq_sn=12.5,
    )
    etree.XMLSchema(etree.parse(str(SCHEMAS_DIR / "DPS_v1.00.xsd"))).assertValid(etree.ElementTree(dps))
    t = lambda caminho: dps.find(".//" + "/".join(f"{{{NS}}}{p}" for p in caminho.split("/")))
    assert t("toma/end/endExt/cPais").text == "CN" and t("toma/end/endExt/xCidade").text == "-"
    assert t("serv/comExt/vServMoeda").text == "2.83" and t("serv/comExt/tpMoeda").text == "986"
    assert t("valores/trib/tribMun/tribISSQN").text == "1"
    # Tomador brasileiro não ganha nada disso.
    br = montar_dps_xml(
        prest={"CNPJ": "11222333000181", "IM": "123", "cMun": "3106200", "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"},
        toma={"CNPJ": "11222333000181", "xNome": "Loja", "cMun": "3550308", "CEP": "01311000", "xLgr": "Av X", "nro": "1", "xBairro": "Centro"},
        serv={"cLocPrestacao": "3106200", "cTribNac": "170601", "descricao": "Comissão"}, serie="900", n_dps=8, valor=10, tpAmb="2",
    )
    assert br.find(f".//{{{NS}}}comExt") is None and br.find(f".//{{{NS}}}endExt") is None
