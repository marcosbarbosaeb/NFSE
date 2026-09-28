"""shopee_tomador_avulso_metodo

Pedido do Marcos (28/09/2026):
- Relatório da Shopee: a nota vai pra CADA vendedor do relatório, sem
  salvar esses vendedores como tomadores. O vínculo "Shopee" passa a ter
  VÁRIAS notas na mesma competência (uma por vendedor), então a trava de
  "uma nota ativa por vínculo+competência" ganha o documento do tomador na
  chave: `emissao.tomador_documento` (CNPJ/CPF/NIF de quem recebeu a nota
  quando ele não é o tomador do vínculo; nulo no caso de sempre).
- "Só usamos o CSV nesse caso [Shopee], desative isso para os demais. E
  usamos o PDF para a Awin": o método de informar o valor volta a ser
  configurado por tomador — AWIN = pdf, CSV só pra Shopee, o resto manual.

Revision ID: e5b2c8f1a310
Revises: c7e1a4d9b203
Create Date: 2026-09-28 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5b2c8f1a310'
down_revision: Union[str, Sequence[str], None] = 'c7e1a4d9b203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CNPJ_AWIN = "14182871000188"
CNPJ_SHOPEE = "35635824000112"


def upgrade() -> None:
    op.add_column('emissao', sa.Column('tomador_documento', sa.String(length=40), nullable=True))
    op.drop_index('uq_emissao_vinculo_competencia_ativa', table_name='emissao', postgresql_where=sa.text("estado != 'cancelada'"))
    op.execute(
        "CREATE UNIQUE INDEX uq_emissao_vinculo_competencia_ativa ON emissao "
        "(prestador_tomador_id, competencia, COALESCE(tomador_documento, '')) WHERE estado != 'cancelada'"
    )
    # Método por tomador. Com role sujeito a RLS isto não acha nada (sem
    # erro); em produção roda como dono do banco.
    op.execute(
        f"""
        UPDATE prestador_tomador v SET metodo_captura_valor = 'pdf'
        FROM tomador t WHERE t.id = v.tomador_id AND t.cnpj = '{CNPJ_AWIN}'
        """
    )
    op.execute(
        f"""
        UPDATE prestador_tomador v SET metodo_captura_valor = 'manual'
        FROM tomador t
        WHERE t.id = v.tomador_id AND v.metodo_captura_valor IN ('csv', 'chat') AND t.cnpj <> '{CNPJ_SHOPEE}'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_emissao_vinculo_competencia_ativa")
    op.create_index(
        'uq_emissao_vinculo_competencia_ativa', 'emissao', ['prestador_tomador_id', 'competencia'],
        unique=True, postgresql_where=sa.text("estado != 'cancelada'"),
    )
    op.drop_column('emissao', 'tomador_documento')
