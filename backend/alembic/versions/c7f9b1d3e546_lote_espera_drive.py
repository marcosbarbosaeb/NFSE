"""Lote que espera a cota de e-mail e Google Drive da empresa (05/10/2026)

- `lote_fila.retomar_em`: lote de e-mail que bateu no limite diário do
  serviço de e-mail fica esperando e volta sozinho nesse horário.
- `prestador.drive_token` (cifrado), `drive_email`, `drive_pasta_id`: a
  conta Google Drive que a empresa conectou pra guardar os arquivos das
  notas.

Revision ID: c7f9b1d3e546
Revises: b6e8a0c2d435
Create Date: 2026-10-05 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c7f9b1d3e546'
down_revision: Union[str, Sequence[str], None] = 'b6e8a0c2d435'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lote_fila', sa.Column('retomar_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('prestador', sa.Column('drive_token', sa.LargeBinary(), nullable=True))
    op.add_column('prestador', sa.Column('drive_email', sa.String(length=200), nullable=True))
    op.add_column('prestador', sa.Column('drive_pasta_id', sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column('prestador', 'drive_pasta_id')
    op.drop_column('prestador', 'drive_email')
    op.drop_column('prestador', 'drive_token')
    op.drop_column('lote_fila', 'retomar_em')
