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
4. 'revisar_aliquota' — Marco 16, item 5: um lembrete no dia 1 de cada mês
   do intervalo pra confirmar a alíquota de referência do Simples Nacional
   (`Prestador.aliquota_atual`), IGUAL ao 'prazo_emissao' já sai da lista
   assim que a competência tem emissão: aqui, sai assim que
   `aliquota_atualizada_em` cai naquele mês (ver PATCH
   /api/prestador/aliquota). Não é cálculo de imposto nem gera boleto —
   Marcos decidiu (22/09/2026) não construir isso agora; só quer ser
   lembrado de revisar o número manualmente.
"""
import datetime
import uuid
from calendar import monthrange

from sqlalchemy.orm import Session

from app.models import Emissao, EventoManual, PagamentoRecebido, Prestador
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

    # 4) Lembrete de revisar a alíquota de referência (Marco 16) — ao
    # contrário de 'prazo_emissao' (um evento por competência do
    # intervalo), este é ligado ao calendário REAL (`date.today()`), não à
    # competência sendo consultada: não faz sentido pedir pra revisar a
    # alíquota "de agosto de 2024" ao navegar pro passado. Só entra na
    # resposta quando o intervalo pedido cobre o dia 1 do mês corrente.
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is not None:
        hoje = datetime.date.today()
        ja_confirmada_este_mes = (
            prestador.aliquota_atualizada_em is not None
            and (prestador.aliquota_atualizada_em.year, prestador.aliquota_atualizada_em.month) == (hoje.year, hoje.month)
        )
        data_evento = datetime.date(hoje.year, hoje.month, 1)
        if not ja_confirmada_este_mes and inicio <= data_evento <= fim:
            eventos.append({
                "data": data_evento,
                "tipo": "revisar_aliquota",
                "titulo": "Revisar alíquota do Simples Nacional",
                "vinculo_id": None,
                "apelido": None,
                "valor": None,
            })

    # 5) Eventos manuais (Marco 15) — únicos com linha própria no banco
    # (os tipos acima são sempre recalculados, nunca guardados).
    manuais = (
        db.query(EventoManual)
        .filter(
            EventoManual.prestador_id == prestador_id,
            EventoManual.data >= inicio,
            EventoManual.data <= fim,
        )
        .all()
    )
    for evento in manuais:
        eventos.append({
            "data": evento.data,
            "tipo": "manual",
            "titulo": evento.titulo,
            "vinculo_id": None,
            "apelido": None,
            "valor": None,
            "id": evento.id,
            "descricao": evento.descricao,
        })

    eventos.sort(key=lambda e: e["data"])
    return eventos


# --- CRUD de eventos manuais (Marco 15) ---


def criar_evento_manual(
    db: Session, prestador_id: uuid.UUID, *, data: datetime.date, titulo: str, descricao: str | None = None
) -> EventoManual:
    evento = EventoManual(id=uuid.uuid4(), prestador_id=prestador_id, data=data, titulo=titulo, descricao=descricao)
    db.add(evento)
    db.flush()
    return evento


def buscar_evento_manual(db: Session, evento_id: uuid.UUID) -> EventoManual | None:
    """RLS já restringe a leitura ao prestador da sessão — não filtra por
    prestador_id aqui de propósito, mesmo padrão de buscar_vinculo."""
    return db.query(EventoManual).filter_by(id=evento_id).one_or_none()


def atualizar_evento_manual(db: Session, evento: EventoManual, **campos) -> EventoManual:
    for campo, valor in campos.items():
        setattr(evento, campo, valor)
    db.flush()
    return evento


def excluir_evento_manual(db: Session, evento: EventoManual) -> None:
    db.delete(evento)
    db.flush()
