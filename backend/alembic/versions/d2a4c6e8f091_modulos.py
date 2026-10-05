"""Módulos por empresa (05/10/2026)

Emissor e financeiro passam a ser produtos separados: cada empresa tem
ligado o que usa (`prestador.modulos`). Quem já existe fica com os dois (não
perde nada do que usava); empresa nova começa só com o emissor.

O preenchimento das empresas existentes vem do DEFAULT da coluna, não de um
UPDATE — `prestador` tem RLS, e um UPDATE de migração não enxerga as linhas
(foi o erro da migração b0e2a4c6d879).

Revision ID: d2a4c6e8f091
Revises: c1f3b5d7e980
Create Date: 2026-10-05 04:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd2a4c6e8f091'
down_revision: Union[str, Sequence[str], None] = 'c1f3b5d7e980'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'prestador',
        sa.Column('modulos', postgresql.JSONB(), nullable=False, server_default=sa.text("""'["emissor", "financeiro"]'::jsonb""")),
    )
    op.alter_column('prestador', 'modulos', server_default=sa.text("""'["emissor"]'::jsonb"""))


def downgrade() -> None:
    op.drop_column('prestador', 'modulos')
