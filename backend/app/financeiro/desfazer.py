"""Desfazer uma importação do financeiro (07/10/2026).

Pedido do Marcos: "precisamos poder desfazer uma importação — por exemplo,
se a pessoa importou um extrato e bagunçou — é importante ter um botão pra
desfazer isso".

Não existe uma tabela de "importações": tudo que uma importação grava nasce
na mesma transação, e por isso com o mesmo `criado_em` (o `now()` do
Postgres é o início da transação). É por esse instante que uma importação é
reconhecida e desfeita.

- **Extrato**: as linhas (`lancamento_bancario`) e o que elas viraram — o
  recebimento criado é apagado (a nota volta a ficar a receber); a despesa
  criada é apagada; a conta que já existia e foi dada como paga volta a
  ficar em aberto.
- **Planilha de controle**: recebimentos, despesas, retiradas, contas fixas
  e rotinas criados por ela, e os clientes "sem nota" que ela criou e
  ficaram sem nada.

O que a pessoa lançou à mão nunca é tocado.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Despesa, DespesaRecorrente, Emissao, LancamentoBancario, PagamentoRecebido, PrestadorTomador, RotinaMensal,
)

LIMITE = 30


class DesfazerError(Exception):
    pass


def _instante(texto: str) -> datetime:
    try:
        return datetime.fromisoformat(texto)
    except (TypeError, ValueError) as exc:
        raise DesfazerError("Importação não encontrada.") from exc


def listar(db: Session) -> list[dict]:
    """As importações feitas, da mais nova pra mais antiga."""
    saida: list[dict] = []
    extratos = (
        db.query(
            LancamentoBancario.criado_em, func.max(LancamentoBancario.arquivo), func.count(LancamentoBancario.id),
            func.count(LancamentoBancario.id).filter(LancamentoBancario.pagamento_id.isnot(None)),
            func.count(LancamentoBancario.id).filter(LancamentoBancario.despesa_id.isnot(None)),
        )
        .group_by(LancamentoBancario.criado_em).order_by(LancamentoBancario.criado_em.desc()).limit(LIMITE)
    )
    for quando, arquivo, linhas, recebimentos, despesas in extratos:
        partes = [f"{linhas} linha{'s' if linhas != 1 else ''}"]
        if recebimentos:
            partes.append(f"{recebimentos} recebimento{'s' if recebimentos != 1 else ''}")
        if despesas:
            partes.append(f"{despesas} despesa{'s' if despesas != 1 else ''}")
        saida.append({
            "tipo": "extrato", "quando": quando.isoformat(), "titulo": arquivo or "Extrato do banco", "resumo": ", ".join(partes),
        })

    planilhas: dict[datetime, dict] = {}
    for modelo, chave in ((PagamentoRecebido, "recebimentos"), (Despesa, "despesas")):
        for quando, n in (
            db.query(modelo.criado_em, func.count(modelo.id)).filter(modelo.origem == "planilha").group_by(modelo.criado_em)
        ):
            planilhas.setdefault(quando, {"recebimentos": 0, "despesas": 0})[chave] = n
    for quando, n in planilhas.items():
        partes = []
        if n["recebimentos"]:
            partes.append(f"{n['recebimentos']} recebimento{'s' if n['recebimentos'] != 1 else ''}")
        if n["despesas"]:
            partes.append(f"{n['despesas']} despesa{'s' if n['despesas'] != 1 else ''} e retirada{'s' if n['despesas'] != 1 else ''}")
        saida.append({"tipo": "planilha", "quando": quando.isoformat(), "titulo": "Planilha de controle", "resumo": ", ".join(partes)})

    saida.sort(key=lambda i: i["quando"], reverse=True)
    return saida[:LIMITE]


def desfazer_extrato(db: Session, quando: str) -> dict:
    linhas = db.query(LancamentoBancario).filter(LancamentoBancario.criado_em == _instante(quando)).all()
    if not linhas:
        raise DesfazerError("Importação não encontrada (talvez já tenha sido desfeita).")
    res = {"linhas": len(linhas), "recebimentos": 0, "despesas": 0, "contas_reabertas": 0}
    for lanc in linhas:
        if lanc.pagamento_id is not None:
            pagamento = db.get(PagamentoRecebido, lanc.pagamento_id)
            if pagamento is not None:
                db.delete(pagamento)
                res["recebimentos"] += 1
        if lanc.despesa_id is not None:
            despesa = db.get(Despesa, lanc.despesa_id)
            if despesa is not None and despesa.origem == "extrato":
                db.delete(despesa)
                res["despesas"] += 1
            elif despesa is not None:
                # Conta que já existia e o extrato só deu como paga.
                despesa.pago, despesa.pago_em = False, None
                res["contas_reabertas"] += 1
        db.delete(lanc)
    db.flush()
    return res


def desfazer_planilha(db: Session, quando: str) -> dict:
    instante = _instante(quando)
    res = {
        "recebimentos": db.query(PagamentoRecebido)
        .filter(PagamentoRecebido.origem == "planilha", PagamentoRecebido.criado_em == instante).delete(synchronize_session=False),
        "despesas": db.query(Despesa)
        .filter(Despesa.origem == "planilha", Despesa.criado_em == instante).delete(synchronize_session=False),
        "contas_fixas": 0, "rotinas": 0, "clientes": 0,
    }
    if not res["recebimentos"] and not res["despesas"]:
        raise DesfazerError("Importação não encontrada (talvez já tenha sido desfeita).")
    for fixa in db.query(DespesaRecorrente).filter(DespesaRecorrente.criado_em == instante).all():
        if db.query(Despesa.id).filter(Despesa.recorrente_id == fixa.id).first() is None:
            db.delete(fixa)
            res["contas_fixas"] += 1
    res["rotinas"] = db.query(RotinaMensal).filter(RotinaMensal.criado_em == instante).delete(synchronize_session=False)
    # Clientes "sem nota" que a planilha criou e ficaram sem nada.
    for v in db.query(PrestadorTomador).filter(PrestadorTomador.criado_em == instante, PrestadorTomador.sem_nota.is_(True)).all():
        tem_pagamento = db.query(PagamentoRecebido.id).filter(PagamentoRecebido.prestador_tomador_id == v.id).first()
        tem_nota = db.query(Emissao.id).filter(Emissao.prestador_tomador_id == v.id).first()
        if not tem_pagamento and not tem_nota:
            db.delete(v)
            res["clientes"] += 1
    db.flush()
    return res


def desfazer(db: Session, tipo: str, quando: str) -> dict:
    if tipo == "extrato":
        return desfazer_extrato(db, quando)
    if tipo == "planilha":
        return desfazer_planilha(db, quando)
    raise DesfazerError("Importação não encontrada.")
