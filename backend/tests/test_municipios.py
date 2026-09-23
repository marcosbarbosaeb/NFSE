"""Tabela de municípios (pedido do Marcos: esconder o código IBGE — ver
app/services/municipios.py)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.municipios import buscar_municipios, codigo_por_nome, municipio_por_codigo, rotulo_municipio


def test_busca_sem_acento_e_por_prefixo_primeiro():
    nomes = [m["rotulo"] for m in buscar_municipios("belo")]
    assert nomes[0] == "Belo Horizonte/MG" or "Belo Horizonte/MG" in nomes[:3]
    assert buscar_municipios("sao paulo", uf="SP")[0]["codigo"] == "3550308"


def test_busca_aceita_cidade_barra_uf():
    r = buscar_municipios("manaus/am")
    assert r and r[0]["codigo"] == "1302603"


def test_busca_curta_demais_volta_vazio():
    assert buscar_municipios("a") == []


def test_rotulo_e_codigo_por_nome():
    assert rotulo_municipio("3106200") == "Belo Horizonte/MG"
    assert rotulo_municipio(None) is None
    assert rotulo_municipio("9999999") == "9999999"
    assert codigo_por_nome("Belo Horizonte", "mg") == "3106200"
    assert codigo_por_nome("São Paulo", "SP") == "3550308"
    assert municipio_por_codigo("0000000") is None


def test_endpoints_publicos():
    client = TestClient(app)
    r = client.get("/api/municipios", params={"q": "manaus"})
    assert r.status_code == 200
    assert r.json()[0]["rotulo"] == "Manaus/AM"
    assert client.get("/api/municipios/1302603").json()["nome"] == "Manaus"
    assert client.get("/api/municipios/0000000").status_code == 404
