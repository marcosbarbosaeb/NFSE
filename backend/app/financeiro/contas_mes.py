"""Módulo financeiro (28/09/2026) — a planilha "Controle CP" dentro da Ana.

O que a planilha fazia e agora vive aqui:
- Lucro e margem por mês (recebido − despesas), com as retiradas
  (distribuição de lucros) separadas das despesas e o saldo que ainda dá pra
  distribuir.
- Contas fixas do mês com check ("sacou o pró-labore ✓, pagou o cartão ✓"):
  cada conta recorrente vira, em cada mês, um lançamento em `despesa` que
  nasce "a pagar" e a pessoa tica quando paga.
- Rotina de fechamento com check por mês (conferir extrato do banco, do
  PayPal, baixar a NF do Facebook...).
"""
import calendar
import datetime
import re
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Despesa, DespesaRecorrente, Emissao, PagamentoRecebido, RotinaMensal, RotinaMensalFeita
from app.financeiro import a_receber

MESES = [f"{m:02d}" for m in range(1, 13)]
# Categorias que contam como imposto no resumo (o resto é custo).
_IMPOSTO = re.compile(r"simples|inss|das\b|parcela das|imposto|iss\b|irpj|csll|pis|cofins|darf", re.I)
_FERRAMENTA = re.compile(r"ferrament|automa|software|assinatura|manychat|disparador|grupos|divulgador|mandanota|sistema", re.I)


class FinanceiroError(Exception):
    pass


def _competencia_de(data: datetime.date) -> str:
    return f"{data.year:04d}-{data.month:02d}"


def _vencimento(competencia: str, dia: int | None) -> datetime.date | None:
    if not dia:
        return None
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    return datetime.date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


# --- contas fixas ----------------------------------------------------------


def listar_recorrentes(db: Session) -> list[DespesaRecorrente]:
    return db.query(DespesaRecorrente).order_by(DespesaRecorrente.ativa.desc(), DespesaRecorrente.ordem, DespesaRecorrente.nome).all()


def criar_recorrente(db: Session, prestador_id: uuid.UUID, **campos) -> DespesaRecorrente:
    ordem = (db.query(func.max(DespesaRecorrente.ordem)).scalar() or 0) + 1
    r = DespesaRecorrente(id=uuid.uuid4(), prestador_id=prestador_id, ordem=ordem, **campos)
    db.add(r)
    db.flush()
    return r


def garantir_lancamentos(db: Session, prestador_id: uuid.UUID, competencia: str) -> None:
    """Cria (uma vez) o lançamento "a pagar" de cada conta fixa ativa no mês.
    Não cria pra meses antes de a conta existir."""
    ja = {r for (r,) in db.query(Despesa.recorrente_id).filter(Despesa.competencia == competencia, Despesa.recorrente_id.isnot(None))}
    for r in db.query(DespesaRecorrente).filter(DespesaRecorrente.ativa.is_(True)):
        if r.id in ja:
            continue
        if r.criado_em and _competencia_de(r.criado_em.date()) > competencia:
            continue
        db.add(Despesa(
            id=uuid.uuid4(), prestador_id=prestador_id, categoria=r.categoria, descricao=r.nome, tipo=r.tipo,
            competencia=competencia, valor=r.valor_padrao or Decimal(0), conta=r.conta,
            vencimento=_vencimento(competencia, r.dia_vencimento), pago=False, recorrente_id=r.id, origem="recorrente",
        ))
    db.flush()


def _linha_despesa(d: Despesa) -> dict:
    return {
        "id": d.id, "categoria": d.categoria, "descricao": d.descricao, "tipo": d.tipo, "competencia": d.competencia,
        "valor": float(d.valor), "conta": d.conta, "vencimento": d.vencimento, "pago": d.pago, "pago_em": d.pago_em,
        "recorrente_id": d.recorrente_id, "valor_a_definir": d.recorrente_id is not None and not d.pago and d.valor == 0,
    }


def contas_do_mes(db: Session, prestador_id: uuid.UUID, competencia: str) -> dict:
    garantir_lancamentos(db, prestador_id, competencia)
    despesas = (
        db.query(Despesa).filter(Despesa.competencia == competencia)
        .order_by(Despesa.pago, Despesa.vencimento.nulls_last(), Despesa.categoria).all()
    )
    feitas = {
        f.rotina_id: f.feita_em for f in db.query(RotinaMensalFeita).filter(RotinaMensalFeita.competencia == competencia)
    }
    rotinas = [
        {"id": r.id, "nome": r.nome, "feita": r.id in feitas, "feita_em": feitas.get(r.id)}
        for r in db.query(RotinaMensal).filter(RotinaMensal.ativa.is_(True)).order_by(RotinaMensal.ordem, RotinaMensal.nome)
    ]
    linhas = [_linha_despesa(d) for d in despesas]
    so_despesas = [x for x in linhas if x["tipo"] == "despesa"]
    return {
        "competencia": competencia,
        "contas": linhas,
        "rotinas": rotinas,
        "total_previsto": round(sum(x["valor"] for x in so_despesas), 2),
        "total_pago": round(sum(x["valor"] for x in so_despesas if x["pago"]), 2),
        "a_pagar": sum(1 for x in linhas if not x["pago"]),
        "rotinas_feitas": sum(1 for r in rotinas if r["feita"]),
    }


def marcar_rotina(db: Session, prestador_id: uuid.UUID, rotina: RotinaMensal, competencia: str, feita: bool) -> None:
    atual = db.query(RotinaMensalFeita).filter_by(rotina_id=rotina.id, competencia=competencia).one_or_none()
    if feita and atual is None:
        db.add(RotinaMensalFeita(id=uuid.uuid4(), prestador_id=prestador_id, rotina_id=rotina.id, competencia=competencia))
    elif not feita and atual is not None:
        db.delete(atual)
    db.flush()


def criar_rotina(db: Session, prestador_id: uuid.UUID, nome: str) -> RotinaMensal:
    ordem = (db.query(func.max(RotinaMensal.ordem)).scalar() or 0) + 1
    r = RotinaMensal(id=uuid.uuid4(), prestador_id=prestador_id, nome=nome.strip()[:120], ordem=ordem)
    db.add(r)
    db.flush()
    return r


# --- resumo do ano -----------------------------------------------------------


def _por_mes(linhas) -> list[float]:
    somas = {m: Decimal(0) for m in MESES}
    for competencia, valor in linhas:
        somas[competencia[5:7]] += valor or 0
    return [round(float(somas[m]), 2) for m in MESES]


def resumo_anual(db: Session, ano: str) -> dict:
    """Linha a linha o que a planilha calculava, mês a mês."""
    faturado = _por_mes(
        db.query(Emissao.competencia, Emissao.valor)
        .filter(Emissao.competencia.like(f"{ano}-%"), Emissao.estado == "confirmado")
    )
    recebido = _por_mes(
        db.query(PagamentoRecebido.competencia, PagamentoRecebido.valor).filter(PagamentoRecebido.competencia.like(f"{ano}-%"))
    )
    despesas_ano = db.query(Despesa).filter(Despesa.competencia.like(f"{ano}-%")).all()
    custos = _por_mes((d.competencia, d.valor) for d in despesas_ano if d.tipo == "despesa")
    impostos = _por_mes((d.competencia, d.valor) for d in despesas_ano if d.tipo == "despesa" and _IMPOSTO.search(d.categoria))
    ferramentas = _por_mes(
        (d.competencia, d.valor) for d in despesas_ano
        if d.tipo == "despesa" and (_FERRAMENTA.search(d.categoria) or _FERRAMENTA.search(d.descricao or ""))
    )
    retiradas = _por_mes((d.competencia, d.valor) for d in despesas_ano if d.tipo == "retirada")
    lucro = [round(r - c, 2) for r, c in zip(recebido, custos)]
    margem = [round(l / r * 100, 1) if r else None for l, r in zip(lucro, recebido)]
    saldo, acumulado = [], 0.0
    for l, ret in zip(lucro, retiradas):
        acumulado += l - ret
        saldo.append(round(acumulado, 2))

    por_categoria: dict[str, float] = {}
    for d in despesas_ano:
        if d.tipo == "despesa":
            por_categoria[d.categoria] = por_categoria.get(d.categoria, 0) + float(d.valor)
    categorias = sorted(({"categoria": k, "total": round(v, 2)} for k, v in por_categoria.items()), key=lambda x: -x["total"])

    total_recebido = sum(recebido)
    total_lucro = sum(lucro)
    return {
        "ano": ano,
        "meses": MESES,
        "faturado": faturado, "recebido": recebido, "despesas": custos, "impostos": impostos,
        "ferramentas": ferramentas, "retiradas": retiradas, "lucro": lucro, "margem": margem, "saldo_a_distribuir": saldo,
        "totais": {
            "faturado": round(sum(faturado), 2), "recebido": round(total_recebido, 2), "despesas": round(sum(custos), 2),
            "impostos": round(sum(impostos), 2), "ferramentas": round(sum(ferramentas), 2),
            "retiradas": round(sum(retiradas), 2), "lucro": round(total_lucro, 2),
            "margem": round(total_lucro / total_recebido * 100, 1) if total_recebido else None,
            "carga_impostos": round(sum(impostos) / total_recebido * 100, 1) if total_recebido else None,
            "saldo_a_distribuir": saldo[-1] if saldo else 0,
            "a_receber": round(a_receber.totais(db)["a_receber_total"], 2),
        },
        "categorias": categorias,
    }
