"""Classificação lembrada do extrato (03/10/2026)

`regra_extrato`: o que a pessoa escolheu pra uma descrição do extrato
(receita de qual tomador, ou despesa de qual categoria) — na próxima
importação a mesma descrição já vem classificada. RLS.

Revision ID: f8c0e2a4b657
Revises: e7b9d1f3a546
Create Date: 2026-10-03 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f8c0e2a4b657'
down_revision: Union[str, Sequence[str], None] = 'e7b9d1f3a546'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'regra_extrato',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chave', sa.String(length=160), nullable=False),
        sa.Column('credito', sa.Boolean(), nullable=False),
        sa.Column(
            'prestador_tomador_id', postgresql.UUID(as_uuid=True),
            sa.ForeignKey('prestador_tomador.id', ondelete='CASCADE'), nullable=True,
        ),
        sa.Column('categoria', sa.String(length=100), nullable=True),
        sa.Column('tipo', sa.String(length=10), nullable=False, server_default='despesa'),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('prestador_id', 'chave', name='uq_regra_extrato_chave'),
        sa.CheckConstraint("tipo IN ('despesa', 'retirada')", name='ck_regra_extrato_tipo'),
    )
    op.execute("ALTER TABLE regra_extrato ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE regra_extrato FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY regra_extrato_isolamento_por_prestador ON regra_extrato
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS regra_extrato_isolamento_por_prestador ON regra_extrato;")
    op.drop_table('regra_extrato')
