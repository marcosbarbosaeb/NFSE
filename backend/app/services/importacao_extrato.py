"""
Confirmação da importação de extrato bancário — Marco 15 (item 5). Segunda
metade do fluxo iniciado em app/services/extrato_pdf.py: depois que a
pessoa revisa as transações extraídas do PDF no painel e escolhe quais são
recebimentos de verdade (e de qual vínculo cada uma é), este módulo grava
um `PagamentoRecebido` por item — reaproveitando
app/services/pagamentos.registrar_pagamento, o mesmo usado pro registro
manual.

Mesmo padrão de isolamento por item do app/services/importacao_csv.py
(Marco 7): cada item roda no seu próprio SAVEPOINT, então um vínculo
inválido ou uma competência malformada em UM item não derruba os demais.
"""
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.services.pagamentos import registrar_pagamento
from app.services.vinculos import buscar_vinculo


@dataclass
class ItemExtrato:
    vinculo_id: uuid.UUID
    competencia: str
    valor: float
    data_recebimento: date | None = None


@dataclass
class ItemConfirmado:
    indice: int
    ok: bool
    mensagem: str | None = None
    pagamento_id: uuid.UUID | None = None


def confirmar_importacao_extrato(db: Session, itens: list[ItemExtrato]) -> list[ItemConfirmado]:
    """Não dá commit — quem chama decide (mesma regra de importar_csv)."""
    resultados: list[ItemConfirmado] = []
    for indice, item in enumerate(itens):
        savepoint = db.begin_nested()
        try:
            vinculo = buscar_vinculo(db, item.vinculo_id)
            if vinculo is None:
                raise ValueError("Vínculo não encontrado (ou não pertence ao prestador ativo).")
            pagamento = registrar_pagamento(
                db, vinculo, competencia=item.competencia, valor=item.valor, data_recebimento=item.data_recebimento
            )
        except (ValueError, KeyError) as exc:
            savepoint.rollback()
            resultados.append(ItemConfirmado(indice=indice, ok=False, mensagem=str(exc)))
        else:
            savepoint.commit()
            resultados.append(ItemConfirmado(indice=indice, ok=True, pagamento_id=pagamento.id))
    return resultados
