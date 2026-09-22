"""google_oauth_marco16

Marco 16, item 1 — login/cadastro via Google (a pedido do Marcos), com
credenciais placeholder (ver app/config.py: google_oauth_client_id/secret
vazios até ele criar o projeto no Google Cloud). Adiciona 1 coluna em
`usuario`:

- `google_sub`: identificador estável do Google (nunca o e-mail — e-mail
  pode mudar de dono/ser reciclado) vinculado a esta conta, se ela algum
  dia logou/se vinculou via Google. Nullable e único: a maioria das contas
  continua só e-mail+senha (`senha_hash` continua obrigatório sempre, ver
  docstring do modelo) — este índice único só existe pra impedir que dois
  Usuario diferentes acabem vinculados à mesma conta Google.

Revision ID: ea20eb3394d6
Revises: 6bc7d363384b
Create Date: 2026-09-22 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea20eb3394d6'
down_revision: Union[str, Sequence[str], None] = '6bc7d363384b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuario', sa.Column('google_sub', sa.String(length=64), nullable=True))
    op.create_index('ix_usuario_google_sub', 'usuario', ['google_sub'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_usuario_google_sub', table_name='usuario')
    op.drop_column('usuario', 'google_sub')
