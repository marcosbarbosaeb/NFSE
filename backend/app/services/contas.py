"""Conta do usuário e empresas (29/09/2026), nos moldes do MandaNotas:

- Sessões no servidor: cada navegador logado é uma `Sessao`. A tela
  "Dispositivos conectados" lista e deixa desconectar; trocar a senha
  derruba os outros aparelhos.
- Vários CNPJs no mesmo login (`usuario_prestador`): a empresa ativa fica na
  sessão; o seletor do topo troca.
- Login por código de 6 dígitos enviado por e-mail (sem senha).
- Excluir empresa / excluir conta.

RLS: `usuario`, `usuario_prestador` e `sessao` não têm RLS (são lidas antes
de saber a empresa ativa). Dados de cada empresa continuam isolados: toda
leitura de `prestador` aqui seta o contexto daquela empresa antes.
"""
import datetime
import hashlib
import hmac
import logging
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import (
    AjusteEvento,
    Assinatura,
    Certificado,
    Despesa,
    Emissao,
    Envio,
    EventoManual,
    LoteAcao,
    PagamentoRecebido,
    Prestador,
    PrestadorTomador,
    Sessao,
    Usuario,
    UsuarioPrestador,
)

logger = logging.getLogger("agenteana.contas")

VALIDADE_CODIGO = datetime.timedelta(minutes=10)
MAX_TENTATIVAS_CODIGO = 5
_ATUALIZAR_ACESSO_A_CADA = datetime.timedelta(minutes=5)


class ContaError(Exception):
    pass


def _agora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# --- sessões ----------------------------------------------------------------


def iniciar_sessao(db: Session, request, usuario: Usuario, prestador_id: uuid.UUID | None = None) -> Sessao:
    """Loga o usuário neste navegador: cria a `Sessao` e grava no cookie."""
    from app.limites import ip_do_cliente

    sessao = Sessao(
        id=uuid.uuid4(), usuario_id=usuario.id,
        user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        ip=ip_do_cliente(request)[:64],
    )
    db.add(sessao)
    db.flush()
    request.session.clear()
    request.session["usuario_id"] = str(usuario.id)
    request.session["sessao_id"] = str(sessao.id)
    request.session["prestador_id"] = str(prestador_id or usuario.prestador_id)
    return sessao


def validar_sessao(db: Session, request, usuario: Usuario) -> bool:
    """False = sessão desconectada (revogada). Cookie antigo, de antes das
    sessões no servidor, ganha uma `Sessao` na hora."""
    bruto = request.session.get("sessao_id")
    if not bruto:
        iniciar_sessao_existente(db, request, usuario)
        return True
    try:
        sessao = db.get(Sessao, uuid.UUID(bruto))
    except ValueError:
        return False
    if sessao is None or sessao.revogada_em is not None or sessao.usuario_id != usuario.id:
        return False
    if sessao.ultimo_acesso is None or _agora() - sessao.ultimo_acesso > _ATUALIZAR_ACESSO_A_CADA:
        sessao.ultimo_acesso = _agora()
        db.commit()
    return True


def iniciar_sessao_existente(db: Session, request, usuario: Usuario) -> None:
    prestador = request.session.get("prestador_id")
    iniciar_sessao(db, request, usuario, uuid.UUID(prestador) if prestador else None)
    db.commit()


def empresa_ativa(db: Session, request, usuario: Usuario) -> uuid.UUID:
    bruto = request.session.get("prestador_id")
    if bruto:
        try:
            escolhida = uuid.UUID(bruto)
        except ValueError:
            escolhida = None
        if escolhida and tem_acesso(db, usuario.id, escolhida):
            return escolhida
    return usuario.prestador_id


def tem_acesso(db: Session, usuario_id: uuid.UUID, prestador_id: uuid.UUID) -> bool:
    """Dono (usuario_prestador) ou contador autorizado (acesso_contador)."""
    if db.get(UsuarioPrestador, (usuario_id, prestador_id)) is not None:
        return True
    from app.services.acesso import acesso_de_contador

    return acesso_de_contador(db, usuario_id, prestador_id) is not None


def eh_dono(db: Session, usuario: Usuario, prestador_id: uuid.UUID) -> bool:
    return usuario.prestador_id == prestador_id or db.get(UsuarioPrestador, (usuario.id, prestador_id)) is not None


def listar_sessoes(db: Session, usuario_id: uuid.UUID, atual: str | None) -> list[dict]:
    sessoes = (
        db.query(Sessao)
        .filter(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
        .order_by(Sessao.ultimo_acesso.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": s.id, "dispositivo": descrever_navegador(s.user_agent), "ip": s.ip,
            "criado_em": s.criado_em, "ultimo_acesso": s.ultimo_acesso, "atual": str(s.id) == atual,
        }
        for s in sessoes
    ]


def descrever_navegador(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    sistema = next((nome for chave, nome in (
        ("iphone", "iPhone"), ("ipad", "iPad"), ("android", "Android"), ("windows", "Windows"),
        ("mac os", "Mac"), ("linux", "Linux"),
    ) if chave in ua), "Outro")
    navegador = next((nome for chave, nome in (
        ("edg/", "Edge"), ("opr/", "Opera"), ("chrome/", "Chrome"), ("firefox/", "Firefox"), ("safari/", "Safari"),
    ) if chave in ua), "Navegador")
    return f"{sistema} · {navegador}"


def revogar_sessao(db: Session, usuario_id: uuid.UUID, sessao_id: uuid.UUID) -> bool:
    sessao = db.get(Sessao, sessao_id)
    if sessao is None or sessao.usuario_id != usuario_id or sessao.revogada_em is not None:
        return False
    sessao.revogada_em = _agora()
    db.flush()
    return True


def revogar_outras(db: Session, usuario_id: uuid.UUID, manter: str | None) -> int:
    quantas = 0
    for s in db.query(Sessao).filter(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None)):
        if str(s.id) != manter:
            s.revogada_em = _agora()
            quantas += 1
    db.flush()
    return quantas


# --- login por código ---------------------------------------------------------


def _hash_codigo(codigo: str) -> str:
    chave = get_settings().session_secret_key.encode()
    return hmac.new(chave, codigo.encode(), hashlib.sha256).hexdigest()


def gerar_codigo(db: Session, email: str) -> tuple[Usuario, str] | None:
    """Cria um código de 6 dígitos (10 min) pro e-mail, se existir conta
    ativa. Devolve (usuario, codigo) pra quem chamou mandar o e-mail; None se
    não há conta (a rota responde igual nos dois casos — não revela quem tem
    conta)."""
    usuario = db.query(Usuario).filter_by(email=email.strip().lower(), ativo=True).one_or_none()
    if usuario is None:
        return None
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    usuario.login_codigo_hash = _hash_codigo(codigo)
    usuario.login_codigo_expira_em = _agora() + VALIDADE_CODIGO
    usuario.login_codigo_tentativas = 0
    db.flush()
    return usuario, codigo


def entrar_com_codigo(db: Session, email: str, codigo: str) -> Usuario | None:
    usuario = db.query(Usuario).filter_by(email=email.strip().lower(), ativo=True).one_or_none()
    if usuario is None or not usuario.login_codigo_hash or not usuario.login_codigo_expira_em:
        return None
    if usuario.login_codigo_expira_em < _agora() or usuario.login_codigo_tentativas >= MAX_TENTATIVAS_CODIGO:
        return None
    if not hmac.compare_digest(usuario.login_codigo_hash, _hash_codigo("".join(c for c in codigo if c.isdigit()))):
        usuario.login_codigo_tentativas += 1
        db.flush()
        return None
    usuario.login_codigo_hash = None
    usuario.login_codigo_expira_em = None
    usuario.login_codigo_tentativas = 0
    # Quem recebeu o código no e-mail provou que o e-mail é dele.
    usuario.email_confirmado = True
    db.flush()
    return usuario


# --- empresas ---------------------------------------------------------------


def listar_empresas(db: Session, usuario: Usuario) -> list[dict]:
    ids = [p for (p,) in db.query(UsuarioPrestador.prestador_id).filter_by(usuario_id=usuario.id)]
    if usuario.prestador_id not in ids:
        ids.insert(0, usuario.prestador_id)
    empresas = []
    for prestador_id in ids:
        definir_prestador_atual(db, prestador_id)
        p = db.get(Prestador, prestador_id)
        if p is not None:
            empresas.append({"id": p.id, "razao_social": p.razao_social, "nome_fantasia": p.nome_fantasia, "cnpj": p.cpf_cnpj, "papel": "dono"})
    return empresas


def listar_empresas_atendidas(db: Session, usuario: Usuario) -> list[dict]:
    """Empresas em que este login entra como contador (pro seletor de empresa)."""
    from app.models import AcessoContador

    proprias = {p for (p,) in db.query(UsuarioPrestador.prestador_id).filter_by(usuario_id=usuario.id)} | {usuario.prestador_id}
    empresas = []
    for (prestador_id,) in db.query(AcessoContador.prestador_id).filter_by(usuario_id=usuario.id, status="ativo").order_by(AcessoContador.aceito_em):
        if prestador_id in proprias:
            continue
        definir_prestador_atual(db, prestador_id)
        p = db.get(Prestador, prestador_id)
        if p is not None:
            empresas.append({"id": p.id, "razao_social": p.razao_social, "nome_fantasia": p.nome_fantasia, "cnpj": p.cpf_cnpj, "papel": "contador"})
    return empresas


def adicionar_empresa(
    db: Session, usuario: Usuario, *, cpf_cnpj: str, razao_social: str, cod_municipio: str,
    nome_fantasia: str | None = None, cep: str | None = None, logradouro: str | None = None,
    numero: str | None = None, complemento: str | None = None, bairro: str | None = None,
    modulos: list[str] | None = None,
) -> Prestador:
    """Mais um CNPJ no mesmo login (com teste grátis próprio)."""
    from app.services.billing import criar_assinatura_trial

    prestador_id = uuid.uuid4()
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        id=prestador_id, cpf_cnpj="".join(c for c in cpf_cnpj if c.isdigit()), razao_social=razao_social.strip()[:200],
        nome_fantasia=(nome_fantasia or "").strip()[:200] or None, cod_municipio=cod_municipio,
        cep=cep, logradouro=logradouro, numero=numero, complemento=complemento, bairro=bairro,
        modulos=list(modulos) if modulos else ["emissor"],
    )
    try:
        # O `add` fica DENTRO do savepoint: se o CNPJ já existe, só a empresa
        # recusada é desfeita (antes, o flush automático do begin_nested
        # derrubava a transação inteira do pedido).
        with db.begin_nested():
            db.add(prestador)
            db.flush()
    except IntegrityError as exc:
        raise ContaError("Esse CNPJ já está cadastrado na Agente Ana.") from exc
    criar_assinatura_trial(db, prestador_id)
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador_id))
    db.flush()
    return prestador


def apagar_empresa(db: Session, prestador_id: uuid.UUID) -> None:
    """Apaga a empresa e TODO o histórico dela no sistema (notas, tomadores,
    recebimentos...). As notas já autorizadas continuam existindo na Receita
    — a tela avisa pra baixar os XMLs antes. Assinatura no Stripe é
    cancelada (se houver). Não dá commit."""
    definir_prestador_atual(db, prestador_id)
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    if assinatura is not None and assinatura.stripe_subscription_id and get_settings().stripe_secret_key:
        try:
            import stripe

            stripe.Subscription.cancel(assinatura.stripe_subscription_id, api_key=get_settings().stripe_secret_key)
        except Exception:  # noqa: BLE001 — não impede a exclusão; fica no log
            logger.exception("Falha ao cancelar assinatura Stripe do prestador %s", prestador_id)
    emissoes = [e for (e,) in db.query(Emissao.id).filter(Emissao.prestador_id == prestador_id)]
    if emissoes:
        db.query(Envio).filter(Envio.emissao_id.in_(emissoes)).delete(synchronize_session=False)
    for modelo in (LoteAcao, Emissao, PagamentoRecebido, Despesa, EventoManual, AjusteEvento, PrestadorTomador, Certificado, Assinatura):
        db.query(modelo).filter(modelo.prestador_id == prestador_id).delete(synchronize_session=False)
    # Usuários que tinham esta como empresa principal passam pra outra (ou
    # são apagados, se não tiverem outra).
    for usuario in db.query(Usuario).filter(Usuario.prestador_id == prestador_id).all():
        outra = (
            db.query(UsuarioPrestador.prestador_id)
            .filter(UsuarioPrestador.usuario_id == usuario.id, UsuarioPrestador.prestador_id != prestador_id)
            .first()
        )
        if outra is None:
            db.delete(usuario)
        else:
            usuario.prestador_id = outra[0]
    db.flush()
    db.query(UsuarioPrestador).filter(UsuarioPrestador.prestador_id == prestador_id).delete(synchronize_session=False)
    db.query(Prestador).filter(Prestador.id == prestador_id).delete(synchronize_session=False)
    db.flush()


def apagar_conta(db: Session, usuario: Usuario) -> None:
    """Apaga o login e as empresas em que ele é o único usuário."""
    ids = {p for (p,) in db.query(UsuarioPrestador.prestador_id).filter_by(usuario_id=usuario.id)} | {usuario.prestador_id}
    usuario_id = usuario.id
    for prestador_id in ids:
        outros = (
            db.query(UsuarioPrestador)
            .filter(UsuarioPrestador.prestador_id == prestador_id, UsuarioPrestador.usuario_id != usuario_id)
            .count()
        )
        if outros == 0:
            apagar_empresa(db, prestador_id)
    restante = db.get(Usuario, usuario_id)
    if restante is not None:
        db.delete(restante)
    db.flush()
