"""Drive como forma de envio e padrões de envio no catálogo (05/10/2026)

- "a ideia é a pessoa, nas formas de compartilhar a nota, poder escolher
  subir elas pro próprio Drive": o envio ganha o canal 'drive'.
- "os dados como a forma da descrição, de envio, já deixe pré-preenchido;
  troque apenas os dados pessoais, nomes, conta bancária": o catálogo passa
  a sugerir as formas de envio e o modelo do e-mail — e as descrições que já
  estavam lá são limpas de dado pessoal (conta bancária, CNPJ, pedido...).

Revision ID: f0c2e4a6b879
Revises: e9b1d3f5a768
Create Date: 2026-10-05 23:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f0c2e4a6b879'
down_revision: Union[str, Sequence[str], None] = 'e9b1d3f5a768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CANAIS = "'download','email','whatsapp','direto_fornecedor','mensagem_pronta','email_geral'"


def upgrade() -> None:
    op.drop_constraint('ck_envio_canal', 'envio', type_='check')
    op.create_check_constraint('ck_envio_canal', 'envio', f"canal IN ({_CANAIS},'drive')")

    op.add_column('tomador', sa.Column('sug_envio_formas', postgresql.JSONB(), nullable=True))
    op.add_column('tomador', sa.Column('sug_email_assunto', sa.String(length=300), nullable=True))
    op.add_column('tomador', sa.Column('sug_email_mensagem', sa.Text(), nullable=True))
    op.add_column('tomador', sa.Column('sug_email_anexos', sa.String(length=10), nullable=True))

    # O catálogo não tem RLS: dá pra limpar aqui o que já foi sugerido.
    from app.services.sugestoes import limpar_texto

    conexao = op.get_bind()
    linhas = conexao.execute(sa.text("SELECT id, sug_template_descricao FROM tomador WHERE sug_template_descricao IS NOT NULL")).fetchall()
    for tomador_id, descricao in linhas:
        limpa = limpar_texto(descricao)
        if limpa != descricao:
            conexao.execute(
                sa.text("UPDATE tomador SET sug_template_descricao = :d WHERE id = :i"), {"d": limpa, "i": tomador_id},
            )


def downgrade() -> None:
    op.drop_column('tomador', 'sug_email_anexos')
    op.drop_column('tomador', 'sug_email_mensagem')
    op.drop_column('tomador', 'sug_email_assunto')
    op.drop_column('tomador', 'sug_envio_formas')
    op.execute("DELETE FROM envio WHERE canal = 'drive'")
    op.drop_constraint('ck_envio_canal', 'envio', type_='check')
    op.create_check_constraint('ck_envio_canal', 'envio', f"canal IN ({_CANAIS})")
