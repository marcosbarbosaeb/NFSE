"""vinculo_prazos_marco13

Marco 13 do plano — calendário de prazos/previsão de recebimento (a pedido
de Marcos, 22/09/2026): "tem prestador que cobra datas limites para o
pagamento não ficar para o próximo mês" — precisa de dois dados NOVOS por
vínculo (não existiam antes), porque isso varia por fornecedor/programa, o
mesmo nível de granularidade de `template_descricao`/`cod_trib_nacional`:

- `dia_limite_emissao`: dia do mês (1-31) até o qual a nota desse vínculo
  precisa ser gerada pra não cair pro ciclo de pagamento do mês seguinte.
  NULL = sem prazo conhecido pra esse vínculo (não gera evento de prazo no
  calendário).
- `dias_para_recebimento`: quantos dias corridos depois da EMISSÃO o
  pagamento costuma cair (contado a partir da emissão, não de um dia fixo
  do mês — mais robusto a quando exatamente a nota foi gerada naquele mês).
  NULL = sem previsão conhecida.

Ambos ficam em `prestador_tomador` (não em `emissao`) por serem regra do
RELACIONAMENTO com aquele tomador/programa, igual todo o resto das "regras
de emissão" já modeladas ali — ver app/services/calendario.py pra como
isso vira eventos de calendário.

Revision ID: 4e44be09cfe3
Revises: 3333b1f7ed68
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e44be09cfe3'
down_revision: Union[str, Sequence[str], None] = '3333b1f7ed68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('dia_limite_emissao', sa.SmallInteger(), nullable=True))
    op.add_column('prestador_tomador', sa.Column('dias_para_recebimento', sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        'ck_prestador_tomador_dia_limite_emissao',
        'prestador_tomador',
        'dia_limite_emissao IS NULL OR (dia_limite_emissao BETWEEN 1 AND 31)',
    )
    op.create_check_constraint(
        'ck_prestador_tomador_dias_para_recebimento',
        'prestador_tomador',
        'dias_para_recebimento IS NULL OR dias_para_recebimento >= 0',
    )


def downgrade() -> None:
    op.drop_constraint('ck_prestador_tomador_dias_para_recebimento', 'prestador_tomador', type_='check')
    op.drop_constraint('ck_prestador_tomador_dia_limite_emissao', 'prestador_tomador', type_='check')
    op.drop_column('prestador_tomador', 'dias_para_recebimento')
    op.drop_column('prestador_tomador', 'dia_limite_emissao')
