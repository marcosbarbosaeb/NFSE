"""O que o financeiro põe no calendário (05/10/2026): a previsão de
recebimento de cada nota em aberto e os recebimentos que já caíram. Saiu de
app/services/calendario.py na separação dos módulos — o calendário pede
"quem tem algo pra agenda?" (app/eventos.py) e o financeiro responde, só
pra empresa que tem o módulo ligado."""
import datetime
import uuid

from sqlalchemy.orm import Session

from app.deps import modulos_da_empresa
from app.financeiro.a_receber import Baixas
from app.models import Emissao, PagamentoRecebido
from app.tempo import data_local


def eventos_da_agenda(db: Session, prestador_id: uuid.UUID, inicio: datetime.date, fim: datetime.date, vinculos: list) -> list[dict]:
    if "financeiro" not in modulos_da_empresa(db, prestador_id):
        return []
    eventos: list[dict] = []
    vinculos_por_id = {v.id: v for v in vinculos}

    # Previsão de recebimento: só quem tem prazo de pagamento configurado, e
    # só o que ainda não foi pago.
    com_prazo = [v.id for v in vinculos if v.dias_para_recebimento is not None]
    baixas = Baixas(db)
    emissoes_ativas = (
        db.query(Emissao).filter(Emissao.estado != "cancelada", Emissao.prestador_tomador_id.in_(com_prazo)).order_by(Emissao.criado_em).all()
        if com_prazo else []
    )
    # Shopee: várias notas por mês (uma por vendedor) — uma previsão só,
    # somando os valores, ancorada na primeira nota do mês.
    agrupadas: dict[tuple, list] = {}
    for emissao in emissoes_ativas:
        chave = (emissao.prestador_tomador_id, emissao.competencia) if emissao.tomador_documento else (emissao.id,)
        agrupadas.setdefault(chave, []).append(emissao)
    for grupo in agrupadas.values():
        emissao = grupo[0]
        vinculo = vinculos_por_id.get(emissao.prestador_tomador_id)
        if vinculo is None or vinculo.dias_para_recebimento is None:
            continue
        if emissao.tomador_documento:
            if baixas.mes_pago(vinculo.id, emissao.competencia):
                continue
        elif baixas.paga(emissao.id, vinculo.id, emissao.competencia):
            continue
        eventos.append({
            "data": data_local(emissao.criado_em) + datetime.timedelta(days=vinculo.dias_para_recebimento),
            "tipo": "recebimento_previsto",
            "titulo": f"Previsão de recebimento — {vinculo.apelido}",
            "vinculo_id": vinculo.id,
            "apelido": vinculo.apelido,
            "valor": float(sum(e.valor for e in grupo)),
            "chave": str(emissao.id),
            "regra_valor": vinculo.dias_para_recebimento,
        })

    # Recebimentos já confirmados (dado real — não ajustável).
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
            "titulo": f"Recebido — {vinculo.apelido if vinculo else 'cliente'}",
            "vinculo_id": pagamento.prestador_tomador_id,
            "apelido": vinculo.apelido if vinculo else None,
            "valor": float(pagamento.valor),
        })
    return eventos
