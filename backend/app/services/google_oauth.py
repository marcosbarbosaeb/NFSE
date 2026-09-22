"""
Login/cadastro via Google — Marco 16, item 1 do pedido do Marcos: "integre
o login/cadastro ao Google". Mesma filosofia do Resend/Stripe (Marco 15):
credenciais placeholder (`Settings.google_oauth_client_id/secret` vazias),
estrutura toda pronta, liga 100% assim que ele criar o projeto no Google
Cloud e trocar essas duas variáveis — nenhum código muda (ver docstring de
`Settings` em app/config.py).

Fluxo (OAuth 2.0 "Authorization Code", sem SDK do Google nem biblioteca
nova — só `requests`, que já é dependência do projeto, mesmo raciocínio
de app/services/cnpj_lookup.py de não adicionar peso pra uma integração
simples):

  1. POST /api/auth/google/iniciar devolve a URL de autorização da Google
     (`montar_url_autorizacao`), com um `state` aleatório guardado na
     sessão (`request.session`) pra CSRF — comparado de volta no passo 3.
  2. O navegador vai pra Google, a pessoa autoriza, a Google redireciona
     pro nosso backend com `?code=...&state=...`.
  3. GET /api/auth/google/callback troca o `code` por um access_token
     (`trocar_code_por_usuario`) e busca e-mail/nome/sub na Google.

O QUE FAZER com esse e-mail/sub fica pro chamador (app/main.py), porque
depende de já existir conta ou não:
  - e-mail já tem Usuario ativo+confirmado → só loga (mesmo efeito de
    `autenticar`, sem senha) e vincula `google_sub` se ainda não tinha.
  - e-mail não tem conta nenhuma → não dá pra criar a conta sozinho: o
    cadastro público (POST /api/cadastro) exige CNPJ/razão social, que a
    Google não sabe — o callback redireciona pro formulário de cadastro
    normal, só com e-mail/nome PRÉ-PREENCHIDOS (mesma filosofia de
    "sugestão editável, nunca autoritativo" do autopreenchimento por CNPJ,
    item 2 do mesmo Marco).

IMPORTANTE (mesma ressalva de cnpj_lookup.py): esta sandbox tem o egress
bloqueado por política da organização pra qualquer host externo — mesmo
com credenciais reais, não dá pra validar este fluxo ao vivo daqui. Os
testes usam `requests.post`/`requests.get` mockados; a validação de
verdade só acontece rodando num ambiente com rede aberta E com
`google_oauth_client_id/secret` reais.
"""
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from app.config import Settings

_URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
_URL_TOKEN = "https://oauth2.googleapis.com/token"
_URL_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
_TIMEOUT_SEGUNDOS = 8

# openid+email+profile: o mínimo pra identificar a pessoa (sub, e-mail já
# verificado pela Google, nome) — nunca pedimos Drive/Calendar/etc, este
# login não precisa de acesso a mais nada da conta Google da pessoa.
_ESCOPOS = "openid email profile"


class GoogleOAuthNaoConfiguradoError(Exception):
    """`google_oauth_client_id`/`google_oauth_client_secret` ainda não
    foram configurados (ver docstring do módulo) — a rota que chamou isto
    deve responder com uma mensagem clara em vez de montar uma URL de
    autorização que a Google ia rejeitar mesmo assim."""


class GoogleOAuthFalhaError(Exception):
    """Troca de code por token (ou busca do userinfo) falhou — code
    expirado/inválido, credencial errada, ou a própria Google fora do ar.
    Nunca deveria acontecer com credencial real e code fresco; sempre vai
    acontecer nesta sandbox com credencial placeholder (ver docstring)."""


@dataclass
class GoogleUserInfo:
    sub: str
    email: str
    email_verificado: bool
    nome: str | None


def _configurado(settings: Settings) -> bool:
    return bool(settings.google_oauth_client_id) and bool(settings.google_oauth_client_secret)


def _exigir_configurado(settings: Settings) -> None:
    if not _configurado(settings):
        raise GoogleOAuthNaoConfiguradoError(
            "Login com Google ainda não está configurado (falta criar o projeto no Google Cloud "
            "e definir GOOGLE_OAUTH_CLIENT_ID/GOOGLE_OAUTH_CLIENT_SECRET). Entre com e-mail e senha."
        )


def gerar_state() -> str:
    """Token aleatório pra CSRF do fluxo OAuth — guardado na sessão antes
    do redirect pra Google, comparado de volta no callback (ver docstring
    do módulo, passo 1)."""
    return secrets.token_urlsafe(24)


def _redirect_uri(settings: Settings) -> str:
    # `app_base_url` já é a origem pública que serve o frontend E faz proxy
    # de /api pro backend (ver frontend/src/lib/api.ts) — é por isso que o
    # callback pode ser uma URL sob essa mesma origem mesmo rodando em
    # processos/portas diferentes em dev.
    return f"{settings.app_base_url}/api/auth/google/callback"


def montar_url_autorizacao(settings: Settings, state: str) -> str:
    """Levanta `GoogleOAuthNaoConfiguradoError` se as credenciais ainda
    forem placeholder (ver docstring do módulo)."""
    _exigir_configurado(settings)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": _redirect_uri(settings),
        "response_type": "code",
        "scope": _ESCOPOS,
        "state": state,
        # prompt=select_account: evita logar automático com a última conta
        # Google usada no navegador sem a pessoa poder escolher — comum
        # num computador compartilhado (o caso do Marcos e da Raiana
        # operando o mesmo negócio, ver docstring de Usuario).
        "prompt": "select_account",
    }
    return f"{_URL_AUTORIZACAO}?{urlencode(params)}"


def trocar_code_por_usuario(settings: Settings, code: str) -> GoogleUserInfo:
    """Troca o `code` do callback por um access_token e busca e-mail/nome
    na Google. Levanta `GoogleOAuthFalhaError` pra qualquer falha de rede,
    resposta inesperada, ou code/credencial inválidos — o chamador nunca
    deveria deixar essa exceção específica da Google vazar pro cliente."""
    _exigir_configurado(settings)
    try:
        resp_token = requests.post(
            _URL_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": _redirect_uri(settings),
                "grant_type": "authorization_code",
            },
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as exc:
        raise GoogleOAuthFalhaError(f"Não foi possível falar com a Google agora: {exc}") from exc
    if resp_token.status_code != 200:
        raise GoogleOAuthFalhaError(f"Google recusou a troca do código de autorização (HTTP {resp_token.status_code}).")
    try:
        access_token = resp_token.json()["access_token"]
    except (ValueError, KeyError) as exc:
        raise GoogleOAuthFalhaError("Resposta de token da Google veio num formato inesperado.") from exc

    try:
        resp_userinfo = requests.get(
            _URL_USERINFO, headers={"Authorization": f"Bearer {access_token}"}, timeout=_TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as exc:
        raise GoogleOAuthFalhaError(f"Não foi possível buscar os dados da conta Google agora: {exc}") from exc
    if resp_userinfo.status_code != 200:
        raise GoogleOAuthFalhaError(f"Google recusou buscar os dados da conta (HTTP {resp_userinfo.status_code}).")
    try:
        dados = resp_userinfo.json()
        sub = dados["sub"]
        email = dados["email"]
    except (ValueError, KeyError) as exc:
        raise GoogleOAuthFalhaError("Resposta de dados da conta Google veio num formato inesperado.") from exc

    return GoogleUserInfo(
        sub=sub,
        email=email.strip().lower(),
        email_verificado=bool(dados.get("email_verified", False)),
        nome=dados.get("name"),
    )
