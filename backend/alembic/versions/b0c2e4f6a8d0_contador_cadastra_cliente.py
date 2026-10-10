"""Contador cadastra cliente e convida o dono (2026.10.7)

`acesso_contador.criado_pelo_contador`: a empresa foi cadastrada pelo próprio
contador (conta pros números de cobrança por cliente). `convite_dono`: o
convite para o dono da empresa criar o login dele (ou juntar a empresa ao login
que já tem). Sem RLS, como `acesso_contador`: é lido pelo token antes de haver
empresa ativa.

Revision ID: b0c2e4f6a8d0
Revises: a9b1c3d5e7f9
Create Date: 2026-10-10 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b0c2e4f6a8d0'
down_revision: Union[str, Sequence[str], None] = 'a9b1c3d5e7f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('acesso_contador', sa.Column('criado_pelo_contador', sa.Boolean(), server_default='false', nullable=False))
    op.create_table(
        'convite_dono',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(200), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('criado_por', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='SET NULL')),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expira_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('aceito_em', sa.DateTime(timezone=True)),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='SET NULL')),
    )
    op.create_index('ix_convite_dono_prestador', 'convite_dono', ['prestador_id'])


def downgrade() -> None:
    op.drop_index('ix_convite_dono_prestador', table_name='convite_dono')
    op.drop_table('convite_dono')
    op.drop_column('acesso_contador', 'criado_pelo_contador')
