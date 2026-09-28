"""indices_desempenho

Revisão de desempenho (28/09/2026): `envio` e `pagamento_recebido` só tinham
a chave primária — toda consulta da Visão geral / NFS-e / Financeiro fazia
varredura completa (inclusive o filtro da RLS por prestador_id).

Revision ID: c5a1e9d3f720
Revises: b8f4d2a6c913
Create Date: 2026-09-29 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c5a1e9d3f720'
down_revision: Union[str, Sequence[str], None] = 'b8f4d2a6c913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDICES = [
    ("ix_envio_emissao_criado", "envio", ["emissao_id", "criado_em"]),
    ("ix_pagamento_vinculo_competencia", "pagamento_recebido", ["prestador_tomador_id", "competencia"]),
    ("ix_pagamento_prestador_competencia", "pagamento_recebido", ["prestador_id", "competencia"]),
    ("ix_emissao_prestador_competencia", "emissao", ["prestador_id", "competencia"]),
]


def upgrade() -> None:
    for nome, tabela, colunas in _INDICES:
        op.create_index(nome, tabela, colunas, if_not_exists=True)


def downgrade() -> None:
    for nome, tabela, _ in _INDICES:
        op.drop_index(nome, table_name=tabela, if_exists=True)
