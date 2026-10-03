"""Baixa por nota (03/10/2026)

`pagamento_recebido.emissao_id`: o recebimento dá baixa NAQUELA nota, não em
tudo que o tomador tem no mês. Pagamento antigo (planilha, conciliação,
lançado antes desta data) fica sem nota e continua valendo pro mês inteiro
do tomador, como sempre valeu — nada do histórico muda de situação.

Revision ID: a9d1f3b5c768
Revises: f8c0e2a4b657
Create Date: 2026-10-03 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a9d1f3b5c768'
down_revision: Union[str, Sequence[str], None] = 'f8c0e2a4b657'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pagamento_recebido',
        sa.Column('emissao_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('emissao.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_pagamento_recebido_emissao', 'pagamento_recebido', ['emissao_id'])


def downgrade() -> None:
    op.drop_index('ix_pagamento_recebido_emissao', table_name='pagamento_recebido')
    op.drop_column('pagamento_recebido', 'emissao_id')
