import uuid

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, future=True)
# expire_on_commit=False É NECESSÁRIO aqui, não só uma otimização: o padrão
# do painel é "grava, dá commit, monta a resposta a partir do objeto ORM"
# (ver _para_resposta em app/main.py). Com o default (True), o commit expira
# os atributos do objeto — o próximo acesso dispara um SELECT novo, numa
# transação NOVA. Só que `app.current_prestador_id` (a variável de sessão
# que a RLS exige, ver definir_prestador_atual) foi setada com escopo LOCAL
# na transação que acabou de terminar — e, uma vez que essa GUC customizada
# já foi tocada nesta conexão, ela NÃO volta a ficar "nunca definida" (NULL)
# depois do commit: vira string vazia (é assim que o Postgres trata um
# parâmetro de classe placeholder já tocado, mesmo sem valor de sessão
# anterior). `current_setting(..., true)::uuid` então tenta converter '' pra
# uuid e a policy de RLS explode com "invalid input syntax for type uuid:
# ''" — um 500 em produção, não um erro claro. Isso só aparece contra o
# Postgres de verdade (achado rodando o servidor de verdade, não nos testes
# — a suíte de testes contorna commit() de propósito, ver conftest.py) e
# bateu em TODO endpoint que faz commit e depois lê o objeto (`/api/dps`,
# `/api/dps/{id}/assinar`, `/api/pagamentos`, `/api/despesas`). Com
# expire_on_commit=False, o objeto mantém os valores que ele mesmo acabou de
# gravar — nenhuma releitura pós-commit acontece, então a variável de
# sessão nunca precisa estar valendo de novo depois do commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency do FastAPI (usada a partir do Marco 6, motor de emissão como
    serviço) — sessão por request, sempre fechada no final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def definir_prestador_atual(db: Session, prestador_id: uuid.UUID) -> None:
    """Seta a variável de sessão que a RLS usa pra isolar por tenant (ver
    alembic/versions/*_rls.py) — `SET LOCAL`, então só vale dentro da
    transação atual dessa `db`, nunca vaza pra outra conexão do pool.

    TODA leitura/escrita nas tabelas com RLS (certificado, prestador_tomador,
    emissao, pagamento_recebido, despesa) precisa disso chamado antes, com o
    prestador_id do usuário autenticado da requisição — sem isso as policies
    negam tudo (falha fechada, ver comentário na migração de RLS), então
    esquecer de chamar aparece na hora como "não achei nada", não como dado
    vazando de outro prestador.
    """
    # `SET LOCAL` não aceita parâmetro bindado no valor (só literal — geraria
    # SQL a montar string à mão, risco de injeção). `set_config(..., true)`
    # é a função equivalente (terceiro argumento `true` = escopo local, como
    # SET LOCAL) e aceita bind normalmente.
    db.execute(
        text("SELECT set_config('app.current_prestador_id', :prestador_id, true)"),
        {"prestador_id": str(prestador_id)},
    )
    # Lembrado na sessão pra valer também nas transações seguintes (ver
    # _reaplicar_prestador_atual abaixo).
    db.info[CHAVE_PRESTADOR_ATUAL] = str(prestador_id)


CHAVE_PRESTADOR_ATUAL = "prestador_atual"


@event.listens_for(SessionLocal, "after_begin")
def _reaplicar_prestador_atual(session: Session, transaction, connection) -> None:
    """09/10/2026 — conserto da família de erro "invalid input syntax for type
    uuid: ''" (05/10, POST /api/dps e /submeter): `set_config(..., true)` vale
    só na transação; depois de um commit, qualquer leitura (um atributo que o
    banco preencheu, como `atualizado_em`, um `db.refresh`, uma consulta nova)
    abre outra transação sem a variável da RLS e quebra. Aqui, toda transação
    nova da mesma sessão já começa com a empresa que a sessão estava usando —
    em qualquer rota, não só nas que deram erro. (O lote em segundo plano
    fazia isso à mão desde antes, em app/services/lotes.py.)"""
    prestador_id = session.info.get(CHAVE_PRESTADOR_ATUAL)
    if prestador_id:
        connection.execute(
            text("SELECT set_config('app.current_prestador_id', :prestador_id, true)"),
            {"prestador_id": prestador_id},
        )
