"""Tomador que paga antes da nota (01/10/2026)

Mercado Livre e Amazon pagam sem nota; a nota do que caiu no mês sai no mês
seguinte. Com `nota_apos_pagamento`, as notas desse tomador nunca ficam "a
receber" e o aviso de gerar a nota só aparece quando já caiu um pagamento no
mês anterior (com o valor dele). E avisos da Visão geral podem ser ignorados
(ajuste_evento tipo 'pendencia').

Revision ID: f7a2c9d4e310
Revises: e4c8f1a2b637
Create Date: 2026-10-01 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f7a2c9d4e310'
down_revision: Union[str, Sequence[str], None] = 'e4c8f1a2b637'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TIPOS_ANTES = "tipo IN ('prazo_emissao', 'recebimento_previsto', 'revisar_aliquota')"


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('nota_apos_pagamento', sa.Boolean(), nullable=False, server_default='false'))
    # "Ignorar este aviso" na Visão geral reaproveita ajuste_evento.
    op.drop_constraint('ck_ajuste_evento_tipo', 'ajuste_evento', type_='check')
    op.create_check_constraint(
        'ck_ajuste_evento_tipo', 'ajuste_evento',
        "tipo IN ('prazo_emissao', 'recebimento_previsto', 'revisar_aliquota', 'pendencia')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM ajuste_evento WHERE tipo = 'pendencia'")
    op.drop_constraint('ck_ajuste_evento_tipo', 'ajuste_evento', type_='check')
    op.create_check_constraint('ck_ajuste_evento_tipo', 'ajuste_evento', _TIPOS_ANTES)
    op.drop_column('prestador_tomador', 'nota_apos_pagamento')
