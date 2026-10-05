"""
Vínculos (prestador_tomador) — Marco 5 (consulta) + Marco 13 (criação e
edição self-service, ver app/services/tomadores.py pro mesmo racional do
lado do catálogo de tomadores).

Toda função aqui presume que `definir_prestador_atual` já foi chamado na
sessão — a RLS cuida de só devolver/gravar vínculos do prestador certo.
"""
import datetime
import re
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models import Emissao, Prestador, PrestadorTomador, Tomador


class ApelidoJaExisteError(Exception):
    """Já existe um vínculo com esse apelido pra este prestador (ver
    UniqueConstraint uq_prestador_tomador_apelido em app/models.py) — dá um
    erro claro em vez de deixar estourar IntegrityError genérico."""


def listar_vinculos_ativos(db: Session) -> list[PrestadorTomador]:
    return (
        db.query(PrestadorTomador)
        .options(joinedload(PrestadorTomador.tomador))
        .filter(PrestadorTomador.ativo.is_(True), PrestadorTomador.excluido_em.is_(None))
        .order_by(PrestadorTomador.apelido)
        .all()
    )


def listar_vinculos_da_tela(db: Session) -> list[PrestadorTomador]:
    """Aba Tomadores (28/09/2026): ativos E inativos — "quando a pessoa
    desmarcar ele não suma, mas vá pra baixo com uma cor diferente". Só os
    excluídos ficam de fora. A ordem (dia de emissão, inativos por último)
    é decidida em `ordenar_para_tela`."""
    return (
        db.query(PrestadorTomador)
        .options(joinedload(PrestadorTomador.tomador))
        .filter(PrestadorTomador.excluido_em.is_(None))
        .all()
    )


def ordenar_para_tela(vinculos: list[PrestadorTomador]) -> list[PrestadorTomador]:
    """Ativos primeiro; dentro de cada grupo, pelo dia de emissão (quem não
    tem dia vai pro fim) e depois pelo apelido."""
    return sorted(
        vinculos,
        key=lambda v: (not v.ativo, v.dia_limite_emissao is None, v.dia_limite_emissao or 0, v.apelido.lower()),
    )


def emissoes_da_competencia(db: Session, competencia: str) -> dict[uuid.UUID, dict]:
    """Nota(s) ATIVA(s) (não canceladas) de cada vínculo na competência — o
    "gerado / não gerado" da aba Tomadores (mesmo critério do calendário e
    do dashboard). A Shopee tem várias no mês (uma por vendedor), por isso
    devolve a primeira + quantidade + soma."""
    emissoes = (
        db.query(Emissao)
        .filter(Emissao.competencia == competencia, Emissao.estado != "cancelada")
        .order_by(Emissao.criado_em)
        .all()
    )
    resumo: dict[uuid.UUID, dict] = {}
    for e in emissoes:
        atual = resumo.setdefault(e.prestador_tomador_id, {"id": e.id, "estado": e.estado, "valor": 0.0, "quantidade": 0})
        atual["valor"] += float(e.valor)
        atual["quantidade"] += 1
    return resumo


def excluir_vinculo(db: Session, vinculo: PrestadorTomador) -> str:
    """Devolve 'apagado' (sem notas: some do banco) ou 'arquivado' (com
    notas: fica no banco só pra as notas antigas continuarem íntegras, mas
    sai de todas as listas)."""
    tem_notas = db.query(Emissao.id).filter(Emissao.prestador_tomador_id == vinculo.id).first() is not None
    if not tem_notas:
        db.delete(vinculo)
        db.flush()
        return "apagado"
    # Libera o apelido pra ser reusado num tomador novo (o apelido é único
    # por prestador) — as notas antigas guardam o apelido original no
    # snapshot, então não perdem nada.
    carimbo = datetime.datetime.now(datetime.timezone.utc)
    sufixo = f" (excluído {carimbo:%d/%m/%Y %H:%M:%S})"
    vinculo.apelido = (vinculo.apelido[: 100 - len(sufixo)] + sufixo)
    vinculo.ativo = False
    vinculo.excluido_em = carimbo
    db.flush()
    return "arquivado"


def registrar_sugestoes(db: Session, vinculo: PrestadorTomador) -> None:
    """Guarda no catálogo (tomador, sem RLS) o que acabou de ser usado com
    este tomador — vira a "prévia de sugestão de preenchimento" pra
    próxima pessoa que for faturar o mesmo tomador. Contas de simulação não
    ensinam nada ao catálogo."""
    if db.query(Prestador.demo).filter_by(id=vinculo.prestador_id).scalar():
        return
    tomador = db.get(Tomador, vinculo.tomador_id)
    if tomador is None:
        return
    tomador.sug_cod_trib_nacional = vinculo.cod_trib_nacional
    tomador.sug_template_descricao = vinculo.template_descricao
    if vinculo.dia_limite_emissao is not None:
        tomador.sug_dia_emissao = vinculo.dia_limite_emissao
    if vinculo.dias_para_recebimento is not None:
        tomador.sug_dias_recebimento = vinculo.dias_para_recebimento
    db.flush()


def buscar_vinculo(db: Session, vinculo_id: uuid.UUID) -> PrestadorTomador | None:
    return (
        db.query(PrestadorTomador)
        .options(joinedload(PrestadorTomador.tomador), joinedload(PrestadorTomador.prestador))
        .filter_by(id=vinculo_id)
        .one_or_none()
    )


def _apelido_em_uso(db: Session, prestador_id: uuid.UUID, apelido: str, *, ignorar_id: uuid.UUID | None = None) -> bool:
    apelido = apelido.strip()
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
    email_contato: str | None = None, whatsapp_contato: str | None = None,
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
        email_contato=email_contato, whatsapp_contato=whatsapp_contato,
        ativo=True,
    )
    db.add(vinculo)
    db.flush()
    registrar_sugestoes(db, vinculo)
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
    if campos.keys() & {"cod_trib_nacional", "template_descricao", "dia_limite_emissao", "dias_para_recebimento"}:
        registrar_sugestoes(db, vinculo)
    return vinculo


# --- Cadastro comum de clientes (05/10/2026): usado pelo emissor (notas
# importadas) e pelo financeiro (fontes de receita sem nota) ---


def apelido_livre(db: Session, prestador_id: uuid.UUID, nome: str) -> str:
    base = re.sub(r"\s+", " ", nome).strip()[:60] or "Tomador"
    usados = {a.lower() for (a,) in db.query(PrestadorTomador.apelido).filter(PrestadorTomador.prestador_id == prestador_id)}
    apelido, n = base, 2
    while apelido.lower() in usados:
        apelido, n = f"{base[:55]} ({n})", n + 1
    return apelido


def criar_tomador_interno(db: Session, nome: str, cod_municipio: str) -> Tomador:
    """Tomador só desta conta (fonte de receita sem CNPJ, pessoa física,
    estrangeiro): não entra no catálogo compartilhado."""
    t = Tomador(
        id=uuid.uuid4(), cnpj="X" + uuid.uuid4().hex[:13].upper(), razao_social=nome[:200] or "Receita",
        cod_municipio=cod_municipio, status="interno",
    )
    db.add(t)
    db.flush()
    return t
