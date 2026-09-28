"""email_destinatarios

Pedido do Marcos (28/09/2026): "no e-mail da nota tem que configurar o
destinatário também, não necessariamente enviamos para o e-mail da nota e às
vezes enviamos com cópia para outro, ou até cópia para a gente mesmo".
- `prestador_tomador.email_para`: pra quem a nota vai (vários, separados por
  vírgula). Vazio = e-mail de contato do tomador.
- `prestador.email_copia_padrao`: cópia que vai em TODO e-mail de nota (ex.:
  o próprio e-mail da pessoa).

Revision ID: b8f4d2a6c913
Revises: a3d9e7c51b20
Create Date: 2026-09-28 23:50:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8f4d2a6c913'
down_revision: Union[str, Sequence[str], None] = 'a3d9e7c51b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('email_para', sa.String(length=400), nullable=True))
    op.add_column('prestador', sa.Column('email_copia_padrao', sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column('prestador', 'email_copia_padrao')
    op.drop_column('prestador_tomador', 'email_para')
