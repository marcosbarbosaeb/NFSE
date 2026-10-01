"""nDPS em BIGINT (01/10/2026)

Notas emitidas por outros sistemas (o portal nacional usa números como
2200000000031) passam do limite de INTEGER — aparece ao importar do
Emissor Nacional.

Revision ID: c5f7a9b1d324
Revises: b4d6e8f0a213
Create Date: 2026-10-01 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5f7a9b1d324'
down_revision: Union[str, Sequence[str], None] = 'b4d6e8f0a213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('emissao', 'n_dps', type_=sa.BigInteger(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column('emissao', 'n_dps', type_=sa.Integer(), existing_nullable=True)
