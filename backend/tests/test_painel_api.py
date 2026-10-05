"""
Testes de integração do painel (Marco 5/6) — batem na API de verdade
(fastapi.testclient) contra o Postgres local, usando um vínculo real criado
no teste (nunca os dados de produção da Raiana).

`db_sessao` do app usa `settings.prestador_ativo_id` fixo (sem login) — pra
testar isolado sem depender/poluir o prestador real, sobrescrevemos essa
dependency via `app.dependency_overrides` apontando pro prestador de teste.

A partir do Marco 6, POST /api/dps PERSISTE (cria rascunho + monta) — os
testes de nDPS automático e da máquina de estados de verdade vivem em
tests/test_motor_emissao.py; aqui é só a camada HTTP por cima disso.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import PrestadorTomador, Tomador

# vinculo_teste vem de conftest.py (compartilhado com test_motor_emissao.py)


@pytest.fixture
def client(db, prestador_teste):
    # api_salvar_certificado dá commit() de propósito (senão o certificado
    # não sobreviveria ao fim do request, em uso real). Aqui, `db` é a MESMA
    # sessão/transação da fixture `prestador_teste` — um commit() de verdade
    # vazaria o prestador de teste pro banco permanentemente, já que o
    # rollback() do teardown vira no-op depois de um commit. flush() já
    # basta pra o próprio teste enxergar a escrita (mesma transação).
    db.commit = db.flush

    def _get_db_override():
        # precisa ser generator function de verdade (yield, não um
        # iterator já pronto) — é assim que o FastAPI reconhece e aplica o
        # mesmo protocolo de cleanup da dependency original (get_db).
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_listar_vinculos_vazio_sem_nenhum_cadastrado(client, prestador_teste):
    resp = client.get("/api/vinculos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_vinculos_devolve_o_criado(client, vinculo_teste):
    resp = client.get("/api/vinculos")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    assert dados[0]["apelido"] == "Fornecedor Teste"
    assert dados[0]["tomador_cnpj"] == "11222333000181"


def test_status_certificado_sem_certificado(client, prestador_teste):
    resp = client.get("/api/certificado/status")
    assert resp.status_code == 200
    assert resp.json() == {"carregado": False, "validade": None, "vencido": False}


def test_upload_certificado_e_status_reflete(client, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        resp = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": certificado_teste["senha"]},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["carregado"] is True

    resp2 = client.get("/api/certificado/status")
    assert resp2.json()["carregado"] is True


def test_upload_certificado_com_senha_errada_da_400(client, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        resp = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": "senha-errada"},
        )
    assert resp.status_code == 400


def test_criar_dps_persiste_com_ndps_automatico(client, vinculo_teste):
    resp = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0, "tpAmb": "2",
    })
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "montado"
    assert dados["n_dps"] == 1  # atribuído sozinho — sem campo n_dps no request
    assert "<DPS" in dados["xml"]
    assert "Signature" not in dados["xml"]
    assert dados["tomador"] == "TOMADOR DE TESTE LTDA"
    assert "08/2026" in dados["descricao"]

    # persistiu de verdade: uma segunda emissão pega o próximo nDPS.
    resp2 = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09", "valor": 50.0, "tpAmb": "2",
    })
    assert resp2.json()["n_dps"] == 2


def test_criar_dps_vinculo_inexistente_da_404(client, prestador_teste):
    resp = client.post("/api/dps", json={
        "vinculo_id": str(uuid.uuid4()), "competencia": "2026-08", "valor": 100.0,
    })
    assert resp.status_code == 404


def test_criar_dps_duplicada_mesma_competencia_da_409(client, vinculo_teste):
    r1 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0})
    assert r1.status_code == 200
    r2 = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 200.0})
    assert r2.status_code == 409


def test_verificar_duplicata_sem_emissao_da_existe_false(client, vinculo_teste):
    resp = client.get(
        "/api/dps/verificar-duplicata",
        params={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"existe": False, "emissao_id": None, "estado": None, "valor": None, "pode_substituir": False}


def test_verificar_duplicata_com_emissao_ativa_da_existe_true(client, vinculo_teste):
    criada = client.post(
        "/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}
    ).json()

    resp = client.get(
        "/api/dps/verificar-duplicata",
        params={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08"},
    )
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["existe"] is True
    assert dados["emissao_id"] == criada["id"]
    assert dados["estado"] == "montado"


def test_verificar_duplicata_ignora_emissao_cancelada(client, db, vinculo_teste):
    criada = client.post(
        "/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}
    ).json()
    from app.models import Emissao

    emissao = db.get(Emissao, uuid.UUID(criada["id"]))
    emissao.estado = "cancelada"
    db.flush()

    resp = client.get(
        "/api/dps/verificar-duplicata",
        params={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08"},
    )
    assert resp.json()["existe"] is False


def test_verificar_duplicata_competencia_malformada_da_422(client, vinculo_teste):
    resp = client.get(
        "/api/dps/verificar-duplicata",
        params={"vinculo_id": str(vinculo_teste.id), "competencia": "2026/08"},
    )
    assert resp.status_code == 422


def test_ver_dps_por_id(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.get(f"/api/dps/{criada['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == criada["id"]


def test_assinar_dps_sem_certificado_da_409(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/assinar")
    assert resp.status_code == 409


def test_assinar_dps_com_certificado_carregado(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        r = client.post(
            "/api/certificado",
            files={"pfx": ("cert.pfx", f, "application/x-pkcs12")},
            data={"senha": certificado_teste["senha"]},
        )
    assert r.status_code == 200

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/assinar")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "assinado"
    assert "<Signature" in dados["xml"]


def test_assinar_dps_duas_vezes_da_409_na_segunda(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    r1 = client.post(f"/api/dps/{criada['id']}/assinar")
    assert r1.status_code == 200
    r2 = client.post(f"/api/dps/{criada['id']}/assinar")
    assert r2.status_code == 409  # já está assinado, não pode assinar de novo


# --- submeter/cancelar de verdade (Marco 16, item 7 — ver
# app/services/motor_emissao.submeter/cancelar). `requests.post` sempre
# mockado no nível de app.fiscal.cliente_sefin (mesmo ponto que
# test_cliente_sefin.py usa) — nenhum teste aqui toca rede de verdade. ---


class _RespostaSefinFake:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self.content = b"{}"
        self.headers = {"content-type": "application/json"}
        self._json = json_data
        self.text = "fake"

    def json(self):
        return self._json


def _mockar_requests_sefin(monkeypatch, *, submissao=None, evento=None):
    """`submissao`/`evento`: (status_code, json_data) ou None (a chamada
    correspondente não deveria acontecer nesse teste)."""

    def _post_fake(url, **kwargs):
        if "/eventos" in url:
            assert evento is not None, f"não esperava POST de evento de cancelamento: {url}"
            return _RespostaSefinFake(*evento)
        assert submissao is not None, f"não esperava POST de submissão: {url}"
        return _RespostaSefinFake(*submissao)

    monkeypatch.setattr("app.fiscal.cliente_sefin.requests.post", _post_fake)


def _emissao_assinada(client, certificado_teste, vinculo_teste, competencia="2026-08"):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": competencia, "valor": 100.0}).json()
    client.post(f"/api/dps/{criada['id']}/assinar")
    return criada["id"]


def test_submeter_dps_sem_certificado_da_409(client, vinculo_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/submeter")
    assert resp.status_code == 409


def test_submeter_dps_estado_invalido_da_409(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    resp = client.post(f"/api/dps/{criada['id']}/submeter")  # ainda 'montado', não assinou
    assert resp.status_code == 409


def test_submeter_dps_sucesso_confirma_e_grava_chave_acesso(client, vinculo_teste, certificado_teste, monkeypatch):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(201, {"chaveAcesso": "chave-fake-123", "nfseXmlGZipB64": None}))

    resp = client.post(f"/api/dps/{emissao_id}/submeter")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "confirmado"
    assert dados["chave_acesso"] == "chave-fake-123"


def test_submeter_dps_recusado_pela_sefin_fica_em_erro_mas_200(client, vinculo_teste, certificado_teste, monkeypatch):
    """Recusa de negócio da Sefin não é um erro NOSSO — a emissão fica
    registrada em estado='erro' (retentável), a resposta HTTP continua
    200 (ver docstring de api_submeter_dps)."""
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(400, {"mensagem": "algo deu errado"}))

    resp = client.post(f"/api/dps/{emissao_id}/submeter")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "erro"
    assert dados["erro_detalhe"]


def test_submeter_dps_retenta_a_partir_do_erro(client, vinculo_teste, certificado_teste, monkeypatch):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(400, {"mensagem": "fora do ar"}))
    client.post(f"/api/dps/{emissao_id}/submeter")

    _mockar_requests_sefin(monkeypatch, submissao=(201, {"chaveAcesso": "chave-na-segunda-tentativa", "nfseXmlGZipB64": None}))
    resp = client.post(f"/api/dps/{emissao_id}/submeter")
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "confirmado"


def test_cancelar_dps_estado_invalido_da_409(client, vinculo_teste, certificado_teste):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)  # só 'assinado', não confirmado
    resp = client.post(
        f"/api/dps/{emissao_id}/cancelar",
        json={"cmotivo": "1", "xmotivo": "Nota emitida com valor errado por engano"},
    )
    assert resp.status_code == 409


# montar_evento_cancelamento exige exatamente 50 dígitos na chave de
# acesso (ver app/fiscal/eventos.py) — diferente do teste de submeter, que
# não valida formato nenhum, os testes de cancelar precisam de uma chave
# fake mas VÁLIDA nesse formato pra chegar na parte que estão testando.
_CHAVE_ACESSO_FAKE_50_DIGITOS = "1" * 50


def test_cancelar_dps_xmotivo_curto_demais_da_422(client, vinculo_teste, certificado_teste, monkeypatch):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(201, {"chaveAcesso": _CHAVE_ACESSO_FAKE_50_DIGITOS, "nfseXmlGZipB64": None}))
    client.post(f"/api/dps/{emissao_id}/submeter")

    resp = client.post(f"/api/dps/{emissao_id}/cancelar", json={"cmotivo": "1", "xmotivo": "curto"})
    assert resp.status_code == 422


def test_cancelar_dps_sucesso(client, vinculo_teste, certificado_teste, monkeypatch):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(201, {"chaveAcesso": _CHAVE_ACESSO_FAKE_50_DIGITOS, "nfseXmlGZipB64": None}))
    client.post(f"/api/dps/{emissao_id}/submeter")

    _mockar_requests_sefin(monkeypatch, evento=(201, {"alertas": []}))
    resp = client.post(
        f"/api/dps/{emissao_id}/cancelar",
        json={"cmotivo": "1", "xmotivo": "Nota emitida com valor errado por engano"},
    )
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["estado"] == "cancelada"


def test_cancelar_dps_recusado_pela_sefin_da_400(client, vinculo_teste, certificado_teste, monkeypatch):
    emissao_id = _emissao_assinada(client, certificado_teste, vinculo_teste)
    _mockar_requests_sefin(monkeypatch, submissao=(201, {"chaveAcesso": _CHAVE_ACESSO_FAKE_50_DIGITOS, "nfseXmlGZipB64": None}))
    client.post(f"/api/dps/{emissao_id}/submeter")

    _mockar_requests_sefin(monkeypatch, evento=(400, {"mensagem": "evento recusado"}))
    resp = client.post(
        f"/api/dps/{emissao_id}/cancelar",
        json={"cmotivo": "1", "xmotivo": "Nota emitida com valor errado por engano"},
    )
    assert resp.status_code == 400


def test_criar_dps_com_template_de_ordem_sem_ordem_da_422(client, db, prestador_teste):
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

    resp = client.post("/api/dps", json={
        "vinculo_id": str(vinculo.id), "competencia": "2026-08", "valor": 100.0,
    })
    assert resp.status_code == 422


def test_pagina_inicial_carrega(client):
    """Marco 12: `/` agora serve o SPA novo (React/Vite, frontend/dist) —
    o backend só entrega o index.html gerado pelo `npm run build`; o
    conteúdo de verdade é montado no navegador, então o teste checa só a
    casca (`id="root"`), não texto de UI (que mudaria a cada ajuste
    visual sem relação nenhuma com este endpoint)."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="root"' in resp.text


# --- Marco 11: /api/dps/{id}/nota — máscara visual (ver app/services/nota_visual.py) ---


def test_nota_visual_apos_montar_traz_prestador_tomador_e_servico(client, vinculo_teste, prestador_teste):
    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 150.0}).json()

    resp = client.get(f"/api/dps/{criada['id']}/nota")
    assert resp.status_code == 200, resp.text
    nota = resp.json()

    assert nota["estado"] == "montado"
    assert nota["serie"] == vinculo_teste.serie
    assert nota["n_dps"] == criada["n_dps"]
    assert nota["competencia"] == "2026-08"
    assert nota["ambiente"] == "1"  # sem tpAmb: ambiente da conta (prestador.tp_amb_padrao, padrão produção)
    assert nota["xml_disponivel"] is True
    assert nota["id_dps"]  # nasce na montagem

    # PRESTADOR vem do banco (Prestador), não do XML — a DPS deliberadamente
    # não leva nome/endereço do prestador (ver docstring de app/fiscal/dps.py,
    # erro E0121) — é por isso que este endpoint existe em vez de só reler o XML.
    assert nota["prestador"]["razao_social"] == prestador_teste.razao_social
    assert "00.000.000/0001-91" == nota["prestador"]["cnpj"]

    # TOMADOR vem do snapshot congelado no rascunho, não do catálogo ao vivo.
    assert nota["tomador"]["razao_social"] == "TOMADOR DE TESTE LTDA"
    assert "11.222.333/0001-81" == nota["tomador"]["cnpj"]

    assert nota["servico"]["codigo_tributacao_nacional"] == "170601"
    assert "08/2026" in nota["servico"]["descricao"]

    assert nota["valores"]["valor_servico"] == 150.0


def test_nota_visual_reflete_estado_apos_assinar(client, vinculo_teste, certificado_teste):
    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})

    criada = client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 100.0}).json()
    client.post(f"/api/dps/{criada['id']}/assinar")

    resp = client.get(f"/api/dps/{criada['id']}/nota")
    assert resp.status_code == 200
    nota = resp.json()
    assert nota["estado"] == "assinado"
    assert nota["estado_label"].startswith("Assinada")


def test_nota_visual_emissao_inexistente_da_404(client, prestador_teste):
    resp = client.get(f"/api/dps/{uuid.uuid4()}/nota")
    assert resp.status_code == 404


# --- Gráficos da Visão geral (05/10/2026) ---


def _nota_grafico(db, vinculo, competencia, valor, *, estado="confirmado", documento=None, n=[990000]):
    from decimal import Decimal

    from app.models import Emissao

    n[0] += 1
    db.add(Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="77", n_dps=n[0], estado=estado, valor=Decimal(str(valor)), origem="importada",
        tomador_snapshot={"apelido": vinculo.apelido}, tomador_documento=documento,
    ))
    db.flush()


def test_graficos_do_painel(client, db, prestador_teste, vinculo_teste):
    tomador = Tomador(id=uuid.uuid4(), cnpj="22333444000181", razao_social="MARKETPLACE SINTETICO LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    marketplace = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador.id, apelido="Marketplace",
        cod_local_prestacao="3550308", cod_trib_nacional="170601", template_descricao="x",
    )
    db.add(marketplace)
    db.flush()

    _nota_grafico(db, vinculo_teste, "2026-10", 1000)
    _nota_grafico(db, vinculo_teste, "2026-08", 500, estado="montado")
    _nota_grafico(db, vinculo_teste, "2025-11", 300)       # primeiro mês da janela de 12
    _nota_grafico(db, vinculo_teste, "2025-10", 9999)      # fora da janela (13 meses atrás)
    _nota_grafico(db, vinculo_teste, "2026-09", 7777, estado="cancelada")  # não é faturamento
    # notas de vendedores (relatório do marketplace): entram no nome do marketplace
    for doc, valor in (("52998224725", 40), ("11222333000181", 60.5), ("39053344705", 20)):
        _nota_grafico(db, marketplace, "2026-10", valor, documento=doc)

    r = client.get("/api/painel/graficos?competencia=2026-10")
    assert r.status_code == 200, r.text
    g = r.json()
    serie = g["serie"]
    assert [p["competencia"] for p in serie] == [
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
        "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10",
    ]
    valores = {p["competencia"]: p["valor"] for p in serie}
    assert valores["2025-11"] == 300 and valores["2026-08"] == 500 and valores["2026-09"] == 0
    assert valores["2026-10"] == 1120.5
    assert g["media"] == round((300 + 500 + 1120.5) / 12, 2)
    # o mês do gráfico bate com o "Faturado no mês" da mesma tela
    assert client.get("/api/painel/resumo-mes?competencia=2026-10").json()["faturado_no_mes"] == valores["2026-10"]

    assert g["ano"] == "2026" and g["total_ano"] == 1620.5
    assert [(t["nome"], t["total"], t["notas"]) for t in g["por_tomador"]] == [
        ("Fornecedor Teste", 1500.0, 2), ("Marketplace", 120.5, 3),
    ]

    # empresa sem nota nenhuma: série zerada, sem média, sem tomador
    vazio = client.get("/api/painel/graficos?competencia=2024-06").json()
    assert all(p["valor"] == 0 for p in vazio["serie"]) and vazio["media"] is None and vazio["por_tomador"] == []
    assert client.get("/api/painel/graficos?competencia=2026-13").status_code == 422
    assert len(client.get("/api/painel/graficos").json()["serie"]) == 12


def test_graficos_do_painel_pedem_o_emissor(client, db, prestador_teste):
    prestador_teste.modulos = ["financeiro"]
    db.flush()
    assert client.get("/api/painel/graficos").status_code == 403
