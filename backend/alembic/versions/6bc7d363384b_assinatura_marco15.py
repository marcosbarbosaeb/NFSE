"""assinatura_marco15

Marco 15 (item 4), a pedido de Marcos: "cobrança real (Stripe ou similar)"
— ele ainda não tem conta criada no provedor ("monta a estrutura agora, eu
crio a conta depois"), então esta migração cria a estrutura de dados
completa (ver Assinatura em app/models.py e o racional em app/config.py /
app/services/billing.py), mas com os valores de configuração do Stripe
propositalmente vazios/placeholder até a conta existir.

Todo prestador que JÁ existe no banco (hoje, só a Raiana — migrada pelo
Marco 1) ganha uma linha "cortesia" automaticamente aqui: contas
administrativas nunca deveriam depender de uma assinatura Stripe pra
continuar funcionando, e mesmo que uma futura versão passe a checar o
status da assinatura pra liberar acesso, ninguém que já estava usando o
painel antes desta migração fica bloqueado por não ter linha nenhuma.

Revision ID: 6bc7d363384b
Revises: c002aca320f3
Create Date: 2026-09-21 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6bc7d363384b'
down_revision: Union[str, Sequence[str], None] = 'c002aca320f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assinatura',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='trial'),
        sa.Column('trial_termina_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=100), nullable=True, unique=True),
        sa.Column('stripe_subscription_id', sa.String(length=100), nullable=True, unique=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('cortesia', 'trial', 'ativa', 'inadimplente', 'cancelada')",
            name='ck_assinatura_status_valido',
        ),
    )
    # server_default só ajuda o INSERT (abaixo, no backfill); a coluna
    # continua obrigatória a partir daqui pra novas linhas via ORM/serviço —
    # mesmo raciocínio do server_default de email_confirmado na migração
    # c002aca320f3 (evita travar o INSERT de linhas já existentes, mas não
    # fica um default "invisível" pra sempre).
    op.alter_column('assinatura', 'status', server_default=None)

    # RLS — mesmo padrão de 5af6e092d5e1_rls.py / evento_manual (falha
    # fechada sem app.current_prestador_id setado).
    op.execute("ALTER TABLE assinatura ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE assinatura FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY assinatura_isolamento_por_prestador ON assinatura
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
        """
    )

    # Backfill: todo prestador já existente ganha "cortesia" (ver docstring
    # acima) — hoje isso é só a Raiana, mas roda de forma genérica pra
    # qualquer prestador que já exista neste banco no momento da migração.
    #
    # O role que roda migrações (mesmo role de runtime da app, ver
    # alembic/env.py) É O DONO de `prestador`/`assinatura`, mas ambas usam
    # FORCE ROW LEVEL SECURITY — ou seja, mesmo o dono fica sujeito à
    # policy (de propósito, ver 5af6e092d5e1_rls.py). Um SELECT * FROM
    # prestador sem app.current_prestador_id setado devolveria ZERO linhas
    # (falha fechada) mesmo pro dono, e o INSERT em assinatura falharia o
    # WITH CHECK pelo mesmo motivo — nenhum UUID fixo serviria porque a
    # policy de `prestador` compara contra o PRÓPRIO id de cada linha.
    # Solução: suspender FORCE (não RLS em si) só durante esta migração —
    # exige apenas ser dono da tabela, não superusuário (compatível com
    # como migrações rodam em produção nesta arquitetura) — e restaurar
    # logo em seguida, tudo dentro da mesma transação da migração.
    op.execute("ALTER TABLE prestador NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE assinatura NO FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        INSERT INTO assinatura (id, prestador_id, status, criado_em, atualizado_em)
        SELECT gen_random_uuid(), id, 'cortesia', now(), now() FROM prestador;
        """
    )
    op.execute("ALTER TABLE prestador FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE assinatura FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS assinatura_isolamento_por_prestador ON assinatura;")
    op.drop_table('assinatura')
