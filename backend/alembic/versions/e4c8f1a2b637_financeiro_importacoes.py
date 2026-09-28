"""Financeiro de verdade e importações (28/09/2026)

- Despesa ganha descrição, tipo (despesa | retirada — distribuição de
  lucros não é despesa), conta de onde saiu, vencimento, pago/pago_em e o
  modelo recorrente de onde veio ("sacou o pró-labore ✓, pagou cartão ✓").
- `despesa_recorrente`: contas fixas do mês (contabilidade, ferramentas,
  pró-labore...) que viram o checklist de cada mês. RLS por prestador.
- `rotina_mensal` + `rotina_mensal_feita`: conferências do fechamento
  (extrato do banco, PayPal, NF do Facebook...) com check por mês. RLS.
- Tomador "interno" (status): fonte de receita só pra controle (parcerias,
  bônus, PayPal) ou tomador estrangeiro vindo da importação — não entra no
  catálogo compartilhado. Vínculo `sem_nota`: a Ana não gera nota pra ele.
- Emissão `origem` (ana | importada) — notas trazidas do Emissor Nacional.
- Prestador `adn_ultimo_nsu`: de onde continuar a importação.
- Pagamento `origem` aceita 'planilha'.

Revision ID: e4c8f1a2b637
Revises: d2b7c4e8a519
Create Date: 2026-09-28 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e4c8f1a2b637'
down_revision: Union[str, Sequence[str], None] = 'd2b7c4e8a519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLITICA = """
    CREATE POLICY {t}_isolamento_por_prestador ON {t}
        USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
        WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
"""


def _rls(tabela: str) -> None:
    op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY;")
    op.execute(_POLITICA.format(t=tabela))


def upgrade() -> None:
    op.create_table(
        'despesa_recorrente',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('categoria', sa.String(length=100), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False, server_default='despesa'),
        sa.Column('valor_padrao', sa.Numeric(14, 2), nullable=True),
        sa.Column('dia_vencimento', sa.SmallInteger(), nullable=True),
        sa.Column('conta', sa.String(length=60), nullable=True),
        sa.Column('ativa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tipo IN ('despesa', 'retirada')", name='ck_despesa_recorrente_tipo'),
        sa.CheckConstraint('dia_vencimento IS NULL OR (dia_vencimento BETWEEN 1 AND 31)', name='ck_despesa_recorrente_dia'),
    )
    op.create_index('ix_despesa_recorrente_prestador', 'despesa_recorrente', ['prestador_id'])
    _rls('despesa_recorrente')

    op.add_column('despesa', sa.Column('descricao', sa.String(length=200), nullable=True))
    op.add_column('despesa', sa.Column('tipo', sa.String(length=10), nullable=False, server_default='despesa'))
    op.add_column('despesa', sa.Column('conta', sa.String(length=60), nullable=True))
    op.add_column('despesa', sa.Column('vencimento', sa.Date(), nullable=True))
    op.add_column('despesa', sa.Column('pago', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('despesa', sa.Column('pago_em', sa.Date(), nullable=True))
    op.add_column('despesa', sa.Column(
        'recorrente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('despesa_recorrente.id', ondelete='SET NULL'), nullable=True,
    ))
    op.add_column('despesa', sa.Column('origem', sa.String(length=20), nullable=False, server_default='manual'))
    op.create_check_constraint('ck_despesa_tipo', 'despesa', "tipo IN ('despesa', 'retirada')")
    op.create_index('ix_despesa_prestador_competencia', 'despesa', ['prestador_id', 'competencia'])
    # Um lançamento por conta fixa por mês.
    op.create_index(
        'uq_despesa_recorrente_mes', 'despesa', ['recorrente_id', 'competencia'], unique=True,
        postgresql_where=sa.text('recorrente_id IS NOT NULL'),
    )

    op.create_table(
        'rotina_mensal',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('ativa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_rotina_mensal_prestador', 'rotina_mensal', ['prestador_id'])
    _rls('rotina_mensal')

    op.create_table(
        'rotina_mensal_feita',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rotina_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rotina_mensal.id', ondelete='CASCADE'), nullable=False),
        sa.Column('competencia', sa.String(length=7), nullable=False),
        sa.Column('feita_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('rotina_id', 'competencia', name='uq_rotina_feita_mes'),
    )
    _rls('rotina_mensal_feita')

    op.drop_constraint('ck_tomador_status', 'tomador', type_='check')
    op.create_check_constraint('ck_tomador_status', 'tomador', "status IN ('pendente', 'aprovado', 'interno')")
    op.add_column('prestador_tomador', sa.Column('sem_nota', sa.Boolean(), nullable=False, server_default='false'))

    op.add_column('emissao', sa.Column('origem', sa.String(length=12), nullable=False, server_default='ana'))
    op.create_check_constraint('ck_emissao_origem', 'emissao', "origem IN ('ana', 'importada')")
    op.add_column('prestador', sa.Column('adn_ultimo_nsu', sa.BigInteger(), nullable=True))

    op.drop_constraint('ck_pagamento_origem', 'pagamento_recebido', type_='check')
    op.create_check_constraint('ck_pagamento_origem', 'pagamento_recebido', "origem IN ('manual', 'extrato', 'planilha')")


def downgrade() -> None:
    op.drop_constraint('ck_pagamento_origem', 'pagamento_recebido', type_='check')
    op.execute("DELETE FROM pagamento_recebido WHERE origem = 'planilha'")
    op.create_check_constraint('ck_pagamento_origem', 'pagamento_recebido', "origem IN ('manual', 'extrato')")
    op.drop_column('prestador', 'adn_ultimo_nsu')
    op.drop_constraint('ck_emissao_origem', 'emissao', type_='check')
    op.drop_column('emissao', 'origem')
    op.drop_column('prestador_tomador', 'sem_nota')
    op.drop_constraint('ck_tomador_status', 'tomador', type_='check')
    op.create_check_constraint('ck_tomador_status', 'tomador', "status IN ('pendente', 'aprovado')")
    for tabela in ('rotina_mensal_feita', 'rotina_mensal'):
        op.execute(f"DROP POLICY IF EXISTS {tabela}_isolamento_por_prestador ON {tabela};")
    op.drop_table('rotina_mensal_feita')
    op.drop_index('ix_rotina_mensal_prestador', table_name='rotina_mensal')
    op.drop_table('rotina_mensal')
    op.drop_index('uq_despesa_recorrente_mes', table_name='despesa')
    op.drop_index('ix_despesa_prestador_competencia', table_name='despesa')
    op.drop_constraint('ck_despesa_tipo', 'despesa', type_='check')
    for coluna in ('origem', 'recorrente_id', 'pago_em', 'pago', 'vencimento', 'conta', 'tipo', 'descricao'):
        op.drop_column('despesa', coluna)
    op.execute("DROP POLICY IF EXISTS despesa_recorrente_isolamento_por_prestador ON despesa_recorrente;")
    op.drop_index('ix_despesa_recorrente_prestador', table_name='despesa_recorrente')
    op.drop_table('despesa_recorrente')
