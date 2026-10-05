"""Anotações em formatos diferentes: texto, lista e tabela (05/10/2026)

- `anotacao.formato`: "texto" (o que já existia), "lista" (itens com tique)
  ou "tabela" (controle com colunas e total). As notas antigas ficam "texto".
- `anotacao.dados` (JSONB): o conteúdo da lista ou da tabela. O formato
  "texto" continua usando a coluna `texto`.

Revision ID: f4c6e8a0b213
Revises: e3b5d7f9a102
Create Date: 2026-10-05 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f4c6e8a0b213'
down_revision: Union[str, Sequence[str], None] = 'e3b5d7f9a102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('anotacao', sa.Column('formato', sa.String(length=10), nullable=False, server_default='texto'))
    op.add_column('anotacao', sa.Column('dados', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('anotacao', 'dados')
    op.drop_column('anotacao', 'formato')
