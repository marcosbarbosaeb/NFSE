"""Parceiras de indicação com comissão (06/10/2026)

"Tenho algumas pessoas que poderiam ser parceiras na indicação (uma
contadora e uma economista)... pagar uma porcentagem de cada assinatura
ativa pra essas pessoas": cadastro da parceira, quem ela indicou e a
comissão de cada mensalidade paga. Tabelas da plataforma, sem RLS.

Revision ID: a1d3f5b7c980
Revises: f0c2e4a6b879
Create Date: 2026-10-06 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1d3f5b7c980'
down_revision: Union[str, Sequence[str], None] = 'f0c2e4a6b879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'parceiro',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('codigo', sa.String(length=20), nullable=False, unique=True),
        sa.Column('token_painel', sa.String(length=64), nullable=False, unique=True),
        sa.Column('comissao_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('desconto_1_mes_pct', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('comissao_pct >= 0 AND comissao_pct <= 100', name='ck_parceiro_comissao'),
        sa.CheckConstraint('desconto_1_mes_pct >= 0 AND desconto_1_mes_pct <= 100', name='ck_parceiro_desconto'),
    )
    op.create_table(
        'indicacao_parceiro',
        sa.Column('indicado_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('parceiro_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parceiro.id', ondelete='CASCADE'), nullable=False),
        sa.Column('indicado_nome', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='trial'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_indicacao_parceiro_parceiro', 'indicacao_parceiro', ['parceiro_id'])
    op.create_table(
        'comissao_parceiro',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parceiro_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parceiro.id', ondelete='CASCADE'), nullable=False),
        sa.Column('indicado_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='SET NULL'), nullable=True),
        sa.Column('indicado_nome', sa.String(length=200), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(length=80), nullable=False, unique=True),
        sa.Column('competencia', sa.String(length=7), nullable=False),
        sa.Column('valor_pago', sa.Numeric(12, 2), nullable=False),
        sa.Column('comissao_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('valor', sa.Numeric(12, 2), nullable=False),
        sa.Column('pago_em', sa.Date(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_comissao_parceiro_parceiro', 'comissao_parceiro', ['parceiro_id', 'competencia'])


def downgrade() -> None:
    op.drop_table('comissao_parceiro')
    op.drop_table('indicacao_parceiro')
    op.drop_table('parceiro')
