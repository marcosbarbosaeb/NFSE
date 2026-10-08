"""Uso e limite de notas do plano (07/10/2026).

Decisões do Marcos:
- Conta nota AUTORIZADA no mês, por CNPJ. Cancelada, recusada, de teste
  (homologação) e importada não contam.
- Aos 80% do limite a Ana avisa e sugere o plano de cima.
- No limite: quem assina pode continuar pagando R$ 0,80 por nota (aceita uma
  vez; entra na fatura seguinte). Sem aceitar — ou no teste grátis, que não
  tem cartão — a emissão para até subir de plano.
- Teste grátis: 150 notas, com o Financeiro liberado.

O limite só TRAVA quando `BLOQUEIO_ATIVO` está ligado (a mesma chave do
bloqueio de quem não tem assinatura): antes de a cobrança estar no ar a tela
mostra o uso, mas ninguém é parado.
"""
from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Assinatura, Emissao
from app.services import billing
from app.tempo import hoje as hoje_br

logger = logging.getLogger("agenteana.planos")

AVISO_EM = 0.8  # a partir de 80% do limite


class LimiteDeNotasError(Exception):
    """A empresa chegou no limite de notas do plano e não pode (ou não
    aceitou) pagar por nota a mais."""


def _competencia(hoje: datetime.date) -> str:
    return f"{hoje.year:04d}-{hoje.month:02d}"


def notas_do_mes(db: Session, prestador_id: uuid.UUID, hoje: datetime.date | None = None) -> int:
    """Notas autorizadas no mês (horário de Brasília). No ambiente de teste
    da plataforma as de homologação contam — senão não dava pra testar."""
    hoje = hoje or hoje_br()
    inicio = datetime.datetime(hoje.year, hoje.month, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    consulta = db.query(func.count(Emissao.id)).filter(
        Emissao.prestador_id == prestador_id, Emissao.estado == "confirmado", Emissao.origem != "importada",
        Emissao.criado_em >= inicio,
    )
    if not get_settings().ambiente_teste:
        consulta = consulta.filter(func.coalesce(Emissao.tomador_snapshot["tpAmb"].astext, "1") != "2")
    return int(consulta.scalar() or 0)


def limite_da_assinatura(assinatura: Assinatura | None) -> tuple[int | None, str | None]:
    """(limite de notas no mês, plano que define esse limite). None = sem limite."""
    situacao = billing.situacao_do_acesso(assinatura)
    if assinatura is None or situacao["motivo"] in ("cortesia", "liberacao"):
        return None, None  # cortesia e liberação da Gestão (personalizado): sem limite
    if situacao["motivo"] in ("assinatura", "pagamento_pendente") and assinatura.plano in billing.PLANOS:
        return billing.PLANOS[assinatura.plano]["limite"], assinatura.plano
    # teste grátis (em dia ou vencido): o limite do teste
    return get_settings().trial_limite_notas, None


def _proximo_plano(plano: str | None, usadas: int) -> dict | None:
    """O primeiro plano acima do atual que comporta o que a empresa já usa."""
    escada = billing.ESCADA_DE_NOTAS
    inicio = escada.index(plano) + 1 if plano in escada else 0
    for chave in escada[inicio:]:
        info = billing.PLANOS[chave]
        if info["limite"] is None or info["limite"] > usadas:
            return {"id": chave, "nome": info["nome"], "limite_notas": info["limite"], "valor": info["preco"]}
    return None


def uso(db: Session, prestador_id: uuid.UUID, hoje: datetime.date | None = None) -> dict:
    """O retrato do mês: quantas notas, o limite, o aviso e o que dá pra fazer."""
    hoje = hoje or hoje_br()
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    limite, plano = limite_da_assinatura(assinatura)
    if not billing.cobranca_ativa():
        # Fase sem cobrança: não há plano pra subir nem nota excedente pra
        # pagar — o limite não vale (nem aviso), quem controla é a Gestão.
        limite, plano = None, None
    usadas = notas_do_mes(db, prestador_id, hoje)
    preco = get_settings().nota_excedente_centavos / 100
    paga = bool(assinatura and assinatura.stripe_subscription_id and assinatura.status in ("ativa", "inadimplente"))
    aceito = bool(paga and assinatura.excedente_aceito_em)
    excedentes = max(0, usadas - limite) if limite is not None else 0
    aviso = None
    if limite is not None and limite > 0:
        if usadas >= limite:
            aviso = "limite"
        elif usadas >= limite * AVISO_EM:
            aviso = "perto"
    return {
        "competencia": _competencia(hoje), "usadas": usadas, "limite": limite,
        "restantes": None if limite is None else max(0, limite - usadas),
        "pct": None if not limite else min(999, round(usadas * 100 / limite)),
        "aviso": aviso, "plano": plano, "plano_nome": billing.PLANOS[plano]["nome"] if plano else None,
        "em_teste": plano is None and limite is not None,
        "proximo_plano": _proximo_plano(plano, usadas) if limite is not None else None,
        "excedente_preco": preco, "excedente_pode": paga, "excedente_aceito": aceito,
        "excedentes": excedentes, "excedente_valor": round(excedentes * preco, 2) if aceito else 0,
        # o limite só trava com a cobrança no ar
        "trava_ligada": get_settings().bloqueio_ativo,
        "travado": get_settings().bloqueio_ativo and aviso == "limite" and not aceito,
    }


def _mensagem(u: dict, quantidade: int) -> str:
    limite, usadas = u["limite"], u["usadas"]
    if limite == 0:
        return "O plano desta empresa não inclui emissão de notas. Escolha um plano de notas em Minha conta › Assinatura."
    quem = "do teste grátis" if u["em_teste"] else f"do plano {u['plano_nome']}"
    if quantidade > 1:
        inicio = f"Esse lote tem {quantidade} notas, mas só cabem mais {u['restantes']} no limite {quem} ({usadas} de {limite} este mês)."
    else:
        inicio = f"Você chegou no limite {quem}: {usadas} de {limite} notas este mês."
    proximo = u["proximo_plano"]
    subir = f" O plano {proximo['nome']} comporta {'notas sem limite' if proximo['limite_notas'] is None else str(proximo['limite_notas']) + ' notas por mês'}." if proximo else ""
    if u["em_teste"]:
        return f"{inicio} Pra continuar emitindo, assine um plano em Minha conta › Assinatura.{subir}"
    if u["excedente_pode"]:
        preco = f"{u['excedente_preco']:.2f}".replace(".", ",")
        return f"{inicio} Pra continuar, suba de plano ou aceite pagar R$ {preco} por nota a mais, em Minha conta › Assinatura.{subir}"
    return f"{inicio} Pra continuar emitindo, suba de plano em Minha conta › Assinatura.{subir}"


def conferir(db: Session, prestador_id: uuid.UUID, quantidade: int = 1) -> None:
    """Levanta `LimiteDeNotasError` se mandar `quantidade` notas à prefeitura
    agora estouraria o limite sem cobertura. Não faz nada com a trava desligada."""
    if not get_settings().bloqueio_ativo:
        return
    u = uso(db, prestador_id)
    if u["limite"] is None or u["excedente_aceito"]:
        return
    if u["usadas"] + max(1, quantidade) > u["limite"]:
        raise LimiteDeNotasError(_mensagem(u, quantidade))


def aceitar_excedente(db: Session, prestador_id: uuid.UUID, aceitar: bool) -> dict:
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if aceitar:
        if assinatura is None or not assinatura.stripe_subscription_id or assinatura.status not in ("ativa", "inadimplente"):
            raise LimiteDeNotasError("Pra pagar por nota a mais é preciso ter um plano assinado. Assine em Minha conta › Assinatura.")
        assinatura.excedente_aceito_em = datetime.datetime.now(datetime.timezone.utc)
    elif assinatura is not None:
        assinatura.excedente_aceito_em = None
    db.flush()
    return uso(db, prestador_id)


def cobrar_excedente(db: Session, prestador_id: uuid.UUID) -> int:
    """Depois de uma nota autorizada: manda pra Stripe as notas acima do
    limite que ainda não foram cobradas (um item pendente no cliente, que
    entra na próxima fatura). Devolve quantas mandou agora. Nunca derruba a
    emissão: falha da Stripe fica no log e a próxima nota tenta de novo."""
    u = uso(db, prestador_id)
    if not u["excedente_aceito"] or u["excedentes"] <= 0:
        return 0
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    chave = get_settings().stripe_secret_key
    if assinatura is None or not assinatura.stripe_customer_id or not chave:
        return 0
    registro = dict((assinatura.excedente_cobranca or {}).get(u["competencia"]) or {})
    novas = u["excedentes"] - int(registro.get("cobradas") or 0)
    if novas <= 0:
        return 0
    centavos = get_settings().nota_excedente_centavos
    mes = f"{u['competencia'][5:]}/{u['competencia'][:4]}"
    import stripe

    try:
        item_qtd = int(registro.get("item_qtd") or 0)
        atualizado = False
        if registro.get("item"):
            try:  # o item ainda está pendente: só aumenta
                total = item_qtd + novas
                stripe.InvoiceItem.modify(
                    registro["item"], amount=total * centavos,
                    description=f"{total} nota{'s' if total != 1 else ''} acima do limite do plano ({mes})", api_key=chave,
                )
                registro["item_qtd"] = total
                atualizado = True
            except Exception:  # noqa: BLE001 — já entrou numa fatura: abre outro
                atualizado = False
        if not atualizado:
            item = stripe.InvoiceItem.create(
                customer=assinatura.stripe_customer_id, currency="brl", amount=novas * centavos,
                description=f"{novas} nota{'s' if novas != 1 else ''} acima do limite do plano ({mes})",
                metadata={"prestador_id": str(prestador_id), "competencia": u["competencia"]}, api_key=chave,
            )
            registro["item"], registro["item_qtd"] = item["id"], novas
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao cobrar %s nota(s) excedente(s) do prestador %s", novas, prestador_id)
        return 0
    registro["cobradas"] = int(registro.get("cobradas") or 0) + novas
    assinatura.excedente_cobranca = {**(assinatura.excedente_cobranca or {}), u["competencia"]: registro}
    db.flush()
    return novas
