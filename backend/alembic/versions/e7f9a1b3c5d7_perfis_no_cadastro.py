"""Perfis no cadastro (2026.10.7)

`prestador.perfis` (lista, o primeiro é o principal), `perfil_outro`,
`perfil_pulou`, `perfil_respondido_em`; tabela `perfil_busca` (profissões
buscadas que não bateram com nenhum perfil — só o texto). As empresas que já
existem ficam sem resposta: veem a pergunta uma vez ao entrar.

Revision ID: e7f9a1b3c5d7
Revises: d6e8f0a2b4c6
Create Date: 2026-10-10 05:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e7f9a1b3c5d7'
down_revision: Union[str, Sequence[str], None] = 'd6e8f0a2b4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador', sa.Column('perfis', postgresql.JSONB(), nullable=True))
    op.add_column('prestador', sa.Column('perfil_outro', sa.String(length=300), nullable=True))
    op.add_column('prestador', sa.Column('perfil_pulou', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('prestador', sa.Column('perfil_respondido_em', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'perfil_busca',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('texto', sa.String(length=80), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('perfil_busca')
    for c in ('perfil_respondido_em', 'perfil_pulou', 'perfil_outro', 'perfis'):
        op.drop_column('prestador', c)
