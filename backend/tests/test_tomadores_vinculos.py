"""
Catálogo de tomadores + vínculo self-service — Marco 13 (ver
app/services/tomadores.py e app/services/vinculos.py). Mesmo padrão
real-Postgres-com-rollback das demais suítes.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.services.tomadores import CnpjJaCadastradoError, criar_tomador, listar_catalogo
from app.services.vinculos import ApelidoJaExisteError, atualizar_vinculo, criar_vinculo


# --- Camada de serviço ---


def test_criar_tomador_normaliza_cnpj_e_usa_status_aprovado(db):
    tomador = criar_tomador(
        db, cnpj="99.888.777/0001-66", razao_social="NOVO TOMADOR LTDA", cod_municipio="3550308",
    )
    assert tomador.cnpj == "99888777000166"
    assert tomador.status == "aprovado"


def test_criar_tomador_cnpj_duplicado_da_erro(db):
    criar_tomador(db, cnpj="99888777000166", razao_social="A", cod_municipio="3550308")
    with pytest.raises(CnpjJaCadastradoError):
        criar_tomador(db, cnpj="99888777000166", razao_social="B", cod_municipio="3550308")


def test_listar_catalogo_apenas_meus_so_traz_quem_tem_vinculo_ativo(db, prestador_teste, vinculo_teste):
    # `tomador` é catálogo CENTRAL sem RLS (ver alembic/versions/5af6e092d5e1_rls.py)
    # — o banco de dev pode ter outros tomadores reais além dos desta
    # fixture, então a checagem é "contém", não "é exatamente".
    outro_tomador = criar_tomador(db, cnpj="11111111000191", razao_social="SEM VINCULO LTDA", cod_municipio="3550308")

    todos = listar_catalogo(db, prestador_id=prestador_teste.id, apenas_meus=False)
    razoes_todos = {t.razao_social for t in todos}
    assert {"TOMADOR DE TESTE LTDA", "SEM VINCULO LTDA"} <= razoes_todos

    meus = listar_catalogo(db, prestador_id=prestador_teste.id, apenas_meus=True)
    razoes_meus = {t.razao_social for t in meus}
    assert razoes_meus == {"TOMADOR DE TESTE LTDA"}
    assert outro_tomador.razao_social not in razoes_meus


def test_criar_vinculo_usando_tomador_existente(db, prestador_teste, vinculo_teste):
    novo = criar_vinculo(
        db, prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido="Segundo programa",
        cod_local_prestacao=prestador_teste.cod_municipio, cod_trib_nacional="170601",
        template_descricao="Serviço - {competencia_mm_aaaa}",
    )
    assert novo.apelido == "Segundo programa"
    assert novo.tomador_id == vinculo_teste.tomador_id
    assert novo.ativo is True


def test_criar_vinculo_apelido_duplicado_da_erro(db, prestador_teste, vinculo_teste):
    with pytest.raises(ApelidoJaExisteError):
        criar_vinculo(
            db, prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido=vinculo_teste.apelido,
            cod_local_prestacao=prestador_teste.cod_municipio, cod_trib_nacional="170601",
            template_descricao="X",
        )


def test_atualizar_vinculo_so_muda_campos_passados(db, vinculo_teste):
    original_template = vinculo_teste.template_descricao
    atualizado = atualizar_vinculo(db, vinculo_teste, dia_limite_emissao=25, dias_para_recebimento=10)
    assert atualizado.dia_limite_emissao == 25
    assert atualizado.dias_para_recebimento == 10
    assert atualizado.template_descricao == original_template  # não tocado


def test_atualizar_vinculo_apelido_para_um_ja_usado_da_erro(db, prestador_teste, vinculo_teste):
    outro = criar_vinculo(
        db, prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido="Outro apelido",
        cod_local_prestacao=prestador_teste.cod_municipio, cod_trib_nacional="170601", template_descricao="X",
    )
    with pytest.raises(ApelidoJaExisteError):
        atualizar_vinculo(db, outro, apelido=vinculo_teste.apelido)


# --- Camada HTTP ---


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_endpoint_criar_vinculo_com_tomador_existente(client, vinculo_teste):
    resp = client.post("/api/vinculos", json={
        "tomador_id": str(vinculo_teste.tomador_id),
        "apelido": "Programa B",
        "cod_local_prestacao": "3550308",
        "cod_trib_nacional": "170601",
        "template_descricao": "Serviço B - {competencia_mm_aaaa}",
    })
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["apelido"] == "Programa B"
    assert dados["tomador"]["razao_social"] == "TOMADOR DE TESTE LTDA"


def test_endpoint_criar_vinculo_com_novo_tomador(client, prestador_teste):
    resp = client.post("/api/vinculos", json={
        "novo_tomador": {
            "cnpj": "22333444000155", "razao_social": "CLIENTE NOVO LTDA", "cod_municipio": "3550308",
        },
        "apelido": "Cliente Novo",
        "cod_local_prestacao": "3550308",
        "cod_trib_nacional": "170601",
        "template_descricao": "Serviço - {competencia_mm_aaaa}",
        "dia_limite_emissao": 25,
        "dias_para_recebimento": 15,
    })
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["tomador"]["cnpj"] == "22333444000155"
    assert dados["dia_limite_emissao"] == 25
    assert dados["dias_para_recebimento"] == 15


def test_endpoint_criar_vinculo_sem_tomador_nem_novo_tomador_da_422(client):
    resp = client.post("/api/vinculos", json={
        "apelido": "X", "cod_local_prestacao": "3550308", "cod_trib_nacional": "170601", "template_descricao": "X",
    })
    assert resp.status_code == 422


def test_endpoint_criar_vinculo_com_os_dois_da_422(client, vinculo_teste):
    resp = client.post("/api/vinculos", json={
        "tomador_id": str(vinculo_teste.tomador_id),
        "novo_tomador": {"cnpj": "22333444000155", "razao_social": "X", "cod_municipio": "3550308"},
        "apelido": "X", "cod_local_prestacao": "3550308", "cod_trib_nacional": "170601", "template_descricao": "X",
    })
    assert resp.status_code == 422


def test_endpoint_ver_vinculo(client, vinculo_teste):
    resp = client.get(f"/api/vinculos/{vinculo_teste.id}")
    assert resp.status_code == 200
    assert resp.json()["apelido"] == vinculo_teste.apelido


def test_endpoint_ver_vinculo_inexistente_da_404(client):
    resp = client.get(f"/api/vinculos/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_endpoint_atualizar_vinculo_parcial(client, vinculo_teste):
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"dia_limite_emissao": 20})
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["dia_limite_emissao"] == 20
    assert dados["template_descricao"] == vinculo_teste.template_descricao


def test_endpoint_listar_tomadores_meus_vs_todos(client, prestador_teste, vinculo_teste, db):
    criar_tomador(db, cnpj="11111111000191", razao_social="SEM VINCULO LTDA", cod_municipio="3550308")

    resp_todos = client.get("/api/tomadores")
    assert resp_todos.status_code == 200
    razoes_todos = {t["razao_social"] for t in resp_todos.json()}
    assert {"TOMADOR DE TESTE LTDA", "SEM VINCULO LTDA"} <= razoes_todos

    resp_meus = client.get("/api/tomadores", params={"apenas_meus": "true"})
    assert resp_meus.status_code == 200
    assert len(resp_meus.json()) == 1
    assert resp_meus.json()[0]["razao_social"] == "TOMADOR DE TESTE LTDA"
