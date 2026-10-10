"""Gestão com usuários próprios (2026.10.7)

Tabela `gestor` (pelo e-mail do login) no lugar da lista ADMIN_EMAILS — que
continua valendo junto, como reserva. Já nasce com a conta do Marcos e com
quem estiver em ADMIN_EMAILS no momento da migração.

Revision ID: d6e8f0a2b4c6
Revises: c5d7e9f1a3b5
Create Date: 2026-10-10 05:00:00.000000
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd6e8f0a2b4c6'
down_revision: Union[str, Sequence[str], None] = 'c5d7e9f1a3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRIMEIRO = "marcosbarbosaeb@gmail.com"


def upgrade() -> None:
    op.create_table(
        'gestor',
        sa.Column('email', sa.String(length=254), primary_key=True),
        sa.Column('adicionado_por', sa.String(length=254), nullable=True),
        sa.Column('adicionado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    emails = {PRIMEIRO}
    emails |= {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if "@" in e}
    tabela = sa.table('gestor', sa.column('email', sa.String), sa.column('adicionado_por', sa.String))
    op.bulk_insert(tabela, [{"email": e, "adicionado_por": "migração 2026.10.7"} for e in sorted(emails)])


def downgrade() -> None:
    op.drop_table('gestor')
