"""email_modelo_indicacao

Pedidos do Marcos (28/09/2026):
- "É importante que os campos dessa mensagem [e-mail da nota] sejam
  configuráveis. Tem tomador que pede que o assunto seja específico e
  precisamos enviar em XML e em PDF": modelo de e-mail padrão no prestador
  (assunto, texto, anexos) e, por tomador, assunto/texto/anexos/cópia que
  sobrescrevem o padrão. Tudo nulo = texto de sempre.
- Programa de indicação: "10% para cada 1 [assinatura ativa] até 100%",
  cobrado pelo Stripe.
  * `codigo_indicacao`: código público de cada prestador. SEM RLS de
    propósito — quem se cadastra com um código precisa achar o dono dele
    antes de ter conta; a tabela só tem código -> id.
  * `indicacao`: quem indicou quem e o status da assinatura do indicado.
    RLS deixa ver a linha tanto o indicador quanto o indicado (o webhook do
    Stripe atualiza no contexto do indicado; a tela lê no do indicador).
- "Troque isso de produção e homologação. Deixe a opção no final de gerar
  rascunho ou gerar e assinar": `prestador.tp_amb_padrao` (1 = produção).
  * `assinatura.desconto_indicacao_pct`: o desconto que está aplicado no
    Stripe agora (pra só mexer na assinatura quando mudar).

Revision ID: a3d9e7c51b20
Revises: e5b2c8f1a310
Create Date: 2026-09-28 23:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a3d9e7c51b20'
down_revision: Union[str, Sequence[str], None] = 'e5b2c8f1a310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('email_assunto', sa.String(length=300), nullable=True))
    op.add_column('prestador_tomador', sa.Column('email_mensagem', sa.Text(), nullable=True))
    op.add_column('prestador_tomador', sa.Column('email_anexos', sa.String(length=10), nullable=True))
    op.add_column('prestador_tomador', sa.Column('email_copia', sa.String(length=400), nullable=True))
    op.add_column('prestador', sa.Column('email_assunto_padrao', sa.String(length=300), nullable=True))
    op.add_column('prestador', sa.Column('email_mensagem_padrao', sa.Text(), nullable=True))
    op.add_column('prestador', sa.Column('email_anexos_padrao', sa.String(length=10), nullable=True))
    # "Troque isso de produção e homologação" (28/09/2026): o ambiente sai da
    # tela de gerar nota e vira uma configuração da conta (padrão: produção).
    op.add_column('prestador', sa.Column('tp_amb_padrao', sa.String(length=1), nullable=False, server_default='1'))
    op.add_column('assinatura', sa.Column('desconto_indicacao_pct', sa.SmallInteger(), nullable=False, server_default='0'))

    op.create_table(
        'codigo_indicacao',
        sa.Column('codigo', sa.String(length=20), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'indicacao',
        sa.Column('indicado_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('indicador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('indicado_nome', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='trial'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_indicacao_indicador', 'indicacao', ['indicador_id'])
    op.execute("ALTER TABLE indicacao ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE indicacao FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY indicacao_indicador_ou_indicado ON indicacao
            USING (
                indicador_id = current_setting('app.current_prestador_id', true)::uuid
                OR indicado_id = current_setting('app.current_prestador_id', true)::uuid
            )
            WITH CHECK (
                indicador_id = current_setting('app.current_prestador_id', true)::uuid
                OR indicado_id = current_setting('app.current_prestador_id', true)::uuid
            );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS indicacao_indicador_ou_indicado ON indicacao;")
    op.drop_index('ix_indicacao_indicador', table_name='indicacao')
    op.drop_table('indicacao')
    op.drop_table('codigo_indicacao')
    op.drop_column('assinatura', 'desconto_indicacao_pct')
    op.drop_column('prestador', 'tp_amb_padrao')
    for coluna in ('email_anexos_padrao', 'email_mensagem_padrao', 'email_assunto_padrao'):
        op.drop_column('prestador', coluna)
    for coluna in ('email_copia', 'email_anexos', 'email_mensagem', 'email_assunto'):
        op.drop_column('prestador_tomador', coluna)
