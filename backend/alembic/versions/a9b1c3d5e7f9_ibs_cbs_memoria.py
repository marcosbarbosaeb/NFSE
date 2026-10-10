"""IBS e CBS: o que a empresa escolhe e a memória da classificação (2026.10.7)

`prestador.regime_ibs_cbs`: como a empresa do Simples recolhe IBS e CBS
(1 = tudo pelo Simples, 2 = CBS pelo Simples e IBS pelo regime regular,
3 = tudo pelo regime regular — `regApIBSCBSSN` da NT 009), com o semestre em
que vale (`regime_ibs_cbs_desde`, "2027-01") e a data da última confirmação
(`ibs_cbs_confirmado_em`, pro aviso antes da virada do semestre).
`prestador_tomador.cclass_trib` / `cind_op`: classificação tributária e
código indicador da operação do serviço, guardados como memória. Ainda NÃO
vão para o XML: o esquema da NT 009 não foi publicado (raio-x, seção 15).

Revision ID: a9b1c3d5e7f9
Revises: f8a0b2c4d6e8
Create Date: 2026-10-10 08:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a9b1c3d5e7f9'
down_revision: Union[str, Sequence[str], None] = 'f8a0b2c4d6e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador', sa.Column('regime_ibs_cbs', sa.String(1), nullable=True))
    op.add_column('prestador', sa.Column('regime_ibs_cbs_desde', sa.String(7), nullable=True))
    op.add_column('prestador', sa.Column('ibs_cbs_confirmado_em', sa.Date(), nullable=True))
    op.add_column('prestador_tomador', sa.Column('cclass_trib', sa.String(6), nullable=True))
    op.add_column('prestador_tomador', sa.Column('cind_op', sa.String(6), nullable=True))


def downgrade() -> None:
    op.drop_column('prestador_tomador', 'cind_op')
    op.drop_column('prestador_tomador', 'cclass_trib')
    op.drop_column('prestador', 'ibs_cbs_confirmado_em')
    op.drop_column('prestador', 'regime_ibs_cbs_desde')
    op.drop_column('prestador', 'regime_ibs_cbs')
