"""Mais sugestões no catálogo de tomadores (05/10/2026)

"Editei nos tomadores da minha conta as descrições e as configurações.
Tirando os dados pessoais, deixe essas configurações como a configuração
padrão dos tomadores pré-cadastrados": além do código do serviço, da
descrição, do dia e do prazo, o catálogo passa a sugerir o código
municipal, o NBS e o mês que aparece na descrição. Nada de e-mail,
telefone ou destinatários — isso é de cada conta.

Revision ID: e9b1d3f5a768
Revises: d8a0c2e4f657
Create Date: 2026-10-05 22:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e9b1d3f5a768'
down_revision: Union[str, Sequence[str], None] = 'd8a0c2e4f657'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tomador', sa.Column('sug_cod_trib_municipal', sa.String(length=5), nullable=True))
    op.add_column('tomador', sa.Column('sug_cod_nbs', sa.String(length=12), nullable=True))
    op.add_column('tomador', sa.Column('sug_meses_atras', sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('tomador', 'sug_meses_atras')
    op.drop_column('tomador', 'sug_cod_nbs')
    op.drop_column('tomador', 'sug_cod_trib_municipal')
