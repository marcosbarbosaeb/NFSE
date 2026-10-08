"""Limpa nomes de pessoa e cupons do catálogo de tomadores (08/10/2026)

O catálogo (`tomador`, sem RLS) é compartilhado entre as contas. Na revisão
do modo demonstração apareceram, nas sugestões de e-mail, uma assinatura com
nome de pessoa ("Atenciosamente, <nome>") e um assunto com cupom de desconto.
A limpeza (app/services/sugestoes.py) passou a tirar isso; aqui ela roda de
novo sobre o que já estava gravado.

Revision ID: e1c3d5f7a9b2
Revises: d0b2c4e6f8a1
Create Date: 2026-10-08 23:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e1c3d5f7a9b2'
down_revision: Union[str, Sequence[str], None] = 'd0b2c4e6f8a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CAMPOS = {"sug_template_descricao": None, "sug_email_assunto": "{prestador}", "sug_email_mensagem": "{prestador}"}


def upgrade() -> None:
    from app.services.sugestoes import limpar_texto

    conexao = op.get_bind()
    for campo, troca in _CAMPOS.items():
        linhas = conexao.execute(sa.text(f"SELECT id, {campo} FROM tomador WHERE {campo} IS NOT NULL")).fetchall()
        for tomador_id, texto in linhas:
            limpo = limpar_texto(texto, (), troca)
            if limpo != texto:
                conexao.execute(sa.text(f"UPDATE tomador SET {campo} = :t WHERE id = :i"), {"t": limpo, "i": tomador_id})


def downgrade() -> None:
    # Limpeza de dado pessoal não volta.
    pass
