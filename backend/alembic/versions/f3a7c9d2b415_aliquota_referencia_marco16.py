"""aliquota_referencia_marco16

Marco 16, item 5 — depois de pesquisar a viabilidade de uma "aba de
impostos" completa (cálculo + boleto do DAS-MEI, que exigiria integração
paga com a SERPRO), Marcos decidiu não construir isso agora: só quer poder
registrar a alíquota de referência do Simples Nacional usada nas notas e
ser lembrado mensalmente de revisá-la (ver docstring de
Prestador.aliquota_atualizada_em em app/models.py).

`prestador.aliquota_atual` (Numeric(6,4)) já existia desde a migração
inicial — nunca foi exposta na API nem na UI. Esta migração adiciona só a
coluna que faltava, pra saber QUANDO ela foi confirmada pela última vez:

- `aliquota_atualizada_em`: data (sem hora) da última confirmação/edição da
  alíquota. Nullable — contas antigas, ou que nunca definiram a alíquota,
  simplesmente não têm confirmação registrada ainda (o dashboard/calendário
  tratam isso como "precisa revisar").

Revision ID: f3a7c9d2b415
Revises: ea20eb3394d6
Create Date: 2026-09-22 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c9d2b415'
down_revision: Union[str, Sequence[str], None] = 'ea20eb3394d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador', sa.Column('aliquota_atualizada_em', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('prestador', 'aliquota_atualizada_em')
