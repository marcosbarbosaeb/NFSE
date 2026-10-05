"""Formas de envio por tomador, destinatários com e-mail próprio e lote completo (05/10/2026)

- `prestador_tomador.envio_formas` (JSONB): as formas de envio padrão do
  tomador — pode ser mais de uma (e-mail + baixar o PDF ao finalizar...).
  Nulo = o que estava em `envio_canal` (que continua guardando a principal).
- `prestador_tomador.email_extras` (JSONB): outros destinatários (contador,
  financeiro...) que recebem a nota num e-mail próprio, com assunto e texto
  deles.
- `prestador_tomador.descricao_meses_atras`: o mês que aparece na descrição
  da nota quando não é o da própria nota (1 = mês anterior, 2 = dois meses
  antes...).
- `assinatura.plano`: o plano contratado (emissor | financeiro | ambos) —
  é ele que define os módulos da empresa quando há assinatura paga.
- `lote_acao.opcoes` / `lote_acao.relatorio` (JSONB): os passos do lote
  "completo" (assinar, prefeitura, e-mail) e o que aconteceu em cada um —
  é o relatório que a pessoa vê quando volta.
- `lote_fila`: lotes que ainda estão rodando. SEM RLS de propósito: é lida
  quando o servidor sobe (sem empresa ativa) pra retomar o que um reinício
  interrompeu. Só guarda os ids.

Revision ID: a5d7f9b1c324
Revises: f4c6e8a0b213
Create Date: 2026-10-05 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a5d7f9b1c324'
down_revision: Union[str, Sequence[str], None] = 'f4c6e8a0b213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column('prestador_tomador', sa.Column('envio_formas', jsonb, nullable=True))
    op.add_column('prestador_tomador', sa.Column('email_extras', jsonb, nullable=True))
    op.add_column('prestador_tomador', sa.Column('descricao_meses_atras', sa.SmallInteger(), nullable=False, server_default='0'))
    op.add_column('assinatura', sa.Column('plano', sa.String(length=12), nullable=True))
    op.add_column('lote_acao', sa.Column('opcoes', jsonb, nullable=True))
    op.add_column('lote_acao', sa.Column('relatorio', jsonb, nullable=True))
    op.create_table(
        'lote_fila',
        sa.Column('lote_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('lote_acao.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('base_url', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('lote_fila')
    op.drop_column('lote_acao', 'relatorio')
    op.drop_column('lote_acao', 'opcoes')
    op.drop_column('assinatura', 'plano')
    op.drop_column('prestador_tomador', 'descricao_meses_atras')
    op.drop_column('prestador_tomador', 'email_extras')
    op.drop_column('prestador_tomador', 'envio_formas')
