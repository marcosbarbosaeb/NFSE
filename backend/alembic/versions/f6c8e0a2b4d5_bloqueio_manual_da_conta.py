"""Bloqueio manual de uma conta pela Gestão (08/10/2026)

"Nessa fase em que o sistema de pagamento não está implementado quero poder
fazer a gestão de contas manualmente, aceitando, bloqueando e excluindo."

Revision ID: f6c8e0a2b4d5
Revises: e5b7d9f1a3c4
Create Date: 2026-10-08 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6c8e0a2b4d5'
down_revision: Union[str, Sequence[str], None] = 'e5b7d9f1a3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assinatura', sa.Column('bloqueada_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assinatura', sa.Column('bloqueada_obs', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('assinatura', 'bloqueada_obs')
    op.drop_column('assinatura', 'bloqueada_em')
