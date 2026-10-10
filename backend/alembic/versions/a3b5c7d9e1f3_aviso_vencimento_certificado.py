"""Aviso de vencimento do certificado por e-mail (2026.10.7)

`certificado.aviso_vencimento_para`: a validade que já foi avisada (um aviso
por certificado; ao trocar de certificado, a validade muda e avisa de novo).

Revision ID: a3b5c7d9e1f3
Revises: f2a4c6e8b0d1
Create Date: 2026-10-10 03:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3b5c7d9e1f3'
down_revision: Union[str, Sequence[str], None] = 'f2a4c6e8b0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('certificado', sa.Column('aviso_vencimento_para', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('certificado', 'aviso_vencimento_para')
