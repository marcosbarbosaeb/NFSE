"""Marco 15 (item 4): assinatura/cobrança (ver app/services/billing.py).

Nenhum teste aqui fala com a API de verdade da Stripe (não existe conta
ainda, ver docstring do módulo) — `stripe.Customer.create`/
`checkout.Session.create`/`billing_portal.Session.create`/
`Webhook.construct_event` são todos monkeypatchados quando o "caminho
feliz" (configurado) precisa ser exercitado.
"""
import datetime

import pytest

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Assinatura
from app.services.billing import (
    AssinaturaNaoEncontradaError,
    BillingNaoConfiguradoError,
    WebhookInvalidoError,
    assinatura_esta_ativa,
    criar_assinatura_cortesia,
    criar_assinatura_trial,
    criar_sessao_checkout,
    criar_sessao_portal,
    processar_webhook,
)
from app.services.usuarios import criar_usuario


# --- nível de serviço ---


def test_criar_assinatura_cortesia(db, prestador_teste):
    assinatura = criar_assinatura_cortesia(db, prestador_teste.id)
    assert assinatura.status == "cortesia"
    assert assinatura.trial_termina_em is None
    assert assinatura_esta_ativa(assinatura) is True


def test_criar_assinatura_cortesia_e_idempotente(db, prestador_teste):
    primeira = criar_assinatura_cortesia(db, prestador_teste.id)
    segunda = criar_assinatura_cortesia(db, prestador_teste.id)
    assert primeira.id == segunda.id
    assert db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).count() == 1


def test_criar_assinatura_trial(db, prestador_teste):
    assinatura = criar_assinatura_trial(db, prestador_teste.id)
    assert assinatura.status == "trial"
    assert assinatura.trial_termina_em is not None
    agora = datetime.datetime.now(datetime.timezone.utc)
    assert assinatura.trial_termina_em > agora
    assert assinatura_esta_ativa(assinatura) is True


def test_assinatura_esta_ativa_none_e_falso():
    assert assinatura_esta_ativa(None) is False


def test_assinatura_esta_ativa_trial_expirado_e_falso(db, prestador_teste):
    assinatura = criar_assinatura_trial(db, prestador_teste.id)
    assinatura.trial_termina_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    db.flush()
    assert assinatura_esta_ativa(assinatura) is False


@pytest.mark.parametrize("status", ["inadimplente", "cancelada"])
def test_assinatura_esta_ativa_status_inativo(db, prestador_teste, status):
    assinatura = criar_assinatura_cortesia(db, prestador_teste.id)
    assinatura.status = status
    db.flush()
    assert assinatura_esta_ativa(assinatura) is False


def test_criar_sessao_checkout_sem_stripe_configurado_da_erro(db, prestador_teste):
    with pytest.raises(BillingNaoConfiguradoError):
        criar_sessao_checkout(db, prestador_teste.id, "raiana@exemplo.com")


def test_criar_sessao_portal_sem_assinatura_da_erro(db, prestador_teste, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(get_settings(), "stripe_price_id_mensal", "price_de_verdade")
    with pytest.raises(AssinaturaNaoEncontradaError):
        criar_sessao_portal(db, prestador_teste.id)


def test_criar_sessao_checkout_caminho_feliz(db, prestador_teste, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(get_settings(), "stripe_price_id_mensal", "price_de_verdade")

    criados = {}

    class _FakeCustomer(dict):
        pass

    class _FakeSession(dict):
        pass

    def _fake_customer_create(**kwargs):
        criados["customer_kwargs"] = kwargs
        return _FakeCustomer(id="cus_fake123")

    def _fake_session_create(**kwargs):
        criados["session_kwargs"] = kwargs
        return _FakeSession(url="https://checkout.stripe.com/fake-session")

    monkeypatch.setattr(billing.stripe.Customer, "create", _fake_customer_create)
    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    url = criar_sessao_checkout(db, prestador_teste.id, "raiana@exemplo.com")
    assert url == "https://checkout.stripe.com/fake-session"
    assert criados["customer_kwargs"]["email"] == "raiana@exemplo.com"
    assert criados["session_kwargs"]["metadata"] == {"prestador_id": str(prestador_teste.id)}
    assert criados["session_kwargs"]["subscription_data"] == {"metadata": {"prestador_id": str(prestador_teste.id)}}

    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).one()
    assert assinatura.stripe_customer_id == "cus_fake123"


def test_criar_sessao_checkout_reaproveita_customer_existente(db, prestador_teste, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(get_settings(), "stripe_price_id_mensal", "price_de_verdade")

    assinatura = criar_assinatura_trial(db, prestador_teste.id)
    assinatura.stripe_customer_id = "cus_ja_existe"
    db.flush()

    chamadas = {"customer_create": 0}
    monkeypatch.setattr(
        billing.stripe.Customer, "create", lambda **kw: chamadas.__setitem__("customer_create", chamadas["customer_create"] + 1)
    )
    monkeypatch.setattr(billing.stripe.checkout.Session, "create", lambda **kw: {"url": "https://checkout.stripe.com/x"})

    criar_sessao_checkout(db, prestador_teste.id, "raiana@exemplo.com")
    assert chamadas["customer_create"] == 0  # não criou um Customer novo


def test_processar_webhook_sem_secret_configurada_da_erro(db):
    with pytest.raises(BillingNaoConfiguradoError):
        processar_webhook(db, b"{}", "assinatura-qualquer")


def test_processar_webhook_assinatura_invalida_da_erro(db, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")

    def _fake_construct_event(payload, sig_header, secret):
        raise billing.stripe.SignatureVerificationError("assinatura inválida", sig_header)

    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", _fake_construct_event)
    with pytest.raises(WebhookInvalidoError):
        processar_webhook(db, b"{}", "assinatura-forjada")


def test_processar_webhook_checkout_completo_ativa_assinatura(db, prestador_teste, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")
    criar_assinatura_trial(db, prestador_teste.id)
    db.flush()

    evento = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_abc",
                "subscription": "sub_abc",
                "metadata": {"prestador_id": str(prestador_teste.id)},
            }
        },
    }
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", lambda payload, sig_header, secret: evento)

    tipo = processar_webhook(db, b"{}", "assinatura-valida")
    assert tipo == "checkout.session.completed"

    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).one()
    assert assinatura.status == "ativa"
    assert assinatura.stripe_subscription_id == "sub_abc"


def test_processar_webhook_subscription_deleted_cancela(db, prestador_teste, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")
    assinatura = criar_assinatura_trial(db, prestador_teste.id)
    assinatura.status = "ativa"
    assinatura.stripe_subscription_id = "sub_abc"
    db.flush()

    evento = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_abc", "metadata": {"prestador_id": str(prestador_teste.id)}}},
    }
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", lambda payload, sig_header, secret: evento)

    processar_webhook(db, b"{}", "assinatura-valida")
    db.refresh(assinatura)
    assert assinatura.status == "cancelada"


def test_processar_webhook_sem_metadata_prestador_id_nao_quebra(db, monkeypatch):
    """Evento sem metadata.prestador_id (ex.: assinatura criada manualmente
    no dashboard Stripe, fora do fluxo de Checkout desta app) — deve ser
    ignorado, nunca lançar exceção."""
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")
    evento = {"type": "checkout.session.completed", "data": {"object": {"customer": "cus_x", "metadata": {}}}}
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", lambda payload, sig_header, secret: evento)

    tipo = processar_webhook(db, b"{}", "assinatura-valida")
    assert tipo == "checkout.session.completed"


def test_processar_webhook_evento_desconhecido_ignorado(db, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")
    evento = {"type": "invoice.paid", "data": {"object": {}}}
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", lambda payload, sig_header, secret: evento)

    assert processar_webhook(db, b"{}", "assinatura-valida") is None


# --- nível HTTP ---


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    from fastapi.testclient import TestClient

    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_endpoint_ver_assinatura_sem_linha_devolve_trial_nao_ativo(client):
    resp = client.get("/api/assinatura")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "trial"
    assert corpo["ativa"] is False


def test_endpoint_ver_assinatura_cortesia(client, db, prestador_teste):
    criar_assinatura_cortesia(db, prestador_teste.id)
    resp = client.get("/api/assinatura")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "cortesia"
    assert corpo["ativa"] is True


def test_endpoint_checkout_sem_stripe_configurado_da_400(client):
    resp = client.post("/api/assinatura/checkout")
    assert resp.status_code == 401  # sem sessão de usuário real neste fixture (só prestador_id foi overridado)


@pytest.fixture
def client_logado(db, prestador_teste):
    """Diferente do fixture `client` acima: faz login de verdade (cookie de
    sessão), necessário pros endpoints que leem `request.session` direto
    (checkout) — mesmo padrão de `client_sem_login` em tests/test_auth.py."""
    criar_usuario(db, prestador_teste.id, "raiana@exemplo.com", "senhaforte123")
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    from fastapi.testclient import TestClient

    c = TestClient(app)
    login = c.post("/api/auth/login", json={"email": "raiana@exemplo.com", "senha": "senhaforte123"})
    assert login.status_code == 200
    yield c
    app.dependency_overrides.pop(get_db, None)


def test_endpoint_checkout_logado_sem_stripe_configurado_da_400(client_logado):
    resp = client_logado.post("/api/assinatura/checkout")
    assert resp.status_code == 400
    assert "configurada" in resp.json()["detail"].lower()


def test_endpoint_portal_sem_assinatura_da_400(client_logado, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(get_settings(), "stripe_price_id_mensal", "price_de_verdade")
    resp = client_logado.post("/api/assinatura/portal")
    assert resp.status_code == 400


def test_endpoint_webhook_assinatura_invalida_da_400(db, monkeypatch):
    from app.config import get_settings
    import app.services.billing as billing

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_fake")

    def _fake_construct_event(payload, sig_header, secret):
        raise billing.stripe.SignatureVerificationError("inválida", sig_header)

    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", _fake_construct_event)

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    from fastapi.testclient import TestClient

    c = TestClient(app)
    resp = c.post("/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "forjada"})
    app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 400
