"""
Calendário de prazos e previsão de recebimento — Marco 13 do plano, a
pedido de Marcos (22/09/2026): "montar um calendário (padrão Google
Agenda) com a previsão de recebimento dos pagamentos e com a data para
gerar nota (tem [tomador] que cobra data limite pro pagamento não ficar
pro próximo mês)".

Três tipos de evento, todos calculados na hora pro intervalo pedido — não
existe tabela de eventos, isto é uma leitura derivada de dados que já
existem (Emissao, PagamentoRecebido, PrestadorTomador):

1. 'prazo_emissao' — pro vínculo ativo com `dia_limite_emissao` definido
   (ver migração 4e44be09cfe3), um evento no dia X de cada mês do
   intervalo em que esse vínculo AINDA NÃO tem uma emissão ativa (mesmo
   critério de 'aguardando' em app/services/dashboard.py — já emitiu não
   precisa de lembrete). `dia_limite_emissao` maior que o número de dias
   do mês (ex.: 31 em fevereiro) é ajustado pro último dia daquele mês.
2. 'recebimento_previsto' — pra cada emissão ATIVA sem pagamento
   registrado (mesma checagem de app/services/dashboard.py), se o vínculo
   tem `dias_para_recebimento` definido: um evento em
   `emissao.criado_em.date() + dias_para_recebimento`. É só uma
   estimativa — sai do calendário assim que um pagamento for registrado
   pra aquele vínculo+competência (vira o evento abaixo).
3. 'recebimento_confirmado' — todo PagamentoRecebido com
   `data_recebimento` preenchida dentro do intervalo — dado real, não
   previsão (por isso não depende de `dias_para_recebimento` estar
   configurado).
"""
import datetime
import uuid
from calendar import monthrange

from sqlalchemy.orm import Session

from app.models import Emissao, PagamentoRecebido
from app.services.vinculos import listar_vinculos_ativos


def _tem_pagamento(db: Session, prestador_tomador_id: uuid.UUID, competencia: str) -> bool:
    return (
        db.query(PagamentoRecebido)
        .filter_by(prestador_tomador_id=prestador_tomador_id, competencia=competencia)
        .first()
        is not None
    )


def _dia_valido_no_mes(ano: int, mes: int, dia: int) -> int:
    return min(dia, monthrange(ano, mes)[1])


def _competencias_no_intervalo(inicio: datetime.date, fim: datetime.date) -> list[str]:
    competencias = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        competencias.append(f"{ano:04d}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return competencias


def eventos_calendario(db: Session, prestador_id: uuid.UUID, inicio: datetime.date, fim: datetime.date) -> list[dict]:
    """Só leitura — não muda estado de nada. `inicio`/`fim` são inclusivos."""
    eventos: list[dict] = []
    vinculos = listar_vinculos_ativos(db)
    vinculos_por_id = {v.id: v for v in vinculos}

    # 1) Prazo pra emitir
    for vinculo in vinculos:
        if vinculo.dia_limite_emissao is None:
            continue
        for competencia in _competencias_no_intervalo(inicio, fim):
            ano, mes = (int(p) for p in competencia.split("-"))
            ja_emitiu = (
                db.query(Emissao)
                .filter(
                    Emissao.prestador_tomador_id == vinculo.id,
                    Emissao.competencia == competencia,
                    Emissao.estado != "cancelada",
                )
                .first()
                is not None
            )
            if ja_emitiu:
                continue
            data_evento = datetime.date(ano, mes, _dia_valido_no_mes(ano, mes, vinculo.dia_limite_emissao))
            if not (inicio <= data_evento <= fim):
                continue
            eventos.append({
                "data": data_evento,
                "tipo": "prazo_emissao",
                "titulo": f"Prazo pra emitir — {vinculo.apelido}",
                "vinculo_id": vinculo.id,
                "apelido": vinculo.apelido,
                "valor": None,
            })

    # 2) Previsão de recebimento
    emissoes_ativas = db.query(Emissao).filter(Emissao.estado != "cancelada").all()
    for emissao in emissoes_ativas:
        vinculo = vinculos_por_id.get(emissao.prestador_tomador_id)
        if vinculo is None or vinculo.dias_para_recebimento is None:
            continue
        if _tem_pagamento(db, vinculo.id, emissao.competencia):
            continue
        data_evento = emissao.criado_em.date() + datetime.timedelta(days=vinculo.dias_para_recebimento)
        if not (inicio <= data_evento <= fim):
            continue
        eventos.append({
            "data": data_evento,
            "tipo": "recebimento_previsto",
            "titulo": f"Previsão de recebimento — {vinculo.apelido}",
            "vinculo_id": vinculo.id,
            "apelido": vinculo.apelido,
            "valor": float(emissao.valor),
        })

    # 3) Recebimentos já confirmados
    pagamentos = (
        db.query(PagamentoRecebido)
        .filter(
            PagamentoRecebido.prestador_id == prestador_id,
            PagamentoRecebido.data_recebimento.isnot(None),
            PagamentoRecebido.data_recebimento >= inicio,
            PagamentoRecebido.data_recebimento <= fim,
        )
        .all()
    )
    for pagamento in pagamentos:
        vinculo = vinculos_por_id.get(pagamento.prestador_tomador_id)
        eventos.append({
            "data": pagamento.data_recebimento,
            "tipo": "recebimento_confirmado",
            "titulo": f"Recebido — {vinculo.apelido if vinculo else 'fornecedor'}",
            "vinculo_id": pagamento.prestador_tomador_id,
            "apelido": vinculo.apelido if vinculo else None,
            "valor": float(pagamento.valor),
        })

    eventos.sort(key=lambda e: e["data"])
    return eventos
