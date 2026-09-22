"""
Cadastro público self-service — Marco 15, item 4 do pedido do Marcos: "cria
a conta na hora" (não é só captura de lead — o Prestador+Usuario nascem de
verdade no banco no momento do POST), com confirmação por e-mail
obrigatória antes de liberar login (escolha do Marcos entre as opções
apresentadas — reduz cadastro com e-mail errado/alheio).

Cria DOIS registros numa única operação: um Prestador novo (razão social,
CNPJ, município — o mínimo pra esse prestador já poder configurar vínculos
depois) e o Usuario que loga nele, com `email_confirmado=False` e um token
de uso único (ver Usuario.token_confirmacao em app/models.py). O e-mail de
confirmação é OPCIONAL de verdade nesse sentido: se o envio falhar (Resend
fora do ar, por exemplo), a conta AINDA é criada — só não fica utilizável
até alguém confirmar (por reenvio) ou um admin confirmar manualmente via
banco. Falha de e-mail nunca deve apagar um cadastro que já aconteceu.
"""
import datetime
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_senha
from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import Prestador, Usuario
from app.services.billing import criar_assinatura_trial
from app.services.email import EmailEnvioError, get_email_sender

_VALIDADE_TOKEN = datetime.timedelta(hours=24)


class EmailJaCadastradoError(Exception):
    pass


class PrestadorJaCadastradoError(Exception):
    """CNPJ já tem uma conta — mensagem intencionalmente vaga sobre QUEM é o
    dono (não expõe a razão social de outra empresa pra quem está tentando
    cadastrar)."""


class TokenInvalidoOuExpiradoError(Exception):
    pass


def _gerar_token() -> str:
    return secrets.token_urlsafe(32)


def criar_cadastro(
    db: Session,
    *,
    email: str,
    senha: str,
    razao_social: str,
    cpf_cnpj: str,
    cod_municipio: str,
    cep: str | None = None,
    logradouro: str | None = None,
    numero: str | None = None,
    complemento: str | None = None,
    bairro: str | None = None,
) -> Usuario:
    email_norm = email.strip().lower()
    cnpj_norm = "".join(c for c in cpf_cnpj if c.isdigit())

    if db.query(Usuario).filter_by(email=email_norm).one_or_none() is not None:
        raise EmailJaCadastradoError(f"Já existe uma conta com o e-mail '{email_norm}'.")

    # SEM pre-check de CNPJ duplicado via SELECT de propósito: a RLS de
    # `prestador` isola por `id` (não por prestador_id — é a própria tabela
    # raiz do tenant, ver alembic/versions/5af6e092d5e1_rls.py), então uma
    # sessão só enxerga a PRÓPRIA linha. Numa sessão nova (cadastro público,
    # sem prestador autenticado ainda) isso significa que ELA NÃO ENXERGA
    # NENHUM prestador existente — um SELECT filtrado por cpf_cnpj sempre
    # devolveria vazio, mesmo se o CNPJ já estiver cadastrado (falso
    # negativo perigoso). A garantia de verdade é a UniqueConstraint do
    # banco (cpf_cnpj, ver app/models.py); pegamos a violação dela abaixo.
    prestador_id = uuid.uuid4()
    # RLS em `prestador` exige app.current_prestador_id == id já NA HORA do
    # INSERT (WITH CHECK) — como este cadastro cria um prestador NOVO (ainda
    # não existe sessão autenticada nenhuma pra ter setado isso), a única
    # forma de o INSERT passar é setar a variável pro id que a gente MESMO
    # acabou de gerar, antes de inserir. Mesmo padrão usado pelo fixture
    # `prestador_teste` em tests/conftest.py.
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        id=prestador_id,
        cpf_cnpj=cnpj_norm,
        razao_social=razao_social.strip(),
        cod_municipio=cod_municipio,
        # Marco 16 — vêm do autopreenchimento via CNPJ (opcional; None
        # quando quem cadastrou digitou tudo na mão, como sempre foi).
        cep=cep,
        logradouro=logradouro,
        numero=numero,
        complemento=complemento,
        bairro=bairro,
    )
    db.add(prestador)
    try:
        # SAVEPOINT (não a transação toda) — se a UniqueConstraint de
        # cpf_cnpj estourar, só ESTE insert é desfeito; o resto da sessão
        # (e o check de e-mail acima) continua utilizável normalmente.
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise PrestadorJaCadastradoError("Já existe uma conta cadastrada com este CNPJ.") from exc

    # Marco 15 (item 4) — cadastro self-service libera acesso por um trial
    # sem cartão (ver docstring de criar_assinatura_trial); RLS de
    # `assinatura` já enxerga este prestador_id porque `definir_prestador_atual`
    # foi chamado acima, antes do INSERT de `prestador`.
    criar_assinatura_trial(db, prestador_id)

    token = _gerar_token()
    usuario = Usuario(
        id=uuid.uuid4(),
        prestador_id=prestador.id,
        email=email_norm,
        senha_hash=hash_senha(senha),
        email_confirmado=False,
        token_confirmacao=token,
        token_confirmacao_expira_em=datetime.datetime.now(datetime.timezone.utc) + _VALIDADE_TOKEN,
    )
    db.add(usuario)
    db.flush()

    _enviar_email_confirmacao(usuario.email, token)
    return usuario


def _enviar_email_confirmacao(email: str, token: str) -> None:
    link = f"{get_settings().app_base_url}/confirmar-email?token={token}"
    corpo_texto = (
        f"Bem-vindo(a) ao NotaFácil!\n\n"
        f"Confirme seu e-mail clicando no link abaixo (válido por 24 horas):\n{link}\n\n"
        f"Se você não pediu esse cadastro, pode ignorar esta mensagem."
    )
    corpo_html = (
        f"<p>Bem-vindo(a) ao NotaFácil!</p>"
        f'<p>Confirme seu e-mail clicando <a href="{link}">aqui</a> (válido por 24 horas).</p>'
        f"<p>Se você não pediu esse cadastro, pode ignorar esta mensagem.</p>"
    )
    try:
        get_email_sender().enviar(
            destinatario=email, assunto="Confirme seu e-mail — NotaFácil", corpo_texto=corpo_texto, corpo_html=corpo_html
        )
    except EmailEnvioError:
        # Ver docstring do módulo: a conta já foi criada, não desfaz o
        # cadastro por causa disso — só fica pendente até reenvio/confirmação
        # manual. app/services/email.py já loga o motivo da falha.
        pass


def confirmar_email(db: Session, token: str) -> Usuario:
    usuario = db.query(Usuario).filter_by(token_confirmacao=token).one_or_none()
    agora = datetime.datetime.now(datetime.timezone.utc)
    if usuario is None or usuario.token_confirmacao_expira_em is None or usuario.token_confirmacao_expira_em < agora:
        raise TokenInvalidoOuExpiradoError("Link de confirmação inválido ou expirado.")
    usuario.email_confirmado = True
    usuario.token_confirmacao = None
    usuario.token_confirmacao_expira_em = None
    db.flush()
    return usuario


def reenviar_confirmacao(db: Session, email: str) -> None:
    """Sempre 'silencioso' do ponto de vista de quem chama (não revela se o
    e-mail existe ou já está confirmado) — quem decide o que a API devolve
    é app/main.py, esta função só faz o trabalho quando aplicável."""
    email_norm = email.strip().lower()
    usuario = db.query(Usuario).filter_by(email=email_norm, email_confirmado=False).one_or_none()
    if usuario is None:
        return
    token = _gerar_token()
    usuario.token_confirmacao = token
    usuario.token_confirmacao_expira_em = datetime.datetime.now(datetime.timezone.utc) + _VALIDADE_TOKEN
    db.flush()
    _enviar_email_confirmacao(usuario.email, token)
