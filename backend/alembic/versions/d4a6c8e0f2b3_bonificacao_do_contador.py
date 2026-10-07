"""Bonificação do contador (07/10/2026)

"O contador entra no módulo de parceria ganhando uma bonificação de 10% pra
cada cliente dele que usar o sistema": o parceiro pode ser um login
(`parceiro.usuario_id`) e a indicação pode nascer do acesso de contador
(`indicacao_parceiro.por_contador`).

Revision ID: d4a6c8e0f2b3
Revises: c3f5b7d9e1a2
Create Date: 2026-10-07 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd4a6c8e0f2b3'
down_revision: Union[str, Sequence[str], None] = 'c3f5b7d9e1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('parceiro', sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='SET NULL'), nullable=True))
    op.create_unique_constraint('uq_parceiro_usuario', 'parceiro', ['usuario_id'])
    op.add_column('indicacao_parceiro', sa.Column('por_contador', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('indicacao_parceiro', 'por_contador')
    op.drop_constraint('uq_parceiro_usuario', 'parceiro', type_='unique')
    op.drop_column('parceiro', 'usuario_id')
