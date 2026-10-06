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
import math
import logging
import uuid

import stripe
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import Assinatura, Prestador

logger = logging.getLogger("agenteana.billing")

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


# Planos (05/10/2026): cada um libera um conjunto de módulos da empresa.
PLANOS = {
    "emissor": {"nome": "Notas", "modulos": ["emissor"], "descricao": "Emissão de NFS-e, tomadores, envio das notas e calendário."},
    "financeiro": {"nome": "Financeiro", "modulos": ["financeiro"], "descricao": "Recebimentos, contas do mês, conciliação do extrato e resultado."},
    "ambos": {"nome": "Notas + Financeiro", "modulos": ["emissor", "financeiro"], "descricao": "Tudo junto: a nota emitida já vira conta a receber."},
}
_precos_cache: dict[str, tuple[float, dict]] = {}


class PlanoInvalidoError(Exception):
    pass


def preco_do_plano(plano: str) -> str | None:
    """Price ID da Stripe configurado pro plano (None = não está à venda).
    Sem nenhum plano configurado, o preço único antigo vale como "ambos"."""
    s = get_settings()
    proprio = {"emissor": s.stripe_price_id_emissor, "financeiro": s.stripe_price_id_financeiro, "ambos": s.stripe_price_id_ambos}.get(plano)
    if proprio:
        return proprio
    unico = s.stripe_price_id_mensal
    if plano == "ambos" and unico and not unico.startswith("price_placeholder"):
        return unico
    return None


def plano_do_preco(price_id: str | None) -> str | None:
    if not price_id:
        return None
    for plano in PLANOS:
        if preco_do_plano(plano) == price_id:
            return plano
    return None


def _valor_do_preco(price_id: str) -> dict:
    """Valor e moeda direto da Stripe (nada de preço escrito no código),
    guardado em memória por 1 hora. Falha -> {} (a tela mostra sem valor)."""
    import time

    em_cache = _precos_cache.get(price_id)
    if em_cache and time.time() - em_cache[0] < 3600:
        return em_cache[1]
    try:
        preco = stripe.Price.retrieve(price_id, api_key=get_settings().stripe_secret_key)
        dados = {
            "valor": (preco["unit_amount"] or 0) / 100, "moeda": str(preco["currency"]).upper(),
            "intervalo": ((preco.get("recurring") or {}).get("interval")) or "month",
        }
    except Exception:  # noqa: BLE001 — preço indisponível não derruba a tela
        logger.warning("Não consegui ler o preço %s na Stripe", price_id)
        dados = {}
    _precos_cache[price_id] = (time.time(), dados)
    return dados


def listar_planos(plano_atual: str | None = None) -> list[dict]:
    lista = []
    for chave, info in PLANOS.items():
        price_id = preco_do_plano(chave)
        disponivel = bool(price_id) and bool(get_settings().stripe_secret_key)
        lista.append({
            "id": chave, "nome": info["nome"], "descricao": info["descricao"], "modulos": info["modulos"],
            "disponivel": disponivel, "atual": chave == plano_atual,
            **({k: v for k, v in _valor_do_preco(price_id).items()} if disponivel else {}),
        })
    return lista


def aplicar_plano(db: Session, assinatura: Assinatura, plano: str | None) -> None:
    """O plano pago define os módulos da empresa (os dados de um módulo
    desligado ficam guardados e voltam se ele for contratado de novo)."""
    if plano not in PLANOS:
        return
    assinatura.plano = plano
    prestador = db.get(Prestador, assinatura.prestador_id)
    if prestador is not None:
        prestador.modulos = list(PLANOS[plano]["modulos"])
    db.flush()


def modulos_presos_ao_plano(assinatura: Assinatura | None) -> bool:
    """Com assinatura paga em vigor, quem liga/desliga módulo é o plano
    (em teste grátis ou cortesia a pessoa escolhe à vontade)."""
    return bool(assinatura and assinatura.plano and assinatura.stripe_subscription_id and assinatura.status in ("ativa", "inadimplente"))


def trocar_plano(db: Session, prestador_id: uuid.UUID, plano: str) -> Assinatura:
    """Muda o plano de uma assinatura já paga: troca o preço do item na
    Stripe (com acerto proporcional na próxima fatura) e já ajusta os
    módulos — o webhook confirma depois."""
    _exigir_stripe_configurado_para(plano)
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if assinatura is None or not assinatura.stripe_subscription_id:
        raise AssinaturaNaoEncontradaError("Nenhuma assinatura paga ainda — assine o plano primeiro.")
    chave = get_settings().stripe_secret_key
    atual = stripe.Subscription.retrieve(assinatura.stripe_subscription_id, api_key=chave)
    item = atual["items"]["data"][0]
    stripe.Subscription.modify(
        assinatura.stripe_subscription_id,
        items=[{"id": item["id"], "price": preco_do_plano(plano)}],
        proration_behavior="create_prorations",
        metadata={"prestador_id": str(prestador_id), "plano": plano},
        api_key=chave,
    )
    aplicar_plano(db, assinatura, plano)
    return assinatura


def _exigir_stripe_configurado_para(plano: str) -> None:
    if plano not in PLANOS:
        raise PlanoInvalidoError("Plano desconhecido.")
    if not get_settings().stripe_secret_key or not preco_do_plano(plano):
        raise BillingNaoConfiguradoError(
            f"O plano {PLANOS[plano]['nome']} ainda não está à venda (falta configurar o preço dele). Fale com o suporte."
        )


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


def _dias_ate(fim: datetime.datetime, agora: datetime.datetime) -> int:
    """Dias que faltam, arredondando pra cima (falta 1h = "1 dia", igual à tela de Assinatura)."""
    return max(0, math.ceil((fim - agora).total_seconds() / 86400))


def situacao_do_acesso(assinatura: Assinatura | None, agora: datetime.datetime | None = None) -> dict:
    """"Esta empresa pode usar tudo?" e por quê. `motivo`:
    cortesia | assinatura | pagamento_pendente | liberacao | teste (liberados)
    teste_acabou | cancelada | sem_assinatura (não liberados).

    - "pagamento_pendente": o cartão falhou e o Stripe ainda está tentando;
      não trava (quando ele desiste, a assinatura vira "cancelada").
    - "liberacao": a Gestão liberou na mão (`liberado_sempre`/`liberado_ate`).
    Quem decide se o "não liberado" trava de fato é `BLOQUEIO_ATIVO`
    (ver app/services/acesso.py)."""
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    if assinatura is None:
        return {"liberado": False, "motivo": "sem_assinatura", "ate": None, "dias_restantes": None}
    if assinatura.status == "cortesia":
        return {"liberado": True, "motivo": "cortesia", "ate": None, "dias_restantes": None}
    if assinatura.status == "ativa":
        return {"liberado": True, "motivo": "assinatura", "ate": None, "dias_restantes": None}
    if assinatura.status == "inadimplente":
        return {"liberado": True, "motivo": "pagamento_pendente", "ate": None, "dias_restantes": None}
    if assinatura.liberado_sempre:
        return {"liberado": True, "motivo": "liberacao", "ate": None, "dias_restantes": None}
    if assinatura.liberado_ate is not None and assinatura.liberado_ate > agora:
        return {"liberado": True, "motivo": "liberacao", "ate": assinatura.liberado_ate, "dias_restantes": _dias_ate(assinatura.liberado_ate, agora)}
    if assinatura.status == "trial":
        fim = assinatura.trial_termina_em
        if fim is not None and fim > agora:
            return {"liberado": True, "motivo": "teste", "ate": fim, "dias_restantes": _dias_ate(fim, agora)}
        return {"liberado": False, "motivo": "teste_acabou", "ate": fim, "dias_restantes": None}
    return {"liberado": False, "motivo": "cancelada", "ate": None, "dias_restantes": None}


def assinatura_esta_ativa(assinatura: Assinatura | None) -> bool:
    """"Tem acesso liberado?" — ver `situacao_do_acesso`."""
    return situacao_do_acesso(assinatura)["liberado"]


def liberar_acesso(assinatura: Assinatura, *, dias: int | None, sempre: bool, obs: str | None) -> None:
    """Gestão: libera a empresa sem assinatura. `dias` conta de agora."""
    assinatura.liberado_sempre = bool(sempre)
    assinatura.liberado_ate = None if sempre or not dias else datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=dias)
    assinatura.liberado_obs = (obs or "").strip()[:200] or None


def tirar_liberacao(assinatura: Assinatura) -> None:
    assinatura.liberado_sempre = False
    assinatura.liberado_ate = None
    assinatura.liberado_obs = None


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


def criar_sessao_checkout(db: Session, prestador_id: uuid.UUID, email: str, plano: str | None = None) -> str:
    """Cria (ou reaproveita) o Customer da Stripe e devolve a URL de uma
    Checkout Session em modo assinatura. Levanta `BillingNaoConfiguradoError`
    enquanto não houver conta Stripe de verdade (ver docstring do
    módulo). `plano`: emissor | financeiro | ambos (sem ele, o preço único
    antigo, que libera os dois módulos)."""
    if plano is None:
        _exigir_stripe_configurado()
    else:
        _exigir_stripe_configurado_para(plano)
    settings = get_settings()
    price_id = preco_do_plano(plano) if plano else settings.stripe_price_id_mensal
    marcas = {"prestador_id": str(prestador_id), **({"plano": plano} if plano else {})}
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
    # Programa de indicação: quem já tem indicados ativos assina com o
    # desconto aplicado (ver app/services/indicacao.py).
    from app.services.indicacao import desconto_no_checkout

    extras = {}
    descontos = desconto_no_checkout(db, prestador_id)
    if descontos:
        extras["discounts"] = descontos
    sessao = stripe.checkout.Session.create(
        **extras,
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base}/app/conta?aba=assinatura&assinatura=sucesso",
        cancel_url=f"{base}/app/conta?aba=assinatura&assinatura=cancelado",
        metadata=marcas,
        subscription_data={"metadata": marcas},
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
        return_url=f"{settings.app_base_url}/app/conta?aba=assinatura",
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


def _prestador_da_fatura(fatura: dict) -> uuid.UUID | None:
    """O `metadata.prestador_id` que gravamos na assinatura aparece na fatura
    em lugares diferentes conforme a versão da API do Stripe."""
    candidatos = [
        fatura.get("subscription_details") or {},
        ((fatura.get("parent") or {}).get("subscription_details")) or {},
        *(((fatura.get("lines") or {}).get("data")) or []),
        fatura,
    ]
    for candidato in candidatos:
        prestador_id = _resolver_prestador_id_do_evento(candidato)
        if prestador_id is not None:
            return prestador_id
    return None


def _comissao_da_fatura(db: Session, fatura: dict) -> str:
    """Mensalidade paga: se a empresa veio por uma parceira, nasce a comissão
    dela (app/services/parceiros.py). Sem parceira, não faz nada."""
    from decimal import Decimal

    from app.services import parceiros

    prestador_id = _prestador_da_fatura(fatura)
    centavos = fatura.get("amount_paid") or 0
    if prestador_id is not None and centavos > 0:
        parceiros.registrar_pagamento(db, prestador_id, fatura.get("id") or "", Decimal(centavos) / Decimal(100))
    return "invoice.paid"


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

    if tipo == "invoice.paid":
        return _comissao_da_fatura(db, obj)

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

    # Plano: o preço do item da assinatura é a fonte de verdade (cobre a
    # troca feita no portal da Stripe); no checkout, o plano escolhido vem
    # no metadata. Só aplica os módulos com a assinatura em vigor.
    plano = None
    if tipo != "checkout.session.completed":
        itens = ((obj.get("items") or {}).get("data")) or []
        plano = plano_do_preco(((itens[0].get("price") or {}).get("id")) if itens else None)
    plano = plano or (obj.get("metadata") or {}).get("plano")

    if tipo == "checkout.session.completed":
        assinatura.stripe_subscription_id = obj.get("subscription")
        # Boleto/Pix: a sessão "completa" antes do dinheiro cair — só vira
        # ativa quando pago; o customer.subscription.updated confirma depois.
        if obj.get("payment_status") in ("paid", "no_payment_required", None):
            assinatura.status = "ativa"
    elif tipo in ("customer.subscription.updated", "customer.subscription.created"):
        assinatura.stripe_subscription_id = obj.get("id")
        novo_status = _STRIPE_STATUS_PARA_NOSSO.get(obj.get("status"))
        if novo_status is not None:
            assinatura.status = novo_status
    elif tipo == "customer.subscription.deleted":
        assinatura.status = "cancelada"
    if plano in PLANOS and assinatura.status == "ativa" and tipo != "customer.subscription.deleted":
        aplicar_plano(db, assinatura, plano)

    db.flush()
    # Programa de indicação: o status deste prestador conta pro desconto de
    # quem o indicou; e se ele mesmo acabou de assinar, já leva o desconto
    # dos indicados dele.
    from app.services.indicacao import atualizar_status_indicado, sincronizar_desconto

    atualizar_status_indicado(db, prestador_id, assinatura.status)
    from app.services import parceiros

    parceiros.atualizar_status_indicado(db, prestador_id, assinatura.status)
    if assinatura.stripe_subscription_id:
        sincronizar_desconto(db, prestador_id)
    return tipo
