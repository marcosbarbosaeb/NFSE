"""Lançamentos do extrato e conciliação (05/10/2026)

- `pagamento_recebido.mes_inteiro`: marca o pagamento ANTIGO (planilha,
  conciliação, baixas de antes da baixa por nota) que vale pro mês inteiro
  do tomador. Recebimento novo sem nota passa a ser só isso — um recebimento
  sem nota — mesmo que o tomador tenha outra nota no mês (Amazon e Mercado
  Livre pagam antes da nota).
- `lancamento_bancario`: toda linha do extrato importado fica guardada,
  classificada ou não, pra tela de conciliação. RLS.
- `usuario.preferencias`: disposição dos cards do Financeiro.

Revision ID: b0e2a4c6d879
Revises: a9d1f3b5c768
Create Date: 2026-10-05 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b0e2a4c6d879'
down_revision: Union[str, Sequence[str], None] = 'a9d1f3b5c768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pagamento_recebido', sa.Column('mes_inteiro', sa.Boolean(), nullable=False, server_default='false'))
    op.execute("UPDATE pagamento_recebido SET mes_inteiro = true WHERE emissao_id IS NULL")

    op.create_table(
        'lancamento_bancario',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data', sa.Date(), nullable=True),
        sa.Column('descricao', sa.String(length=300), nullable=False),
        sa.Column('valor', sa.Numeric(14, 2), nullable=False),
        sa.Column('credito', sa.Boolean(), nullable=False),
        sa.Column('chave', sa.String(length=160), nullable=False, server_default=''),
        sa.Column('seq', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pendente'),
        sa.Column('pagamento_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pagamento_recebido.id', ondelete='SET NULL'), nullable=True),
        sa.Column('despesa_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('despesa.id', ondelete='SET NULL'), nullable=True),
        sa.Column('arquivo', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pendente', 'conciliado', 'ignorado')", name='ck_lancamento_bancario_status'),
    )
    op.create_index('ix_lancamento_bancario_prestador', 'lancamento_bancario', ['prestador_id', 'status'])
    op.execute("ALTER TABLE lancamento_bancario ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE lancamento_bancario FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY lancamento_bancario_isolamento_por_prestador ON lancamento_bancario
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
    """)


    # Preferências da pessoa (ordem e cards abertos/fechados do Financeiro).
    op.add_column('usuario', sa.Column('preferencias', postgresql.JSONB(), nullable=False, server_default='{}'))


def downgrade() -> None:
    op.drop_column('usuario', 'preferencias')
    op.execute("DROP POLICY IF EXISTS lancamento_bancario_isolamento_por_prestador ON lancamento_bancario;")
    op.drop_table('lancamento_bancario')
    op.drop_column('pagamento_recebido', 'mes_inteiro')
