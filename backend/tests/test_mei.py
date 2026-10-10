"""MEI de verdade e regimes no XML (2026.10.7 — item A do roteiro).

Antes, campo vazio ia pro XML como o texto "None" (regApTribSN, regEspTrib,
IM) — o caso de quem é MEI ou não optante. As regras abaixo são do Anexo VI
da NT 009 (raio-x, seção 15). Tudo validado no esquema oficial 1.00 (o que a
Ana manda hoje) e no 1.01. Só dados sintéticos."""
from pathlib import Path

import pytest
from lxml import etree

from app.fiscal.dps import RegimeNaoInformadoError, montar_dps_xml, regras_do_regime

SCHEMAS = Path(__file__).resolve().parents[2] / "integracao" / "schemas"
NS = {"n": "http://www.sped.fazenda.gov.br/nfse"}


def _esquema(versao: str) -> etree.XMLSchema:
    if versao == "1.00":
        return etree.XMLSchema(etree.parse(str(SCHEMAS / "DPS_v1.00.xsd")))
    # O 1.01 oficial usa um "lookahead" (série não pode ser só zeros) que a
    # libxml2 não entende: troca pela expressão equivalente só pra validar aqui.
    import shutil
    import tempfile

    pasta = Path(tempfile.mkdtemp())
    for f in SCHEMAS.glob("*.xsd"):
        shutil.copy(f, pasta / f.name)
    simples = pasta / "tiposSimples_v1.01.xsd"
    simples.write_text(simples.read_text(encoding="utf-8").replace("^(?!0{1,5}$)\\d{1,5}$", "[0-9]*[1-9][0-9]*"), encoding="utf-8")
    return etree.XMLSchema(etree.parse(str(pasta / "DPS_v1.01.xsd")))


TOMA = {"CNPJ": "11222333000181", "xNome": "TOMADOR SINTETICO LTDA", "cMun": "3550308", "CEP": "01311000",
        "xLgr": "Av Teste", "nro": "100", "xBairro": "Centro"}
SERV = {"cLocPrestacao": "3106200", "cTribNac": "170601", "cTribMun": None, "descricao": "Serviço de teste", "cNBS": "118069000"}


def _dps(prest, **kw):
    base = {"CNPJ": "00000000000191", "IM": None, "cMun": "3106200", "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"}
    return montar_dps_xml(prest={**base, **prest}, toma=TOMA, serv=SERV, serie="1", n_dps=7, valor=150.0, tpAmb="2", **kw)


def _texto(dps) -> str:
    return etree.tostring(dps, encoding="unicode")


def _valida(dps, versao="1.00"):
    if versao == "1.01":
        dps = etree.fromstring(etree.tostring(dps))
        dps.set("versao", "1.01")
    _esquema(versao).assertValid(etree.ElementTree(dps))


def _um(dps, caminho):
    achados = dps.findall(f".//n:{caminho}", NS)
    return [a.text for a in achados]


@pytest.mark.parametrize("versao", ["1.00", "1.01"])
def test_mei_sai_sem_none_e_valida_no_esquema(versao):
    dps = _dps({"opSimpNac": "2", "regApTribSN": None, "regEspTrib": None, "IM": ""}, aliq_sn=6.0, iss_retido=True, aliq_iss=3.0)
    texto = _texto(dps)
    assert "None" not in texto
    assert _um(dps, "opSimpNac") == ["2"]
    assert _um(dps, "regApTribSN") == []  # E0162: MEI não manda
    assert _um(dps, "regEspTrib") == ["0"]  # E0174
    assert _um(dps, "IM") == []
    assert _um(dps, "pTotTribSN") == [] and _um(dps, "indTotTrib") == ["0"]  # E0710
    assert _um(dps, "tpRetISSQN") == ["1"] and _um(dps, "pAliq") == []  # E0583, E0600
    _valida(dps, versao)


def test_mei_com_regime_especial_cadastrado_vai_nenhum():
    dps = _dps({"opSimpNac": "2", "regApTribSN": "1", "regEspTrib": "5"})
    assert _um(dps, "regEspTrib") == ["0"] and _um(dps, "regApTribSN") == []


@pytest.mark.parametrize("versao", ["1.00", "1.01"])
def test_simples_me_epp_continua_igual(versao):
    dps = _dps({"IM": "12345"}, aliq_sn=6.0)
    assert _um(dps, "regApTribSN") == ["1"] and _um(dps, "IM") == ["12345"]
    assert _um(dps, "pTotTribSN") == ["6.00"] and _um(dps, "tpRetISSQN") == ["1"]
    _valida(dps, versao)


def test_me_epp_sem_regime_de_apuracao_nao_manda_o_campo():
    dps = _dps({"regApTribSN": None, "regEspTrib": None}, aliq_sn=6.0)
    assert "None" not in _texto(dps)
    assert _um(dps, "regApTribSN") == [] and _um(dps, "regEspTrib") == ["0"]
    _valida(dps)


def test_nao_optante_nao_manda_regime_de_apuracao():
    dps = _dps({"opSimpNac": "1", "regApTribSN": "1"})
    assert _um(dps, "regApTribSN") == []
    assert "None" not in _texto(dps)


def test_sem_regime_para_antes_de_montar():
    with pytest.raises(RegimeNaoInformadoError, match="regime tributário"):
        _dps({"opSimpNac": None})


def test_iss_retido_me_epp_leva_a_aliquota():
    dps = _dps({}, aliq_sn=6.0, iss_retido=True, aliq_iss=2.5)
    assert _um(dps, "tpRetISSQN") == ["2"] and _um(dps, "pAliq") == ["2.50"]
    _valida(dps)  # só 1.00: no 1.01 a ordem de pAliq e tpRetISSQN inverte (raio-x, seção 15)


def test_iss_retido_fora_do_simples_pro_iss_nao_manda_aliquota():
    dps = _dps({"regApTribSN": "2"}, aliq_sn=6.0, iss_retido=True, aliq_iss=2.5)
    assert _um(dps, "tpRetISSQN") == ["2"] and _um(dps, "pAliq") == []  # E0635
    _valida(dps)


def test_regras_do_regime():
    assert regras_do_regime({"opSimpNac": "2", "regApTribSN": "1", "regEspTrib": "3"})["regEspTrib"] == "0"
    assert regras_do_regime({"opSimpNac": "3", "regApTribSN": "", "regEspTrib": None}) == {
        "op": "3", "mei": False, "me_epp": True, "regApTribSN": None, "regEspTrib": "0",
    }
