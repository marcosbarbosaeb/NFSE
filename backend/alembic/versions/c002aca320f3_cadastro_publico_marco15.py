"""cadastro_publico_marco15

Marco 15 do plano — cadastro público self-service ("cria a conta na
hora", com confirmação por e-mail antes de liberar login, ver docstring
de app/services/cadastro.py). Adiciona 3 colunas em `usuario`:

- `email_confirmado`: gate de login (ver autenticar/api_login em
  app/main.py) — só usuários confirmados conseguem entrar.
- `token_confirmacao` / `token_confirmacao_expira_em`: token de uso único
  que vai no link do e-mail de confirmação, com expiração.

IMPORTANTE: usuários que já existem (criados via scripts/criar_usuario.py,
como a própria Raiana) não podem ficar trancados de fora por causa desta
migração — por isso o `server_default='true'` na criação da coluna (linhas
existentes viram confirmadas automaticamente), removido logo em seguida
(`alter_column` tira o server_default) pra que RESPONSABILIDADE de decidir
"confirmado ou não" volte a ser 100% da aplicação (Usuario.email_confirmado
tem default=False no lado Python, ver app/models.py) pra qualquer INSERT
daqui pra frente — só assim um cadastro novo nasce não-confirmado de
verdade.

Revision ID: c002aca320f3
Revises: f825376b4bac
Create Date: 2026-09-21 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c002aca320f3'
down_revision: Union[str, Sequence[str], None] = 'f825376b4bac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuario', sa.Column('email_confirmado', sa.Boolean(), nullable=False, server_default='true'))
    op.alter_column('usuario', 'email_confirmado', server_default=None)
    op.add_column('usuario', sa.Column('token_confirmacao', sa.String(length=64), nullable=True))
    op.add_column('usuario', sa.Column('token_confirmacao_expira_em', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_usuario_token_confirmacao', 'usuario', ['token_confirmacao'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_usuario_token_confirmacao', table_name='usuario')
    op.drop_column('usuario', 'token_confirmacao_expira_em')
    op.drop_column('usuario', 'token_confirmacao')
    op.drop_column('usuario', 'email_confirmado')
