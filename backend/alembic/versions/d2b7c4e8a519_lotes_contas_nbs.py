"""lotes_contas_nbs

Pedido do Marcos (29/09/2026), comparando com o MandaNotas:
- Código NBS e "intermediário" no serviço de cada tomador
  (`prestador_tomador.cod_nbs`, `incluir_intermediario`).
- Ações em lote em segundo plano (enviar todas as notas por e-mail,
  assinar, enviar à prefeitura): `lote_acao`, com progresso e falhas. RLS
  por prestador.
- Vários CNPJs no mesmo login: `usuario_prestador` (sem RLS — é consultada
  antes de saber qual empresa está ativa, igual `usuario`). Preenchida com o
  vínculo que cada usuário já tem.
- Sessões no servidor (dispositivos conectados, sair de um aparelho, trocar
  a senha derruba os outros): `sessao`.
- Login por código no e-mail: campos em `usuario`. Nome de exibição.
- Nome fantasia da empresa (dados do emitente editáveis).

Revision ID: d2b7c4e8a519
Revises: c5a1e9d3f720
Create Date: 2026-09-29 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd2b7c4e8a519'
down_revision: Union[str, Sequence[str], None] = 'c5a1e9d3f720'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('cod_nbs', sa.String(length=12), nullable=True))
    op.add_column('prestador_tomador', sa.Column('incluir_intermediario', sa.Boolean(), nullable=False, server_default='false'))
    # Últimas escolhas de envio ao fornecedor (canal e texto do WhatsApp).
    op.add_column('prestador_tomador', sa.Column('envio_canal', sa.String(length=10), nullable=True))
    op.add_column('prestador_tomador', sa.Column('whatsapp_mensagem', sa.Text(), nullable=True))
    # Como o tomador recebe a nota (envio_canal: email | whatsapp | portal |
    # nenhum) e o endereço do portal dele, quando for "portal".
    op.add_column('prestador_tomador', sa.Column('portal_url', sa.String(length=400), nullable=True))
    # E-mails gerais (contador, a própria pessoa) com texto padrão próprio.
    op.add_column('prestador', sa.Column('email_geral_para', sa.String(length=400), nullable=True))
    op.add_column('prestador', sa.Column('email_geral_assunto', sa.String(length=300), nullable=True))
    op.add_column('prestador', sa.Column('email_geral_mensagem', sa.Text(), nullable=True))
    op.add_column('prestador', sa.Column('email_geral_anexos', sa.String(length=10), nullable=True))
    op.add_column('prestador', sa.Column('nome_fantasia', sa.String(length=200), nullable=True))
    op.add_column('usuario', sa.Column('nome', sa.String(length=120), nullable=True))
    op.add_column('usuario', sa.Column('login_codigo_hash', sa.String(length=128), nullable=True))
    op.add_column('usuario', sa.Column('login_codigo_expira_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('usuario', sa.Column('login_codigo_tentativas', sa.SmallInteger(), nullable=False, server_default='0'))

    # Canal novo: cópia pros e-mails gerais (contador etc.) — não conta como
    # "enviada ao fornecedor".
    op.drop_constraint('ck_envio_canal', 'envio', type_='check')
    op.create_check_constraint(
        'ck_envio_canal', 'envio',
        "canal IN ('download','email','whatsapp','direto_fornecedor','mensagem_pronta','email_geral')",
    )

    op.create_table(
        'usuario_prestador',
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_usuario_prestador_prestador', 'usuario_prestador', ['prestador_id'])
    op.execute("INSERT INTO usuario_prestador (usuario_id, prestador_id) SELECT id, prestador_id FROM usuario ON CONFLICT DO NOTHING")

    op.create_table(
        'sessao',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ultimo_acesso', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('revogada_em', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_sessao_usuario', 'sessao', ['usuario_id'])

    op.create_table(
        'lote_acao',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('acao', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='fila'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('feitos', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('falhas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emissao_ids', postgresql.JSONB(), nullable=False),
        sa.Column('erros', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('concluido_em', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_lote_acao_prestador', 'lote_acao', ['prestador_id', 'criado_em'])
    op.execute("ALTER TABLE lote_acao ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE lote_acao FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY lote_acao_isolamento_por_prestador ON lote_acao
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS lote_acao_isolamento_por_prestador ON lote_acao;")
    op.drop_constraint('ck_envio_canal', 'envio', type_='check')
    op.create_check_constraint(
        'ck_envio_canal', 'envio', "canal IN ('download','email','whatsapp','direto_fornecedor','mensagem_pronta')",
    )
    op.drop_index('ix_lote_acao_prestador', table_name='lote_acao')
    op.drop_table('lote_acao')
    op.drop_index('ix_sessao_usuario', table_name='sessao')
    op.drop_table('sessao')
    op.drop_index('ix_usuario_prestador_prestador', table_name='usuario_prestador')
    op.drop_table('usuario_prestador')
    for coluna in ('login_codigo_tentativas', 'login_codigo_expira_em', 'login_codigo_hash', 'nome'):
        op.drop_column('usuario', coluna)
    op.drop_column('prestador', 'nome_fantasia')
    for coluna in ('email_geral_anexos', 'email_geral_mensagem', 'email_geral_assunto', 'email_geral_para'):
        op.drop_column('prestador', coluna)
    op.drop_column('prestador_tomador', 'portal_url')
    op.drop_column('prestador_tomador', 'whatsapp_mensagem')
    op.drop_column('prestador_tomador', 'envio_canal')
    op.drop_column('prestador_tomador', 'incluir_intermediario')
    op.drop_column('prestador_tomador', 'cod_nbs')
