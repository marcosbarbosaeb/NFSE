"""IA do Claude dentro da Ana (2026.10.7)

`ia_chamada`: cada chamada à IA (tipo, resultado, tokens, tempo) — conta o
limite diário por pessoa e mostra o custo na Gestão. Sem RLS, como
`evento_uso`. `emissao.erro_explicacao`: a explicação da recusa, guardada
pra não pagar de novo ao reabrir a nota.

Revision ID: f2a4c6e8b0d1
Revises: e1c3d5f7a9b2
Create Date: 2026-10-10 02:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f2a4c6e8b0d1'
down_revision: Union[str, Sequence[str], None] = 'e1c3d5f7a9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ia_chamada',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('resultado', sa.String(length=12), nullable=False),
        sa.Column('modelo', sa.String(length=60), nullable=True),
        sa.Column('tokens_entrada', sa.Integer(), server_default='0', nullable=False),
        sa.Column('tokens_saida', sa.Integer(), server_default='0', nullable=False),
        sa.Column('milissegundos', sa.Integer(), server_default='0', nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ia_chamada_usuario_criado', 'ia_chamada', ['usuario_id', 'criado_em'])
    op.add_column('emissao', sa.Column('erro_explicacao', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('emissao', 'erro_explicacao')
    op.drop_index('ix_ia_chamada_usuario_criado', table_name='ia_chamada')
    op.drop_table('ia_chamada')
