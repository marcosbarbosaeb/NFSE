"""Contador com permissões e liberação de acesso pela Gestão (06/10/2026)

- `acesso_contador`: a empresa autoriza um contador (por e-mail) e escolhe o
  que ele pode fazer. `registro_contador`: o que ele fez (só o título).
  As duas sem RLS, como `usuario_prestador`.
- `assinatura.liberado_*`: a Gestão libera o uso de uma empresa sem
  assinatura (até uma data ou sem prazo).

Revision ID: b2e4a6c8d091
Revises: a1d3f5b7c980
Create Date: 2026-10-06 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b2e4a6c8d091'
down_revision: Union[str, Sequence[str], None] = 'a1d3f5b7c980'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assinatura', sa.Column('liberado_ate', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assinatura', sa.Column('liberado_sempre', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('assinatura', sa.Column('liberado_obs', sa.String(length=200), nullable=True))
    op.create_table(
        'acesso_contador',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=True),
        sa.Column('permissoes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='pendente'),
        sa.Column('convidado_por', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('aceito_em', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('prestador_id', 'email', name='uq_acesso_contador_empresa_email'),
        sa.CheckConstraint("status IN ('pendente', 'ativo')", name='ck_acesso_contador_status'),
    )
    op.create_index('ix_acesso_contador_usuario', 'acesso_contador', ['usuario_id'])
    op.create_index('ix_acesso_contador_email', 'acesso_contador', ['email'])
    op.create_table(
        'registro_contador',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('acao', sa.String(length=200), nullable=False),
        sa.Column('quando', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_registro_contador_empresa', 'registro_contador', ['prestador_id', 'quando'])


def downgrade() -> None:
    op.drop_table('registro_contador')
    op.drop_table('acesso_contador')
    op.drop_column('assinatura', 'liberado_obs')
    op.drop_column('assinatura', 'liberado_sempre')
    op.drop_column('assinatura', 'liberado_ate')
