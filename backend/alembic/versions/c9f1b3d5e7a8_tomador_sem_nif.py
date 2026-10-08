"""tomador de fora do Brasil sem número fiscal (cNaoNIF)

Revision ID: c9f1b3d5e7a8
Revises: b8e0a2c4d6f7
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9f1b3d5e7a8'
down_revision: Union[str, Sequence[str], None] = 'b8e0a2c4d6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # "1" = dispensado do NIF; "2" = o país não exige NIF (os códigos do cNaoNIF da DPS).
    op.add_column("tomador", sa.Column("motivo_sem_nif", sa.String(1), nullable=True))


def downgrade() -> None:
    op.drop_column("tomador", "motivo_sem_nif")
