"""
Listagens por linha (com id) — Marco 14 do plano: as telas novas de
NFS-e/Recebimentos/Despesas precisam de uma lista navegável (uma linha por
nota/pagamento/despesa, com id pra abrir o detalhe), diferente de
app/services/painel_status.py (agrega o ano inteiro, fornecedor×mês, sem
id nenhum — bom pro resumo, ruim pra abrir um registro específico) e de
app/services/dashboard.py (só a competência corrente).

Mesma disciplina de RLS das demais consultas: toda query aqui presume que
`definir_prestador_atual` já rodou na sessão (ver db_sessao em app/main.py)
— os filtros de prestador vêm de graça da RLS, nunca de um WHERE explícito
nestas tabelas.
"""
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models import Despesa, Emissao, PagamentoRecebido, PrestadorTomador
from app.services.dashboard import ESTADO_NFSE_LABEL


def listar_emissoes(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[dict]:
    query = (
        db.query(Emissao)
        .options(joinedload(Emissao.vinculo).joinedload(PrestadorTomador.tomador))
        # Desempate por n_dps (sequencial por prestador+série, ver
        # motor_emissao._proximo_ndps) além de criado_em: dentro de uma
        # MESMA transação — o caso comum é a importação de CSV, que gera
        # várias emissões em lote — `criado_em` (server_default=now())
        # fica CONGELADO no início da transação no Postgres, então todas as
        # linhas do lote nascem com o mesmo timestamp; sem o desempate, a
        # ordem dentro do lote ficaria arbitrária.
        .order_by(Emissao.criado_em.desc(), Emissao.n_dps.desc())
    )
    if ano:
        query = query.filter(Emissao.competencia.like(f"{ano}-%"))
    if vinculo_id:
        query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    if estado:
        query = query.filter(Emissao.estado == estado)

    return [
        {
            "id": e.id,
            "vinculo_id": e.prestador_tomador_id,
            "apelido": e.vinculo.apelido,
            "tomador_razao_social": e.vinculo.tomador.razao_social,
            "competencia": e.competencia,
            "valor": float(e.valor),
            "serie": e.serie,
            "n_dps": e.n_dps,
            "estado": e.estado,
            "estado_label": ESTADO_NFSE_LABEL.get(e.estado, e.estado),
            "criado_em": e.criado_em,
        }
        for e in query.all()
    ]


def listar_pagamentos(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
) -> list[dict]:
    """`PagamentoRecebido` não tem relationship pro vínculo (ver
    app/models.py) — join explícito com `PrestadorTomador` só pra buscar o
    apelido de exibição."""
    query = (
        db.query(PagamentoRecebido, PrestadorTomador.apelido)
        .join(PrestadorTomador, PagamentoRecebido.prestador_tomador_id == PrestadorTomador.id)
        .order_by(PagamentoRecebido.criado_em.desc())
    )
    if ano:
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
        }
        for p, apelido in query.all()
    ]


def listar_despesas(db: Session, *, ano: str | None = None) -> list[dict]:
    query = db.query(Despesa).order_by(Despesa.criado_em.desc())
    if ano:
        query = query.filter(Despesa.competencia.like(f"{ano}-%"))
    return [
        {"id": d.id, "categoria": d.categoria, "competencia": d.competencia, "valor": float(d.valor)}
        for d in query.all()
    ]
