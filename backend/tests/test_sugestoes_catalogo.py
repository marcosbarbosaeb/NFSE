"""Padrões do catálogo (05/10/2026): "deixe essas configurações como a
configuração padrão dos tomadores pré-cadastrados" — só regras de nota,
nunca dados de contato; e a conta de um cliente não troca o que já está lá."""
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Assinatura, Tomador
from app.services import vinculos


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


def test_registrar_so_preenche_o_que_falta_e_publicar_sobrescreve(db, prestador_teste, vinculo_teste):
    tomador = db.get(Tomador, vinculo_teste.tomador_id)
    tomador.status = "aprovado"
    tomador.sug_template_descricao = "Descrição que já estava no catálogo"
    tomador.sug_cod_nbs = None
    vinculo_teste.template_descricao = "Comissão ref. {mes}/{ano}"
    vinculo_teste.cod_nbs = "117019000"
    vinculo_teste.descricao_meses_atras = 1
    vinculo_teste.email_tomador = "financeiro@cliente.com"
    db.flush()

    assert vinculos.registrar_sugestoes(db, vinculo_teste) is True
    # preencheu o que estava vazio, não trocou o que já existia
    assert (tomador.sug_cod_nbs, tomador.sug_meses_atras) == ("117019000", 1)
    assert tomador.sug_template_descricao == "Descrição que já estava no catálogo"

    # curadoria: as regras desta empresa viram o padrão
    assert vinculos.publicar_sugestoes(db) == 1
    assert tomador.sug_template_descricao == "Comissão ref. {mes}/{ano}"
    # nada de contato vai pro catálogo
    assert not any("financeiro@cliente.com" in str(v) for v in vars(tomador).values())


def test_cliente_so_de_controle_nao_ensina_o_catalogo(db, vinculo_teste):
    tomador = db.get(Tomador, vinculo_teste.tomador_id)
    tomador.status = "aprovado"
    tomador.sug_cod_nbs = None
    vinculo_teste.sem_nota = True
    vinculo_teste.cod_nbs = "117019000"
    db.flush()
    assert vinculos.registrar_sugestoes(db, vinculo_teste, sobrescrever=True) is False and tomador.sug_cod_nbs is None


def test_so_a_conta_administradora_publica(client, db, prestador_teste, vinculo_teste):
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).one_or_none()
    if assinatura is not None:
        assinatura.status = "ativa"
        db.flush()
    assert client.post("/api/vinculos/publicar-sugestoes").status_code == 403
