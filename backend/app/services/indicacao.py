"""Programa de indicação — pedido do Marcos (28/09/2026): "quero criar um
serviço de afiliado", regra confirmada: **10% de desconto pra cada indicado
com assinatura ativa, até 100%** (10 indicados ativos = mensalidade zerada),
cobrado pelo Stripe.

Como funciona:
- Todo prestador tem um código (`codigo_indicacao`, criado na primeira vez
  que ele abre a tela de indicação). O link é `/cadastro?ref=CODIGO`.
- Quem se cadastra com o código vira uma linha em `indicacao` (indicador ->
  indicado), com o status da assinatura do indicado.
- O webhook do Stripe (app/services/billing.py) atualiza esse status quando
  a assinatura do indicado muda e recalcula o desconto do indicador.
- O desconto vira um cupom do Stripe (`indicacao-10` ... `indicacao-100`,
  duração "forever") aplicado na assinatura do indicador; quando o número de
  indicados ativos muda, o cupom é trocado (ou tirado). Quem ainda não
  assinou leva o cupom já no Checkout.

RLS: `codigo_indicacao` não tem RLS (só código -> id). `indicacao` é visível
pro indicador e pro indicado. Pra mexer na assinatura do indicador a partir
do evento do indicado, a sessão troca o `app.current_prestador_id` pro
indicador e depois volta.
"""
import logging
import secrets
import uuid

import stripe
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import Assinatura, CodigoIndicacao, Indicacao

logger = logging.getLogger("agenteana.indicacao")

PCT_POR_INDICADO = 10
PCT_MAXIMO = 100
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O, 1/I


def desconto_para(ativos: int) -> int:
    return min(PCT_MAXIMO, PCT_POR_INDICADO * max(0, ativos))


def _novo_codigo() -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(7))


def normalizar_codigo(codigo: str | None) -> str:
    return "".join(c for c in (codigo or "").upper() if c.isalnum())[:20]


def codigo_do_prestador(db: Session, prestador_id: uuid.UUID) -> str:
    existente = db.query(CodigoIndicacao).filter_by(prestador_id=prestador_id).one_or_none()
    if existente is not None:
        return existente.codigo
    for _ in range(10):
        codigo = _novo_codigo()
        if db.get(CodigoIndicacao, codigo) is not None:
            continue
        try:
            with db.begin_nested():
                db.add(CodigoIndicacao(codigo=codigo, prestador_id=prestador_id))
                db.flush()
            return codigo
        except IntegrityError:
            # Duas abas abrindo a tela ao mesmo tempo: a outra já criou.
            existente = db.query(CodigoIndicacao).filter_by(prestador_id=prestador_id).one_or_none()
            if existente is not None:
                return existente.codigo
    raise RuntimeError("Não foi possível gerar um código de indicação único.")


def registrar_indicacao(db: Session, codigo: str | None, indicado_id: uuid.UUID, indicado_nome: str | None) -> bool:
    """Chamado no cadastro, com a sessão já no contexto do indicado. Código
    desconhecido ou o próprio prestador: ignora em silêncio (cadastro nunca
    falha por causa de um link de indicação)."""
    codigo = normalizar_codigo(codigo)
    if not codigo:
        return False
    dono = db.get(CodigoIndicacao, codigo)
    if dono is None or dono.prestador_id == indicado_id:
        return False
    db.add(Indicacao(indicado_id=indicado_id, indicador_id=dono.prestador_id, indicado_nome=(indicado_nome or "")[:200], status="trial"))
    db.flush()
    return True


def _contexto_atual(db: Session) -> str | None:
    return db.execute(text("SELECT current_setting('app.current_prestador_id', true)")).scalar() or None


def ativos_do_indicador(db: Session, indicador_id: uuid.UUID) -> int:
    return db.query(Indicacao).filter_by(indicador_id=indicador_id, status="ativa").count()


# Chamadas ao Stripe com prazo curto (o padrão da biblioteca espera até 80 s).
stripe.max_network_retries = 1
try:
    stripe.default_http_client = stripe.RequestsClient(timeout=15)
except Exception:  # noqa: BLE001 — versão da lib sem RequestsClient: fica o padrão
    pass


def _stripe_configurado() -> bool:
    return bool(get_settings().stripe_secret_key)


def cupom_para(pct: int) -> str | None:
    """Cria (se ainda não existe) e devolve o id do cupom do Stripe."""
    if pct <= 0:
        return None
    cupom_id = f"indicacao-{pct}"
    api_key = get_settings().stripe_secret_key
    try:
        stripe.Coupon.retrieve(cupom_id, api_key=api_key)
    except stripe.InvalidRequestError:
        stripe.Coupon.create(
            id=cupom_id, percent_off=pct, duration="forever",
            name=f"Indicação — {pct}% de desconto", api_key=api_key,
        )
    return cupom_id


def sincronizar_desconto(db: Session, indicador_id: uuid.UUID) -> int:
    """Recalcula o desconto do indicador e, se mudou e ele já tem assinatura
    no Stripe, troca o cupom. Devolve o % calculado. Nunca levanta erro do
    Stripe pra quem chamou (webhook): só registra no log."""
    anterior = _contexto_atual(db)
    try:
        definir_prestador_atual(db, indicador_id)
        pct = desconto_para(ativos_do_indicador(db, indicador_id))
        assinatura = db.query(Assinatura).filter_by(prestador_id=indicador_id).one_or_none()
        if assinatura is None or assinatura.desconto_indicacao_pct == pct:
            return pct
        if assinatura.stripe_subscription_id and _stripe_configurado():
            try:
                cupom = cupom_para(pct)
                stripe.Subscription.modify(
                    assinatura.stripe_subscription_id,
                    discounts=[{"coupon": cupom}] if cupom else "",
                    api_key=get_settings().stripe_secret_key,
                )
            except stripe.StripeError:
                logger.exception("Falha ao aplicar desconto de indicação (%s%%) no prestador %s", pct, indicador_id)
                return pct
        assinatura.desconto_indicacao_pct = pct
        db.flush()
        return pct
    finally:
        if anterior:
            definir_prestador_atual(db, uuid.UUID(anterior))


def atualizar_status_indicado(db: Session, indicado_id: uuid.UUID, status: str) -> None:
    """Chamado pelo webhook no contexto do indicado: guarda o novo status e
    recalcula o desconto de quem indicou."""
    indicacao = db.get(Indicacao, indicado_id)
    if indicacao is None or indicacao.status == status:
        return
    indicacao.status = status
    db.flush()
    sincronizar_desconto(db, indicacao.indicador_id)


def _nome_curto(nome: str | None) -> str:
    partes = (nome or "").split()
    if not partes:
        return "Conta indicada"
    return partes[0].title() + (f" {partes[1][0].upper()}." if len(partes) > 1 else "")


def resumo(db: Session, prestador_id: uuid.UUID) -> dict:
    codigo = codigo_do_prestador(db, prestador_id)
    indicados = (
        db.query(Indicacao).filter_by(indicador_id=prestador_id).order_by(Indicacao.criado_em.desc()).all()
    )
    ativos = sum(1 for i in indicados if i.status == "ativa")
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    settings = get_settings()
    return {
        "codigo": codigo,
        "link": f"{settings.app_base_url}/cadastro?ref={codigo}",
        "ativos": ativos,
        "total": len(indicados),
        "desconto_pct": desconto_para(ativos),
        "desconto_aplicado_pct": assinatura.desconto_indicacao_pct if assinatura else 0,
        "pct_por_indicado": PCT_POR_INDICADO,
        "pct_maximo": PCT_MAXIMO,
        "cobranca_ativa": _stripe_configurado(),
        "indicados": [
            {"nome": _nome_curto(i.indicado_nome), "status": i.status, "desde": i.criado_em.date()} for i in indicados
        ],
    }


def desconto_no_checkout(db: Session, prestador_id: uuid.UUID) -> list[dict] | None:
    """`discounts` pro Checkout de quem ainda vai assinar e já tem indicados."""
    pct = desconto_para(ativos_do_indicador(db, prestador_id))
    cupom = cupom_para(pct) if pct and _stripe_configurado() else None
    return [{"coupon": cupom}] if cupom else None
