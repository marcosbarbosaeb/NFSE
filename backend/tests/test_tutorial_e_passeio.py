"""Tutorial e passeio "o que mudou" (2026.10.7 — observações de teste do Marcos).

O looping: o passeio das novidades levava a pessoa a /cadastro (fora do
painel); o cadastro devolve quem está logado para /app, o painel monta de novo,
esquece que o passeio estava aberto e, como as novidades ainda não tinham sido
marcadas como vistas, convida outra vez — sem fim. A reprodução no navegador
fica em `scripts/e2e_tutorial_looping.py`; aqui fica a trava de que nenhum item
de novidade leva para fora do painel, e a das dicas guardadas na conta (pra não
repetirem em outro navegador). Só dados sintéticos."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import novidades
from app.database import definir_prestador_atual, get_db
from app.main import app
from app.models import Prestador, Usuario


def test_nenhuma_novidade_leva_para_fora_do_painel():
    """Item com link fora de /app tira a pessoa do painel no meio do passeio
    (foi assim que o passeio entrou em looping)."""
    fora = [(v["versao"], i["titulo"], i["link"]) for v in novidades.VERSOES for i in v["itens"]
            if i.get("link") and not i["link"].startswith("/app")]
    assert fora == []


@pytest.fixture
def logado(db, prestador_teste, monkeypatch):
    monkeypatch.setattr(db, "commit", db.flush)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db

    def entrar(usuario):
        import base64
        import json

        from itsdangerous import TimestampSigner

        from app.config import get_settings

        c = TestClient(app)
        dados = base64.b64encode(json.dumps({"usuario_id": str(usuario.id), "prestador_id": str(usuario.prestador_id)}).encode())
        c.cookies.set("session", TimestampSigner(get_settings().session_secret_key).sign(dados).decode())
        return c

    yield entrar
    app.dependency_overrides.pop(get_db, None)


def test_dicas_vistas_ficam_na_conta(db, prestador_teste, logado):
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"dicas{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    c = logado(u)
    assert c.put("/api/conta/tutorial", json={"vistos": ["visao-geral", "<script>"]}).json()["vistos"] == ["visao-geral"]
    assert c.put("/api/conta/tutorial", json={"vistos": ["tomadores"]}).json()["vistos"] == ["tomadores", "visao-geral"]
    assert c.put("/api/conta/tutorial", json={"ativo": False}).json() == {"vistos": ["tomadores", "visao-geral"], "ativo": False}
    # outro navegador: as preferências da conta trazem o que já foi visto
    assert c.get("/api/conta/preferencias").json()["tutorial"]["vistos"] == ["tomadores", "visao-geral"]
    # "rever todas as dicas"
    assert c.put("/api/conta/tutorial", json={"limpar": True, "vistos": []}).json()["vistos"] == []


def test_pergunte_a_ana_na_conta_so_de_contador(db, logado):
    """Na conta só de contador o "Pergunte à Ana" dava 403 (a casa do contador não aceita pedidos que mudam algo)."""
    casa = Prestador(id=uuid.uuid4(), cpf_cnpj=f"CT{uuid.uuid4().hex[:10]}", razao_social="ESCRITORIO SINTETICO", cod_municipio="3106200", so_contador=True)
    definir_prestador_atual(db, casa.id)
    db.add(casa)
    db.flush()
    u = Usuario(id=uuid.uuid4(), prestador_id=casa.id, email=f"cont{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    r = logado(u).post("/api/ajuda/perguntar", json={"pergunta": "Como eu cancelo uma nota?"})
    assert r.status_code == 200, r.text
