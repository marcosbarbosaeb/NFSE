"""Conta de teste (01/10/2026)

Começa em branco como um usuário novo, mas as notas saem só em homologação
(sem valor fiscal) e os e-mails de nota vão só pra quem testa. Pode repetir
o CNPJ de uma conta real — o CNPJ passa a ser único só entre as contas reais.

Revision ID: d6a8c0e2f435
Revises: c5f7a9b1d324
Create Date: 2026-10-01 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd6a8c0e2f435'
down_revision: Union[str, Sequence[str], None] = 'c5f7a9b1d324'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador', sa.Column('modo_teste', sa.Boolean(), nullable=False, server_default='false'))
    op.execute("ALTER TABLE prestador DROP CONSTRAINT IF EXISTS prestador_cpf_cnpj_key")
    op.execute("CREATE UNIQUE INDEX uq_prestador_cnpj_real ON prestador (cpf_cnpj) WHERE modo_teste = false")


def downgrade() -> None:
    op.execute("DELETE FROM prestador WHERE modo_teste = true")
    op.execute("DROP INDEX IF EXISTS uq_prestador_cnpj_real")
    op.create_unique_constraint('prestador_cpf_cnpj_key', 'prestador', ['cpf_cnpj'])
    op.drop_column('prestador', 'modo_teste')
