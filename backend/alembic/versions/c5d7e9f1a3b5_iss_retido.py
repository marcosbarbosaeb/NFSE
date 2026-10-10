"""ISS retido pelo tomador (2026.10.7)

`prestador_tomador.iss_retido`: memória do tomador ("este tomador retém o
ISS"). `prestador.aliquota_iss_retido`: a alíquota do ISS que vai na nota
com retenção (ME/EPP do Simples).

Revision ID: c5d7e9f1a3b5
Revises: b4c6d8e0f2a4
Create Date: 2026-10-10 04:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5d7e9f1a3b5'
down_revision: Union[str, Sequence[str], None] = 'b4c6d8e0f2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('iss_retido', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('prestador', sa.Column('aliquota_iss_retido', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('prestador', 'aliquota_iss_retido')
    op.drop_column('prestador_tomador', 'iss_retido')
