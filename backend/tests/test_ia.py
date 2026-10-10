"""IA do Claude dentro da Ana (2026.10.7, `app/services/ia.py`).

Nenhum teste chama a API de verdade: `requests.post` é trocado por respostas
de mentira. Cobre: IA desligada, limite diário, falha e demora, "não sei",
recusa já explicada, recusa de regra fixa, simulação e o que vai pro Claude.
Só dados sintéticos."""
import uuid
from decimal import Decimal

import pytest
import requests
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.deps import usuario_logado
from app.main import app, prestador_atual_id
from app.models import Emissao, IaChamada, Usuario
from app.services import ia


class _Resp:
    def __init__(self, status=200, texto="Clique em NFS-e e depois em Cancelar.", entrada=900, saida=60):
        self.status_code = status
        self._dados = {"model": "claude-haiku-5-5", "content": [{"type": "text", "text": texto}],
                       "usage": {"input_tokens": entrada, "output_tokens": saida}}

    def json(self):
        return self._dados


@pytest.fixture
def ligada(monkeypatch, db):
    s = get_settings()
    monkeypatch.setattr(s, "ia_ativa", True)
    monkeypatch.setattr(s, "anthropic_api_key", "chave-falsa-de-teste")
    monkeypatch.setattr(s, "ia_limite_diario", 20)

    def gravar(registro):
        db.add(registro)
        db.flush()

    monkeypatch.setattr(ia, "_gravar_chamada", gravar)
    monkeypatch.setattr(db, "commit", db.flush)  # as rotas dão commit: aqui fica tudo na transação do teste
    chamadas = []

    def post(url, headers=None, json=None, timeout=None):  # noqa: A002
        chamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return post.resposta() if callable(post.resposta) else post.resposta

    post.resposta = _Resp()
    monkeypatch.setattr(requests, "post", post)
    post.chamadas = chamadas
    return post


@pytest.fixture
def usuario(db, prestador_teste):
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"dona-{uuid.uuid4().hex[:6]}@exemplo.test", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    return u


def _perguntar(db, usuario, prestador_teste, texto="Como cancelo uma nota?", tela="/app/nfse"):
    return ia.perguntar(db, usuario_id=usuario.id, prestador_id=prestador_teste.id, pergunta=texto, tela=tela, perfil="dono")


def test_sobe_desligada_e_nao_chama_nada(db, usuario, prestador_teste, monkeypatch):
    chamou = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: chamou.append(1))
    assert get_settings().ia_ativa is False
    assert ia.ligada() is False
    assert _perguntar(db, usuario, prestador_teste).situacao == "desligada"
    assert chamou == []


def test_ligada_sem_chave_continua_desligada(monkeypatch):
    monkeypatch.setattr(get_settings(), "ia_ativa", True)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "  ")
    assert ia.ligada() is False


def test_responde_com_trechos_do_guia_tela_e_perfil(db, usuario, prestador_teste, ligada):
    r = _perguntar(db, usuario, prestador_teste)
    assert r.situacao == "ok" and "Cancelar" in r.texto
    assert r.restantes == 19
    enviado = ligada.chamadas[0]["json"]
    assert enviado["model"] == "claude-haiku-5-5"
    msg = enviado["messages"][0]["content"]
    assert "Cancelar uma nota" in msg  # trecho certo do guia
    assert "NFS-e (lista)" in msg and "dono(a)" in msg
    assert "<pergunta>\nComo cancelo uma nota?\n</pergunta>" in msg
    assert len(msg) < 20000  # não manda o guia inteiro
    assert ligada.chamadas[0]["headers"]["x-api-key"] == "chave-falsa-de-teste"
    # registro sem o texto da pergunta
    reg = db.query(IaChamada).filter_by(usuario_id=usuario.id).one()
    assert (reg.tipo, reg.resultado, reg.tokens_entrada, reg.tokens_saida) == ("pergunta", "ok", 900, 60)


def test_nao_sei_e_contador(db, usuario, prestador_teste, ligada):
    ligada.resposta = _Resp(texto="[NAO_SEI] Não tenho essa informação. O suporte pode ajudar.")
    r = _perguntar(db, usuario, prestador_teste, "Vocês emitem NF-e de produto?")
    assert r.situacao == "nao_sei" and not r.texto.startswith("[")
    ligada.resposta = _Resp(texto="[CONTADOR] Quem define o código é o seu contador.")
    assert _perguntar(db, usuario, prestador_teste, "Qual código de serviço eu uso?").situacao == "contador"


def test_limite_diario(db, usuario, prestador_teste, ligada, monkeypatch):
    monkeypatch.setattr(get_settings(), "ia_limite_diario", 2)
    assert _perguntar(db, usuario, prestador_teste).situacao == "ok"
    assert _perguntar(db, usuario, prestador_teste).situacao == "ok"
    r = _perguntar(db, usuario, prestador_teste)
    assert r.situacao == "limite" and r.restantes == 0
    assert len(ligada.chamadas) == 2  # a terceira nem chamou a IA
    # a contagem vem do banco (sobrevive a reinício), por pessoa
    assert ia.perguntas_hoje(db, usuario.id) == 2


@pytest.mark.parametrize("problema", ["timeout", "http500", "sem_credito", "vazia"])
def test_falha_ou_demora_nao_derruba_e_nao_conta(db, usuario, prestador_teste, ligada, problema):
    def erro():
        if problema == "timeout":
            raise requests.Timeout("demorou")
        return {"http500": _Resp(status=500), "sem_credito": _Resp(status=400), "vazia": _Resp(texto="")}[problema]

    ligada.resposta = erro
    r = _perguntar(db, usuario, prestador_teste)
    assert r.situacao == "falha" and r.texto is None
    assert ia.perguntas_hoje(db, usuario.id) == 0
    assert ligada.chamadas[0]["timeout"] == ia.TEMPO_PERGUNTA


def test_rota_da_ajuda_com_ia(db, prestador_teste, usuario, ligada):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    app.dependency_overrides[usuario_logado] = lambda: usuario
    try:
        c = TestClient(app)
        info = c.get("/api/ajuda").json()
        assert info == {"ia_url": None, "ia_ativa": True, "ia_restantes": 20, "ia_limite": 20}
        r = c.post("/api/ajuda/perguntar", json={"pergunta": "Como cancelo uma nota?", "tela": "/app/nfse/123e4567-e89b-12d3-a456-426614174000"})
        assert r.status_code == 200 and r.json()["situacao"] == "ok" and r.json()["restantes"] == 19
        assert "Nota (detalhe)" in ligada.chamadas[0]["json"]["messages"][0]["content"]
        assert c.post("/api/ajuda/perguntar", json={"pergunta": ""}).status_code == 422
    finally:
        for dep in (get_db, prestador_atual_id, usuario_logado):
            app.dependency_overrides.pop(dep, None)


def test_simulacao_nao_gasta_ia(db, prestador_teste, ligada):
    from app.services.demo import DOMINIO_EMAIL_DEMO as DOMINIO_DEMO

    demo = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"x@{DOMINIO_DEMO}", senha_hash="x", email_confirmado=True)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    app.dependency_overrides[usuario_logado] = lambda: demo
    try:
        c = TestClient(app)
        assert c.get("/api/ajuda").json()["ia_ativa"] is False
        assert c.post("/api/ajuda/perguntar", json={"pergunta": "oi"}).json()["situacao"] == "desligada"
        assert ligada.chamadas == []
    finally:
        for dep in (get_db, prestador_atual_id, usuario_logado):
            app.dependency_overrides.pop(dep, None)


# ---------------------------------------------------------------- recusa

def _nota_recusada(db, vinculo, detalhe):
    e = Emissao(
        id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=vinculo.prestador_id, competencia="2026-10",
        valor=Decimal("150.00"), serie="1", n_dps=987, estado="erro", erro_detalhe=detalhe,
        tomador_snapshot={"razao_social": "CLIENTE SECRETO LTDA", "cnpj": "11222333000181", "tpAmb": "2", "aliq_sn": 6.0,
                          "endereco": {"cMun": "3550308", "CEP": "01311000"},
                          "codigo_servico_usado": {"cTribNac": "170601", "cTribMun": "001", "cNBS": None, "cLocPrestacao": "3106200"}},
    )
    db.add(e)
    db.flush()
    return e


RECUSA = "A Receita recusou a nota: E0312 — O código de tributação nacional informado não está administrado pelo município"


def test_recusa_explicada_uma_vez_e_guardada(db, vinculo_teste, usuario, prestador_teste, ligada):
    ligada.resposta = _Resp(texto='{"o_que": "A prefeitura não usa esse código de serviço.", "passos": ["Abra o tomador", "Troque o código"]}')
    nota = _nota_recusada(db, vinculo_teste, RECUSA)
    r = ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id)
    assert r == {"o_que": "A prefeitura não usa esse código de serviço.", "passos": ["Abra o tomador", "Troque o código"]}
    enviado = ligada.chamadas[0]["json"]["messages"][0]["content"]
    assert "E0312" in enviado and "170601" in enviado
    assert "CLIENTE SECRETO" not in enviado and "11222333000181" not in enviado  # nada do cliente
    assert ligada.chamadas[0]["timeout"] == ia.TEMPO_RECUSA
    # reabrir a nota não gasta de novo
    assert ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id) == r
    assert len(ligada.chamadas) == 1
    # a explicação não conta no limite de perguntas
    assert ia.perguntas_hoje(db, usuario.id) == 0
    # recusada de novo por outro motivo: explica de novo
    nota.erro_detalhe = "A Receita recusou a nota: E0160 — opção do Simples não confere"
    ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id)
    assert len(ligada.chamadas) == 2


@pytest.mark.parametrize("detalhe", [
    "A Receita recusou a nota: E0008 — data de emissão posterior. Clique em “Corrigir e reenviar”",
    "A Receita recusou a nota: E0240 — CEP inexistente",
    "[comunicacao] Sem resposta da Receita",
])
def test_regra_fixa_e_falha_de_rede_nao_vao_pra_ia(db, vinculo_teste, usuario, prestador_teste, ligada, detalhe):
    nota = _nota_recusada(db, vinculo_teste, detalhe)
    assert ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id) is None
    assert ligada.chamadas == []


def test_recusa_com_ia_desligada_ou_resposta_ruim(db, vinculo_teste, usuario, prestador_teste, ligada, monkeypatch):
    nota = _nota_recusada(db, vinculo_teste, RECUSA)
    ligada.resposta = _Resp(texto="isto não é json")
    assert ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id) is None
    assert nota.erro_explicacao is None
    monkeypatch.setattr(get_settings(), "ia_ativa", False)
    assert ia.explicar_recusa(db, nota, usuario_id=usuario.id, prestador_id=prestador_teste.id) is None


def test_rota_explicar_recusa(db, vinculo_teste, prestador_teste, usuario, ligada):
    ligada.resposta = _Resp(texto='Aqui: {"o_que": "Código não aceito.", "passos": ["Confirme com o contador"]}')
    nota = _nota_recusada(db, vinculo_teste, RECUSA)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    app.dependency_overrides[usuario_logado] = lambda: usuario
    try:
        c = TestClient(app)
        r = c.post(f"/api/dps/{nota.id}/explicar-recusa")
        assert r.json() == {"disponivel": True, "o_que": "Código não aceito.", "passos": ["Confirme com o contador"]}
        assert c.post(f"/api/dps/{nota.id}/explicar-recusa").json()["disponivel"] is True
        assert len(ligada.chamadas) == 1
        assert c.post(f"/api/dps/{uuid.uuid4()}/explicar-recusa").status_code == 404
    finally:
        for dep in (get_db, prestador_atual_id, usuario_logado):
            app.dependency_overrides.pop(dep, None)


def test_resumo_da_gestao(db, usuario, prestador_teste, ligada, vinculo_teste):
    _perguntar(db, usuario, prestador_teste)
    ligada.resposta = _Resp(texto='{"o_que": "x", "passos": []}', entrada=500, saida=40)
    ia.explicar_recusa(db, _nota_recusada(db, vinculo_teste, RECUSA), usuario_id=usuario.id, prestador_id=prestador_teste.id)
    r = ia.resumo_gestao(db, 30)
    assert r["perguntas"].get("ok", 0) >= 1 and r["recusas"].get("ok", 0) >= 1
    assert r["custo_por_pergunta_usd"] is not None and r["custo_estimado_usd"] > 0
