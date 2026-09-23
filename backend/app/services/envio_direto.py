"""
Envio direto da nota pro fornecedor — Marco 17 (pedido do Marcos,
23/09/2026: "é possível integrar o WhatsApp ou o e-mail pra enviar direto?
... seria interessante um serviço de e-mail nosso que disparasse os
e-mails para os fornecedores").

Três peças:

1. Link público da nota: URL assinada (itsdangerous, com a mesma
   SESSION_SECRET_KEY do login) que baixa a nota sem login — é o que vai
   no WhatsApp e no corpo do e-mail. O token carrega emissão + prestador,
   então o endpoint público consegue ligar a RLS do prestador certo sem
   sessão. Vale 180 dias.
2. E-mail do NotaFácil: via Resend (app/services/email.py), remetente
   `email_remetente_notas`, reply-to = e-mail do prestador (resposta do
   fornecedor cai na caixa da própria pessoa), PDF oficial + XML em anexo.
   Fica DESLIGADO enquanto não houver domínio próprio (ver config).
3. WhatsApp: link wa.me com a mensagem já escrita (+ número do
   fornecedor, se cadastrado). A pessoa só aperta enviar — mandar sozinho
   exigiria a API oficial do WhatsApp Business (conta verificada na Meta,
   modelos aprovados, custo por conversa), que ficou pra depois.

PDF: o DANFSe oficial só existe depois da confirmação pela Sefin; é baixado
do ADN com o certificado (ClienteSefin.baixar_danfse) na primeira vez que
alguém precisa dele e guardado em `emissao.danfse_pdf`. Nunca testado
contra o ADN de verdade (rede bloqueada no sandbox onde foi escrito) — se
não vier, o envio segue só com o XML.
"""
import datetime
import logging
import re
import uuid
from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.fiscal.cliente_sefin import ClienteSefin
from app.models import Emissao, Envio, Prestador, PrestadorTomador
from app.services import mensagens
from app.services.certificados import CertificadoNaoEncontradoError, carregar_certificado
from app.services.email import EmailEnvioError, get_email_sender
from app.services.envios import melhor_xml_disponivel

logger = logging.getLogger("notafacil.envio")

_SALT = "nota-publica"
VALIDADE_LINK = datetime.timedelta(days=180)


class LinkInvalidoError(Exception):
    pass


class EmailIndisponivelError(Exception):
    """Envio por e-mail não pode acontecer (sistema sem domínio ou fornecedor
    sem e-mail) — mensagem já vem pronta pra mostrar na tela."""


# --- link público ---


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret_key, salt=_SALT)


def gerar_token(emissao: Emissao) -> str:
    return _serializer().dumps({"e": str(emissao.id), "p": str(emissao.prestador_id)})


def ler_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        dados = _serializer().loads(token, max_age=int(VALIDADE_LINK.total_seconds()))
        return uuid.UUID(dados["e"]), uuid.UUID(dados["p"])
    except SignatureExpired as exc:
        raise LinkInvalidoError("Este link expirou — peça um novo pra quem te enviou a nota.") from exc
    except (BadSignature, KeyError, ValueError, TypeError) as exc:
        raise LinkInvalidoError("Link inválido.") from exc


def base_url(base_da_requisicao: str | None = None) -> str:
    """APP_BASE_URL quando configurada; senão, o endereço pelo qual a
    requisição chegou (forçando https fora de localhost — atrás do proxy do
    Railway a requisição chega como http)."""
    configurada = get_settings().app_base_url.rstrip("/")
    if "localhost" not in configurada and "127.0.0.1" not in configurada:
        return configurada
    if base_da_requisicao:
        b = base_da_requisicao.rstrip("/")
        if b.startswith("http://") and "localhost" not in b and "127.0.0.1" not in b:
            b = "https://" + b[len("http://"):]
        return b
    return configurada


def link_publico(emissao: Emissao, base: str) -> str:
    return f"{base}/api/publico/nota/{gerar_token(emissao)}"


# --- PDF oficial (DANFSe) ---


def obter_danfse(db: Session, emissao: Emissao, prestador_id: uuid.UUID) -> bytes | None:
    """PDF oficial, do cache ou baixado agora (só nota confirmada, com
    certificado carregado). Qualquer falha -> None, nunca exceção: o PDF é
    um extra, não pode travar o envio."""
    if emissao.danfse_pdf:
        return emissao.danfse_pdf
    if emissao.estado != "confirmado" or not emissao.chave_acesso:
        return None
    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
        tp_amb = (emissao.tomador_snapshot or {}).get("tpAmb", "2")
        pdf = ClienteSefin(private_key, cert, tp_amb, timeout=8).baixar_danfse(emissao.chave_acesso)
    except CertificadoNaoEncontradoError:
        return None
    except Exception:  # noqa: BLE001 — extra opcional, só registra
        logger.exception("Falha ao baixar DANFSe da emissão %s", emissao.id)
        return None
    if pdf:
        emissao.danfse_pdf = pdf
        db.flush()
    return pdf


def nome_pdf(emissao: Emissao) -> str:
    return f"nfse_{emissao.n_dps}_{emissao.competencia}.pdf"


# --- dados comuns das mensagens ---


def _dados(db: Session, emissao: Emissao, base: str) -> mensagens.DadosMensagem:
    snap = emissao.tomador_snapshot or {}
    prestador = db.get(Prestador, emissao.prestador_id)
    return mensagens.DadosMensagem(
        prestador_nome=prestador.razao_social if prestador else "",
        fornecedor_apelido=snap.get("apelido", ""),
        descricao=snap.get("descricao_renderizada") or f"serviços de {emissao.competencia}",
        competencia=emissao.competencia,
        valor=float(emissao.valor),
        n_dps=emissao.n_dps,
        chave_acesso=emissao.chave_acesso,
        link=link_publico(emissao, base),
    )


def _so_digitos(telefone: str | None) -> str:
    return re.sub(r"\D", "", telefone or "")


def _numero_whatsapp(telefone: str | None) -> str | None:
    """Brasil por padrão: '(92) 99999-0000' -> '5592999990000'."""
    digitos = _so_digitos(telefone)
    if not digitos:
        return None
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos


# --- opções da tela ---


def motivo_email_desabilitado(vinculo: PrestadorTomador | None) -> str | None:
    s = get_settings()
    if not (s.resend_api_key and s.email_remetente_notas):
        return "O envio por e-mail do NotaFácil será ativado quando o domínio de e-mail estiver configurado."
    if vinculo is None or not vinculo.email_contato:
        return "Cadastre o e-mail deste fornecedor pra enviar direto."
    return None


def opcoes_envio(db: Session, emissao: Emissao, base: str) -> dict:
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    motivo = motivo_email_desabilitado(vinculo)
    return {
        "email_habilitado": motivo is None,
        "email_motivo_desabilitado": motivo,
        "email_destino": vinculo.email_contato if vinculo else None,
        "whatsapp_destino": vinculo.whatsapp_contato if vinculo else None,
        "link_publico": link_publico(emissao, base),
        "tem_pdf": bool(emissao.danfse_pdf) or emissao.estado == "confirmado",
        "vinculo_id": emissao.prestador_tomador_id,
    }


# --- envio ---


def _novo_envio(db: Session, emissao: Emissao, canal: str, destino: str | None) -> Envio:
    envio = Envio(id=uuid.uuid4(), emissao_id=emissao.id, canal=canal, tentativas=1, status="pendente", destino=destino)
    db.add(envio)
    db.flush()
    return envio


def enviar_email(db: Session, emissao: Emissao, prestador_id: uuid.UUID, base: str) -> Envio:
    """Manda de verdade (Resend). Falha do provedor vira envio com status
    'falha' + motivo (não exceção) — a tela mostra e a pessoa tenta de novo."""
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    motivo = motivo_email_desabilitado(vinculo)
    if motivo:
        raise EmailIndisponivelError(motivo)

    nome_xml, conteudo_xml = melhor_xml_disponivel(emissao)
    anexos: list[tuple[str, bytes]] = []
    pdf = obter_danfse(db, emissao, prestador_id)
    if pdf:
        anexos.append((nome_pdf(emissao), pdf))
    anexos.append((nome_xml, conteudo_xml.encode("utf-8")))

    dados = _dados(db, emissao, base)
    prestador = db.get(Prestador, prestador_id)
    envio = _novo_envio(db, emissao, "email", vinculo.email_contato)
    try:
        get_email_sender().enviar(
            destinatario=vinculo.email_contato,
            assunto=mensagens.email_assunto(dados),
            corpo_texto=mensagens.email_texto(dados),
            corpo_html=mensagens.email_html(dados),
            remetente=get_settings().email_remetente_notas,
            responder_para=prestador.email if prestador and prestador.email else None,
            anexos=anexos,
        )
    except EmailEnvioError as exc:
        envio.status = "falha"
        envio.erro = str(exc)
    else:
        envio.status = "enviado"
        envio.enviado_em = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return envio


def link_whatsapp(db: Session, emissao: Emissao, base: str) -> tuple[str, Envio]:
    """URL wa.me com a mensagem pronta. Registra o envio como PENDENTE: quem
    aperta 'enviar' no WhatsApp é a pessoa, então ela confirma depois (mesmo
    fluxo de marcar enviado/falha que já existia)."""
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    numero = _numero_whatsapp(vinculo.whatsapp_contato if vinculo else None)
    texto = quote(mensagens.whatsapp_texto(_dados(db, emissao, base)))
    url = f"https://wa.me/{numero}?text={texto}" if numero else f"https://wa.me/?text={texto}"
    envio = _novo_envio(db, emissao, "whatsapp", vinculo.whatsapp_contato if vinculo else None)
    return url, envio
