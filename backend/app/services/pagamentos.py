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

from app.models import PagamentoRecebido, PrestadorTomador


def registrar_pagamento(
    db: Session,
    vinculo: PrestadorTomador,
    *,
    competencia: str,
    valor: float,
    data_recebimento: date | None = None,
) -> PagamentoRecebido:
    pagamento = PagamentoRecebido(
        id=uuid.uuid4(),
        prestador_tomador_id=vinculo.id,
        prestador_id=vinculo.prestador_id,
        competencia=competencia,
        valor=valor,
        data_recebimento=data_recebimento,
        origem="manual",
    )
    db.add(pagamento)
    db.flush()
    return pagamento
