"""
Envio direto ao fornecedor — Marco 17 (ver app/services/envio_direto.py).
Nenhum teste fala com o Resend de verdade: o sender é trocado por um fake.
"""
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app, prestador_atual_id
from app.services import envio_direto
from app.services.email import EmailEnvioError
from app.services.vinculos import atualizar_vinculo


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


class _SenderFake:
    def __init__(self, falhar=False):
        self.enviados = []
        self.falhar = falhar

    def enviar(self, **kw):
        if self.falhar:
            raise EmailEnvioError("provedor fora do ar")
        self.enviados.append(kw)


def _ligar_email(monkeypatch, sender):
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_fake")
    monkeypatch.setattr(get_settings(), "email_remetente_notas", "NotaFácil <notas@notafacil.test>")
    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: sender)


def _nova_emissao(client, vinculo_teste):
    return client.post("/api/dps", json={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-08", "valor": 1234.5}).json()["id"]


def test_token_ida_e_volta_e_token_adulterado(db, vinculo_teste, client):
    from app.models import Emissao

    emissao = db.get(Emissao, _nova_emissao(client, vinculo_teste))
    token = envio_direto.gerar_token(emissao)
    assert envio_direto.ler_token(token) == (emissao.id, emissao.prestador_id)
    with pytest.raises(envio_direto.LinkInvalidoError):
        envio_direto.ler_token(token[:-2] + "xx")


def test_opcoes_email_desligado_sem_dominio(client, vinculo_teste):
    eid = _nova_emissao(client, vinculo_teste)
    r = client.get(f"/api/dps/{eid}/envio-opcoes").json()
    assert r["email_habilitado"] is False
    assert "domínio" in r["email_motivo_desabilitado"]
    assert "/api/publico/nota/" in r["link_publico"]


def test_opcoes_pede_email_do_fornecedor(client, vinculo_teste, monkeypatch):
    _ligar_email(monkeypatch, _SenderFake())
    eid = _nova_emissao(client, vinculo_teste)
    r = client.get(f"/api/dps/{eid}/envio-opcoes").json()
    assert r["email_habilitado"] is False
    assert "e-mail deste fornecedor" in r["email_motivo_desabilitado"]
    assert client.post(f"/api/dps/{eid}/enviar-email").status_code == 400


def test_enviar_email_com_xml_anexo_e_reply_to(client, db, vinculo_teste, prestador_teste, monkeypatch):
    sender = _SenderFake()
    _ligar_email(monkeypatch, sender)
    prestador_teste.email = "raiana@exemplo.com"
    atualizar_vinculo(db, vinculo_teste, email_contato="financeiro@fornecedor.com")
    eid = _nova_emissao(client, vinculo_teste)

    r = client.post(f"/api/dps/{eid}/enviar-email")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "enviado"
    assert r.json()["destino"] == "financeiro@fornecedor.com"

    enviado = sender.enviados[0]
    assert enviado["destinatario"] == "financeiro@fornecedor.com"
    assert enviado["responder_para"] == "raiana@exemplo.com"
    assert enviado["remetente"].endswith("<notas@notafacil.test>")
    assert [n for n, _ in enviado["anexos"]][0].endswith(".xml")  # sem PDF: nota não confirmada
    assert "R$ 1.234,50" in enviado["corpo_texto"]
    assert "/api/publico/nota/" in enviado["corpo_texto"]


def test_falha_do_provedor_vira_envio_com_falha(client, db, vinculo_teste, monkeypatch):
    _ligar_email(monkeypatch, _SenderFake(falhar=True))
    atualizar_vinculo(db, vinculo_teste, email_contato="financeiro@fornecedor.com")
    eid = _nova_emissao(client, vinculo_teste)
    r = client.post(f"/api/dps/{eid}/enviar-email").json()
    assert r["status"] == "falha" and "fora do ar" in r["erro"]


def test_whatsapp_com_numero_e_mensagem(client, db, vinculo_teste):
    atualizar_vinculo(db, vinculo_teste, whatsapp_contato="(92) 99999-0000")
    eid = _nova_emissao(client, vinculo_teste)
    r = client.post(f"/api/dps/{eid}/whatsapp").json()
    url = urlparse(r["url"])
    assert url.netloc == "wa.me" and url.path == "/5592999990000"
    texto = unquote(parse_qs(url.query)["text"][0])
    assert "/api/publico/nota/" in texto and "08/2026" in texto
    assert r["envio"]["canal"] == "whatsapp" and r["envio"]["status"] == "pendente"


def test_whatsapp_sem_numero_abre_seletor_de_contato(client, vinculo_teste):
    eid = _nova_emissao(client, vinculo_teste)
    assert client.post(f"/api/dps/{eid}/whatsapp").json()["url"].startswith("https://wa.me/?text=")


def test_link_publico_baixa_xml_sem_login_e_rejeita_token_ruim(client, vinculo_teste):
    eid = _nova_emissao(client, vinculo_teste)
    link = client.get(f"/api/dps/{eid}/envio-opcoes").json()["link_publico"]
    caminho = urlparse(link).path

    app.dependency_overrides.pop(prestador_atual_id, None)  # sem sessão
    r = client.get(caminho)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert client.get("/api/publico/nota/lixo").status_code == 404


def test_pdf_indisponivel_antes_da_confirmacao(client, vinculo_teste):
    eid = _nova_emissao(client, vinculo_teste)
    assert client.get(f"/api/dps/{eid}/pdf").status_code == 404


def test_vinculo_guarda_contatos(client, vinculo_teste):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"email_contato": "a@b.com", "whatsapp_contato": "92999990000"})
    assert r.status_code == 200, r.text
    assert r.json()["email_contato"] == "a@b.com"
    assert r.json()["whatsapp_contato"] == "92999990000"


def test_nota_confirmada_anexa_pdf_oficial_e_guarda_em_cache(client, db, vinculo_teste, certificado_teste, monkeypatch):
    from app.fiscal.cliente_sefin import ClienteSefin
    from app.models import Emissao

    with open(certificado_teste["path"], "rb") as f:
        client.post("/api/certificado", files={"pfx": ("cert.pfx", f, "application/x-pkcs12")}, data={"senha": certificado_teste["senha"]})
    eid = _nova_emissao(client, vinculo_teste)
    emissao = db.get(Emissao, eid)
    emissao.estado = "confirmado"
    emissao.chave_acesso = "1" * 50
    db.flush()

    chamadas = []

    def _danfse_fake(self, chave):
        chamadas.append(chave)
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(ClienteSefin, "baixar_danfse", _danfse_fake)
    sender = _SenderFake()
    _ligar_email(monkeypatch, sender)
    atualizar_vinculo(db, vinculo_teste, email_contato="financeiro@fornecedor.com")

    assert client.post(f"/api/dps/{eid}/enviar-email").json()["status"] == "enviado"
    nomes = [n for n, _ in sender.enviados[0]["anexos"]]
    assert nomes[0].endswith(".pdf") and nomes[1].endswith(".xml")

    r = client.get(f"/api/dps/{eid}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert len(chamadas) == 1  # segunda vez veio do cache
