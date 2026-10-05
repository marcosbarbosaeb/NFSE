"""Contas recorrentes com pagamento agendado e anotações livres (05/10/2026)

- `despesa_recorrente.agendado_ate` (AAAA-MM, inclusive): a conta já está
  paga/agendada até aquele mês — o lançamento de cada mês nasce ticado
  ("a contabilidade está agendada até dezembro, só pago de novo em janeiro").
- `anotacao`: abas/notas que a pessoa cria no Financeiro pra deixar
  registrado o que quiser (controle de recarga de telefone etc.). RLS.

Revision ID: e3b5d7f9a102
Revises: d2a4c6e8f091
Create Date: 2026-10-05 10:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e3b5d7f9a102'
down_revision: Union[str, Sequence[str], None] = 'd2a4c6e8f091'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('despesa_recorrente', sa.Column('agendado_ate', sa.String(length=7), nullable=True))

    op.create_table(
        'anotacao',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('titulo', sa.String(length=80), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False, server_default=''),
        sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_anotacao_prestador', 'anotacao', ['prestador_id', 'ordem'])
    op.execute("ALTER TABLE anotacao ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE anotacao FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY anotacao_isolamento_por_prestador ON anotacao
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS anotacao_isolamento_por_prestador ON anotacao;")
    op.drop_table('anotacao')
    op.drop_column('despesa_recorrente', 'agendado_ate')
