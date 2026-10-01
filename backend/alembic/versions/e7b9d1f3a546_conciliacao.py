"""Conciliação de histórico (01/10/2026)

Notas antigas controladas em outra plataforma: dá baixa sem lançar valor
(o dinheiro já está contado em outro lugar) — origem 'conciliacao'.

Revision ID: e7b9d1f3a546
Revises: d6a8c0e2f435
Create Date: 2026-10-01 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e7b9d1f3a546'
down_revision: Union[str, Sequence[str], None] = 'd6a8c0e2f435'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_pagamento_origem', 'pagamento_recebido', type_='check')
    op.create_check_constraint(
        'ck_pagamento_origem', 'pagamento_recebido', "origem IN ('manual', 'extrato', 'planilha', 'conciliacao')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM pagamento_recebido WHERE origem = 'conciliacao'")
    op.drop_constraint('ck_pagamento_origem', 'pagamento_recebido', type_='check')
    op.create_check_constraint('ck_pagamento_origem', 'pagamento_recebido', "origem IN ('manual', 'extrato', 'planilha')")
