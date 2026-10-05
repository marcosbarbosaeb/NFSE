"""Anotações: em que telas cada uma aparece (05/10/2026)

"Na visão geral, falta a opção de criar anotação." A nota passa a dizer onde
aparece — `anotacao.telas` (JSONB): ["financeiro"], ["visao_geral"] ou as
duas. As que já existiam continuam só no Financeiro, onde foram criadas
(o valor padrão da coluna cuida disso: UPDATE em migração não enxerga
linhas por causa da RLS).

Revision ID: d8a0c2e4f657
Revises: c7f9b1d3e546
Create Date: 2026-10-05 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8a0c2e4f657"
down_revision: Union[str, Sequence[str], None] = "c7f9b1d3e546"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "anotacao",
        sa.Column(
            "telas", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'[\"financeiro\"]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("anotacao", "telas")
