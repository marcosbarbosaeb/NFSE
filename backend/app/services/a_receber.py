"""Notas a receber x recebidas, de TODOS os meses — pedido do Marcos
(28/09/2026): "Notas a receber / Notas recebidas (total), existem diversos
pagamentos que ficam pendentes"; "notas abertas há mais de dois meses também
devem entrar no Precisa da sua atenção"; "nos recebimentos coloque os
pagamentos também".

Mesma aproximação do resto do sistema (ver app/services/dashboard.py): o
pagamento é por tomador + competência, então uma competência com qualquer
pagamento registrado conta como recebida. Notas de um mesmo tomador na mesma
competência (Shopee: uma por vendedor) viram um grupo só.
"""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Emissao, PagamentoRecebido, PrestadorTomador
from app.tempo import data_local, hoje as hoje_br

# O que já saiu como nota (montado = gerada, ainda sem assinar). Rascunho,
# erro, cancelada e substituída não entram na conta de "a receber".
ESTADOS_COBRAVEIS = ("montado", "assinado", "submetido", "confirmado")
DIAS_ABERTA_ALERTA = 60


def _pares_pagos(db: Session) -> set[tuple[uuid.UUID, str]]:
    linhas = db.query(PagamentoRecebido.prestador_tomador_id, PagamentoRecebido.competencia).distinct()
    return {(v, c) for v, c in linhas}


def _grupos(db: Session) -> list[dict]:
    grupos: dict[tuple[uuid.UUID, str], dict] = {}
    # Só as colunas necessárias (nada de XML/snapshot).
    emissoes = (
        db.query(
            Emissao.id, Emissao.prestador_tomador_id, Emissao.competencia, Emissao.estado,
            Emissao.valor, Emissao.criado_em, PrestadorTomador.apelido,
        )
        .join(PrestadorTomador, PrestadorTomador.id == Emissao.prestador_tomador_id)
        # Notas de vendedores da Shopee não têm cobrança própria: a Shopee
        # paga tudo junto na nota dela (01/10/2026).
        .filter(Emissao.estado.in_(ESTADOS_COBRAVEIS), Emissao.tomador_documento.is_(None))
        .order_by(Emissao.criado_em)
        .all()
    )
    for e in emissoes:
        apelido = e.apelido
        chave = (e.prestador_tomador_id, e.competencia)
        g = grupos.get(chave)
        if g is None:
            g = grupos[chave] = {
                "vinculo_id": e.prestador_tomador_id,
                "apelido": apelido,
                "competencia": e.competencia,
                "emissao_id": e.id,
                "estado": e.estado,
                "valor": Decimal(0),
                "quantidade": 0,
                "emitida_em": e.criado_em,
            }
        g["valor"] += e.valor
        g["quantidade"] += 1
    return list(grupos.values())


def calcular(db: Session) -> tuple[list[dict], set]:
    """Grupos + competências pagas, pra reaproveitar numa mesma tela."""
    return _grupos(db), _pares_pagos(db)


def recebimentos_sem_nota(db: Session, desde: str | None = None) -> list[dict]:
    """O lado contrário do "a receber" (01/10/2026): dinheiro que caiu de um
    tomador num mês em que não há nota dele — caso do Mercado Livre e da
    Amazon, que pagam antes e a nota sai depois. A tela oferece gerar a nota
    daquele recebimento (POST /api/dps com pagamento_id)."""
    com_nota = {
        (v, c) for v, c in db.query(Emissao.prestador_tomador_id, Emissao.competencia)
        .filter(Emissao.estado.notin_(("cancelada", "substituida")), Emissao.tomador_documento.is_(None)).distinct()
    }
    query = (
        db.query(PagamentoRecebido, PrestadorTomador.apelido)
        .join(PrestadorTomador, PrestadorTomador.id == PagamentoRecebido.prestador_tomador_id)
        .filter(PrestadorTomador.sem_nota.is_(False))
    )
    if desde:
        query = query.filter(PagamentoRecebido.competencia >= desde)
    grupos: dict[tuple, dict] = {}
    for p, apelido in query.order_by(PagamentoRecebido.competencia, PagamentoRecebido.criado_em):
        chave = (p.prestador_tomador_id, p.competencia)
        if chave in com_nota:
            continue
        g = grupos.setdefault(chave, {
            "pagamento_id": p.id, "vinculo_id": p.prestador_tomador_id, "apelido": apelido,
            "competencia": p.competencia, "valor": Decimal(0), "data_recebimento": p.data_recebimento,
        })
        g["valor"] += p.valor
    return [{**g, "valor": float(g["valor"])} for g in grupos.values()]


def notas_em_aberto(db: Session, hoje: datetime.date | None = None, base: tuple | None = None) -> list[dict]:
    """Grupos (tomador + competência) sem nenhum pagamento, do mais antigo
    pro mais novo."""
    hoje = hoje or hoje_br()
    grupos, pagos = base or calcular(db)
    abertas = []
    for g in grupos:
        if (g["vinculo_id"], g["competencia"]) in pagos:
            continue
        emitida = data_local(g["emitida_em"]) or hoje
        abertas.append({**g, "valor": float(g["valor"]), "emitida_em": emitida, "dias_em_aberto": (hoje - emitida).days})
    return sorted(abertas, key=lambda g: (g["competencia"], g["apelido"]))


def totais(db: Session, base: tuple | None = None) -> dict:
    grupos, pagos = base or calcular(db)
    a_receber, qtd_aberta, qtd_recebida = Decimal(0), 0, 0
    for g in grupos:
        if (g["vinculo_id"], g["competencia"]) in pagos:
            qtd_recebida += g["quantidade"]
        else:
            a_receber += g["valor"]
            qtd_aberta += g["quantidade"]
    recebido = db.query(func.coalesce(func.sum(PagamentoRecebido.valor), 0)).scalar()
    return {
        "a_receber_total": float(a_receber),
        "notas_a_receber": qtd_aberta,
        "recebido_total": float(recebido or 0),
        "notas_recebidas": qtd_recebida,
    }


def avisos_abertas_ha_muito(db: Session, hoje: datetime.date | None = None, limite: int = 5, base: tuple | None = None) -> list[dict]:
    antigas = [g for g in notas_em_aberto(db, hoje, base) if g["dias_em_aberto"] > DIAS_ABERTA_ALERTA]
    avisos = []
    for g in antigas[:limite]:
        ano, mes = g["competencia"].split("-")
        valor = f"R$ {g['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        avisos.append({
            "tipo": "nota_aberta_antiga",
            "titulo": g["apelido"],
            "mensagem": f"Nota de {mes}/{ano} ({valor}) sem pagamento há {g['dias_em_aberto']} dias.",
            "link": "/app/financeiro#a-receber",
            "link_label": "Dar baixa ou cobrar",
        })
    if len(antigas) > limite:
        avisos.append({
            "tipo": "nota_aberta_antiga",
            "titulo": f"Mais {len(antigas) - limite} nota(s) em aberto há mais de dois meses",
            "mensagem": "Veja a lista completa em Financeiro › A receber.",
            "link": "/app/financeiro#a-receber",
            "link_label": "Ver todas",
        })
    return avisos


def conciliar(db: Session, prestador_id: uuid.UUID, pares: list[tuple[uuid.UUID, str]]) -> int:
    """Dá baixa sem valor (origem 'conciliacao') nas notas (tomador + mês)
    que eram controladas em outra plataforma — saem do "a receber" sem
    mexer no total recebido."""
    pagos = _pares_pagos(db)
    feitos = 0
    for vinculo_id, competencia in pares:
        if (vinculo_id, competencia) in pagos:
            continue
        db.add(PagamentoRecebido(
            id=uuid.uuid4(), prestador_tomador_id=vinculo_id, prestador_id=prestador_id, competencia=competencia,
            valor=Decimal(0), origem="conciliacao",
        ))
        pagos.add((vinculo_id, competencia))
        feitos += 1
    db.flush()
    return feitos
