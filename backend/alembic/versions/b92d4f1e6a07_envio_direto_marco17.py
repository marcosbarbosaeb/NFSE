"""envio_direto_marco17

Pedido do Marcos (23/09/2026): enviar a nota direto pro fornecedor por
e-mail (saindo de um endereço do NotaFácil) e por WhatsApp.

- `prestador_tomador.email_contato` / `whatsapp_contato`: pra onde mandar
  as notas daquele fornecedor.
- `envio.destino` (e-mail/telefone usado) e `envio.erro` (motivo de falha).
- `emissao.danfse_pdf`: cache do PDF oficial (DANFSe) baixado do ADN
  depois da confirmação — anexado no e-mail e servido pelo link público.

Revision ID: b92d4f1e6a07
Revises: a81c2e5d7f30
Create Date: 2026-09-23 11:20:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b92d4f1e6a07'
down_revision: Union[str, Sequence[str], None] = 'a81c2e5d7f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestador_tomador', sa.Column('email_contato', sa.String(length=200), nullable=True))
    op.add_column('prestador_tomador', sa.Column('whatsapp_contato', sa.String(length=20), nullable=True))
    op.add_column('envio', sa.Column('destino', sa.String(length=200), nullable=True))
    op.add_column('envio', sa.Column('erro', sa.Text(), nullable=True))
    op.add_column('emissao', sa.Column('danfse_pdf', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('emissao', 'danfse_pdf')
    op.drop_column('envio', 'erro')
    op.drop_column('envio', 'destino')
    op.drop_column('prestador_tomador', 'whatsapp_contato')
    op.drop_column('prestador_tomador', 'email_contato')
