"""Conta só de contador (07/10/2026)

"O contador pode ter uma conta apenas de gestão": cadastro sem CNPJ, sem
teste e sem assinatura. `prestador.so_contador` marca a empresa de fachada
desse login.

Revision ID: c3f5b7d9e1a2
Revises: b2e4a6c8d091
Create Date: 2026-10-07 00:20:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3f5b7d9e1a2'
down_revision: Union[str, Sequence[str], None] = 'b2e4a6c8d091'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador', sa.Column('so_contador', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('prestador', 'so_contador')
