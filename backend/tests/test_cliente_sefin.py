"""
app.fiscal.cliente_sefin — testa a CONSTRUÇÃO das requisições (URL, corpo
JSON, gzip+base64) contra os 4 scripts originais, com `requests` mockado.
Nenhum teste aqui toca rede de verdade: nenhum dos scripts fiscais nunca
rodou contra a API a partir deste sandbox (bloqueado — ver submit_dps.py),
então "testar de verdade" significa isso, e significava isso também nos
scripts originais.
"""
import base64
import gzip
import json
from unittest.mock import MagicMock, patch

import pytest

from app.fiscal.cliente_sefin import ADN_BASES, BASES, URL_SUBMISSAO, ClienteSefin


@pytest.fixture
def cliente(certificado_teste):
    return ClienteSefin(certificado_teste["private_key"], certificado_teste["cert"], tpAmb="1")


def _resposta_mock(status_code=201, json_data=None, content=b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = {"content-type": "application/json" if json_data is not None else ""}
    if json_data is not None:
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    else:
        resp.json.side_effect = ValueError("not json")
        resp.text = ""
    return resp


def test_tpamb_invalido_recusado(certificado_teste):
    with pytest.raises(ValueError):
        ClienteSefin(certificado_teste["private_key"], certificado_teste["cert"], tpAmb="3")


def test_submeter_dps_monta_url_e_corpo_certos(cliente):
    xml_bytes = b"<DPS>conteudo</DPS>"
    with patch("app.fiscal.cliente_sefin.requests.post") as post_mock:
        post_mock.return_value = _resposta_mock(201, {"chaveAcesso": "abc123", "nfseXmlGZipB64": None})
        resposta = cliente.submeter_dps(xml_bytes)

    assert post_mock.call_args.args[0] == URL_SUBMISSAO["1"] == f"{BASES['1']}/nfse"
    body = post_mock.call_args.kwargs["json"]
    assert set(body.keys()) == {"dpsXmlGZipB64"}
    assert gzip.decompress(base64.b64decode(body["dpsXmlGZipB64"])) == xml_bytes
    assert resposta.status_code == 201
    assert resposta.dados["chaveAcesso"] == "abc123"


def test_extrair_nfse_xml_descomprime_corretamente(cliente):
    from app.fiscal.cliente_sefin import RespostaSefin

    xml_original = b"<NFSe>ok</NFSe>"
    b64 = base64.b64encode(gzip.compress(xml_original)).decode("ascii")
    resposta = RespostaSefin(status_code=201, dados={"nfseXmlGZipB64": b64})
    assert cliente.extrair_nfse_xml(resposta) == xml_original


def test_consultar_dps_existe_devolve_status(cliente):
    with patch("app.fiscal.cliente_sefin.requests.get") as get_mock:
        get_mock.return_value = _resposta_mock(404)
        status = cliente.consultar_dps_existe("DPS31062002451723740001220000100000000000001")

    url_chamada = get_mock.call_args.args[0]
    assert url_chamada == f"{BASES['1']}/dps/DPS31062002451723740001220000100000000000001"
    assert status == 404


def test_proximo_ndps_livre_para_na_primeira_lacuna(cliente):
    respostas = [_resposta_mock(200), _resposta_mock(200), _resposta_mock(404)]
    with patch("app.fiscal.cliente_sefin.requests.get", side_effect=respostas):
        livre = cliente.proximo_ndps_livre_por_varredura(lambda n: f"id-{n}", max_tentativas=10)
    assert livre == 3


def test_enviar_evento_cancelamento_monta_url_e_corpo_certos(cliente):
    xml_bytes = b"<pedRegEvento>conteudo</pedRegEvento>"
    chave = "31062002245172374000122000000000094726097112223684"
    with patch("app.fiscal.cliente_sefin.requests.post") as post_mock:
        post_mock.return_value = _resposta_mock(201, {"alertas": []})
        resposta = cliente.enviar_evento_cancelamento(chave, xml_bytes)

    assert post_mock.call_args.args[0] == f"{BASES['1']}/nfse/{chave}/eventos"
    body = post_mock.call_args.kwargs["json"]
    assert set(body.keys()) == {"pedidoRegistroEventoXmlGZipB64"}
    assert gzip.decompress(base64.b64decode(body["pedidoRegistroEventoXmlGZipB64"])) == xml_bytes
    assert resposta.ok


def test_consultar_nfse_usa_base_correta(cliente):
    with patch("app.fiscal.cliente_sefin.requests.get") as get_mock:
        get_mock.return_value = _resposta_mock(200, {"nfseXmlGZipB64": None})
        cliente.consultar_nfse("chave-teste")
    assert get_mock.call_args.args[0] == f"{BASES['1']}/nfse/chave-teste"


def test_baixar_danfse_tenta_candidatos_do_adn_ate_achar_pdf(cliente):
    pdf_bytes = b"%PDF-1.4 conteudo falso"
    respostas = [_resposta_mock(404), _resposta_mock(200, content=pdf_bytes)]
    respostas[1].headers = {"content-type": "application/pdf"}
    with patch("app.fiscal.cliente_sefin.requests.get", side_effect=respostas):
        pdf = cliente.baixar_danfse("chave-teste")
    assert pdf == pdf_bytes


def test_homologacao_e_producao_usam_hosts_diferentes(certificado_teste):
    c_prod = ClienteSefin(certificado_teste["private_key"], certificado_teste["cert"], tpAmb="1")
    c_homolog = ClienteSefin(certificado_teste["private_key"], certificado_teste["cert"], tpAmb="2")
    assert c_prod.base != c_homolog.base
    assert "producaorestrita" in c_homolog.base
    assert "producaorestrita" not in c_prod.base
    assert ADN_BASES["1"] != ADN_BASES["2"]
