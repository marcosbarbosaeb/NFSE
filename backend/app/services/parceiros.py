"""Parceiras de indicação com comissão (06/10/2026).

Pedido do Marcos: "tenho algumas pessoas que poderiam ser parceiras na
indicação (uma contadora e uma economista)... pagar uma porcentagem de
cada assinatura ativa pra essas pessoas". Regras escolhidas por ele:

- a parceira recebe X% do que cada indicado PAGA, enquanto a assinatura
  dele estiver ativa (X é de cada parceira);
- ela não precisa ser cliente: não tem empresa nem login — acompanha por
  um link secreto (`token_painel`), que a administração pode trocar;
- o indicado ganha um desconto só na PRIMEIRA mensalidade (cupom "once").

Como funciona:
- cada parceira tem um código; o link é o mesmo do "Indique e ganhe":
  `/cadastro?ref=CODIGO` (os códigos não se repetem entre os dois programas);
- quem se cadastra com o código vira uma linha em `indicacao_parceiro`;
- o webhook do Stripe atualiza o status do indicado e, a cada fatura paga
  (`invoice.paid`), grava uma `comissao_parceiro` (uma por fatura — repetir
  o evento não duplica);
- o repasse do dinheiro é feito por fora (Pix): a administração vê o que
  deve por mês e marca como pago.

Tabelas sem RLS (são da plataforma): o acesso é controlado nas rotas.
"""
from __future__ import annotations

import datetime
import logging
import secrets
import uuid
from decimal import ROUND_HALF_UP, Decimal

import stripe
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CodigoIndicacao, ComissaoParceiro, IndicacaoParceiro, Parceiro
from app.tempo import hoje as hoje_br

logger = logging.getLogger("agenteana.parceiros")

_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O, 1/I
_CENTAVO = Decimal("0.01")


class ParceiroInvalidoError(ValueError):
    pass


def _novo_codigo(db: Session) -> str:
    for _ in range(20):
        codigo = "".join(secrets.choice(_ALFABETO) for _ in range(7))
        if db.get(CodigoIndicacao, codigo) is None and db.query(Parceiro.id).filter_by(codigo=codigo).first() is None:
            return codigo
    raise RuntimeError("Não foi possível gerar um código único.")


def _pct(valor, nome: str, maximo: int = 100) -> Decimal:
    try:
        pct = Decimal(str(valor))
    except Exception as exc:  # noqa: BLE001
        raise ParceiroInvalidoError(f"{nome}: informe um número.") from exc
    if pct < 0 or pct > maximo:
        raise ParceiroInvalidoError(f"{nome}: tem que ficar entre 0 e {maximo}%.")
    return pct


def criar(db: Session, nome: str, email: str | None, comissao_pct, desconto_1_mes_pct=0) -> Parceiro:
    nome = (nome or "").strip()
    if len(nome) < 2:
        raise ParceiroInvalidoError("Escreva o nome da parceira.")
    parceiro = Parceiro(
        id=uuid.uuid4(), nome=nome[:120], email=(email or "").strip().lower()[:200] or None,
        codigo=_novo_codigo(db), token_painel=secrets.token_urlsafe(32),
        comissao_pct=_pct(comissao_pct, "Comissão"), desconto_1_mes_pct=int(_pct(desconto_1_mes_pct, "Desconto do 1º mês")),
        ativo=True,
    )
    db.add(parceiro)
    db.flush()
    return parceiro


def atualizar(db: Session, parceiro: Parceiro, campos: dict) -> Parceiro:
    """Muda nome, e-mail, percentuais ou ativa/desativa. Percentual novo só
    vale pras comissões que nascerem depois (as antigas guardam o delas)."""
    if campos.get("nome") is not None:
        nome = campos["nome"].strip()
        if len(nome) < 2:
            raise ParceiroInvalidoError("Escreva o nome da parceira.")
        parceiro.nome = nome[:120]
    if "email" in campos:
        parceiro.email = (campos["email"] or "").strip().lower()[:200] or None
    if campos.get("comissao_pct") is not None:
        parceiro.comissao_pct = _pct(campos["comissao_pct"], "Comissão")
    if campos.get("desconto_1_mes_pct") is not None:
        parceiro.desconto_1_mes_pct = int(_pct(campos["desconto_1_mes_pct"], "Desconto do 1º mês"))
    if campos.get("ativo") is not None:
        parceiro.ativo = bool(campos["ativo"])
    db.flush()
    return parceiro


def trocar_link_do_painel(db: Session, parceiro: Parceiro) -> Parceiro:
    """O link antigo para de funcionar na hora (vazou, mudou de pessoa...)."""
    parceiro.token_painel = secrets.token_urlsafe(32)
    db.flush()
    return parceiro


# --- cadastro do indicado e status da assinatura ------------------------------

def registrar_indicacao(db: Session, codigo: str, indicado_id: uuid.UUID, indicado_nome: str | None) -> bool:
    """Chamado no cadastro quando o código não é de um cliente. Parceira
    desativada ou código desconhecido: ignora em silêncio."""
    parceiro = db.query(Parceiro).filter_by(codigo=codigo, ativo=True).one_or_none()
    if parceiro is None or db.get(IndicacaoParceiro, indicado_id) is not None:
        return False
    db.add(IndicacaoParceiro(indicado_id=indicado_id, parceiro_id=parceiro.id, indicado_nome=(indicado_nome or "")[:200], status="trial"))
    db.flush()
    return True


def atualizar_status_indicado(db: Session, indicado_id: uuid.UUID, status: str) -> None:
    indicacao = db.get(IndicacaoParceiro, indicado_id)
    if indicacao is not None and indicacao.status != status:
        indicacao.status = status
        db.flush()


def parceiro_do_indicado(db: Session, indicado_id: uuid.UUID) -> Parceiro | None:
    indicacao = db.get(IndicacaoParceiro, indicado_id)
    return db.get(Parceiro, indicacao.parceiro_id) if indicacao is not None else None


def desconto_no_checkout(db: Session, prestador_id: uuid.UUID) -> list[dict] | None:
    """`discounts` do Checkout pra quem veio por uma parceira: X% só na
    primeira mensalidade (cupom do Stripe com duração "once")."""
    parceiro = parceiro_do_indicado(db, prestador_id)
    pct = parceiro.desconto_1_mes_pct if parceiro is not None else 0
    api_key = get_settings().stripe_secret_key
    if not pct or not api_key:
        return None
    # Já pagou alguma mensalidade: o desconto era só da primeira.
    if db.query(ComissaoParceiro.id).filter_by(indicado_id=prestador_id).first() is not None:
        return None
    cupom_id = f"parceira-1mes-{pct}"
    try:
        stripe.Coupon.retrieve(cupom_id, api_key=api_key)
    except stripe.InvalidRequestError:
        stripe.Coupon.create(
            id=cupom_id, percent_off=pct, duration="once",
            name=f"Indicação de parceira — {pct}% na 1ª mensalidade", api_key=api_key,
        )
    return [{"coupon": cupom_id}]


# --- comissão ------------------------------------------------------------------

def registrar_pagamento(
    db: Session, indicado_id: uuid.UUID, fatura_id: str, valor_pago: Decimal, quando: datetime.date | None = None,
) -> ComissaoParceiro | None:
    """Uma mensalidade paga por um indicado. Devolve a comissão criada, ou
    None (não veio por parceira, fatura zerada, já registrada)."""
    if not fatura_id or valor_pago is None or valor_pago <= 0:
        return None
    indicacao = db.get(IndicacaoParceiro, indicado_id)
    if indicacao is None:
        return None
    if db.query(ComissaoParceiro.id).filter_by(stripe_invoice_id=fatura_id).first() is not None:
        return None  # o Stripe repete eventos: uma comissão por fatura
    parceiro = db.get(Parceiro, indicacao.parceiro_id)
    # Parceira desativada só para de receber NOVOS cadastros: quem ela já
    # trouxe continua rendendo comissão (pra encerrar, ponha a comissão em 0%).
    if parceiro is None or parceiro.comissao_pct <= 0:
        return None
    quando = quando or hoje_br()
    valor = (valor_pago * parceiro.comissao_pct / Decimal(100)).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    comissao = ComissaoParceiro(
        id=uuid.uuid4(), parceiro_id=parceiro.id, indicado_id=indicado_id, indicado_nome=indicacao.indicado_nome,
        stripe_invoice_id=fatura_id[:80], competencia=f"{quando.year:04d}-{quando.month:02d}",
        valor_pago=valor_pago.quantize(_CENTAVO), comissao_pct=parceiro.comissao_pct, valor=valor,
    )
    db.add(comissao)
    db.flush()
    return comissao


def marcar_pago(db: Session, parceiro: Parceiro, competencia: str, pago: bool = True) -> int:
    """Repasse feito (por fora, via Pix): marca as comissões do mês."""
    comissoes = db.query(ComissaoParceiro).filter_by(parceiro_id=parceiro.id, competencia=competencia)
    comissoes = comissoes.filter(ComissaoParceiro.pago_em.is_(None) if pago else ComissaoParceiro.pago_em.isnot(None)).all()
    for c in comissoes:
        c.pago_em = hoje_br() if pago else None
    db.flush()
    return len(comissoes)


# --- o que as telas mostram -----------------------------------------------------

def _nome_curto(nome: str | None) -> str:
    partes = (nome or "").split()
    if not partes:
        return "Conta indicada"
    return partes[0].title() + (f" {partes[1][0].upper()}." if len(partes) > 1 else "")


def _f(valor) -> float:
    return float(valor or 0)


def _meses(db: Session, parceiro_id: uuid.UUID) -> list[dict]:
    por_mes: dict[str, dict] = {}
    for c in db.query(ComissaoParceiro).filter_by(parceiro_id=parceiro_id).order_by(ComissaoParceiro.competencia.desc()):
        m = por_mes.setdefault(c.competencia, {"competencia": c.competencia, "pagamentos": 0, "base": Decimal(0), "comissao": Decimal(0), "a_pagar": Decimal(0), "pago_em": None})
        m["pagamentos"] += 1
        m["base"] += c.valor_pago
        m["comissao"] += c.valor
        if c.pago_em is None:
            m["a_pagar"] += c.valor
        elif m["pago_em"] is None or c.pago_em > m["pago_em"]:
            m["pago_em"] = c.pago_em
    return [{**m, "base": _f(m["base"]), "comissao": _f(m["comissao"]), "a_pagar": _f(m["a_pagar"])} for m in por_mes.values()]


def _resumo(db: Session, parceiro: Parceiro, *, nomes_inteiros: bool) -> dict:
    indicados = db.query(IndicacaoParceiro).filter_by(parceiro_id=parceiro.id).order_by(IndicacaoParceiro.criado_em.desc()).all()
    meses = _meses(db, parceiro.id)
    base = get_settings().app_base_url
    return {
        "nome": parceiro.nome, "codigo": parceiro.codigo, "link": f"{base}/cadastro?ref={parceiro.codigo}",
        "comissao_pct": _f(parceiro.comissao_pct), "desconto_1_mes_pct": parceiro.desconto_1_mes_pct, "ativo": parceiro.ativo,
        "indicados_total": len(indicados), "indicados_ativos": sum(1 for i in indicados if i.status == "ativa"),
        "total_comissao": round(sum(m["comissao"] for m in meses), 2), "a_receber": round(sum(m["a_pagar"] for m in meses), 2),
        "indicados": [
            {"nome": (i.indicado_nome or "Conta indicada") if nomes_inteiros else _nome_curto(i.indicado_nome), "status": i.status, "desde": i.criado_em.date()}
            for i in indicados
        ],
        "meses": meses,
    }


def painel_publico(db: Session, token: str) -> dict | None:
    """O que a parceira vê pelo link secreto: o link de indicação dela, quem
    indicou (só o primeiro nome) e as comissões, mês a mês."""
    if not token or len(token) < 20:
        return None
    parceiro = db.query(Parceiro).filter_by(token_painel=token).one_or_none()
    if parceiro is None:
        return None
    return _resumo(db, parceiro, nomes_inteiros=False)


def listar(db: Session) -> list[dict]:
    """Pra administração: todas as parceiras, com o link do painel de cada uma."""
    base = get_settings().app_base_url
    return [
        {"id": p.id, "email": p.email, "painel": f"{base}/parceira/{p.token_painel}", "criado_em": p.criado_em, **_resumo(db, p, nomes_inteiros=True)}
        for p in db.query(Parceiro).order_by(Parceiro.criado_em)
    ]
