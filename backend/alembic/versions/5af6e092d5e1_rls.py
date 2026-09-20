"""rls

Ativa Row-Level Security como defesa em profundidade, além dos checks de
autorização na camada de aplicação (compromisso assumido no plano a partir
da revisão do Gemini). O isolamento é por `prestador_id` (ou `id`, na
própria tabela `prestador`), lido de uma variável de sessão Postgres —
`app.current_prestador_id` — que a aplicação DEVE setar por request/conexão
(`SET LOCAL app.current_prestador_id = '<uuid>'`, dentro da transação) antes
de tocar essas tabelas. Sem essa variável setada, `current_setting(...,
true)` retorna NULL, a comparação com a coluna nunca é verdadeira, e a
policy nega tudo — falha fechada, não aberta.

`FORCE ROW LEVEL SECURITY` é usado (não só `ENABLE`) porque, sem ela, o dono
da tabela — que normalmente é o mesmo role usado pela aplicação — ficaria
automaticamente isento da RLS, esvaziando a proteção.

`tomador` fica de fora de propósito: é o catálogo central compartilhado
entre prestadores (ver Modelo de dados no plano), não dado de um tenant só.

`envio` também fica de fora nesta migração: não carrega `prestador_id`
denormalizado (só `emissao_id`), então a policy exigiria subquery/join. Como
o vínculo de propriedade dele é indireto (via emissao -> prestador_tomador
-> prestador) e o plano não lista `envio` entre as tabelas sensíveis a
isolar por RLS, deixo registrado aqui como possível follow-up em vez de
denormalizar o schema sem necessidade comprovada.

Revision ID: 5af6e092d5e1
Revises: 1d31bb056433
Create Date: 2026-09-20 16:14:58.691885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5af6e092d5e1'
down_revision: Union[str, Sequence[str], None] = '1d31bb056433'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabela, coluna que identifica o dono)
_TABELAS_ISOLADAS = [
    ("prestador", "id"),
    ("certificado", "prestador_id"),
    ("prestador_tomador", "prestador_id"),
    ("emissao", "prestador_id"),
    ("pagamento_recebido", "prestador_id"),
    ("despesa", "prestador_id"),
]


def upgrade() -> None:
    for tabela, coluna in _TABELAS_ISOLADAS:
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {tabela}_isolamento_por_prestador ON {tabela}
                USING ({coluna} = current_setting('app.current_prestador_id', true)::uuid)
                WITH CHECK ({coluna} = current_setting('app.current_prestador_id', true)::uuid);
            """
        )


def downgrade() -> None:
    for tabela, _coluna in reversed(_TABELAS_ISOLADAS):
        op.execute(f"DROP POLICY IF EXISTS {tabela}_isolamento_por_prestador ON {tabela};")
        op.execute(f"ALTER TABLE {tabela} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tabela} DISABLE ROW LEVEL SECURITY;")
