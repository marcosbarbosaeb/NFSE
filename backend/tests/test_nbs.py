"""NBS pesquisável no cadastro do tomador (06/10/2026)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import nbs


def test_lista_tem_so_codigos_completos_sem_repetir():
    lista = nbs.listar_nbs()
    assert len(lista) > 800
    assert all(len(n["codigo"]) == 9 and n["codigo"].isdigit() and n["descricao"] for n in lista)
    assert len({n["codigo"] for n in lista}) == len(lista)
    assert lista[0]["formatado"] == "1.0101.11.00" and nbs.formatar("114062000") == "1.1406.20.00"


def test_busca_por_palavra_sem_acento_e_por_codigo():
    achados = nbs.buscar_nbs("construcao edificacoes residenciais")
    assert achados and all("residenciais" in n["descricao"] for n in achados)
    # com ou sem pontos dá no mesmo; quem começa pelo número vem primeiro
    assert [n["codigo"] for n in nbs.buscar_nbs("1.0101.11")] == [n["codigo"] for n in nbs.buscar_nbs("1010111")]
    assert nbs.buscar_nbs("1010111")[0]["codigo"] == "101011100"
    assert nbs.buscar_nbs("palavraquenaoexiste") == [] and len(nbs.buscar_nbs("", limite=5)) == 5
    assert nbs.nbs_por_codigo("1.0101.11.00")["codigo"] == "101011100" and nbs.nbs_por_codigo("999999999") is None


def test_rota_devolve_a_lista():
    client = TestClient(app)
    r = client.get("/api/nbs?q=edificacoes&limite=3")
    assert r.status_code == 200 and len(r.json()) == 3 and set(r.json()[0]) == {"codigo", "descricao", "grupo", "formatado"}
    assert len(client.get("/api/nbs").json()) > 800
