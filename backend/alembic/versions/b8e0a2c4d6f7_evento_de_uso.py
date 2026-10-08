"""Eventos de uso da plataforma (08/10/2026)

"Você conseguiria rastrear a atividade do usuário na plataforma, de forma
futura sugerir melhorias?" — só o NOME da tela/ação e quem fez; nunca o
conteúdo. Sem RLS e sem chave estrangeira (é estatística da plataforma,
lida só pela Gestão; apagada sozinha depois de 180 dias).

Revision ID: b8e0a2c4d6f7
Revises: a7d9f1b3c5e6
Create Date: 2026-10-08 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b8e0a2c4d6f7'
down_revision: Union[str, Sequence[str], None] = 'a7d9f1b3c5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evento_uso',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tipo', sa.String(length=8), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('detalhe', sa.String(length=60), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_evento_uso_criado', 'evento_uso', ['criado_em'])
    op.create_index('ix_evento_uso_tipo_nome', 'evento_uso', ['tipo', 'nome'])


def downgrade() -> None:
    op.drop_index('ix_evento_uso_tipo_nome', table_name='evento_uso')
    op.drop_index('ix_evento_uso_criado', table_name='evento_uso')
    op.drop_table('evento_uso')
