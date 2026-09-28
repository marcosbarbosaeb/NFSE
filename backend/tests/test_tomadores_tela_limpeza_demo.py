"""Pedido do Marcos de 28/09/2026: aba Tomadores (dia de emissão, ativo,
excluir, gerado/não gerado), sugestões de preenchimento, lista oficial de
códigos de serviço, limpar dados e ambiente de simulação."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, EventoManual, PagamentoRecebido, Prestador, PrestadorTomador, Tomador, Usuario
from app.services.demo import DOMINIO_EMAIL_DEMO, apagar_conta_demo, criar_conta_demo
from app.services.limpeza import limpar_dados
from app.services.motor_emissao import criar_rascunho, montar
from app.services.servicos_nacionais import buscar_servicos, normalizar_codigo, servico_por_codigo
from app.services.vinculos import criar_vinculo, excluir_vinculo, listar_vinculos_ativos, ordenar_para_tela


def _competencia_atual() -> str:
    hoje = datetime.date.today()
    return f"{hoje.year:04d}-{hoje.month:02d}"


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


def _novo_vinculo(db, prestador, apelido, dia=None, ativo=True):
    tomador = Tomador(id=uuid.uuid4(), cnpj=str(uuid.uuid4().int)[:14], razao_social=f"{apelido} LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    vinculo = criar_vinculo(
        db, prestador_id=prestador.id, tomador_id=tomador.id, apelido=apelido, cod_local_prestacao="3106200",
        cod_trib_nacional="170601", template_descricao="Comissão {competencia_mm_aaaa}", dia_limite_emissao=dia,
    )
    vinculo.ativo = ativo
    db.flush()
    return vinculo


# --- Aba Tomadores -----------------------------------------------------------


def test_ordem_da_tela_por_dia_com_inativos_no_fim(db, prestador_teste):
    sem_dia = _novo_vinculo(db, prestador_teste, "Sem dia")
    dia20 = _novo_vinculo(db, prestador_teste, "Dia 20", dia=20)
    dia5 = _novo_vinculo(db, prestador_teste, "Dia 5", dia=5)
    inativo = _novo_vinculo(db, prestador_teste, "Inativo", dia=1, ativo=False)
    assert [v.apelido for v in ordenar_para_tela([sem_dia, dia20, inativo, dia5])] == ["Dia 5", "Dia 20", "Sem dia", "Inativo"]


def test_listagem_todos_traz_inativos_e_a_nota_do_mes(client, db, prestador_teste, vinculo_teste):
    inativo = _novo_vinculo(db, prestador_teste, "Parado", ativo=False)
    emissao = criar_rascunho(db, vinculo_teste, competencia=_competencia_atual(), valor=100)
    montar(db, emissao)

    so_ativos = client.get("/api/vinculos").json()
    assert inativo.apelido not in [v["apelido"] for v in so_ativos]

    todos = {v["apelido"]: v for v in client.get("/api/vinculos?todos=true").json()}
    assert todos["Parado"]["ativo"] is False
    assert todos[vinculo_teste.apelido]["emissao_estado"] == "montado"
    assert todos[vinculo_teste.apelido]["emissao_valor"] == 100
    assert todos["Parado"]["emissao_id"] is None


def test_desativar_pelo_patch_mantem_na_tela(client, vinculo_teste):
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"ativo": False, "dia_limite_emissao": 12})
    assert resp.status_code == 200
    linha = next(v for v in client.get("/api/vinculos?todos=true").json() if v["id"] == str(vinculo_teste.id))
    assert linha["ativo"] is False and linha["dia_limite_emissao"] == 12


def test_excluir_sem_notas_apaga_de_verdade(client, db, prestador_teste):
    vinculo = _novo_vinculo(db, prestador_teste, "Descartável")
    resp = client.delete(f"/api/vinculos/{vinculo.id}")
    assert resp.status_code == 200
    assert resp.json()["resultado"] == "apagado"
    assert db.get(PrestadorTomador, vinculo.id) is None


def test_excluir_com_notas_arquiva_e_libera_o_apelido(db, prestador_teste, vinculo_teste):
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-01", valor=50)
    assert excluir_vinculo(db, vinculo_teste) == "arquivado"
    assert vinculo_teste.excluido_em is not None and vinculo_teste.ativo is False
    assert vinculo_teste not in listar_vinculos_ativos(db)
    assert db.get(Emissao, emissao.id) is not None
    # o apelido original fica livre pra um tomador novo
    _novo_vinculo(db, prestador_teste, "Fornecedor Teste")


# --- Sugestões e códigos -----------------------------------------------------


def test_vinculo_ensina_sugestoes_ao_catalogo(db, prestador_teste):
    vinculo = _novo_vinculo(db, prestador_teste, "Ensina", dia=7)
    tomador = db.get(Tomador, vinculo.tomador_id)
    assert tomador.sug_cod_trib_nacional == "170601"
    assert tomador.sug_template_descricao == "Comissão {competencia_mm_aaaa}"
    assert tomador.sug_dia_emissao == 7


def test_lista_oficial_de_codigos():
    assert servico_por_codigo("17.06.01")["descricao"].startswith("Propaganda e publicidade")
    assert normalizar_codigo("10101") == "010101"
    assert servico_por_codigo("999999") is None
    achados = buscar_servicos("publicidade")
    assert any(s["codigo"] == "170601" for s in achados)
    assert [s["codigo"] for s in buscar_servicos("1706")][0] == "170601"


def test_endpoint_servicos_nacionais(client):
    resp = client.get("/api/servicos-nacionais?q=programa")
    assert resp.status_code == 200
    assert any(s["codigo"] == "010201" for s in resp.json())


def test_codigo_inexistente_e_recusado(client, vinculo_teste):
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cod_trib_nacional": "999999"})
    assert resp.status_code == 422
    resp = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cod_trib_nacional": "01.02.01"})
    assert resp.status_code == 200
    assert resp.json()["cod_trib_nacional"] == "010201"


# --- Limpar dados ------------------------------------------------------------


def test_limpar_dados_preserva_notas_ja_enviadas(db, prestador_teste, vinculo_teste):
    montada = criar_rascunho(db, vinculo_teste, competencia="2026-01", valor=10)
    enviada = criar_rascunho(db, vinculo_teste, competencia="2026-02", valor=20)
    enviada.estado = "confirmado"
    db.add(PagamentoRecebido(id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=prestador_teste.id, competencia="2026-02", valor=20))
    db.add(Despesa(id=uuid.uuid4(), prestador_id=prestador_teste.id, categoria="X", competencia="2026-02", valor=5))
    db.add(EventoManual(id=uuid.uuid4(), prestador_id=prestador_teste.id, data=datetime.date(2026, 2, 1), titulo="t"))
    db.flush()
    montada_id, enviada_id = montada.id, enviada.id

    removidos = limpar_dados(db, prestador_teste.id, ["nfse", "recebimentos", "despesas", "calendario", "tomadores"])

    assert removidos["nfse"] == 1 and removidos["nfse_mantidas"] == 1
    assert db.get(Emissao, montada_id) is None
    assert db.get(Emissao, enviada_id) is not None
    assert removidos["recebimentos"] == 1 and removidos["despesas"] == 1 and removidos["calendario"] == 1
    assert removidos["tomadores_arquivados"] == 1  # ainda tem a nota confirmada


def test_endpoint_limpar_exige_confirmacao(client):
    assert client.post("/api/dados/limpar", json={"categorias": ["despesas"], "confirmacao": "sim"}).status_code == 422
    assert client.post("/api/dados/limpar", json={"categorias": ["xyz"], "confirmacao": "LIMPAR"}).status_code == 422
    resp = client.post("/api/dados/limpar", json={"categorias": ["despesas"], "confirmacao": "limpar"})
    assert resp.status_code == 200


# --- Ambiente de simulação ---------------------------------------------------


def test_conta_demo_nasce_com_dados_de_exemplo(db):
    usuario = criar_conta_demo(db)
    assert usuario.email.endswith("@" + DOMINIO_EMAIL_DEMO)
    definir_prestador_atual(db, usuario.prestador_id)
    prestador = db.get(Prestador, usuario.prestador_id)
    assert prestador.demo is True
    vinculos = db.query(PrestadorTomador).filter_by(prestador_id=prestador.id).all()
    assert len(vinculos) == 4 and sum(1 for v in vinculos if not v.ativo) == 1
    assert db.query(Emissao).filter_by(prestador_id=prestador.id).count() >= 9
    # tomadores fictícios nunca aparecem no catálogo compartilhado
    assert all(db.get(Tomador, v.tomador_id).status == "pendente" for v in vinculos)

    apagar_conta_demo(db, prestador.id)
    assert db.query(Usuario).filter_by(id=usuario.id).one_or_none() is None


def test_endpoint_demo_entra_e_bloqueia_o_que_sai_do_sistema(db):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    try:
        client = TestClient(app)
        resp = client.post("/api/demo")
        assert resp.status_code == 200 and resp.json()["demo"] is True
        assert client.get("/api/auth/me").json()["demo"] is True
        assert len(client.get("/api/vinculos?todos=true").json()) == 4

        bloqueado = client.post("/api/certificado", files={"pfx": ("a.pfx", b"x")}, data={"senha": "x"})
        assert bloqueado.status_code == 403
        assert "simulação" in bloqueado.json()["detail"]
        assert client.post("/api/auth/trocar-senha", json={"senha_atual": "a", "senha_nova": "bbbbbbbb"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- Aviso do dia de gerar (28/09/2026) ---------------------------------------


def test_aviso_na_vespera_no_dia_e_depois(db, prestador_teste):
    from app.services.dashboard import _avisos_dia_de_gerar

    v = _novo_vinculo(db, prestador_teste, "Aviso", dia=10)
    def tipos(dia):
        return [a["tipo"] for a in _avisos_dia_de_gerar(db, [v], datetime.date(2026, 9, dia))]
    assert tipos(8) == []
    assert tipos(9) == ["gerar_amanha"]
    assert tipos(10) == ["gerar_hoje"]
    assert tipos(15) == ["gerar_atrasada"]
    emissao = criar_rascunho(db, v, competencia="2026-09", valor=10)
    assert tipos(10) == []


def test_baixa_e_desfazer_pagamento(client, vinculo_teste):
    resp = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 10})
    assert resp.status_code == 200
    resp = client.delete(f"/api/pagamentos?vinculo_id={vinculo_teste.id}&competencia=2026-09")
    assert resp.json()["removidos"] == 1
