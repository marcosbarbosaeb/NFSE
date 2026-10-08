"""Google Drive da empresa (05/10/2026) — "vamos incluir nas opções de
envio também o Google Drive, pra subirmos os arquivos".

A pessoa conecta a conta Google dela uma vez (OAuth, escopo `drive.file`:
a Ana só enxerga e mexe nos arquivos que ELA MESMA criou — nunca no resto
do Drive). O refresh token fica cifrado no banco com a chave mestra (a
mesma do certificado). Os arquivos vão pra pasta "Agente Ana", numa
subpasta por tomador e mês.

Usa as mesmas credenciais do login com Google (GOOGLE_OAUTH_CLIENT_ID /
SECRET). No Google Cloud é preciso: ativar a "Google Drive API", incluir o
escopo `.../auth/drive.file` na tela de consentimento e cadastrar o
redirect `<APP_BASE_URL>/api/drive/callback`.

Como em google_oauth.py: esta sandbox não fala com a Google — os testes
usam `requests` simulado; a validação de verdade é em produção.
"""
import datetime
import json
import logging
import uuid
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import criptografar, descriptografar
from app.models import Prestador

logger = logging.getLogger("agenteana.drive")

_URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
_URL_TOKEN = "https://oauth2.googleapis.com/token"
_URL_ARQUIVOS = "https://www.googleapis.com/drive/v3/files"
_URL_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_ESCOPO = "https://www.googleapis.com/auth/drive.file openid email"
_TIMEOUT = 30
PASTA_RAIZ = "Agente Ana"
_TIPO_PASTA = "application/vnd.google-apps.folder"


class DriveNaoConfiguradoError(Exception):
    """Faltam as credenciais do Google no servidor."""


class DriveNaoConectadoError(Exception):
    """A empresa ainda não conectou o Drive (ou a autorização foi revogada)."""


class DriveFalhaError(Exception):
    """A Google recusou ou não respondeu — mensagem pronta pra tela."""


def configurado() -> bool:
    s = get_settings()
    return bool(s.google_oauth_client_id and s.google_oauth_client_secret)


def _redirect_uri() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/api/drive/callback"


def url_de_conexao(state: str, email: str | None = None) -> str:
    if not configurado():
        raise DriveNaoConfiguradoError("A conexão com o Google Drive ainda não está ativa neste servidor.")
    return f"{_URL_AUTORIZACAO}?" + urlencode({
        "client_id": get_settings().google_oauth_client_id, "redirect_uri": _redirect_uri(), "response_type": "code",
        "scope": _ESCOPO, "state": state, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "false",
        # quem entrou com o Google já cai na mesma conta (08/10/2026)
        **({"login_hint": email} if email else {}),
    })


def _post_token(dados: dict) -> dict:
    s = get_settings()
    try:
        resp = requests.post(_URL_TOKEN, data={**dados, "client_id": s.google_oauth_client_id, "client_secret": s.google_oauth_client_secret}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise DriveFalhaError("Não deu pra falar com o Google agora. Tente de novo.") from exc
    if resp.status_code != 200:
        raise DriveNaoConectadoError("O Google não aceitou a autorização. Conecte o Drive de novo.")
    try:
        return resp.json()
    except ValueError as exc:
        raise DriveFalhaError("O Google respondeu num formato inesperado.") from exc


def concluir_conexao(db: Session, prestador_id: uuid.UUID, code: str) -> str | None:
    """Troca o `code` do callback pelo refresh token e guarda (cifrado).
    Devolve o e-mail da conta conectada."""
    tokens = _post_token({"code": code, "redirect_uri": _redirect_uri(), "grant_type": "authorization_code"})
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise DriveFalhaError("O Google não devolveu a autorização permanente. Tente conectar de novo e aceite o acesso.")
    email = None
    try:
        info = requests.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {tokens.get('access_token')}"}, timeout=_TIMEOUT)
        email = (info.json().get("email") if info.status_code == 200 else None)
    except (requests.RequestException, ValueError):
        email = None
    prestador = db.get(Prestador, prestador_id)
    prestador.drive_token = criptografar(refresh.encode("utf-8"), get_settings().cert_master_key)
    prestador.drive_email = (email or "")[:200] or None
    prestador.drive_pasta_id = None
    db.flush()
    return prestador.drive_email


def desconectar(db: Session, prestador_id: uuid.UUID) -> None:
    prestador = db.get(Prestador, prestador_id)
    prestador.drive_token = prestador.drive_email = prestador.drive_pasta_id = None
    db.flush()


def status(db: Session, prestador_id: uuid.UUID) -> dict:
    prestador = db.get(Prestador, prestador_id)
    conectado = bool(prestador and prestador.drive_token)
    # "provedor": hoje só o Google; OneDrive/Dropbox entram em Empresa › Integrações.
    return {"disponivel": configurado(), "conectado": conectado, "email": prestador.drive_email if prestador else None,
            "provedor": "google" if conectado else None}


class ClienteDrive:
    """Sessão de envio pro Drive de UMA empresa (um access token por uso)."""

    def __init__(self, db: Session, prestador_id: uuid.UUID):
        prestador = db.get(Prestador, prestador_id)
        if prestador is None or not prestador.drive_token:
            raise DriveNaoConectadoError("Conecte o Google Drive antes de subir os arquivos.")
        refresh = descriptografar(prestador.drive_token, get_settings().cert_master_key).decode("utf-8")
        self._token = _post_token({"refresh_token": refresh, "grant_type": "refresh_token"}).get("access_token")
        if not self._token:
            raise DriveNaoConectadoError("O Google não renovou a autorização. Conecte o Drive de novo.")
        self._db, self._prestador = db, prestador
        self._pastas: dict[tuple[str | None, str], str] = {}

    def _pedir(self, metodo: str, url: str, **kw) -> dict:
        try:
            resp = requests.request(metodo, url, headers={"Authorization": f"Bearer {self._token}", **kw.pop("headers", {})}, timeout=_TIMEOUT, **kw)
        except requests.RequestException as exc:
            raise DriveFalhaError("Não deu pra falar com o Google Drive agora.") from exc
        if resp.status_code in (401, 403):
            raise DriveNaoConectadoError("O Google Drive recusou o acesso. Conecte de novo em Notas em lote › Pacote.")
        if resp.status_code >= 300:
            logger.warning("Drive HTTP %s em %s", resp.status_code, url)
            raise DriveFalhaError(f"O Google Drive recusou o envio (HTTP {resp.status_code}).")
        try:
            return resp.json()
        except ValueError:
            return {}

    def pasta(self, nome: str, dentro_de: str | None = None) -> str:
        """Id da pasta (criada se ainda não existe; só enxerga as que a Ana criou)."""
        chave = (dentro_de, nome)
        if chave in self._pastas:
            return self._pastas[chave]
        seguro = nome.replace("\\", " ").replace("'", " ")
        consulta = f"name = '{seguro}' and mimeType = '{_TIPO_PASTA}' and trashed = false" + (f" and '{dentro_de}' in parents" if dentro_de else "")
        achadas = self._pedir("GET", _URL_ARQUIVOS, params={"q": consulta, "fields": "files(id)", "pageSize": 1}).get("files") or []
        if achadas:
            pasta_id = achadas[0]["id"]
        else:
            corpo = {"name": seguro, "mimeType": _TIPO_PASTA, **({"parents": [dentro_de]} if dentro_de else {})}
            pasta_id = self._pedir("POST", _URL_ARQUIVOS, json=corpo, params={"fields": "id"})["id"]
        self._pastas[chave] = pasta_id
        return pasta_id

    def pasta_raiz(self) -> str:
        if self._prestador.drive_pasta_id:
            return self._prestador.drive_pasta_id
        pasta_id = self.pasta(PASTA_RAIZ)
        self._prestador.drive_pasta_id = pasta_id
        self._db.flush()
        return pasta_id

    def pasta_do_mes(self, tomador: str, competencia: str) -> str:
        """Agente Ana / <tomador> / AAAA-MM"""
        return self.pasta(competencia, self.pasta(tomador[:80] or "Notas", self.pasta_raiz()))

    def enviar(self, pasta_id: str, nome: str, conteudo: bytes, tipo: str) -> str:
        """Sobe um arquivo (multipart). Devolve o id dele no Drive."""
        limite = uuid.uuid4().hex
        meta = json.dumps({"name": nome, "parents": [pasta_id]})
        corpo = (
            f"--{limite}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{limite}\r\nContent-Type: {tipo}\r\n\r\n"
        ).encode("utf-8") + conteudo + f"\r\n--{limite}--".encode("utf-8")
        return self._pedir(
            "POST", _URL_UPLOAD, params={"uploadType": "multipart", "fields": "id"}, data=corpo,
            headers={"Content-Type": f"multipart/related; boundary={limite}"},
        ).get("id", "")

    def link_da_pasta(self, pasta_id: str) -> str:
        return f"https://drive.google.com/drive/folders/{pasta_id}"


# --- Uma nota no Drive (05/10/2026) ---
# "A ideia é a pessoa, nas formas de compartilhar a nota, poder escolher subir
# elas pro próprio Drive. Serve pra todo tipo de nota."

def link_da_nota(db: Session, emissao) -> str | None:
    """Link da pasta onde esta nota já foi guardada (None = ainda não foi)."""
    from app.models import Envio

    envio = (
        db.query(Envio).filter_by(emissao_id=emissao.id, canal="drive", status="enviado")
        .order_by(Envio.criado_em.desc()).first()
    )
    return envio.destino if envio is not None else None


def guardar_nota(db: Session, emissao, *, de_novo: bool = False, cliente: "ClienteDrive | None" = None) -> str:
    """Sobe o PDF e o XML da nota pra Agente Ana / <tomador> / AAAA-MM e
    devolve o link da pasta. Já guardada: devolve o link sem subir de novo
    (a menos de `de_novo`). Levanta Drive*Error se não der."""
    from app.models import Envio
    from app.services import pacote

    if not de_novo:
        link = link_da_nota(db, emissao)
        if link:
            return link
    arquivos = pacote.arquivos_da_nota(db, emissao, "ambos")
    if not arquivos:
        raise DriveFalhaError("Esta nota ainda não tem arquivo pra guardar.")
    cliente = cliente or ClienteDrive(db, emissao.prestador_id)
    vinculo = emissao.vinculo
    pasta = cliente.pasta_do_mes(vinculo.apelido if vinculo is not None else "Notas", emissao.competencia)
    for nome, dados, tipo in arquivos:
        cliente.enviar(pasta, nome, dados, tipo)
    link = cliente.link_da_pasta(pasta)
    db.add(Envio(
        id=uuid.uuid4(), emissao_id=emissao.id, canal="drive", status="enviado", tentativas=1,
        enviado_em=datetime.datetime.now(datetime.timezone.utc), destino=link[:200],
    ))
    db.flush()
    return link


def guardar_se_configurado(db: Session, emissao) -> str | None:
    """Chamado quando a prefeitura autoriza a nota: se o tomador tem o
    Google Drive entre as formas de envio (e o Drive está conectado), guarda
    os arquivos. Nunca atrapalha a nota: qualquer falha só vai pro log."""
    from app.services.envio_direto import formas_de_envio, marcar_enviada

    if emissao.tomador_documento or emissao.vinculo is None:
        return None  # notas de vendedores sobem pelo pacote do mês
    formas = formas_de_envio(emissao.vinculo)
    if "drive" not in formas:
        return None
    prestador = db.get(Prestador, emissao.prestador_id)
    if prestador is None or not prestador.drive_token or not configurado():
        return None
    try:
        with db.begin_nested():
            link = guardar_nota(db, emissao)
            # Só o Drive: guardar é a entrega deste tomador.
            if formas == ["drive"]:
                marcar_enviada(db, emissao, "Google Drive")
        return link
    except (DriveFalhaError, DriveNaoConectadoError, DriveNaoConfiguradoError) as exc:
        logger.warning("Drive: não guardei a nota %s (%s)", emissao.id, exc)
    except Exception:  # noqa: BLE001 — a nota já está autorizada; o Drive é acessório
        logger.exception("Drive: erro inesperado ao guardar a nota %s", emissao.id)
    return None
