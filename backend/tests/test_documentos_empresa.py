"""Documentos da empresa (2026.10.7 — ideias/documentos-da-empresa.md).

Limites (arquivo e empresa), contador com e sem a permissão, gestor que não
abre, validade (30 dias e vencido), empresa apagada leva os documentos e uma
empresa nunca vê documento de outra. Só dados sintéticos."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.deps import usuario_logado
from app.main import app, prestador_atual_id
from app.models import AcessoContador, DocumentoAcesso, DocumentoEmpresa, Prestador, Usuario
from app.services import documentos_empresa as docs
from app.tempo import hoje as hoje_br

PDF = b"%PDF-1.4 documento sintetico"


@pytest.fixture
def dono(db, prestador_teste):
    u = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=f"dono{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def entrar(db, prestador_teste):
    db.commit = db.flush

    def _get_db():
        yield db

    def _entrar(usuario, prestador_id=None):
        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[prestador_atual_id] = lambda: prestador_id or prestador_teste.id
        app.dependency_overrides[usuario_logado] = lambda: usuario
        return TestClient(app)

    yield _entrar
    for dep in (get_db, prestador_atual_id, usuario_logado):
        app.dependency_overrides.pop(dep, None)


def _enviar(c, tipo="contrato_social", conteudo=PDF, validade=None, nome="Contrato"):
    data = {"tipo": tipo, "nome": nome}
    if validade:
        data["validade"] = validade
    return c.post("/api/documentos", data=data, files={"arquivo": ("contrato.pdf", conteudo, "application/pdf")})


def _contador(db, prestador_teste, permissoes):
    casa = Prestador(id=uuid.uuid4(), cpf_cnpj=f"CT{uuid.uuid4().hex[:10]}", razao_social="ESCRITORIO SINTETICO", cod_municipio="3106200", so_contador=True)
    definir_prestador_atual(db, casa.id)
    db.add(casa)
    db.flush()
    u = Usuario(id=uuid.uuid4(), prestador_id=casa.id, email=f"contador{uuid.uuid4().hex[:5]}@exemplo.com.br", senha_hash="x", email_confirmado=True)
    db.add(u)
    db.flush()
    definir_prestador_atual(db, prestador_teste.id)
    db.add(AcessoContador(id=uuid.uuid4(), prestador_id=prestador_teste.id, email=u.email, usuario_id=u.id, status="ativo", permissoes=permissoes))
    db.flush()
    return u


def test_dono_envia_abre_substitui_apaga_e_ve_quem_abriu(db, dono, entrar):
    c = entrar(dono)
    r = _enviar(c, validade=(hoje_br() + datetime.timedelta(days=400)).isoformat())
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]
    lista = c.get("/api/documentos").json()
    assert lista["pode_apagar"] is True and lista["documentos"][0]["tipo_rotulo"] == "Contrato social e alterações"
    assert c.get(f"/api/documentos/{doc_id}/arquivo").content == PDF
    assert c.get(f"/api/documentos/{doc_id}/arquivo?baixar=true").headers["content-disposition"].startswith("attachment")
    r = c.post(f"/api/documentos/{doc_id}/substituir", files={"arquivo": ("novo.pdf", b"%PDF novo", "application/pdf")})
    assert r.status_code == 200
    doc = db.get(DocumentoEmpresa, uuid.UUID(doc_id))
    assert doc.substituido_em is not None and doc.nome_arquivo == "novo.pdf" and doc.validade is not None
    acoes = [a["acao"] for a in c.get(f"/api/documentos/{doc_id}/acessos").json()["acessos"]]
    assert {"enviou", "abriu", "baixou", "substituiu"} <= set(acoes)
    assert c.delete(f"/api/documentos/{doc_id}").status_code == 200
    assert c.get("/api/documentos").json()["documentos"] == []


def test_limites_de_arquivo_e_da_empresa(db, dono, entrar, monkeypatch):
    c = entrar(dono)
    monkeypatch.setattr(docs, "LIMITE_ARQUIVO_MB", 1)
    assert _enviar(c, conteudo=b"x" * (1024 * 1024 + 10)).status_code == 413
    assert _enviar(c, conteudo=b"x" * (1024 * 1024 - 10)).status_code == 200
    monkeypatch.setattr(docs, "LIMITE_EMPRESA_MB", 1)
    r = _enviar(c, conteudo=b"y" * 100)
    assert r.status_code == 413 and "100" not in r.json()["detail"] or "limite" in r.json()["detail"]
    assert _enviar(c, tipo="inventado").status_code in (413, 422)


def test_contador_sem_a_permissao_nem_ve(db, prestador_teste, dono, entrar):
    _enviar(entrar(dono))
    contador = _contador(db, prestador_teste, ["emitir", "empresa"])
    c = entrar(contador)
    assert c.get("/api/documentos").status_code == 403
    assert _enviar(c).status_code == 403
    doc_id = db.query(DocumentoEmpresa.id).filter_by(prestador_id=prestador_teste.id).first()[0]
    assert c.get(f"/api/documentos/{doc_id}/arquivo").status_code == 403
    # o dono é avisado de que pode ligar
    assert contador.email in entrar(dono).get("/api/documentos").json()["contadores_sem_permissao"]


def test_contador_com_a_permissao_ve_envia_substitui_mas_nao_apaga(db, prestador_teste, dono, entrar):
    contador = _contador(db, prestador_teste, ["documentos"])
    c = entrar(contador)
    r = _enviar(c, tipo="socios", nome="RG do sócio")
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]
    lista = c.get("/api/documentos").json()
    assert lista["papel"] == "contador" and lista["pode_apagar"] is False and lista["contadores_sem_permissao"] == []
    assert c.post(f"/api/documentos/{doc_id}/substituir", files={"arquivo": ("rg.pdf", PDF, "application/pdf")}).status_code == 200
    assert c.delete(f"/api/documentos/{doc_id}").status_code == 403
    assert c.get(f"/api/documentos/{doc_id}/acessos").status_code == 403
    assert db.query(DocumentoAcesso).filter_by(documento_id=uuid.UUID(doc_id), papel="contador").count() >= 2


def test_gestor_nao_abre_documento(db, prestador_teste, dono, entrar, monkeypatch):
    doc_id = _enviar(entrar(dono)).json()["id"]
    outra = Prestador(id=uuid.uuid4(), cpf_cnpj="00000000000353", razao_social="EMPRESA DO GESTOR", cod_municipio="3106200")
    definir_prestador_atual(db, outra.id)
    db.add(outra)
    db.flush()
    gestor = Usuario(id=uuid.uuid4(), prestador_id=outra.id, email="gestor@plataforma.example", senha_hash="x", email_confirmado=True)
    db.add(gestor)
    db.flush()
    monkeypatch.setattr(get_settings(), "admin_emails", gestor.email)
    c = entrar(gestor, prestador_id=outra.id)
    # na empresa dele, o documento da outra empresa não existe (RLS)
    assert c.get(f"/api/documentos/{doc_id}/arquivo").status_code == 404
    assert c.get("/api/documentos").json()["documentos"] == []
    # e na empresa do cliente ele não é dono nem contador
    c2 = entrar(gestor, prestador_id=prestador_teste.id)
    assert c2.get("/api/documentos").status_code == 403


def test_uma_empresa_nao_ve_documento_da_outra(db, prestador_teste, dono, entrar):
    _enviar(entrar(dono))
    outra_id = uuid.uuid4()
    definir_prestador_atual(db, outra_id)
    assert db.query(DocumentoEmpresa).count() == 0
    definir_prestador_atual(db, prestador_teste.id)
    assert db.query(DocumentoEmpresa).count() == 1


def test_validade_avisa_30_dias_antes_e_vencido(db, prestador_teste, dono, entrar):
    from app.services.dashboard import resumo_mes

    c = entrar(dono)
    _enviar(c, nome="Alvará", tipo="alvara", validade=(hoje_br() + datetime.timedelta(days=60)).isoformat())
    assert docs.avisos_de_validade(db, prestador_teste.id) == []
    _enviar(c, nome="Certidão", tipo="certidoes", validade=(hoje_br() + datetime.timedelta(days=30)).isoformat())
    _enviar(c, nome="Licença", tipo="alvara", validade=(hoje_br() - datetime.timedelta(days=1)).isoformat())
    avisos = docs.avisos_de_validade(db, prestador_teste.id)
    assert [(a["nome"], a["vencido"]) for a in avisos] == [("Licença", True), ("Certidão", False)]
    hoje = hoje_br()
    atencao = resumo_mes(db, prestador_teste.id, competencia=f"{hoje.year:04d}-{hoje.month:02d}")["atencao"]
    item = next(a for a in atencao if a["titulo"] == "Documentos da empresa")
    assert "1 vencido" in item["mensagem"] and "Licença" not in item["mensagem"]  # sem nome: o contador sem permissão também vê esta lista


def test_empresa_apagada_leva_os_documentos(db, prestador_teste, dono, entrar):
    from app.services.contas import apagar_empresa

    _enviar(entrar(dono))
    apagar_empresa(db, prestador_teste.id)
    definir_prestador_atual(db, prestador_teste.id)
    assert db.query(DocumentoEmpresa).count() == 0


def test_gestao_ve_so_quantidade_e_espaco(db, prestador_teste, dono, entrar):
    _enviar(entrar(dono))
    r = docs.resumo_gestao(db, prestador_teste.id)
    assert r == {"quantidade": 1, "bytes": len(PDF)}
