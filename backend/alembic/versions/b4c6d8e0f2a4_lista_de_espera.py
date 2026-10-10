"""Lista de espera do cadastro (2026.10.7)

Quem não pôde criar conta (cidade fora do Emissor Nacional ou regime não
atendido) deixa e-mail, WhatsApp e CNPJ. Sem RLS: é antes de existir conta.

Revision ID: b4c6d8e0f2a4
Revises: a3b5c7d9e1f3
Create Date: 2026-10-10 04:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b4c6d8e0f2a4'
down_revision: Union[str, Sequence[str], None] = 'a3b5c7d9e1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lista_espera',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('whatsapp', sa.String(length=20), nullable=True),
        sa.Column('cnpj', sa.String(length=14), nullable=False),
        sa.Column('razao_social', sa.String(length=300), nullable=True),
        sa.Column('cod_municipio', sa.String(length=7), nullable=True),
        sa.Column('cidade', sa.String(length=120), nullable=True),
        sa.Column('motivo', sa.String(length=20), nullable=False),
        sa.Column('regime', sa.String(length=1), nullable=True),
        sa.Column('avisado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('cnpj', 'motivo', name='uq_lista_espera_cnpj_motivo'),
    )


def downgrade() -> None:
    op.drop_table('lista_espera')
