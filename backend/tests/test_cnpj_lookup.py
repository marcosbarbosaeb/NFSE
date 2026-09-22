"""
Testes de app.services.cnpj_lookup — `requests.get` sempre mockado (ver
docstring do módulo: rede bloqueada nesta sandbox, nenhum teste aqui pode
depender de acesso de verdade à BrasilAPI).
"""
import pytest
import requests

from app.services.cnpj_lookup import (
    CnpjInvalidoError,
    CnpjNaoEncontradoError,
    ConsultaCnpjIndisponivelError,
    consultar_cnpj,
)


class _RespostaFake:
    def __init__(self, status_code, corpo=None, quebra_json=False):
        self.status_code = status_code
        self._corpo = corpo
        self._quebra_json = quebra_json

    def json(self):
        if self._quebra_json:
            raise ValueError("não é JSON")
        return self._corpo


def test_cnpj_com_menos_de_14_digitos_da_erro_sem_chamar_rede(monkeypatch):
    def _nao_deveria_chamar(*a, **kw):
        raise AssertionError("não deveria ter chamado requests.get pra CNPJ inválido")

    monkeypatch.setattr(requests, "get", _nao_deveria_chamar)
    with pytest.raises(CnpjInvalidoError):
        consultar_cnpj("123")


def test_consulta_caminho_feliz_preenche_todos_os_campos(monkeypatch):
    corpo = {
        "razao_social": "EMPRESA TESTE LTDA",
        "logradouro": "RUA DAS FLORES",
        "numero": "123",
        "complemento": "SALA 4",
        "bairro": "CENTRO",
        "cep": "69000-000",
        "municipio": "MANAUS",
        "uf": "am",
        "codigo_municipio_ibge": 1302603,
        "descricao_situacao_cadastral": "ATIVA",
    }
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(200, corpo))

    dados = consultar_cnpj("12.345.678/0001-99")
    assert dados.razao_social == "EMPRESA TESTE LTDA"
    assert dados.logradouro == "RUA DAS FLORES"
    assert dados.numero == "123"
    assert dados.bairro == "CENTRO"
    assert dados.cep == "69000000"
    assert dados.municipio == "MANAUS"
    assert dados.uf == "AM"
    assert dados.cod_municipio_sugerido == "1302603"
    assert dados.situacao_cadastral == "ATIVA"


def test_consulta_cnpj_normaliza_pontuacao_antes_de_chamar_api(monkeypatch):
    urls_chamadas = []

    def _fake_get(url, timeout):
        urls_chamadas.append(url)
        return _RespostaFake(200, {"razao_social": "X", "municipio": "Y", "uf": "sp"})

    monkeypatch.setattr(requests, "get", _fake_get)
    consultar_cnpj("12.345.678/0001-99")
    assert urls_chamadas == ["https://brasilapi.com.br/api/cnpj/v1/12345678000199"]


def test_consulta_cnpj_nao_encontrado_da_404(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(404))
    with pytest.raises(CnpjNaoEncontradoError):
        consultar_cnpj("12345678000199")


def test_consulta_cnpj_erro_5xx_da_indisponivel(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(503))
    with pytest.raises(ConsultaCnpjIndisponivelError):
        consultar_cnpj("12345678000199")


def test_consulta_cnpj_timeout_de_rede_da_indisponivel(monkeypatch):
    def _fake_get(url, timeout):
        raise requests.exceptions.Timeout("demorou demais")

    monkeypatch.setattr(requests, "get", _fake_get)
    with pytest.raises(ConsultaCnpjIndisponivelError):
        consultar_cnpj("12345678000199")


def test_consulta_cnpj_resposta_sem_json_valido_da_indisponivel(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(200, quebra_json=True))
    with pytest.raises(ConsultaCnpjIndisponivelError):
        consultar_cnpj("12345678000199")


def test_consulta_cnpj_codigo_municipio_nao_numerico_vira_none(monkeypatch):
    corpo = {"razao_social": "X", "municipio": "Y", "uf": "sp", "codigo_municipio_ibge": "desconhecido"}
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(200, corpo))
    dados = consultar_cnpj("12345678000199")
    assert dados.cod_municipio_sugerido is None


def test_consulta_cnpj_campos_ausentes_nao_quebra(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _RespostaFake(200, {}))
    dados = consultar_cnpj("12345678000199")
    assert dados.razao_social == ""
    assert dados.logradouro is None
    assert dados.cod_municipio_sugerido is None
    assert dados.situacao_cadastral is None
