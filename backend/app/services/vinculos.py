"""
Consulta de vínculos (prestador_tomador) para o painel — Marco 5.

Só leitura. Presume que `definir_prestador_atual` já foi chamado na sessão
(a RLS cuida de só devolver vínculos do prestador certo).
"""
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models import PrestadorTomador


def listar_vinculos_ativos(db: Session) -> list[PrestadorTomador]:
    return (
        db.query(PrestadorTomador)
        .options(joinedload(PrestadorTomador.tomador))
        .filter_by(ativo=True)
        .order_by(PrestadorTomador.apelido)
        .all()
    )


def buscar_vinculo(db: Session, vinculo_id: uuid.UUID) -> PrestadorTomador | None:
    return (
        db.query(PrestadorTomador)
        .options(joinedload(PrestadorTomador.tomador), joinedload(PrestadorTomador.prestador))
        .filter_by(id=vinculo_id)
        .one_or_none()
    )
