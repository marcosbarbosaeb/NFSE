"""Listas do financeiro: recebimentos e despesas (saíram de
app/services/listagens.py em 05/10/2026, na separação dos módulos)."""
import datetime
import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Despesa, PagamentoRecebido, PrestadorTomador


def listar_pagamentos(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    por_recebimento: bool = False,
) -> list[dict]:
    """`por_recebimento`: filtra o ano pela data em que o dinheiro caiu
    (sem data, pela competência) — é assim que o Financeiro soma; antes uma
    nota de dezembro paga em janeiro sumia dos dois anos.

    `PagamentoRecebido` não tem relationship pro vínculo (ver
    app/models.py) — join explícito com `PrestadorTomador` só pra buscar o
    apelido de exibição."""
    query = (
        db.query(PagamentoRecebido, PrestadorTomador.apelido, PrestadorTomador.sem_nota)
        .join(PrestadorTomador, PagamentoRecebido.prestador_tomador_id == PrestadorTomador.id)
        # Baixa de conciliação (histórico, sem valor) não é recebimento.
        .filter(PagamentoRecebido.origem != "conciliacao")
        .order_by(PagamentoRecebido.criado_em.desc())
    )
    if ano and por_recebimento:
        inicio, fim = datetime.date(int(ano), 1, 1), datetime.date(int(ano), 12, 31)
        query = query.filter(
            or_(
                PagamentoRecebido.data_recebimento.between(inicio, fim),
                and_(PagamentoRecebido.data_recebimento.is_(None), PagamentoRecebido.competencia.like(f"{ano}-%")),
            )
        )
    elif ano:
        query = query.filter(PagamentoRecebido.competencia.like(f"{ano}-%"))
    if vinculo_id:
        query = query.filter(PagamentoRecebido.prestador_tomador_id == vinculo_id)

    return [
        {
            "id": p.id,
            "apelido": apelido,
            "competencia": p.competencia,
            "valor": float(p.valor),
            "data_recebimento": p.data_recebimento,
            "vinculo_id": p.prestador_tomador_id,
            "emissao_id": p.emissao_id,
            "pode_gerar_nota": p.emissao_id is None and not p.mes_inteiro and not sem_nota,
        }
        for p, apelido, sem_nota in query.all()
    ]


def listar_despesas(db: Session, *, ano: str | None = None) -> list[dict]:
    query = db.query(Despesa).order_by(Despesa.criado_em.desc())
    if ano:
        query = query.filter(Despesa.competencia.like(f"{ano}-%"))
    from app.financeiro.contas_mes import _linha_despesa

    return [_linha_despesa(d) for d in query.all()]
