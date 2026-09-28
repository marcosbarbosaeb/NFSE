"""tomadores_dia_sugestoes_demo

Pedido do Marcos (28/09/2026) — revisão da aba Tomadores, limpeza de
dados e ambiente de simulação:

- `prestador_tomador.excluido_em`: "excluir o tomador e aí sim ele suma".
  Um vínculo SEM notas é apagado de verdade; um vínculo COM notas não pode
  (emissao -> prestador_tomador é RESTRICT, e a nota fiscal precisa
  continuar existindo), então ele é marcado como excluído e some de todas
  as listas, mas as notas antigas continuam apontando pra ele.
- `tomador.sug_*`: "todos os dados devem possuir uma prévia de sugestão
  de preenchimento com o que nós usamos". O catálogo de tomadores é
  compartilhado e SEM RLS; os vínculos têm RLS por prestador. Guardar no
  próprio tomador o último código de serviço / modelo de descrição / dia de
  emissão / prazo de pagamento usado com ele permite sugerir isso a quem
  for faturar o mesmo tomador depois, sem furar a RLS dos vínculos.
- `prestador.demo`: contas do ambiente de simulação ("testar a plataforma
  de forma gratuita") — nunca falam com a Receita, nunca mandam e-mail, e
  são apagadas sozinhas depois de um tempo (ver app/services/demo.py).

Revision ID: c7e1a4d9b203
Revises: b92d4f1e6a07
Create Date: 2026-09-28 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c7e1a4d9b203'
down_revision: Union[str, Sequence[str], None] = 'b92d4f1e6a07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('excluido_em', sa.DateTime(timezone=True), nullable=True))

    op.add_column('tomador', sa.Column('sug_cod_trib_nacional', sa.String(length=6), nullable=True))
    op.add_column('tomador', sa.Column('sug_template_descricao', sa.Text(), nullable=True))
    op.add_column('tomador', sa.Column('sug_dia_emissao', sa.SmallInteger(), nullable=True))
    op.add_column('tomador', sa.Column('sug_dias_recebimento', sa.SmallInteger(), nullable=True))

    op.add_column(
        'prestador',
        sa.Column('demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    # Semente das sugestões a partir dos vínculos que já existem (o mais
    # recente de cada tomador). Com um role sujeito a RLS isto simplesmente
    # não acha nada — sem erro; em produção a migração roda como dono do
    # banco e preenche.
    op.execute(
        """
        UPDATE tomador t SET
            sug_cod_trib_nacional = v.cod_trib_nacional,
            sug_template_descricao = v.template_descricao,
            sug_dia_emissao = v.dia_limite_emissao,
            sug_dias_recebimento = v.dias_para_recebimento
        FROM (
            SELECT DISTINCT ON (tomador_id) tomador_id, cod_trib_nacional, template_descricao,
                   dia_limite_emissao, dias_para_recebimento
            FROM prestador_tomador
            ORDER BY tomador_id, atualizado_em DESC
        ) v
        WHERE v.tomador_id = t.id
        """
    )


def downgrade() -> None:
    op.drop_column('prestador', 'demo')
    op.drop_column('tomador', 'sug_dias_recebimento')
    op.drop_column('tomador', 'sug_dia_emissao')
    op.drop_column('tomador', 'sug_template_descricao')
    op.drop_column('tomador', 'sug_cod_trib_nacional')
    op.drop_column('prestador_tomador', 'excluido_em')
