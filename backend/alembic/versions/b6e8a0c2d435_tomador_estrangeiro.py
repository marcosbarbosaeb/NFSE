"""Tomador de fora do Brasil: país e identificação fiscal estrangeira (05/10/2026)

"Lancei um recebimento de controle do GOOGLE ADSENSE e agora na aba de
tomador não tem a opção de eu inserir ele como tomador para poder gerar
notas." Quem paga é uma empresa de fora — sem CNPJ. O tomador interno (só
desta conta, `status='interno'`) passa a poder guardar:

- `tomador.pais`: código ISO de 2 letras do país (ex.: IE, US, SG);
- `tomador.nif`: o número de identificação fiscal da empresa no país dela.

Com os dois preenchidos a nota sai com NIF + endereço no exterior, a mesma
receita das notas pra vendedores estrangeiros da Shopee (ver
app/services/motor_emissao.py e app/fiscal/dps.py). Nulos = tomador do
Brasil, como sempre foi.

Revision ID: b6e8a0c2d435
Revises: a5d7f9b1c324
Create Date: 2026-10-05 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6e8a0c2d435"
down_revision: Union[str, Sequence[str], None] = "a5d7f9b1c324"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tomador", sa.Column("pais", sa.String(length=2), nullable=True))
    op.add_column("tomador", sa.Column("nif", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("tomador", "nif")
    op.drop_column("tomador", "pais")
