"""Tira o "paga antes da nota" do tomador (01/10/2026)

Ficou confuso pro usuário. No lugar: o recebimento que chega sem nota do
tomador naquele mês vira aviso com a opção de gerar a nota dele.

Revision ID: a3e5b7c9d102
Revises: f7a2c9d4e310
Create Date: 2026-10-01 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3e5b7c9d102'
down_revision: Union[str, Sequence[str], None] = 'f7a2c9d4e310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('prestador_tomador', 'nota_apos_pagamento')


def downgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('nota_apos_pagamento', sa.Boolean(), nullable=False, server_default='false'))
