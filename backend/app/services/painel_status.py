"""
Painel de status completo — Marco 8 do plano, item #7 da lista original do
Marcos: "painel de status, seria notas geradas e notas recebidas... igual a
esta planilha" (Controle_CP_2026.xlsx).

A planilha real tem 3 seções, cada uma fornecedor×mês (ou categoria×mês para
despesas) com colunas JAN..DEZ + Total:

    "NF Geradas"        -> aqui: emissao (via motor de emissão, Marco 6/7)
    "Pagamentos recebidos" -> aqui: pagamento_recebido (Marco 8, registro manual)
    "Despesas"          -> aqui: despesa (Marco 8, registro manual, por categoria)

Este módulo só lê e agrega — não muda estado de nada. Toda soma é feita em
Python (não em SQL agregado) de propósito: os volumes aqui são de um
pequeno negócio (dezenas de linhas/mês, não milhões), então a portabilidade
e a leitura simples do código valem mais que uma otimização que não faz
diferença nenhuma nesta escala.
"""
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Despesa, Emissao, PagamentoRecebido
from app.services.vinculos import listar_vinculos_ativos

MESES = [f"{m:02d}" for m in range(1, 13)]


def _linha_mensal(rotulo: str, somas_por_mes: dict[str, Decimal]) -> dict:
    meses = [float(somas_por_mes.get(mes, 0)) for mes in MESES]
    return {"rotulo": rotulo, "meses": meses, "total": sum(meses)}


def _agrupar_por_mes(linhas: list[tuple[str, Decimal]]) -> dict[str, Decimal]:
    """`linhas` é uma lista de (competencia 'AAAA-MM', valor) — devolve
    {mes 'MM': soma}."""
    somas: dict[str, Decimal] = {}
    for competencia, valor in linhas:
        mes = competencia[5:7]
        somas[mes] = somas.get(mes, Decimal(0)) + valor
    return somas


def status_notas_geradas(db: Session, ano: str) -> list[dict]:
    """Uma linha por vínculo ativo — soma de `emissao.valor` por mês,
    ignorando emissões canceladas (mesmo critério do motor de emissão pra
    'ativa', ver ESTADOS_ATIVOS_PARA_IDEMPOTENCIA)."""
    linhas = []
    for vinculo in listar_vinculos_ativos(db):
        registros = (
            db.query(Emissao.competencia, Emissao.valor)
            .filter(
                Emissao.prestador_tomador_id == vinculo.id,
                Emissao.competencia.like(f"{ano}-%"),
                Emissao.estado != "cancelada",
            )
            .all()
        )
        linhas.append(_linha_mensal(vinculo.apelido, _agrupar_por_mes(registros)))
    return linhas


def status_pagamentos_recebidos(db: Session, ano: str) -> list[dict]:
    """Uma linha por vínculo ativo — soma de `pagamento_recebido.valor` por
    mês (todo pagamento registrado conta; não há estado a filtrar aqui)."""
    linhas = []
    for vinculo in listar_vinculos_ativos(db):
        registros = (
            db.query(PagamentoRecebido.competencia, PagamentoRecebido.valor)
            .filter(PagamentoRecebido.prestador_tomador_id == vinculo.id, PagamentoRecebido.competencia.like(f"{ano}-%"))
            .all()
        )
        linhas.append(_linha_mensal(vinculo.apelido, _agrupar_por_mes(registros)))
    return linhas


def status_despesas(db: Session, prestador_id: uuid.UUID, ano: str) -> list[dict]:
    """Uma linha por CATEGORIA (não por fornecedor — despesa não tem
    vínculo), ordenadas alfabeticamente pra saída estável."""
    registros = (
        db.query(Despesa.categoria, Despesa.competencia, Despesa.valor)
        .filter(Despesa.prestador_id == prestador_id, Despesa.competencia.like(f"{ano}-%"))
        .all()
    )
    por_categoria: dict[str, list[tuple[str, Decimal]]] = {}
    for categoria, competencia, valor in registros:
        por_categoria.setdefault(categoria, []).append((competencia, valor))
    return [_linha_mensal(categoria, _agrupar_por_mes(linhas)) for categoria, linhas in sorted(por_categoria.items())]


def painel_status_completo(db: Session, prestador_id: uuid.UUID, ano: str) -> dict:
    return {
        "ano": ano,
        "notas_geradas": status_notas_geradas(db, ano),
        "pagamentos_recebidos": status_pagamentos_recebidos(db, ano),
        "despesas": status_despesas(db, prestador_id, ano),
    }
