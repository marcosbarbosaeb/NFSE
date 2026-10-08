"""WhatsApp de quem se cadastra e pedido de liberação (08/10/2026)

- `usuario.telefone`: o WhatsApp pedido no cadastro (a Gestão mostrava o
  telefone da Receita, que em muita empresa é o do contador).
- `assinatura.liberacao_pedida_em`: depois do teste, enquanto não há
  cobrança, quem autoriza o uso é a administração — a pessoa pede por aqui.

Revision ID: a7d9f1b3c5e6
Revises: f6c8e0a2b4d5
Create Date: 2026-10-08 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7d9f1b3c5e6'
down_revision: Union[str, Sequence[str], None] = 'f6c8e0a2b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuario', sa.Column('telefone', sa.String(length=20), nullable=True))
    op.add_column('assinatura', sa.Column('liberacao_pedida_em', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('assinatura', 'liberacao_pedida_em')
    op.drop_column('usuario', 'telefone')
