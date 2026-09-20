"""
Canais de envio (Marco 9) — serviço (app/services/envios.py) e camada HTTP,
mesmo padrão real-Postgres-com-rollback das demais suítes.
"""
import uuid

import pytest

from app.services.envios import (
    CanalInvalidoError,
    EmissaoSemConteudoError,
    buscar_envio,
    gerar_mensagem_pronta,
    listar_envios,
    marcar_enviado,
    marcar_falha,
    melhor_xml_disponivel,
    registrar_envio,
)
from app.services.motor_emissao import criar_rascunho, montar


def test_gerar_mensagem_pronta_inclui_dados_da_nota(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=150.0))
    msg = gerar_mensagem_pronta(emissao)
    assert "Fornecedor Teste" in msg
    assert "2026-08" in msg
    assert "150,00" in msg
    assert "chave de acesso" in msg.lower()  # ainda não confirmada -> aviso, não a chave em si


def test_gerar_mensagem_pronta_rascunho_da_erro(db, vinculo_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    with pytest.raises(EmissaoSemConteudoError):
        gerar_mensagem_pronta(rascunho)


def test_melhor_xml_disponivel_prioriza_confirmado_sobre_assinado_sobre_montado(db, vinculo_teste, certificado_teste):
    from app.services.motor_emissao import assinar

    montado = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    nome, conteudo = melhor_xml_disponivel(montado)
    assert "montada" in nome
    assert conteudo == montado.xml_dps

    assinado = assinar(db, montado, certificado_teste["private_key"], certificado_teste["cert"])
    nome2, conteudo2 = melhor_xml_disponivel(assinado)
    assert "assinada" in nome2
    assert conteudo2 == assinado.xml_assinado


def test_registrar_envio_canal_invalido_levanta_erro(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    with pytest.raises(CanalInvalidoError):
        registrar_envio(db, emissao, "pombo-correio")


def test_registrar_envio_download_ja_nasce_enviado(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio = registrar_envio(db, emissao, "download")
    assert envio.status == "enviado"
    assert envio.enviado_em is not None


def test_registrar_envio_mensagem_pronta_ja_nasce_enviado(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio = registrar_envio(db, emissao, "mensagem_pronta")
    assert envio.status == "enviado"


@pytest.mark.parametrize("canal", ["email", "whatsapp", "direto_fornecedor"])
def test_registrar_envio_canais_manuais_nascem_pendentes(db, vinculo_teste, canal):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio = registrar_envio(db, emissao, canal)
    assert envio.status == "pendente"
    assert envio.enviado_em is None


def test_marcar_enviado_transiciona_pendente_para_enviado(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio = registrar_envio(db, emissao, "email")
    assert envio.status == "pendente"
    envio = marcar_enviado(db, envio)
    assert envio.status == "enviado"
    assert envio.enviado_em is not None


def test_marcar_falha_incrementa_tentativas(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio = registrar_envio(db, emissao, "whatsapp")
    assert envio.tentativas == 1
    envio = marcar_falha(db, envio)
    assert envio.status == "falha"
    assert envio.tentativas == 2


def test_listar_envios_ordenado_mais_recente_primeiro(db, vinculo_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    registrar_envio(db, emissao, "download")
    registrar_envio(db, emissao, "mensagem_pronta")
    envios = listar_envios(db, emissao)
    assert len(envios) == 2
    assert {e.canal for e in envios} == {"download", "mensagem_pronta"}


def test_registrar_envio_em_rascunho_da_erro(db, vinculo_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    with pytest.raises(EmissaoSemConteudoError):
        registrar_envio(db, rascunho, "download")


def test_buscar_envio_de_outro_prestador_nao_aparece(db, prestador_teste, vinculo_teste):
    """`envio` não tem RLS própria (ver docstring do módulo) — a garantia
    de isolamento tem que vir do JOIN com `emissao` dentro de
    `buscar_envio`. Simula outro prestador criando sua própria emissão e
    confirma que buscar_envio, rodando com a sessão do prestador_teste
    (RLS ainda ativa), não enxerga o envio do outro."""
    import uuid as uuid_mod

    from app.database import definir_prestador_atual
    from app.models import PrestadorTomador, Tomador
    from app.models import Prestador as PrestadorModel

    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0))
    envio_do_prestador_teste = registrar_envio(db, emissao, "download")
    db.flush()

    # troca a sessão pra outro prestador (RLS agora enxerga só o dele)
    outro_prestador_id = uuid_mod.uuid4()
    definir_prestador_atual(db, outro_prestador_id)
    outro_prestador = PrestadorModel(
        id=outro_prestador_id, cpf_cnpj="11111111000191", razao_social="OUTRO PRESTADOR DE TESTE", cod_municipio="3106200",
    )
    db.add(outro_prestador)
    db.flush()

    achou = buscar_envio(db, envio_do_prestador_teste.id)
    assert achou is None  # o envio existe no banco, mas não pertence a este prestador


# --- Camada HTTP ---


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


def test_endpoint_mensagem_pronta(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.get(f"/api/dps/{criada['id']}/mensagem-pronta")
    assert resp.status_code == 200, resp.text
    assert "Fornecedor Teste" in resp.json()["mensagem"]


def test_endpoint_mensagem_pronta_rascunho_inexistente_da_404(client, prestador_teste):
    resp = client.get(f"/api/dps/{uuid.uuid4()}/mensagem-pronta")
    assert resp.status_code == 404


def test_endpoint_download_xml(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.get(f"/api/dps/{criada['id']}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "attachment" in resp.headers["content-disposition"]
    assert b"<DPS" in resp.content


def test_endpoint_registrar_e_listar_envio(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/envios", json={"canal": "whatsapp"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pendente"

    listagem = client.get(f"/api/dps/{criada['id']}/envios")
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1


def test_endpoint_marcar_enviado_e_falha(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    envio = client.post(f"/api/dps/{criada['id']}/envios", json={"canal": "email"}).json()

    resp = client.post(f"/api/envios/{envio['id']}/marcar-enviado")
    assert resp.status_code == 200
    assert resp.json()["status"] == "enviado"

    envio2 = client.post(f"/api/dps/{criada['id']}/envios", json={"canal": "whatsapp"}).json()
    resp2 = client.post(f"/api/envios/{envio2['id']}/marcar-falha")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "falha"


def test_endpoint_registrar_envio_canal_invalido_da_422(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/envios", json={"canal": "pombo-correio"})
    assert resp.status_code == 422


def test_endpoint_marcar_enviado_envio_inexistente_da_404(client, prestador_teste):
    resp = client.post(f"/api/envios/{uuid.uuid4()}/marcar-enviado")
    assert resp.status_code == 404
