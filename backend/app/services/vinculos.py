"""
Vínculos (prestador_tomador) — Marco 5 (consulta) + Marco 13 (criação e
edição self-service, ver app/services/tomadores.py pro mesmo racional do
lado do catálogo de tomadores).

Toda função aqui presume que `definir_prestador_atual` já foi chamado na
sessão — a RLS cuida de só devolver/gravar vínculos do prestador certo.
"""
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models import PrestadorTomador


class ApelidoJaExisteError(Exception):
    """Já existe um vínculo com esse apelido pra este prestador (ver
    UniqueConstraint uq_prestador_tomador_apelido em app/models.py) — dá um
    erro claro em vez de deixar estourar IntegrityError genérico."""


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


def _apelido_em_uso(db: Session, prestador_id: uuid.UUID, apelido: str, *, ignorar_id: uuid.UUID | None = None) -> bool:
    query = db.query(PrestadorTomador).filter_by(prestador_id=prestador_id, apelido=apelido)
    if ignorar_id is not None:
        query = query.filter(PrestadorTomador.id != ignorar_id)
    return query.first() is not None


def criar_vinculo(
    db: Session, *, prestador_id: uuid.UUID, tomador_id: uuid.UUID, apelido: str,
    cod_local_prestacao: str, cod_trib_nacional: str, template_descricao: str,
    cod_trib_municipal: str | None = None, metodo_captura_valor: str = "manual",
    serie: str = "1", requer_revisao: bool = True,
    dia_limite_emissao: int | None = None, dias_para_recebimento: int | None = None,
) -> PrestadorTomador:
    """'Usar um tomador pré-cadastrado' e 'cadastrar meu próprio tomador' na
    tela de Tomadores viram a MESMA chamada aqui — a diferença já foi
    resolvida antes, em qual `tomador_id` chega (existente do catálogo, ou
    recém-criado por app.services.tomadores.criar_tomador)."""
    if _apelido_em_uso(db, prestador_id, apelido):
        raise ApelidoJaExisteError(f"Já existe um vínculo com o apelido '{apelido}' para este prestador.")

    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_id, tomador_id=tomador_id, apelido=apelido,
        cod_local_prestacao=cod_local_prestacao, cod_trib_nacional=cod_trib_nacional,
        cod_trib_municipal=cod_trib_municipal, template_descricao=template_descricao,
        metodo_captura_valor=metodo_captura_valor, serie=serie, requer_revisao=requer_revisao,
        dia_limite_emissao=dia_limite_emissao, dias_para_recebimento=dias_para_recebimento,
        ativo=True,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def atualizar_vinculo(db: Session, vinculo: PrestadorTomador, **campos) -> PrestadorTomador:
    """Atualiza só os campos passados (as 'regras de emissão' da tela de
    detalhe do tomador) — ex.: `atualizar_vinculo(db, v, template_descricao=novo)`.
    Edita o vínculo PADRÃO in-place; não existe versionamento (uma nota já
    emitida usa o `tomador_snapshot` congelado no rascunho, nunca isto
    aqui — ver app/services/motor_emissao.py, então mudar a regra padrão
    não reescreve notas antigas)."""
    if "apelido" in campos and campos["apelido"] != vinculo.apelido:
        if _apelido_em_uso(db, vinculo.prestador_id, campos["apelido"], ignorar_id=vinculo.id):
            raise ApelidoJaExisteError(f"Já existe um vínculo com o apelido '{campos['apelido']}' para este prestador.")

    for campo, valor in campos.items():
        setattr(vinculo, campo, valor)
    db.flush()
    return vinculo
