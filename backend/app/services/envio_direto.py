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
2. E-mail da Agente Ana: via Resend (app/services/email.py), remetente
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
import time
import uuid
from email.utils import parseaddr
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

logger = logging.getLogger("agenteana.envio")

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
    if time.monotonic() - _FALHA_DANFSE.get(emissao.id, -1e9) < _ESPERA_DANFSE_S:
        return None
    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
        tp_amb = (emissao.tomador_snapshot or {}).get("tpAmb", "2")
        pdf = ClienteSefin(private_key, cert, tp_amb, timeout=8).baixar_danfse(emissao.chave_acesso)
    except CertificadoNaoEncontradoError:
        return None
    except Exception:  # noqa: BLE001 — extra opcional, só registra
        logger.exception("Falha ao baixar DANFSe da emissão %s", emissao.id)
        _FALHA_DANFSE[emissao.id] = time.monotonic()
        return None
    if pdf:
        emissao.danfse_pdf = pdf
        db.flush()
        _FALHA_DANFSE.pop(emissao.id, None)
    else:
        _FALHA_DANFSE[emissao.id] = time.monotonic()
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
        tomador_razao_social=snap.get("razao_social") or "",
        ordem=snap.get("ordem"),
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


_RE_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def lista_emails(texto: str | list[str] | None) -> list[str]:
    """"a@x.com; b@y.com, invalido" -> ["a@x.com", "b@y.com"] (sem repetir)."""
    partes = texto if isinstance(texto, list) else re.split(r"[,;\s]+", texto or "")
    vistos: list[str] = []
    for parte in partes:
        email = (parte or "").strip().lower()
        if _RE_EMAIL.match(email) and email not in vistos:
            vistos.append(email)
    return vistos[:20]


def destinos_email(emissao: Emissao, vinculo: PrestadorTomador | None) -> list[str]:
    """Pra quem a nota vai (28/09/2026: "tem que configurar o destinatário
    também, não necessariamente enviamos para o e-mail da nota").
    Shopee: o vendedor da linha do relatório (e-mail do snapshot). No resto:
    o "Para" configurado no tomador; sem ele, o e-mail de contato."""
    snap = emissao.tomador_snapshot or {}
    if emissao.tomador_documento:
        return lista_emails(snap.get("email"))
    if vinculo is None:
        return []
    return lista_emails(vinculo.email_para) or lista_emails(vinculo.email_contato)


def email_destino(emissao: Emissao, vinculo: PrestadorTomador | None) -> str | None:
    return ", ".join(destinos_email(emissao, vinculo)) or None


def motivo_email_desabilitado(vinculo: PrestadorTomador | None, destino: str | None = None) -> str | None:
    s = get_settings()
    if not (s.resend_api_key and s.email_remetente_notas):
        return "O envio por e-mail da Ana será ativado quando o domínio de e-mail estiver configurado."
    if destino is None and vinculo is not None:
        destino = ", ".join(lista_emails(vinculo.email_para) or lista_emails(vinculo.email_contato))
    if not destino:
        return "Cadastre o e-mail deste tomador (ou o destinatário no e-mail da nota) pra enviar direto."
    return None


def opcoes_envio(db: Session, emissao: Emissao, base: str) -> dict:
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    destino = email_destino(emissao, vinculo)
    motivo = motivo_email_desabilitado(vinculo, destino or "")
    return {
        "email_habilitado": motivo is None,
        "email_motivo_desabilitado": motivo,
        "email_destino": destino,
        "whatsapp_destino": vinculo.whatsapp_contato if vinculo else None,
        "link_publico": link_publico(emissao, base),
        "tem_pdf": bool(emissao.danfse_pdf) or emissao.estado == "confirmado",
        "vinculo_id": emissao.prestador_tomador_id,
    }


# --- envio ---


def remetente_da_nota(nome_prestador: str | None) -> str:
    """Remetente do e-mail da nota com o nome de quem emitiu na frente:
    "Fulano via Agente Ana <notas@agenteana.com.br>". O fornecedor reconhece
    quem mandou, e o endereço continua sendo o do domínio verificado no
    Resend (EMAIL_REMETENTE_NOTAS). Sem nome, usa o remetente configurado."""
    configurado = get_settings().email_remetente_notas
    _, endereco = parseaddr(configurado)
    nome = re.sub(r"[\r\n\"\\<>]", " ", nome_prestador or "")
    nome = re.sub(r"\s+", " ", nome).strip()[:60].strip()
    if not endereco or not nome:
        return configurado
    # Nome entre aspas (pode ter vírgula, ponto etc.) e em UTF-8 puro — o
    # Resend aceita acentos direto no campo "from".
    return f'"{nome} via Agente Ana" <{endereco}>'


LIMITE_EMAILS_DIA = 150
# PDF oficial que falhou há pouco não é tentado de novo por uns minutos:
# cada tentativa passa por 5 endereços com timeout e segurava o pedido por
# até um minuto (inclusive no link público).
_FALHA_DANFSE: dict[uuid.UUID, float] = {}
_ESPERA_DANFSE_S = 600


def _novo_envio(db: Session, emissao: Emissao, canal: str, destino: str | None) -> Envio:
    envio = Envio(id=uuid.uuid4(), emissao_id=emissao.id, canal=canal, tentativas=1, status="pendente", destino=destino)
    db.add(envio)
    db.flush()
    return envio


def modelo_email(db: Session, emissao: Emissao, base: str) -> dict:
    """Assunto, texto, cópias e anexos que esta nota vai usar — tomador >
    padrão do prestador > texto de sempre da Ana (28/09/2026)."""
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    prestador = db.get(Prestador, emissao.prestador_id)
    dados = _dados(db, emissao, base)
    assunto_modelo = (vinculo.email_assunto if vinculo else None) or (prestador.email_assunto_padrao if prestador else None)
    mensagem_modelo = (vinculo.email_mensagem if vinculo else None) or (prestador.email_mensagem_padrao if prestador else None)
    anexos = (vinculo.email_anexos if vinculo else None) or (prestador.email_anexos_padrao if prestador else None) or "pdf_xml"
    if anexos not in mensagens.ANEXOS_VALIDOS:
        anexos = "pdf_xml"
    assunto = mensagens.renderizar_modelo(assunto_modelo, dados) if assunto_modelo else mensagens.email_assunto(dados)
    if mensagem_modelo:
        texto = mensagens.renderizar_modelo(mensagem_modelo, dados)
        html = mensagens.email_html_de_texto(texto, dados)
    else:
        texto, html = mensagens.email_texto(dados), mensagens.email_html(dados)
    return {
        "assunto": re.sub(r"[\r\n]+", " ", assunto).strip()[:300],
        "texto": texto,
        "html": html,
        "anexos": anexos,
        # Cópias do tomador + "sempre me mandar cópia" da conta.
        "copia": lista_emails(
            lista_emails(vinculo.email_copia if vinculo else None)
            + lista_emails(prestador.email_copia_padrao if prestador else None)
        ),
    }


def previa_email(db: Session, emissao: Emissao, base: str) -> dict:
    """O que vai sair se apertar "Enviar ao tomador" — pra tela confirmar."""
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    modelo = modelo_email(db, emissao, base)
    tem_pdf = bool(emissao.danfse_pdf) or emissao.estado == "confirmado"
    arquivos = []
    if modelo["anexos"] in ("pdf_xml", "pdf") and tem_pdf:
        arquivos.append(nome_pdf(emissao))
    if modelo["anexos"] in ("pdf_xml", "xml") or not tem_pdf:
        arquivos.append(f"nfse_{emissao.n_dps}_{emissao.competencia}.xml")
    destinos = destinos_email(emissao, vinculo)
    destino = ", ".join(destinos) or None
    return {
        "destino": destino,
        "destinos": destinos,
        "copia": [c for c in modelo["copia"] if c not in destinos],
        "assunto": modelo["assunto"],
        "texto": modelo["texto"],
        "anexos": modelo["anexos"],
        "arquivos": arquivos,
        "motivo_desabilitado": motivo_email_desabilitado(vinculo, destino or ""),
    }


def enviar_email(
    db: Session, emissao: Emissao, prestador_id: uuid.UUID, base: str,
    para: list[str] | None = None, copia: list[str] | None = None,
) -> Envio:
    """Manda de verdade (Resend). Falha do provedor vira envio com status
    'falha' + motivo (não exceção) — a tela mostra e a pessoa tenta de novo.
    Assunto, texto, cópias e anexos vêm do modelo configurado (tomador >
    padrão do prestador > texto de sempre)."""
    vinculo = db.get(PrestadorTomador, emissao.prestador_tomador_id)
    # `para`/`copia` vindos da tela valem só pra este envio (a pessoa trocou
    # o destinatário na hora); sem eles, o que está configurado.
    destinos = lista_emails(para) if para is not None else destinos_email(emissao, vinculo)
    destino = ", ".join(destinos) or None
    motivo = motivo_email_desabilitado(vinculo, destino or "")
    if motivo:
        raise EmailIndisponivelError(motivo)

    # Teto diário por conta (revisão de segurança, 28/09/2026): o e-mail sai
    # do domínio da Ana com assunto/texto livres — sem teto, uma conta mal
    # intencionada viraria disparador de spam/phishing.
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    enviados_24h = (
        db.query(Envio.id)
        .join(Emissao, Emissao.id == Envio.emissao_id)
        .filter(Envio.canal == "email", Envio.criado_em >= desde)
        .count()
    )
    if enviados_24h >= LIMITE_EMAILS_DIA:
        raise EmailIndisponivelError(
            f"Limite de {LIMITE_EMAILS_DIA} e-mails de nota por dia atingido. Se precisar de mais, fale com o suporte."
        )

    modelo = modelo_email(db, emissao, base)
    copias = [c for c in (lista_emails(copia) if copia is not None else modelo["copia"]) if c not in destinos]
    quer_pdf = modelo["anexos"] in ("pdf_xml", "pdf")
    quer_xml = modelo["anexos"] in ("pdf_xml", "xml")
    anexos: list[tuple[str, bytes]] = []
    pdf = obter_danfse(db, emissao, prestador_id) if quer_pdf else None
    if quer_pdf and pdf is None and emissao.estado == "confirmado":
        # Nota autorizada e o tomador pediu o PDF: não manda sem ele.
        raise EmailIndisponivelError(
            "Não consegui baixar o PDF oficial da nota agora. Tente de novo em alguns minutos."
        )
    if pdf:
        anexos.append((nome_pdf(emissao), pdf))
    if quer_xml or not pdf:
        # Sem PDF (nota ainda não autorizada) o XML vai de qualquer jeito —
        # e-mail de nota sem a nota não serve pra nada.
        nome_xml, conteudo_xml = melhor_xml_disponivel(emissao)
        anexos.append((nome_xml, conteudo_xml.encode("utf-8")))

    prestador = db.get(Prestador, prestador_id)
    envio = _novo_envio(db, emissao, "email", destino[:200] if destino else None)
    try:
        get_email_sender().enviar(
            destinatario=destinos,
            assunto=modelo["assunto"],
            corpo_texto=modelo["texto"],
            corpo_html=modelo["html"],
            remetente=remetente_da_nota(prestador.razao_social if prestador else None),
            responder_para=prestador.email if prestador and prestador.email else None,
            anexos=anexos,
            copia=copias or None,
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
