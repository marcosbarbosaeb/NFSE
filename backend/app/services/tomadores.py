"""
Catálogo de tomadores — Marco 13 do plano. Até aqui, um tomador só nascia
via scripts/migrar_fornecedores.py (migração inicial) ou direto no banco —
não existia self-service nenhum pelo painel. Direção confirmada por Marcos
(22/09/2026): a Raiana deve poder usar um tomador que já está no catálogo
(compartilhado entre prestadores — "Meus tomadores" vs. "Todos os
tomadores" no painel) OU cadastrar um novo na hora, igual o Emissor
Nacional permite — sem fila de aprovação: tudo criado por aqui já nasce
com status='aprovado' (ver docstring do campo em app/models.py pro porquê
a coluna continua existindo mesmo assim).

`tomador` não tem RLS (ver alembic/versions/5af6e092d5e1_rls.py — é
catálogo central de propósito), então nada aqui precisa de
`definir_prestador_atual`; só a parte que junta com `prestador_tomador`
("meus tomadores") depende da RLS já ter sido aplicada na sessão por quem
chamou (mesma disciplina do resto do app.services).
"""
import uuid

from sqlalchemy.orm import Session

from app.models import PrestadorTomador, Tomador


class CnpjJaCadastradoError(Exception):
    """Já existe um tomador no catálogo com esse CNPJ — reaproveita o
    existente em vez de duplicar (mesmo CNPJ, razões sociais diferentes
    seria dado inconsistente no catálogo compartilhado)."""


def _normalizar_cnpj(cnpj: str) -> str:
    return "".join(c for c in cnpj if c.isdigit())


def listar_catalogo(db: Session, *, prestador_id: uuid.UUID, apenas_meus: bool) -> list[Tomador]:
    """`apenas_meus=True` -> só tomadores com vínculo ATIVO com o prestador
    atual ("Meus tomadores" na tela); `False` -> catálogo inteiro aprovado
    ("Todos os tomadores"), igual o Emissor Nacional deixa buscar qualquer
    CNPJ já conhecido, não só quem você já faturou antes."""
    query = db.query(Tomador).filter_by(status="aprovado")
    if apenas_meus:
        query = query.join(PrestadorTomador, PrestadorTomador.tomador_id == Tomador.id).filter(
            PrestadorTomador.prestador_id == prestador_id,
            PrestadorTomador.ativo.is_(True),
        )
    return query.order_by(Tomador.razao_social).all()


def buscar_tomador(db: Session, tomador_id: uuid.UUID) -> Tomador | None:
    return db.query(Tomador).filter_by(id=tomador_id).one_or_none()


def criar_tomador(
    db: Session, *, cnpj: str, razao_social: str, cod_municipio: str,
    cep: str | None = None, logradouro: str | None = None, numero: str | None = None,
    complemento: str | None = None, bairro: str | None = None,
) -> Tomador:
    cnpj_norm = _normalizar_cnpj(cnpj)
    existente = db.query(Tomador).filter_by(cnpj=cnpj_norm).one_or_none()
    if existente is not None:
        raise CnpjJaCadastradoError(
            f"Já existe um tomador cadastrado com o CNPJ '{cnpj_norm}' ({existente.razao_social}) — use-o em vez de duplicar."
        )
    tomador = Tomador(
        id=uuid.uuid4(), cnpj=cnpj_norm, razao_social=razao_social, cod_municipio=cod_municipio,
        cep=cep, logradouro=logradouro, numero=numero, complemento=complemento, bairro=bairro,
        status="aprovado",
    )
    db.add(tomador)
    db.flush()
    return tomador
