"""Link de assinatura do calendário e Pasta do mês (08/10/2026)

- `assinatura_agenda`: token do link .ics por empresa. Sem RLS (busca pelo token).
- `pasta_pedido`, `pasta_arquivo`, `pasta_marca`, `pasta_mensagem`, `pasta_leitura`:
  o que o contador precisa todo mês, os arquivos, as marcações e a conversa. RLS.

Revision ID: d0b2c4e6f8a1
Revises: c9f1b3d5e7a8
Create Date: 2026-10-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd0b2c4e6f8a1'
down_revision: Union[str, Sequence[str], None] = 'c9f1b3d5e7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
_COM_RLS = ("pasta_pedido", "pasta_arquivo", "pasta_marca", "pasta_mensagem", "pasta_leitura")


def _empresa():
    return sa.Column('prestador_id', UUID, sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False)


def _usuario(nome, ondelete='SET NULL', nullable=True):
    return sa.Column(nome, UUID, sa.ForeignKey('usuario.id', ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        'assinatura_agenda',
        sa.Column('prestador_id', UUID, sa.ForeignKey('prestador.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'pasta_pedido',
        sa.Column('id', UUID, primary_key=True),
        _empresa(),
        sa.Column('titulo', sa.String(120), nullable=False),
        sa.Column('descricao', sa.String(300)),
        sa.Column('tipo', sa.String(10), nullable=False, server_default='arquivo'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('ordem', sa.SmallInteger(), nullable=False, server_default='0'),
        _usuario('criado_por'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('arquivo', 'extrato')", name='ck_pasta_pedido_tipo'),
    )
    op.create_table(
        'pasta_arquivo',
        sa.Column('id', UUID, primary_key=True),
        _empresa(),
        sa.Column('competencia', sa.String(7), nullable=False),
        sa.Column('pedido_id', UUID, sa.ForeignKey('pasta_pedido.id', ondelete='SET NULL')),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('tipo_mime', sa.String(100), nullable=False),
        sa.Column('tamanho', sa.BigInteger(), nullable=False),
        sa.Column('conteudo', sa.LargeBinary(), nullable=False),
        _usuario('enviado_por'),
        sa.Column('papel', sa.String(10), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_pasta_arquivo_mes', 'pasta_arquivo', ['prestador_id', 'competencia'])
    op.create_table(
        'pasta_marca',
        sa.Column('id', UUID, primary_key=True),
        _empresa(),
        sa.Column('pedido_id', UUID, sa.ForeignKey('pasta_pedido.id', ondelete='CASCADE'), nullable=False),
        sa.Column('competencia', sa.String(7), nullable=False),
        sa.Column('situacao', sa.String(10), nullable=False),
        _usuario('por'),
        sa.Column('em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('pedido_id', 'competencia', name='uq_pasta_marca'),
        sa.CheckConstraint("situacao IN ('nao_tem', 'conferido')", name='ck_pasta_marca_situacao'),
    )
    op.create_table(
        'pasta_mensagem',
        sa.Column('id', UUID, primary_key=True),
        _empresa(),
        sa.Column('competencia', sa.String(7)),
        _usuario('autor'),
        sa.Column('autor_nome', sa.String(200), nullable=False),
        sa.Column('papel', sa.String(10), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_pasta_mensagem_empresa', 'pasta_mensagem', ['prestador_id', 'criado_em'])
    op.create_table(
        'pasta_leitura',
        sa.Column('prestador_id', UUID, sa.ForeignKey('prestador.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('usuario_id', UUID, sa.ForeignKey('usuario.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('lido_em', sa.DateTime(timezone=True), nullable=False),
    )
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
    op.drop_table('pasta_leitura')
    op.drop_index('ix_pasta_mensagem_empresa', table_name='pasta_mensagem')
    op.drop_table('pasta_mensagem')
    op.drop_table('pasta_marca')
    op.drop_index('ix_pasta_arquivo_mes', table_name='pasta_arquivo')
    op.drop_table('pasta_arquivo')
    op.drop_table('pasta_pedido')
    op.drop_table('assinatura_agenda')
