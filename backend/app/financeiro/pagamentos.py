"""
Registro de pagamentos recebidos — Marco 8. O lado "recebi" do painel de
status (o lado "faturei" já é automático, vem de `emissao`/motor_emissao —
Marco 6/7). Diferente de emissão, um pagamento recebido não passa por
máquina de estados: é só um fato que a Raiana registra (hoje, à mão na
planilha; aqui, manualmente por enquanto — ver ressalva no relatório do
Marco 8 sobre importação em lote pra isso ainda não existir).
"""
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models import Emissao, PagamentoRecebido, PrestadorTomador


def registrar_pagamento(
    db: Session,
    vinculo: PrestadorTomador,
    *,
    competencia: str,
    valor: float,
    data_recebimento: date | None = None,
    emissao_id: uuid.UUID | None = None,
    origem: str = "manual",
) -> PagamentoRecebido:
    """A baixa é por nota (03/10/2026): com `emissao_id`, o recebimento paga
    aquela nota (e fica no mês dela). Sem ele, a nota é escolhida pelo valor
    entre as do tomador naquele mês; se o tomador não tem nota no mês, o
    recebimento fica sem nota (dinheiro que caiu antes da nota)."""
    from app.financeiro import a_receber

    if emissao_id is not None:
        emissao = db.get(Emissao, emissao_id)
        if emissao is None or emissao.prestador_tomador_id != vinculo.id:
            raise ValueError("Essa nota não é deste tomador.")
        competencia = emissao.competencia
    else:
        emissao_id = a_receber.nota_do_recebimento(db, vinculo.id, competencia, valor)
    pagamento = PagamentoRecebido(
        id=uuid.uuid4(),
        prestador_tomador_id=vinculo.id,
        prestador_id=vinculo.prestador_id,
        competencia=competencia,
        valor=valor,
        data_recebimento=data_recebimento,
        emissao_id=emissao_id,
        origem=origem,
    )
    db.add(pagamento)
    db.flush()
    return pagamento
