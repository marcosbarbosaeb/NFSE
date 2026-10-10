"""Perfis no cadastro (2026.10.7 — ideias/perfis-no-cadastro.md).

Um perfil, vários, "Não me encontrei", pular, busca que acha e que não acha,
dois CNPJs com perfis diferentes e os números da Gestão. Só dados sintéticos."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import PerfilBusca, Prestador, Usuario
from app.services import perfis


def test_catalogo_e_busca():
    assert perfis.ids() == ["lote", "clientes_fixos", "fechamento_mensal", "avulso"]
    assert perfis.buscar("fotografo") == ["avulso"]  # sem acento também acha
    assert perfis.buscar("Social") == ["clientes_fixos"]
    assert "lote" in perfis.buscar("shopee")
    assert perfis.buscar("piloto de avião") == []


def test_um_varios_outro_e_pular(db, prestador_teste):
    perfis.salvar(db, prestador_teste, perfis=["avulso"], outro=None, pulou=False)
    assert prestador_teste.perfis == ["avulso"] and perfis.principal(prestador_teste)["id"] == "avulso"
    perfis.salvar(db, prestador_teste, perfis=["fechamento_mensal", "lote", "lote"], outro=None, pulou=False)
    assert prestador_teste.perfis == ["fechamento_mensal", "lote"]
    assert perfis.principal(prestador_teste)["atalho"]["link"] == "/app/nfse?nova=1"
    perfis.salvar(db, prestador_teste, perfis=[], outro="Faço tatuagem", pulou=False)
    assert prestador_teste.perfis == [] and prestador_teste.perfil_outro == "Faço tatuagem"
    perfis.salvar(db, prestador_teste, perfis=["avulso"], outro="x", pulou=True)
    assert prestador_teste.perfis == [] and prestador_teste.perfil_pulou and prestador_teste.perfil_respondido_em
    with pytest.raises(perfis.PerfilError):
        perfis.salvar(db, prestador_teste, perfis=[], outro=None, pulou=False)
    with pytest.raises(perfis.PerfilError):
        perfis.salvar(db, prestador_teste, perfis=["inventado"], outro=None, pulou=False)


def test_buscas_sem_resultado_viram_lista_de_demanda(db, prestador_teste):
    perfis.salvar(db, prestador_teste, perfis=["avulso"], outro=None, pulou=False,
                  buscas_sem_resultado=["Piloto de drone", "fotógrafo", "ab"])
    textos = [t for (t,) in db.query(PerfilBusca.texto).all()]
    assert "Piloto de drone" in textos and "fotógrafo" not in textos and "ab" not in textos


def test_dois_cnpjs_com_perfis_diferentes(db, prestador_teste):
    outra = Prestador(id=uuid.uuid4(), cpf_cnpj="00000000000272", razao_social="FILIAL SINTETICA", cod_municipio="3106200")
    definir_prestador_atual(db, outra.id)
    db.add(outra)
    db.flush()
    perfis.salvar(db, outra, perfis=["lote"], outro=None, pulou=False)
    definir_prestador_atual(db, prestador_teste.id)
    perfis.salvar(db, prestador_teste, perfis=["clientes_fixos"], outro=None, pulou=False)
    assert prestador_teste.perfis == ["clientes_fixos"] and outra.perfis == ["lote"]


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


def test_rotas(client, db, prestador_teste):
    lista = client.get("/api/perfis").json()["perfis"]
    assert [p["titulo"] for p in lista][0] == "Muitas notas de uma vez" and "id" in lista[0]
    assert client.get("/api/empresa/perfil").json()["respondido"] is False
    r = client.put("/api/empresa/perfil", json={"perfis": ["lote"], "buscas_sem_resultado": ["astronauta"]})
    assert r.status_code == 200 and r.json()["perfil_principal"]["atalho"]["link"] == "/app/nfse/lote"
    assert client.put("/api/empresa/perfil", json={"perfis": []}).status_code == 422
    assert client.put("/api/empresa/perfil", json={"pulou": True}).json()["pulou"] is True


def test_cadastro_com_perfil(db, monkeypatch):
    monkeypatch.setattr(db, "commit", db.flush)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    try:
        c = TestClient(app)
        r = c.post("/api/cadastro", json={
            "email": f"perfil{uuid.uuid4().hex[:6]}@exemplo.com.br", "senha": "senha-boa-123", "whatsapp": "31999990000",
            "razao_social": "EMPRESA SINTETICA LTDA", "cpf_cnpj": "11222333000181", "cod_municipio": "3106200",
            "perfil": {"perfis": ["avulso", "clientes_fixos"], "buscas_sem_resultado": ["mergulhador"]},
        })
        assert r.status_code == 200, r.text
        u = db.query(Usuario).filter_by(email=r.json()["email"]).one()
        definir_prestador_atual(db, u.prestador_id)
        p = db.get(Prestador, u.prestador_id)
        assert p.perfis == ["avulso", "clientes_fixos"] and p.perfil_respondido_em is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_resumo_da_gestao(db, prestador_teste):
    db.add(Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"g{uuid.uuid4().hex[:6]}@exemplo.com.br", senha_hash="x"))
    perfis.salvar(db, prestador_teste, perfis=["avulso", "lote"], outro="Também faço bolo", pulou=False,
                  buscas_sem_resultado=["Confeiteira", "confeiteiras"])
    r = perfis.resumo_gestao(db, prestador_teste.id)
    avulso = next(p for p in r["perfis"] if p["id"] == "avulso")
    assert avulso["principal"] >= 1 and avulso["marcado"] >= 1
    assert any(g["texto"] == "Também faço bolo" for g in r["nao_me_encontrei"])
    confeiteira = next(g for g in r["buscas_sem_resultado"] if g["texto"].lower().startswith("confeiteira"))
    assert confeiteira["vezes"] >= 2  # plural agrupado
