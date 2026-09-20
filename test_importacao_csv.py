"""
Importação em lote (Marco 7) — testes de serviço (app/services/
importacao_csv.py) contra o Postgres local, e de HTTP por cima
(POST /api/dps/importar-csv), seguindo o mesmo padrão de test_painel_api.py.
"""
import uuid

import pytest

from app.services.importacao_csv import CsvInvalidoError, importar_csv


def test_importa_linhas_validas_cria_multiplas_emissoes(db, vinculo_teste):
    csv_texto = (
        "apelido,competencia,valor\n"
        "Fornecedor Teste,2026-08,100.50\n"
        "Fornecedor Teste,2026-09,200\n"
    )
    resultados = importar_csv(db, csv_texto)
    assert len(resultados) == 2
    assert all(r.ok for r in resultados)
    assert [r.n_dps for r in resultados] == [1, 2]
    assert resultados[0].linha == 2
    assert resultados[1].linha == 3


def test_valor_com_virgula_decimal_pt_br(db, vinculo_teste):
    csv_texto = "apelido,competencia,valor\nFornecedor Teste,2026-08,\"1.234,50\"\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok
    from app.models import Emissao
    emissao = db.query(Emissao).filter_by(id=resultados[0].emissao_id).one()
    assert float(emissao.valor) == 1234.50


def test_delimitador_ponto_e_virgula_detectado_automaticamente(db, vinculo_teste):
    csv_texto = "apelido;competencia;valor\nFornecedor Teste;2026-08;100,00\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok


def test_apelido_desconhecido_vira_erro_na_linha_sem_travar_as_outras(db, vinculo_teste):
    csv_texto = (
        "apelido,competencia,valor\n"
        "Fornecedor Que Nao Existe,2026-08,100\n"
        "Fornecedor Teste,2026-09,200\n"
    )
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is False
    assert "não encontrado" in resultados[0].mensagem
    assert resultados[1].ok is True
    assert resultados[1].n_dps == 1  # a linha com erro não consumiu nDPS


def test_competencia_duplicada_na_mesma_importacao_reporta_erro_na_segunda(db, vinculo_teste):
    csv_texto = (
        "apelido,competencia,valor\n"
        "Fornecedor Teste,2026-08,100\n"
        "Fornecedor Teste,2026-08,999\n"
    )
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is True
    assert resultados[1].ok is False
    assert "Já existe uma emissão ativa" in resultados[1].mensagem


def test_valor_malformado_vira_erro_de_linha(db, vinculo_teste):
    csv_texto = "apelido,competencia,valor\nFornecedor Teste,2026-08,abacate\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is False


def test_linha_sem_apelido_vira_erro_de_linha(db, vinculo_teste):
    csv_texto = "apelido,competencia,valor\n,2026-08,100\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is False
    assert "apelido" in resultados[0].mensagem


def test_csv_sem_coluna_obrigatoria_levanta_erro_estrutural(db, vinculo_teste):
    with pytest.raises(CsvInvalidoError):
        importar_csv(db, "apelido,valor\nFornecedor Teste,100\n")


def test_csv_vazio_levanta_erro_estrutural(db, vinculo_teste):
    with pytest.raises(CsvInvalidoError):
        importar_csv(db, "")


def test_template_de_ordem_sem_ordem_vira_erro_de_linha_nao_derruba_lote(db, prestador_teste):
    from app.models import PrestadorTomador, Tomador

    tomador = Tomador(
        id=uuid.uuid4(), cnpj="99888777000166", razao_social="AWIN TESTE",
        cod_municipio="3550308", cep="01311000", logradouro="Rua X", numero="1", bairro="Centro",
    )
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador.id,
        apelido="AWIN Teste", cod_local_prestacao=prestador_teste.cod_municipio,
        cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="Ordem número: {ordem}", serie="1", ativo=True,
    )
    db.add(vinculo)
    db.flush()

    csv_texto = "apelido,competencia,valor\nAWIN Teste,2026-08,100\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is False


def test_bom_utf8_no_cabecalho_nao_atrapalha(db, vinculo_teste):
    csv_texto = "﻿apelido,competencia,valor\nFornecedor Teste,2026-08,100\n"
    resultados = importar_csv(db, csv_texto)
    assert resultados[0].ok is True


# --- Camada HTTP (fastapi.testclient), mesmo padrão de test_painel_api.py ---


@pytest.fixture
def client(db, prestador_teste):
    from app.database import get_db
    from app.main import app, prestador_atual_id

    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    from fastapi.testclient import TestClient
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_endpoint_importar_csv_sucesso(client, vinculo_teste):
    csv_bytes = b"apelido,competencia,valor\nFornecedor Teste,2026-08,100\nFornecedor Teste,2026-09,200\n"
    resp = client.post(
        "/api/dps/importar-csv",
        files={"arquivo": ("notas.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["total"] == 2
    assert dados["sucesso"] == 2
    assert dados["erro"] == 0
    assert dados["linhas"][0]["n_dps"] == 1


def test_endpoint_importar_csv_lote_misto_devolve_200_com_detalhe_por_linha(client, vinculo_teste):
    csv_bytes = (
        b"apelido,competencia,valor\n"
        b"Fornecedor Teste,2026-08,100\n"
        b"Desconhecido,2026-08,100\n"
    )
    resp = client.post(
        "/api/dps/importar-csv",
        files={"arquivo": ("notas.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["sucesso"] == 1
    assert dados["erro"] == 1
    assert dados["linhas"][1]["ok"] is False


def test_endpoint_importar_csv_estrutural_invalido_da_400(client, vinculo_teste):
    resp = client.post(
        "/api/dps/importar-csv",
        files={"arquivo": ("notas.csv", b"coluna_errada\nx\n", "text/csv")},
    )
    assert resp.status_code == 400


def test_endpoint_importar_csv_persiste_de_verdade_reflete_em_get_vinculos_e_dps(client, vinculo_teste):
    csv_bytes = b"apelido,competencia,valor\nFornecedor Teste,2026-08,100\n"
    resp = client.post("/api/dps/importar-csv", files={"arquivo": ("notas.csv", csv_bytes, "text/csv")})
    emissao_id = resp.json()["linhas"][0]["emissao_id"]

    resp2 = client.get(f"/api/dps/{emissao_id}")
    assert resp2.status_code == 200
    assert resp2.json()["estado"] == "montado"
    assert resp2.json()["n_dps"] == 1
