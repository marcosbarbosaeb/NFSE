"""Notas importadas fora do "uma nota por tomador e mês" (01/10/2026)

No histórico do Emissor Nacional há meses com mais de uma nota pro mesmo
tomador (duas campanhas, nota complementar). A regra de uma nota ativa por
vínculo+competência existe pra impedir a Ana de gerar duplicada — as
importadas são fato consumado (a chave de acesso já é única), então ficam
fora do índice.

Revision ID: b4d6e8f0a213
Revises: a3e5b7c9d102
Create Date: 2026-10-01 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b4d6e8f0a213'
down_revision: Union[str, Sequence[str], None] = 'a3e5b7c9d102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_emissao_vinculo_competencia_ativa")
    op.execute(
        "CREATE UNIQUE INDEX uq_emissao_vinculo_competencia_ativa ON emissao "
        "(prestador_tomador_id, competencia, COALESCE(tomador_documento, '')) "
        "WHERE estado != 'cancelada' AND origem = 'ana'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_emissao_vinculo_competencia_ativa")
    op.execute(
        "CREATE UNIQUE INDEX uq_emissao_vinculo_competencia_ativa ON emissao "
        "(prestador_tomador_id, competencia, COALESCE(tomador_documento, '')) WHERE estado != 'cancelada'"
    )
