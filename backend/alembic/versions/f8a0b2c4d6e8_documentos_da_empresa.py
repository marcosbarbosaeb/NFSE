"""Documentos da empresa (2026.10.7)

`documento_empresa` (arquivo no banco, sem cifragem, 15 MB por arquivo e
100 MB por empresa — limites no serviço) e `documento_acesso` (quem abriu ou
baixou). As duas com RLS por empresa, como a pasta do mês.

Revision ID: f8a0b2c4d6e8
Revises: e7f9a1b3c5d7
Create Date: 2026-10-10 06:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f8a0b2c4d6e8'
down_revision: Union[str, Sequence[str], None] = 'e7f9a1b3c5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
_COM_RLS = ("documento_empresa", "documento_acesso")


def upgrade() -> None:
    op.create_table(
        'documento_empresa',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prestador_id', UUID, sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('nome_arquivo', sa.String(length=200), nullable=False),
        sa.Column('tipo_mime', sa.String(length=100), nullable=False),
        sa.Column('tamanho', sa.BigInteger(), nullable=False),
        sa.Column('conteudo', sa.LargeBinary(), nullable=False),
        sa.Column('validade', sa.Date(), nullable=True),
        sa.Column('enviado_por', UUID, sa.ForeignKey('usuario.id', ondelete='SET NULL'), nullable=True),
        sa.Column('enviado_por_email', sa.String(length=254), nullable=True),
        sa.Column('papel', sa.String(length=10), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('substituido_em', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_documento_empresa_prestador', 'documento_empresa', ['prestador_id'])
    op.create_table(
        'documento_acesso',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prestador_id', UUID, sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('documento_id', UUID, sa.ForeignKey('documento_empresa.id', ondelete='CASCADE'), nullable=False),
        sa.Column('usuario_id', UUID, sa.ForeignKey('usuario.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email', sa.String(length=254), nullable=True),
        sa.Column('papel', sa.String(length=10), nullable=False),
        sa.Column('acao', sa.String(length=10), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_documento_acesso_doc', 'documento_acesso', ['documento_id'])
    for tabela in _COM_RLS:
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY {tabela}_isolamento_por_prestador ON {tabela}
                USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
                WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
        """)


def downgrade() -> None:
    for tabela in reversed(_COM_RLS):
        op.execute(f"DROP POLICY IF EXISTS {tabela}_isolamento_por_prestador ON {tabela};")
    op.drop_index('ix_documento_acesso_doc', table_name='documento_acesso')
    op.drop_table('documento_acesso')
    op.drop_index('ix_documento_empresa_prestador', table_name='documento_empresa')
    op.drop_table('documento_empresa')
