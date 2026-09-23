"""calendario_ajustes_marco17

Pedido do Marcos (23/09/2026): no calendário a pessoa deve poder criar e
editar outros tipos de evento (ex.: uma previsão de recebimento manual) e
ajustar a data dos alertas automáticos — tanto a REGRA (vale pros próximos
meses) quanto UMA ocorrência só.

- `evento_manual` ganha `categoria` (lembrete | recebimento_previsto |
  prazo_emissao), `valor` e `prestador_tomador_id` (fornecedor opcional).
  Linhas antigas viram 'lembrete' (era o único uso até aqui).
- `ajuste_evento` (nova, com RLS): mover ou ocultar UMA ocorrência de um
  alerta calculado (prazo de emissão, previsão de recebimento, revisar
  alíquota) sem mexer na regra — chave identifica a ocorrência (ver
  app/services/calendario.py).
- `prestador.dia_lembrete_aliquota`: regra do lembrete de alíquota (antes
  fixo no dia 1). Nulo = dia 1.

Revision ID: a81c2e5d7f30
Revises: f3a7c9d2b415
Create Date: 2026-09-23 10:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a81c2e5d7f30'
down_revision: Union[str, Sequence[str], None] = 'f3a7c9d2b415'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evento_manual', sa.Column('categoria', sa.String(length=30), nullable=False, server_default='lembrete'))
    op.add_column('evento_manual', sa.Column('valor', sa.Numeric(14, 2), nullable=True))
    op.add_column(
        'evento_manual',
        sa.Column('prestador_tomador_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('prestador_tomador.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_check_constraint(
        'ck_evento_manual_categoria', 'evento_manual',
        "categoria IN ('lembrete', 'recebimento_previsto', 'prazo_emissao')",
    )

    op.add_column('prestador', sa.Column('dia_lembrete_aliquota', sa.SmallInteger(), nullable=True))

    op.create_table(
        'ajuste_evento',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prestador_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prestador.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('chave', sa.String(length=100), nullable=False),
        sa.Column('nova_data', sa.Date(), nullable=True),
        sa.Column('oculto', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('prestador_id', 'tipo', 'chave', name='uq_ajuste_evento_ocorrencia'),
        sa.CheckConstraint(
            "tipo IN ('prazo_emissao', 'recebimento_previsto', 'revisar_aliquota')",
            name='ck_ajuste_evento_tipo',
        ),
    )
    op.execute("ALTER TABLE ajuste_evento ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ajuste_evento FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY ajuste_evento_isolamento_por_prestador ON ajuste_evento
            USING (prestador_id = current_setting('app.current_prestador_id', true)::uuid)
            WITH CHECK (prestador_id = current_setting('app.current_prestador_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS ajuste_evento_isolamento_por_prestador ON ajuste_evento;")
    op.drop_table('ajuste_evento')
    op.drop_column('prestador', 'dia_lembrete_aliquota')
    op.drop_constraint('ck_evento_manual_categoria', 'evento_manual', type_='check')
    op.drop_column('evento_manual', 'prestador_tomador_id')
    op.drop_column('evento_manual', 'valor')
    op.drop_column('evento_manual', 'categoria')
