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


def registrar_sugestoes(db: Session, vinculo: PrestadorTomador, *, sobrescrever: bool = False) -> bool:
    """Guarda no catálogo (tomador, sem RLS) como este tomador costuma ser
    faturado — vira a sugestão de preenchimento pra próxima pessoa. Só
    regras da nota (códigos, descrição, dia, prazo): nada de e-mail,
    telefone ou destinatários, que são de cada conta.

    Por padrão só PREENCHE o que o catálogo ainda não tem — a conta de um
    cliente qualquer não troca a sugestão que já está lá. `sobrescrever`
    é da curadoria (ver `publicar_sugestoes`). Simulação, cliente só de
    controle e tomador interno não ensinam nada ao catálogo."""
    if db.query(Prestador.demo).filter_by(id=vinculo.prestador_id).scalar():
        return False
    tomador = db.get(Tomador, vinculo.tomador_id)
    if tomador is None or vinculo.sem_nota or tomador.status != "aprovado":
        return False
    from app.services.envio_direto import formas_de_envio
    from app.services.sugestoes import limpar_texto

    # Nada pessoal vai pro catálogo: conta bancária, CNPJ, pedido, ID de
    # afiliado saem; o nome da empresa vira {prestador} nos textos de e-mail.
    prestador = db.get(Prestador, vinculo.prestador_id)
    # 08/10/2026: e o nome de quem usa a conta (assinatura do e-mail).
    from app.models import Usuario, UsuarioPrestador

    pessoas = [
        n for (n,) in db.query(Usuario.nome).join(UsuarioPrestador, UsuarioPrestador.usuario_id == Usuario.id)
        .filter(UsuarioPrestador.prestador_id == vinculo.prestador_id, Usuario.nome.isnot(None))
    ]
    nomes = tuple(n for n in (getattr(prestador, "razao_social", None), getattr(prestador, "nome_fantasia", None), *pessoas) if n)
    tem_modelo_de_envio = vinculo.envio_formas is not None
    novos = {
        "sug_cod_trib_nacional": vinculo.cod_trib_nacional,
        "sug_template_descricao": limpar_texto(vinculo.template_descricao, nomes),
        "sug_dia_emissao": vinculo.dia_limite_emissao,
        "sug_dias_recebimento": vinculo.dias_para_recebimento,
        # (o código municipal muda de cidade pra cidade: não é sugerido)
        "sug_cod_nbs": vinculo.cod_nbs,
        "sug_meses_atras": vinculo.descricao_meses_atras or 0,
        "sug_envio_formas": formas_de_envio(vinculo) if tem_modelo_de_envio else None,
        "sug_email_assunto": limpar_texto(vinculo.email_assunto, nomes, "{prestador}"),
        "sug_email_mensagem": limpar_texto(vinculo.email_mensagem, nomes, "{prestador}"),
        "sug_email_anexos": vinculo.email_anexos,
    }
    # Textos livres: na curadoria, o que não passa na limpeza APAGA a sugestão
    # antiga (ela pode ter dado pessoal de antes desta regra).
    textos_livres = ("sug_template_descricao", "sug_email_assunto", "sug_email_mensagem")
    mudou = False
    for campo, valor in novos.items():
        vazio = valor is None or valor == ""
        if vazio and not (sobrescrever and campo in textos_livres):
            continue
        if sobrescrever or getattr(tomador, campo) in (None, ""):
            if getattr(tomador, campo) != (None if vazio else valor):
                setattr(tomador, campo, None if vazio else valor)
                mudou = True
    if sobrescrever and tomador.sug_cod_trib_municipal is not None:
        tomador.sug_cod_trib_municipal = None
        mudou = True
    db.flush()
    return mudou


def publicar_sugestoes(db: Session) -> int:
    """Curadoria: as regras de TODOS os tomadores da empresa ativa viram a
    sugestão padrão do catálogo (sobrescrevendo). Quando o mesmo tomador
    tem mais de um cadastro (AWIN e AWIN Rchlo), vale o mais antigo."""
    vistos: set[uuid.UUID] = set()
    publicados = 0
    for vinculo in (
        db.query(PrestadorTomador)
        .filter(PrestadorTomador.excluido_em.is_(None), PrestadorTomador.ativo.is_(True), PrestadorTomador.sem_nota.is_(False))
        .order_by(PrestadorTomador.criado_em)
    ):
        if vinculo.tomador_id in vistos:
            continue
        vistos.add(vinculo.tomador_id)
        registrar_sugestoes(db, vinculo, sobrescrever=True)
        publicados += 1
    return publicados


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
    registrar_sugestoes(db, vinculo)  # só preenche o que o catálogo ainda não tem
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
