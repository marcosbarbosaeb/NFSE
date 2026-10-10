"""ISS retido pelo tomador (2026.10.7 — item D do roteiro).

Marca no cadastro do tomador (memória), troca só na nota, alíquota do ISS
guardada na empresa, conferência e XML. Regras do Anexo VI (raio-x, seção
15). Só dados sintéticos."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Emissao
from app.services import conferencia
from app.services.nota_visual import montar_nota_visual

NS = {"n": "http://www.sped.fazenda.gov.br/nfse"}


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _gerar(client, vinculo, **extra):
    r = client.post("/api/dps", json={"vinculo_id": str(vinculo.id), "competencia": "2026-10", "valor": 1000.0, "aliq_sn": 6.0, **extra})
    return r


def _xml(db, emissao_id):
    e = db.get(Emissao, emissao_id)
    return etree.fromstring(e.xml_dps.encode())


def _campo(xml, nome):
    return [x.text for x in xml.findall(f".//n:{nome}", NS)]


def test_tomador_que_retem_vale_pra_nota_com_a_aliquota_da_empresa(client, db, vinculo_teste, prestador_teste):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"iss_retido": True})
    assert r.status_code == 200, r.text
    assert any(v["iss_retido"] for v in client.get("/api/vinculos").json() if v["id"] == str(vinculo_teste.id))
    assert client.patch("/api/prestador", json={"aliquota_iss_retido": 2.5}).json()["aliquota_iss_retido"] == 2.5
    r = _gerar(client, vinculo_teste)
    assert r.status_code == 200, r.text
    xml = _xml(db, r.json()["id"])
    assert _campo(xml, "tpRetISSQN") == ["2"] and _campo(xml, "pAliq") == ["2.50"]
    visual = montar_nota_visual(db.get(Emissao, r.json()["id"]))
    assert visual["valores"]["issqn"].startswith("Retido pelo tomador") and "25,00" in visual["valores"]["issqn"]


def test_muda_so_naquela_nota(client, db, vinculo_teste):
    vinculo_teste.iss_retido = True
    db.flush()
    r = _gerar(client, vinculo_teste, iss_retido=False)
    assert r.status_code == 200, r.text
    assert _campo(_xml(db, r.json()["id"]), "tpRetISSQN") == ["1"]
    assert vinculo_teste.iss_retido is True  # o cadastro não muda


def test_sem_aliquota_a_conferencia_trava_e_a_digitada_vira_memoria(client, db, vinculo_teste, prestador_teste):
    vinculo_teste.iss_retido = True
    prestador_teste.aliquota_iss_retido = None
    db.flush()
    pontos = conferencia.conferir_nota(db, vinculo_teste, 1000, None, None, 6.0)
    assert any(p["codigo"] == "aliquota_iss_faltando" and p["nivel"] == "erro" for p in pontos)
    r = _gerar(client, vinculo_teste)
    assert r.status_code == 422 and "alíquota do ISS" in r.text
    r = _gerar(client, vinculo_teste, aliq_iss=3.0)
    assert r.status_code == 200, r.text
    assert prestador_teste.aliquota_iss_retido == 3.0 or prestador_teste.aliquota_iss_retido == Decimal("3.00")


@pytest.mark.parametrize("aliq", [1.0, 5.5])
def test_aliquota_fora_da_faixa(db, vinculo_teste, aliq):
    vinculo_teste.iss_retido = True
    db.flush()
    pontos = conferencia.conferir_nota(db, vinculo_teste, 1000, None, None, 6.0, aliq_iss=aliq)
    assert any(p["codigo"] == "aliquota_iss_fora" for p in pontos)


def test_mei_nunca_retem(client, db, vinculo_teste, prestador_teste):
    prestador_teste.op_simples_nacional = "2"
    prestador_teste.regime_apuracao_sn = None
    vinculo_teste.iss_retido = True
    db.flush()
    pontos = conferencia.conferir_nota(db, vinculo_teste, 1000, None, None, None)
    assert any(p["codigo"] == "mei_sem_retencao" and p["nivel"] == "aviso" for p in pontos)
    r = _gerar(client, vinculo_teste)
    assert r.status_code == 200, r.text
    xml = _xml(db, r.json()["id"])
    assert _campo(xml, "tpRetISSQN") == ["1"] and _campo(xml, "pAliq") == [] and _campo(xml, "pTotTribSN") == []


def test_sem_retencao_continua_igual(client, db, vinculo_teste):
    r = _gerar(client, vinculo_teste)
    xml = _xml(db, r.json()["id"])
    assert _campo(xml, "tpRetISSQN") == ["1"] and _campo(xml, "pAliq") == []
