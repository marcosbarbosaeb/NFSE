"""Carteira do contador (2026.10.7, pedidos do Marcos em 10/10/2026).

"O contador deve poder fazer a gestão de seus clientes no módulo contador" e
"temos que contabilizar esses clientes ativos dele para gerar nossas
cobranças". Três partes:

1. **Números de cada cliente** (Painel do contador › Gestão): só das empresas
   que ele atende — situação do acesso, notas e faturamento do mês,
   certificado, último uso e se o cliente está **ativo no mês**.
2. **Cadastrar cliente novo**: o contador cria a empresa (com a mesma
   verificação de cidade e regime do cadastro), fica com acesso total a ela e
   a Ana convida o dono por e-mail para criar o login dele.
3. **Contagem para a cobrança** (Gestão da plataforma › Contadores): por
   contador, clientes na carteira, ativos no mês e cadastrados por ele.
   A cobrança em si NÃO está ligada: o modelo (quem paga — o cliente ou o
   contador por cliente; cupom do contador) está em aberto
   (`claude/duvidas-para-o-marcos.md`).

**Cliente ativo no mês** = acesso do contador ativo, empresa não bloqueada nem
cancelada, e no mês corrente teve nota autorizada OU alguém usou a Ana nela
(`evento_uso`). Mudar a regra é mudar `ativo_no_mes`.
"""
from __future__ import annotations

import datetime
import secrets
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import definir_prestador_atual
from app.models import AcessoContador, ConviteDono, EventoUso, Prestador, Usuario, UsuarioPrestador
from app.tempo import hoje as hoje_br

VALIDADE_CONVITE = datetime.timedelta(days=14)
_PARADAS = {"bloqueada", "cancelada", "teste_acabou", "sem_assinatura"}


class CarteiraError(Exception):
    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


# --- 1. números ---------------------------------------------------------------


def ultimo_uso(db: Session, prestador_ids: list[uuid.UUID]) -> dict[uuid.UUID, datetime.datetime]:
    """Último registro de uso de cada empresa (`evento_uso` não tem RLS)."""
    if not prestador_ids:
        return {}
    linhas = db.query(EventoUso.prestador_id, func.max(EventoUso.criado_em)).filter(
        EventoUso.prestador_id.in_(prestador_ids)).group_by(EventoUso.prestador_id).all()
    return {p: quando for p, quando in linhas}


def ativo_no_mes(cliente: dict, uso: datetime.datetime | None, hoje: datetime.date | None = None) -> bool:
    hoje = hoje or hoje_br()
    sit = cliente.get("situacao") or {}
    if sit.get("bloqueado") or sit.get("motivo") in _PARADAS:
        return False
    raio = cliente.get("raio_x") or {}
    if (raio.get("notas_mes") or 0) > 0:
        return True
    return uso is not None and (uso.year, uso.month) == (hoje.year, hoje.month)


def completar_clientes(db: Session, clientes: list[dict], hoje: datetime.date | None = None) -> dict:
    """Acrescenta a cada cliente do painel `ultimo_uso`, `ativo_no_mes`,
    `criado_pelo_contador` e `convite_dono`; devolve a contagem da carteira."""
    hoje = hoje or hoje_br()
    usos = ultimo_uso(db, [c["prestador_id"] for c in clientes])
    acessos = {a.id: a for a in db.query(AcessoContador).filter(AcessoContador.id.in_([c["id"] for c in clientes])).all()} if clientes else {}
    convites = {}
    if clientes:
        for cv in db.query(ConviteDono).filter(ConviteDono.prestador_id.in_([c["prestador_id"] for c in clientes])).order_by(ConviteDono.criado_em).all():
            convites[cv.prestador_id] = cv
    for c in clientes:
        uso = usos.get(c["prestador_id"])
        c["ultimo_uso"] = uso.isoformat() if uso else None
        c["ativo_no_mes"] = ativo_no_mes(c, uso, hoje)
        a = acessos.get(c["id"])
        c["criado_pelo_contador"] = bool(a and a.criado_pelo_contador)
        cv = convites.get(c["prestador_id"])
        c["convite_dono"] = None if cv is None else {
            "email": cv.email, "aceito": cv.aceito_em is not None,
            "vencido": cv.aceito_em is None and cv.expira_em < datetime.datetime.now(datetime.timezone.utc),
        }
    return contagem(clientes)


def contagem(clientes: list[dict]) -> dict:
    return {
        "na_carteira": len(clientes),
        "ativos_no_mes": sum(1 for c in clientes if c.get("ativo_no_mes")),
        "cadastrados_pelo_contador": sum(1 for c in clientes if c.get("criado_pelo_contador")),
    }


# --- 2. cadastrar cliente -----------------------------------------------------


def cadastrar_cliente(
    db: Session, contador: Usuario, *, cpf_cnpj: str, razao_social: str, cod_municipio: str, email_dono: str,
    nome_fantasia: str | None = None, modulos: list[str] | None = None,
) -> tuple[Prestador, AcessoContador, ConviteDono]:
    """Cria a empresa do cliente (teste grátis próprio), dá ao contador acesso
    com todas as permissões (menos documentos da empresa, que só o dono libera)
    e cria o convite do dono. Não dá commit. A verificação de cidade/regime
    fica na rota (a mesma do cadastro)."""
    from sqlalchemy.exc import IntegrityError

    from app.services import acesso
    from app.services.billing import criar_assinatura_trial

    email_dono = email_dono.strip().lower()
    if email_dono == contador.email.lower():
        raise CarteiraError("Use o e-mail do dono da empresa, não o seu.", 422)
    prestador_id = uuid.uuid4()
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        id=prestador_id, cpf_cnpj="".join(c for c in cpf_cnpj if c.isdigit()), razao_social=razao_social.strip()[:200],
        nome_fantasia=(nome_fantasia or "").strip()[:200] or None, cod_municipio=cod_municipio,
        modulos=list(modulos) if modulos else ["emissor", "financeiro"],
    )
    try:
        with db.begin_nested():
            db.add(prestador)
            db.flush()
    except IntegrityError as exc:
        raise CarteiraError("Esse CNPJ já está cadastrado na Agente Ana. Peça ao dono para convidar você em Empresa › Contador.", 409) from exc
    criar_assinatura_trial(db, prestador_id)
    agora = datetime.datetime.now(datetime.timezone.utc)
    # Documentos da empresa ficam de fora: têm documento pessoal de sócio, quem libera é o dono.
    permissoes = [p for p in acesso.PERMISSOES if p != "documentos"]
    a = AcessoContador(
        id=uuid.uuid4(), prestador_id=prestador_id, email=contador.email, usuario_id=contador.id, permissoes=permissoes,
        status="ativo", convidado_por=contador.email, aceito_em=agora, criado_pelo_contador=True,
    )
    db.add(a)
    convite = ConviteDono(id=uuid.uuid4(), prestador_id=prestador_id, email=email_dono, token=secrets.token_urlsafe(32),
                          criado_por=contador.id, expira_em=agora + VALIDADE_CONVITE)
    db.add(convite)
    db.flush()
    from app.services import parceiros

    parceiros.vincular_contador(db, contador, prestador_id, prestador.razao_social, "trial")
    return prestador, a, convite


def renovar_convite(db: Session, contador: Usuario, acesso_id: uuid.UUID) -> tuple[ConviteDono, str]:
    a = db.get(AcessoContador, acesso_id)
    if a is None or a.usuario_id != contador.id or a.status != "ativo":
        raise CarteiraError("Cliente não encontrado.", 404)
    convite = db.query(ConviteDono).filter_by(prestador_id=a.prestador_id).order_by(ConviteDono.criado_em.desc()).first()
    if convite is None:
        raise CarteiraError("Essa empresa não foi cadastrada por você: o dono já tem acesso.", 404)
    if convite.aceito_em is not None:
        raise CarteiraError("O dono já aceitou o convite.", 409)
    convite.token = secrets.token_urlsafe(32)
    convite.expira_em = datetime.datetime.now(datetime.timezone.utc) + VALIDADE_CONVITE
    db.flush()
    return convite, _nome_empresa(db, a.prestador_id)


def _nome_empresa(db: Session, prestador_id: uuid.UUID) -> str:
    definir_prestador_atual(db, prestador_id)
    p = db.get(Prestador, prestador_id)
    return (p.nome_fantasia or p.razao_social) if p else "a empresa"


# --- convite do dono ------------------------------------------------------------


def _convite_valido(db: Session, token: str) -> ConviteDono:
    convite = db.query(ConviteDono).filter_by(token=token).one_or_none()
    if convite is None:
        raise CarteiraError("Convite não encontrado. Peça ao seu contador um link novo.", 404)
    if convite.aceito_em is not None:
        raise CarteiraError("Este convite já foi usado. Entre com o seu e-mail e senha.", 409)
    if convite.expira_em < datetime.datetime.now(datetime.timezone.utc):
        raise CarteiraError("Este convite venceu. Peça ao seu contador um link novo.", 410)
    return convite


def ver_convite(db: Session, token: str) -> dict:
    convite = _convite_valido(db, token)
    contador = db.get(Usuario, convite.criado_por) if convite.criado_por else None
    definir_prestador_atual(db, convite.prestador_id)
    p = db.get(Prestador, convite.prestador_id)
    tem_conta = db.query(Usuario.id).filter_by(email=convite.email).first() is not None
    return {
        "empresa": p.razao_social if p else None, "cnpj": p.cpf_cnpj if p else None, "email": convite.email,
        "contador": (contador.nome or contador.email) if contador else None, "tem_conta": tem_conta,
    }


def aceitar_convite_novo(db: Session, token: str, *, senha: str, telefone: str, nome: str | None = None) -> Usuario:
    """Dono sem conta: cria o login dele já confirmado (o link chegou no e-mail dele)."""
    from app.auth import hash_senha
    from app import novidades

    convite = _convite_valido(db, token)
    if db.query(Usuario.id).filter_by(email=convite.email).first() is not None:
        raise CarteiraError("Já existe uma conta com este e-mail. Entre com ela para aceitar o convite.", 409)
    usuario = Usuario(
        id=uuid.uuid4(), prestador_id=convite.prestador_id, email=convite.email, senha_hash=hash_senha(senha),
        telefone=telefone, nome=(nome or "").strip()[:200] or None, preferencias=novidades.marcar_em_dia(None),
        email_confirmado=True,
    )
    db.add(usuario)
    db.flush()
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=convite.prestador_id))
    convite.aceito_em, convite.usuario_id = datetime.datetime.now(datetime.timezone.utc), usuario.id
    db.flush()
    return usuario


def aceitar_convite_logado(db: Session, token: str, usuario: Usuario) -> uuid.UUID:
    """Dono que já tem conta: a empresa entra no login dele."""
    convite = _convite_valido(db, token)
    if usuario.email.lower() != convite.email.lower():
        raise CarteiraError(f"Este convite é para {convite.email}. Entre com esse e-mail para aceitar.", 403)
    ja = db.query(UsuarioPrestador).filter_by(usuario_id=usuario.id, prestador_id=convite.prestador_id).one_or_none()
    if ja is None:
        db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=convite.prestador_id))
    convite.aceito_em, convite.usuario_id = datetime.datetime.now(datetime.timezone.utc), usuario.id
    db.flush()
    return convite.prestador_id


# --- 3. contagem da plataforma ------------------------------------------------


def resumo_gestao(db: Session, voltar_para: uuid.UUID, hoje: datetime.date | None = None) -> list[dict]:
    """Gestão da plataforma › Contadores: por contador, clientes na carteira,
    ativos no mês e cadastrados por ele. Só números (nunca conteúdo)."""
    from app.services import acesso, raio_x

    hoje = hoje or hoje_br()
    ativos = db.query(AcessoContador).filter(AcessoContador.status == "ativo", AcessoContador.usuario_id.isnot(None)).all()
    por_contador: dict[uuid.UUID, list[AcessoContador]] = {}
    for a in ativos:
        por_contador.setdefault(a.usuario_id, []).append(a)
    usos = ultimo_uso(db, list({a.prestador_id for a in ativos}))
    saida = []
    try:
        cache: dict[uuid.UUID, dict] = {}
        for usuario_id, lista in por_contador.items():
            contador = db.get(Usuario, usuario_id)
            clientes = []
            for a in lista:
                if a.prestador_id not in cache:
                    sit = acesso.situacao(db, a.prestador_id)
                    definir_prestador_atual(db, a.prestador_id)
                    p = db.get(Prestador, a.prestador_id)
                    notas = raio_x.da_empresa(db, p, hoje)["notas_mes"] if p is not None else 0
                    cache[a.prestador_id] = {"situacao": sit, "raio_x": {"notas_mes": notas}}
                base = cache[a.prestador_id]
                clientes.append({**base, "ativo_no_mes": ativo_no_mes(base, usos.get(a.prestador_id), hoje),
                                 "criado_pelo_contador": a.criado_pelo_contador})
            saida.append({"email": contador.email if contador else None, "nome": contador.nome if contador else None, **contagem(clientes)})
    finally:
        definir_prestador_atual(db, voltar_para)
    saida.sort(key=lambda x: (-x["ativos_no_mes"], -x["na_carteira"]))
    return saida
