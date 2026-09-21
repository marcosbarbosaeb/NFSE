"""
Assinatura/cobrança — Marco 15 (item 4), a pedido de Marcos: "cobrança real
(Stripe ou similar)". Mesma filosofia de app/services/email.py: ele ainda
não tem conta criada no Stripe ("monta a estrutura agora, eu crio a conta
depois"), então este módulo é escrito pra funcionar sem credenciais
nenhuma (levanta `BillingNaoConfiguradoError` de forma explícita nos
pontos que precisariam de verdade falar com a API) e ligar 100% assim que
`Settings.stripe_secret_key`/`stripe_price_id_mensal` forem trocados por
valores reais — nenhum código muda.

Ciclo de vida de uma `Assinatura` (ver docstring do modelo em
app/models.py):

    cortesia (admin, scripts/criar_usuario.py)
    trial (self-service, /api/cadastro)  --checkout--> ativa <--webhook--> inadimplente
                                                            \\--webhook--> cancelada

O Checkout (`criar_sessao_checkout`) e o Portal do cliente
(`criar_sessao_portal`) são os dois únicos pontos onde o painel manda o
prestador PRA FORA (pro domínio da Stripe) — ele volta via
`success_url`/`return_url`. O resto do sincronismo (confirmar que o
pagamento passou, marcar inadimplência, cancelamento) chega de volta via
webhook (`processar_webhook`), nunca via redirect do navegador (o
navegador do prestador não é uma fonte confiável de "paguei" — só o
webhook, assinado pela Stripe, é).
"""
import datetime
import logging
import uuid

import stripe
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import Assinatura, Prestador

logger = logging.getLogger("notafacil.billing")

# Mapeia o `status` de uma Subscription da Stripe pro nosso vocabulário
# (ver CheckConstraint em Assinatura). Qualquer status da Stripe que não
# apareça aqui (ex.: "incomplete", enquanto o primeiro pagamento ainda nem
# foi tentado) é ignorado — não regride a assinatura pra um estado pior à
# toa.
_STRIPE_STATUS_PARA_NOSSO = {
    "active": "ativa",
    "trialing": "ativa",
    "past_due": "inadimplente",
    "unpaid": "inadimplente",
    "canceled": "cancelada",
    "incomplete_expired": "cancelada",
}


class BillingNaoConfiguradoError(Exception):
    """`stripe_secret_key`/`stripe_price_id_mensal` ainda não foram
    configurados (ver docstring do módulo) — a rota que chamou isto deve
    responder com uma mensagem clara em vez de deixar a exceção da SDK da
    Stripe vazar pro cliente."""


class AssinaturaNaoEncontradaError(Exception):
    pass


class WebhookInvalidoError(Exception):
    """Assinatura do payload não bate (ver stripe.Webhook.construct_event)
    — o request não veio da Stripe de verdade, ou stripe_webhook_secret
    está errada. NUNCA processar o corpo de um webhook sem essa validação
    passar antes."""


def _stripe_configurado() -> bool:
    s = get_settings()
    return bool(s.stripe_secret_key) and bool(s.stripe_price_id_mensal) and not s.stripe_price_id_mensal.startswith(
        "price_placeholder"
    )


def _exigir_stripe_configurado() -> None:
    if not _stripe_configurado():
        raise BillingNaoConfiguradoError(
            "Cobrança ainda não está configurada (falta criar a conta Stripe e definir "
            "STRIPE_SECRET_KEY/STRIPE_PRICE_ID_MENSAL). Fale com o suporte."
        )


def criar_assinatura_cortesia(db: Session, prestador_id: uuid.UUID) -> Assinatura:
    """Contas administrativas (scripts/criar_usuario.py) nunca deveriam
    depender do Stripe pra continuar funcionando — é o caso da Raiana
    hoje. Idempotente: se já existir uma assinatura pra este prestador
    (ex.: rodar o script de novo pra atualizar dados), não duplica nem
    rebaixa o status."""
    existente = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if existente is not None:
        return existente
    assinatura = Assinatura(id=uuid.uuid4(), prestador_id=prestador_id, status="cortesia")
    db.add(assinatura)
    db.flush()
    return assinatura


def criar_assinatura_trial(db: Session, prestador_id: uuid.UUID) -> Assinatura:
    """Cadastro público self-service (/api/cadastro) — libera acesso por
    `stripe_dias_trial` dias sem precisar de cartão. Quem quiser continuar
    depois do trial passa pelo Checkout (`criar_sessao_checkout`)."""
    termina_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=get_settings().stripe_dias_trial
    )
    assinatura = Assinatura(id=uuid.uuid4(), prestador_id=prestador_id, status="trial", trial_termina_em=termina_em)
    db.add(assinatura)
    db.flush()
    return assinatura


def assinatura_esta_ativa(assinatura: Assinatura | None) -> bool:
    """"Tem acesso liberado?" — cortesia e assinatura Stripe ativa sempre
    sim; trial só até a data expirar. NÃO usada hoje pra bloquear rota
    nenhuma do painel (ver docstring de Assinatura em app/models.py: ligar
    esse bloqueio de verdade fica pra quando houver conta Stripe real pra
    validar contra ela) — existe já pronta pra quando isso acontecer, e
    pro card de Configurações mostrar o status certo."""
    if assinatura is None:
        return False
    if assinatura.status in ("cortesia", "ativa"):
        return True
    if assinatura.status == "trial":
        if assinatura.trial_termina_em is None:
            return False
        agora = datetime.datetime.now(datetime.timezone.utc)
        return assinatura.trial_termina_em > agora
    return False


def _obter_ou_criar_customer(assinatura: Assinatura, prestador: Prestador, email: str) -> str:
    if assinatura.stripe_customer_id:
        return assinatura.stripe_customer_id
    customer = stripe.Customer.create(
        email=email,
        name=prestador.razao_social,
        metadata={"prestador_id": str(prestador.id)},
        api_key=get_settings().stripe_secret_key,
    )
    assinatura.stripe_customer_id = customer["id"]
    return customer["id"]


def criar_sessao_checkout(db: Session, prestador_id: uuid.UUID, email: str) -> str:
    """Cria (ou reaproveita) o Customer da Stripe e devolve a URL de uma
    Checkout Session em modo assinatura. Levanta `BillingNaoConfiguradoError`
    enquanto não houver conta Stripe de verdade (ver docstring do
    módulo)."""
    _exigir_stripe_configurado()
    settings = get_settings()
    prestador = db.get(Prestador, prestador_id)
    if prestador is None:
        raise AssinaturaNaoEncontradaError("Prestador não encontrado.")
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if assinatura is None:
        assinatura = criar_assinatura_trial(db, prestador_id)

    customer_id = _obter_ou_criar_customer(assinatura, prestador, email)
    db.flush()

    # /app/configuracoes — painel movido pra debaixo de /app no item 6 do
    # Marco 15 (marketing pública, ver frontend/src/App.tsx).
    base = settings.app_base_url
    # `metadata` no Session E na subscription resultante (via
    # subscription_data) — é assim que o webhook (que não tem sessão de
    # usuário nenhuma, só o payload que a Stripe manda) sabe A QUEM
    # pertence o evento sem precisar adivinhar por stripe_customer_id (ver
    # docstring de processar_webhook: RLS de `assinatura` exige
    # current_prestador_id setado ANTES de qualquer SELECT/UPDATE, e este é
    # o único jeito seguro de obter esse id a partir de um evento
    # assinado/verificado da própria Stripe).
    sessao = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_id_mensal, "quantity": 1}],
        success_url=f"{base}/app/configuracoes?assinatura=sucesso",
        cancel_url=f"{base}/app/configuracoes?assinatura=cancelado",
        metadata={"prestador_id": str(prestador_id)},
        subscription_data={"metadata": {"prestador_id": str(prestador_id)}},
        api_key=settings.stripe_secret_key,
    )
    return sessao["url"]


def criar_sessao_portal(db: Session, prestador_id: uuid.UUID) -> str:
    """Portal de cobrança da própria Stripe (trocar cartão, cancelar,
    baixar fatura) — exige que o prestador já tenha um Customer (ou seja,
    já passou pelo Checkout ao menos uma vez)."""
    _exigir_stripe_configurado()
    settings = get_settings()
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if assinatura is None or not assinatura.stripe_customer_id:
        raise AssinaturaNaoEncontradaError("Nenhuma assinatura Stripe iniciada ainda — assine primeiro.")
    sessao = stripe.billing_portal.Session.create(
        customer=assinatura.stripe_customer_id,
        return_url=f"{settings.app_base_url}/app/configuracoes",
        api_key=settings.stripe_secret_key,
    )
    return sessao["url"]


def _resolver_prestador_id_do_evento(obj: dict) -> uuid.UUID | None:
    """A ÚNICA fonte confiável de "a quem pertence este evento": o
    `metadata.prestador_id` que a GENTE gravou no Customer/Session/
    Subscription na hora do Checkout (ver criar_sessao_checkout). Nunca
    deriva prestador_id de stripe_customer_id/subscription_id via SELECT
    direto — RLS de `assinatura` (FORCE ROW LEVEL SECURITY) faz qualquer
    SELECT sem `app.current_prestador_id` já setado devolver vazio sempre,
    mesmo que a linha exista (mesma armadilha documentada em
    app/services/cadastro.py pro INSERT em `prestador`)."""
    bruto = (obj.get("metadata") or {}).get("prestador_id")
    if not bruto:
        return None
    try:
        return uuid.UUID(bruto)
    except ValueError:
        return None


def processar_webhook(db: Session, payload: bytes, assinatura_header: str) -> str | None:
    """Verifica a assinatura do payload (`stripe_webhook_secret`) e
    sincroniza o `status`/`stripe_subscription_id` da Assinatura
    correspondente. Devolve o tipo de evento tratado, ou None se o evento
    não é um dos que a gente escuta (a Stripe manda MUITOS tipos de evento
    — ignorar os que não conhecemos é o comportamento certo, não um erro).

    Toda ramificação abaixo chama `definir_prestador_atual` ANTES de
    tocar em `assinatura` — ver `_resolver_prestador_id_do_evento`.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise BillingNaoConfiguradoError("STRIPE_WEBHOOK_SECRET não configurada.")
    try:
        event = stripe.Webhook.construct_event(payload, assinatura_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise WebhookInvalidoError("Payload ou assinatura de webhook inválidos.") from exc

    tipo = event["type"]
    obj = event["data"]["object"]

    if tipo not in (
        "checkout.session.completed",
        "customer.subscription.updated",
        "customer.subscription.created",
        "customer.subscription.deleted",
    ):
        return None

    prestador_id = _resolver_prestador_id_do_evento(obj)
    if prestador_id is None:
        logger.warning("Evento %s sem metadata.prestador_id — ignorado (assinatura não criada por criar_sessao_checkout?).", tipo)
        return tipo

    definir_prestador_atual(db, prestador_id)
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if assinatura is None:
        logger.warning("Evento %s pra prestador_id %s sem Assinatura correspondente.", tipo, prestador_id)
        return tipo

    if tipo == "checkout.session.completed":
        assinatura.stripe_subscription_id = obj.get("subscription")
        assinatura.status = "ativa"
    elif tipo in ("customer.subscription.updated", "customer.subscription.created"):
        assinatura.stripe_subscription_id = obj.get("id")
        novo_status = _STRIPE_STATUS_PARA_NOSSO.get(obj.get("status"))
        if novo_status is not None:
            assinatura.status = novo_status
    elif tipo == "customer.subscription.deleted":
        assinatura.status = "cancelada"

    db.flush()
    return tipo
