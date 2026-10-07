"""Planos por limite de notas (07/10/2026)

Básico 30, Empreendedor 150, Empresa 300 + Financeiro, Avançado 500 +
Financeiro, Ilimitado; Financeiro somado ao Básico/Empreendedor; nota
acima do limite cobrada à parte, com aceite.

Revision ID: e5b7d9f1a3c4
Revises: d4a6c8e0f2b3
Create Date: 2026-10-07 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e5b7d9f1a3c4'
down_revision: Union[str, Sequence[str], None] = 'd4a6c8e0f2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assinatura', sa.Column('com_financeiro', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('assinatura', sa.Column('excedente_aceito_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assinatura', sa.Column('excedente_cobranca', postgresql.JSONB(), nullable=False, server_default='{}'))


def downgrade() -> None:
    op.drop_column('assinatura', 'excedente_cobranca')
    op.drop_column('assinatura', 'excedente_aceito_em')
    op.drop_column('assinatura', 'com_financeiro')
