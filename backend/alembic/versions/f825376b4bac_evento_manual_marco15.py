"""evento_manual_marco15

Marco 15 do plano, a pedido de Marcos: "na aba de agenda coloque opções
para gerenciar os eventos" — até aqui o calendário (Marco 13) só mostrava
eventos COMPUTADOS na hora (prazo de emissão, previsão/confirmação de
recebimento — ver app/services/calendario.py), sem nenhuma tabela própria.
Esta migração cria `evento_manual` pra eventos que o usuário cadastra à
mão (reunião, lembrete, prazo específico) — dado de verdade, não derivado,
por isso precisa de linha e RLS por prestador_id (mesmo padrão de
`despesa`/`pagamento_recebido`/etc., ver 5af6e092d5e1_rls.py).

Revision ID: f825376b4bac
Revises: 4e44be09cfe3
Create Date: 2026-09-21 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f825376b4bac'
down_revision: Union[str, Sequence[str], None] = '4e44be09cfe3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evento_manual',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_evento_manual_prestador_id_data', 'evento_manual', ['prestador_id', 'data'])

    # RLS — mesmo padrão de 5af6e092d5e1_rls.py (falha fechada sem a
    # variável de sessão app.current_prestador_id setada).
    op.execute("ALTER TABLE evento_manual ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE evento_manual FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY evento_manual_isolamento_por_prestador ON evento_manual
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS evento_manual_isolamento_por_prestador ON evento_manual;")
    op.drop_index('ix_evento_manual_prestador_id_data', table_name='evento_manual')
    op.drop_table('evento_manual')
