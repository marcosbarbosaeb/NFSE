"""Corrige `mes_inteiro` dos pagamentos antigos (05/10/2026)

A migração anterior marcava os pagamentos antigos com um UPDATE direto, mas
`pagamento_recebido` tem RLS forçada: sem a empresa definida na sessão, o
UPDATE não enxerga linha nenhuma — em produção nada foi marcado, e o
histórico inteiro apareceu "em aberto". Aqui o UPDATE roda empresa por
empresa, com a variável da RLS definida.

Só os pagamentos de antes da publicação (05/10/2026 02:35 UTC): o que foi
lançado depois sem nota é recebimento sem nota de verdade.

Revision ID: c1f3b5d7e980
Revises: b0e2a4c6d879
Create Date: 2026-10-05 03:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1f3b5d7e980'
down_revision: Union[str, Sequence[str], None] = 'b0e2a4c6d879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conexao = op.get_bind()
    empresas = [
        linha[0] for linha in conexao.execute(sa.text(
            "SELECT prestador_id FROM usuario UNION SELECT prestador_id FROM usuario_prestador"
        ))
    ]
    for prestador_id in empresas:
        conexao.execute(sa.text("SELECT set_config('app.current_prestador_id', :p, true)"), {"p": str(prestador_id)})
        conexao.execute(sa.text(
            "UPDATE pagamento_recebido SET mes_inteiro = true "
            "WHERE emissao_id IS NULL AND mes_inteiro = false AND criado_em < '2026-10-05 02:35:00+00'"
        ))
    conexao.execute(sa.text("SELECT set_config('app.current_prestador_id', '', true)"))


def downgrade() -> None:
    pass
