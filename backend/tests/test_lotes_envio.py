"""Ações em lote, envio ao fornecedor por e-mail/WhatsApp com edição e
"lembrar as últimas escolhas", NBS/intermediário/data de competência na DPS
e zip das notas (29/09/2026)."""
import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Envio, LoteAcao
from app.services import lotes
from app.services.motor_emissao import criar_rascunho, montar


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


class _Falso:
    def __init__(self, falhar_para=None):
        self.enviados = []
        self.falhar_para = falhar_para

    def enviar(self, **kw):
        from app.services.email import EmailEnvioError

        if self.falhar_para and self.falhar_para in kw["destinatario"]:
            raise EmailEnvioError("caixa cheia")
        self.enviados.append(kw)


def _avulsa(db, vinculo, doc, email):
    e = criar_rascunho(db, vinculo, competencia="2026-09", valor=1, tpAmb="2", tomador_avulso={
        "documento": doc, "tipo_documento": "CNPJ", "razao_social": f"Loja {doc[-2:]}",
        "email": email, "endereco": {}, "pais": "BR", "lojas": [],
    })
    montar(db, e)
    return e


def test_lote_de_email_envia_todas_conta_falhas_e_refaz(client, db, prestador_teste, vinculo_teste, monkeypatch):
    import app.services.envio_direto as envio_direto

    falso = _Falso(falhar_para="ruim@x.com")
    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: falso)
    monkeypatch.setattr(envio_direto, "motivo_email_desabilitado", lambda vinculo, destino=None: None if destino else "sem destino")
    monkeypatch.setattr(lotes, "PAUSA_EMAIL_S", 0)
    vinculo_teste.email_anexos = "xml"
    notas = [_avulsa(db, vinculo_teste, f"112223330001{i:02d}", f"v{i}@x.com") for i in range(3)]
    notas.append(_avulsa(db, vinculo_teste, "11222333000199", "ruim@x.com"))

    previa = client.post("/api/lotes/previa", json={"acao": "email", "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09"})
    assert previa.json()["quantidade"] == 4

    monkeypatch.setattr(lotes, "iniciar", lambda *a, **k: None)  # roda síncrono abaixo
    r = client.post("/api/lotes", json={"acao": "email", "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09"})
    assert r.status_code == 200, r.text
    lote = db.get(LoteAcao, uuid.UUID(r.json()["id"]))
    lotes.processar(db, lote, prestador_teste.id, "https://x")
    assert (lote.status, lote.feitos, lote.falhas) == ("concluido", 3, 1)
    assert lote.erros[0]["erro"]

    resumo = client.get(f"/api/envios/resumo?vinculo_id={vinculo_teste.id}").json()
    assert resumo["enviados"] == 3 and resumo["falhas"] == 1
    # já enviadas não entram de novo; a com falha entra
    assert client.post("/api/lotes/previa", json={"acao": "email", "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09"}).json()["quantidade"] == 1

    falso.falhar_para = None
    r = client.post(f"/api/lotes/{lote.id}/refazer-falhas")
    assert r.status_code == 200 and r.json()["total"] == 1
    novo = db.get(LoteAcao, uuid.UUID(r.json()["id"]))
    lotes.processar(db, novo, prestador_teste.id, "https://x")
    assert novo.feitos == 1 and novo.falhas == 0


def test_lote_sem_nada_elegivel_e_cancelar(client, vinculo_teste, db, prestador_teste, monkeypatch):
    assert client.post("/api/lotes", json={"acao": "submeter", "vinculo_id": str(vinculo_teste.id)}).status_code == 422
    monkeypatch.setattr(lotes, "iniciar", lambda *a, **k: None)
    e = criar_rascunho(db, vinculo_teste, competencia="2026-04", valor=5)
    montar(db, e)
    r = client.post("/api/lotes", json={"acao": "assinar", "emissao_ids": [str(e.id)]})
    assert r.status_code == 200
    assert client.post(f"/api/lotes/{r.json()['id']}/cancelar").json()["status"] == "cancelado"


def test_envio_com_edicao_whatsapp_e_lembrar(client, db, vinculo_teste, monkeypatch):
    import app.services.envio_direto as envio_direto

    falso = _Falso()
    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: falso)
    monkeypatch.setattr(envio_direto, "motivo_email_desabilitado", lambda vinculo, destino=None: None if destino else "sem destino")
    vinculo_teste.email_contato = "contato@t.com"
    vinculo_teste.email_anexos = "xml"
    e = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=1234.5, tpAmb="2")
    montar(db, e)

    r = client.post(f"/api/dps/{e.id}/enviar-email", json={
        "para": ["fin@t.com"], "copia": [], "assunto": "NF de 09/2026 — R$ 1.234,50",
        "texto": "Oi, segue a nota de 09/2026.", "salvar_padrao": True,
    })
    assert r.json()["status"] == "enviado"
    assert falso.enviados[-1]["assunto"] == "NF de 09/2026 — R$ 1.234,50"
    assert falso.enviados[-1]["corpo_texto"] == "Oi, segue a nota de 09/2026."
    # lembrou como modelo (sem congelar o mês/valor desta nota)
    assert vinculo_teste.email_para == "fin@t.com"
    assert vinculo_teste.email_assunto == "NF de {competencia} — {valor}"
    assert vinculo_teste.email_mensagem == "Oi, segue a nota de {competencia}."
    assert vinculo_teste.envio_canal == "email"

    # WhatsApp: mesmo sem e-mail, com número e texto editados
    r = client.post(f"/api/dps/{e.id}/whatsapp", json={"numero": "(31) 98888-7777", "texto": "Nota 09/2026 aqui", "salvar_padrao": True})
    assert r.status_code == 200 and "wa.me/5531988887777" in r.json()["url"]
    assert vinculo_teste.whatsapp_contato == "(31) 98888-7777" and vinculo_teste.envio_canal == "whatsapp"
    assert vinculo_teste.whatsapp_mensagem == "Nota {competencia} aqui"
    previa = client.get(f"/api/dps/{e.id}/email-previa").json()
    assert previa["canal_preferido"] == "whatsapp" and previa["whatsapp_texto"] == "Nota 09/2026 aqui"


def test_dps_com_nbs_intermediario_e_data_de_competencia(client, db, vinculo_teste):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cod_nbs": "1.1406.20.00", "incluir_intermediario": True})
    assert r.status_code == 200 and r.json()["cod_nbs"] == "114062000"
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cod_nbs": "123"}).status_code == 422
    r = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": "2026-01", "valor": 10, "data_competencia": "2026-08-15",
    })
    assert r.status_code == 200, r.text
    assert r.json()["competencia"] == "2026-08"  # o mês da data escolhida
    from app.models import Emissao

    emissao = db.get(Emissao, uuid.UUID(r.json()["id"]))
    assert "<cNBS>114062000</cNBS>" in emissao.xml_dps
    assert "<dCompet>2026-08-15</dCompet>" in emissao.xml_dps
    assert "<interm>" not in emissao.xml_dps  # intermediário só nas notas de vendedor (Shopee)

    avulsa = _avulsa(db, vinculo_teste, "11222333000181", "v@x.com")
    assert "<interm>" in avulsa.xml_dps and f"<CNPJ>{vinculo_teste.tomador.cnpj}</CNPJ>" in avulsa.xml_dps


def test_zip_do_mes(client, db, vinculo_teste):
    for doc in ("11222333000181", "11222333000182"):
        _avulsa(db, vinculo_teste, doc, "v@x.com")
    r = client.get("/api/dps/zip?competencia=2026-09")
    assert r.status_code == 200
    nomes = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert len([n for n in nomes if n.startswith("xml/")]) == 2
    assert client.get("/api/dps/zip?competencia=2020-01").status_code == 404


def test_forma_de_envio_emails_gerais_e_portal(client, db, prestador_teste, vinculo_teste, monkeypatch):
    import app.services.envio_direto as envio_direto
    from app.config import get_settings

    falso = _Falso()
    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: falso)
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_teste")
    monkeypatch.setattr(get_settings(), "email_remetente_notas", "notas@x.com")

    # tomador recebe pelo portal: nota fica fora do lote de e-mail
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_canal": "portal", "portal_url": " https://portal.x/notas "})
    assert r.status_code == 200 and r.json()["envio_canal"] == "portal" and r.json()["portal_url"] == "https://portal.x/notas"
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_canal": "fax"}).status_code == 422
    e = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=10, tpAmb="2")
    montar(db, e)
    vinculo_teste.email_anexos = "xml"
    db.flush()
    assert client.post("/api/lotes/previa", json={"acao": "email", "emissao_ids": [str(e.id)]}).json()["quantidade"] == 0
    previa = client.get(f"/api/dps/{e.id}/email-previa").json()
    assert previa["portal_url"] == "https://portal.x/notas"

    # e-mails gerais sem cadastro → 400 com orientação
    assert client.post(f"/api/dps/{e.id}/enviar-geral", json={}).status_code == 400
    r = client.patch("/api/prestador/preferencias", json={
        "email_geral_para": "contador@x.com; eu@x.com", "email_geral_assunto": "Nota {numero} - {tomador}",
        "email_geral_anexos": "xml",
    })
    assert r.status_code == 200, r.text
    assert r.json()["email_geral_para"] == "contador@x.com; eu@x.com"
    r = client.post(f"/api/dps/{e.id}/enviar-geral", json={})
    assert r.status_code == 200, r.text
    assert r.json()["canal"] == "email_geral" and r.json()["status"] == "enviado"
    assert falso.enviados[-1]["destinatario"] == ["contador@x.com", "eu@x.com"]
    # e-mail geral não conta como entregue ao fornecedor
    assert client.get(f"/api/envios/resumo?vinculo_id={vinculo_teste.id}").json()["enviados"] == 0

    r = client.post(f"/api/dps/{e.id}/marcar-enviada", json={"forma": "portal"})
    assert r.status_code == 200 and r.json()["status"] == "enviado"
    assert client.get(f"/api/envios/resumo?vinculo_id={vinculo_teste.id}").json()["enviados"] == 1
    lista = client.get("/api/dps").json()
    item = next(i for i in (lista["itens"] if isinstance(lista, dict) else lista) if i["id"] == str(e.id))
    assert item["envio_forma"] == "portal"
