"""
Envio de e-mail transacional — Marco 15, pro cadastro público self-service
(link de confirmação de e-mail). Escrito como uma interface pequena e
trocável de propósito: o Marcos ainda NÃO tem conta no Resend (provedor
default escolhido — API simples, tier gratuito generoso) na hora em que
isto foi construído, mas quer a estrutura pronta pra plugar a chave de
verdade depois sem reabrir código nenhum (mesmo espírito do
CERT_MASTER_KEY/Stripe: monta agora com placeholder, troca a config
depois).

Duas implementações de `EmailSender`:

- `EmailSenderResend`: fala com a API HTTP do Resend (POST
  https://api.resend.com/emails) via `requests` (já é dependência do
  projeto, não precisa somar SDK novo — mesma filosofia de app/auth.py).
- `EmailSenderConsole`: não manda nada de verdade, só loga o e-mail (pra
  quem não tem RESEND_API_KEY configurada ainda, e pros testes — nenhum
  teste deste projeto pode depender de rede de verdade).

`get_email_sender()` escolhe uma ou outra a partir de
`Settings.resend_api_key` — vazio (default) cai no Console, uma chave de
verdade liga o Resend. Nada mais no resto do código precisa saber qual das
duas está ativa.
"""
import base64
import time
import logging

import requests

from app.config import get_settings

logger = logging.getLogger("agenteana.email")


class EmailEnvioError(Exception):
    """Falha ao mandar o e-mail pro provedor (rede, API fora do ar, chave
    inválida...). Deliberadamente uma exceção À PARTE dos erros de negócio
    do cadastro (ver app/services/cadastro.py) — a conta já foi criada no
    banco nesse ponto; falhar o e-mail não deve reverter o cadastro (o
    usuário pode pedir reenvio depois), só precisa ser visível em log."""


class EmailCotaEsgotadaError(EmailEnvioError):
    """O provedor (Resend) não aceita mais e-mails hoje (ou neste mês): o
    plano gratuito libera 100 por dia / 3.000 por mês. Não é falha da nota
    nem do destinatário — o envio fica pra depois."""

    def __init__(self, mensagem: str, mensal: bool = False):
        super().__init__(mensagem)
        self.mensal = mensal


class EmailSender:
    def enviar(
        self, *, destinatario: str | list[str], assunto: str, corpo_texto: str, corpo_html: str,
        remetente: str | None = None, responder_para: str | None = None,
        anexos: list[tuple[str, bytes]] | None = None, copia: list[str] | None = None,
    ) -> None:
        """`anexos`: [(nome_arquivo, bytes)]. `remetente` sobrescreve o
        padrão (e-mails de nota saem de email_remetente_notas)."""
        raise NotImplementedError


class EmailSenderConsole(EmailSender):
    """Default enquanto não existe RESEND_API_KEY configurada (dev local e
    testes) — nunca faz uma chamada de rede."""

    def enviar(
        self, *, destinatario: str | list[str], assunto: str, corpo_texto: str, corpo_html: str,
        remetente: str | None = None, responder_para: str | None = None,
        anexos: list[tuple[str, bytes]] | None = None, copia: list[str] | None = None,
    ) -> None:
        logger.info("=== E-MAIL (modo console — RESEND_API_KEY não configurada) ===")
        logger.info("Para: %s", destinatario)
        if copia:
            logger.info("Cópia: %s", ", ".join(copia))
        if anexos:
            logger.info("Anexos: %s", ", ".join(nome for nome, _ in anexos))
        logger.info("Assunto: %s", assunto)
        logger.info("%s", corpo_texto)
        logger.info("=== fim do e-mail ===")


class EmailSenderResend(EmailSender):
    _URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, remetente: str):
        self._api_key = api_key
        self._remetente = remetente

    def enviar(
        self, *, destinatario: str | list[str], assunto: str, corpo_texto: str, corpo_html: str,
        remetente: str | None = None, responder_para: str | None = None,
        anexos: list[tuple[str, bytes]] | None = None, copia: list[str] | None = None,
    ) -> None:
        corpo = {
            "from": remetente or self._remetente,
            "to": destinatario if isinstance(destinatario, list) else [destinatario],
            "subject": assunto,
            "text": corpo_texto,
            "html": corpo_html,
        }
        if responder_para:
            corpo["reply_to"] = [responder_para]
        if copia:
            corpo["cc"] = copia
        if anexos:
            corpo["attachments"] = [
                {"filename": nome, "content": base64.b64encode(conteudo).decode("ascii")} for nome, conteudo in anexos
            ]
        # Limite por segundo do Resend (rate_limit_exceeded): espera e tenta
        # de novo, até 4 vezes. Cota do dia/mês esgotada é outro erro —
        # insistir não adianta; quem chama decide o que fazer (05/10/2026).
        for tentativa in range(4):
            try:
                resp = requests.post(self._URL, headers={"Authorization": f"Bearer {self._api_key}"}, json=corpo, timeout=20)
            except requests.RequestException as exc:
                logger.warning("E-mail não saiu (rede): %s", type(exc).__name__)
                raise EmailEnvioError("Não deu pra falar com o serviço de e-mail agora. Tente de novo em instantes.") from exc
            if resp.status_code < 300:
                return
            try:
                dados = resp.json()
            except ValueError:
                dados = {}
            nome = str(dados.get("name") or "")
            mensagem = str(dados.get("message") or "")[:200]
            if resp.status_code == 429 and nome in ("daily_quota_exceeded", "monthly_quota_exceeded"):
                logger.warning("E-mail não saiu: cota do Resend esgotada (%s)", nome)
                raise EmailCotaEsgotadaError(
                    "O serviço de e-mail atingiu o limite de envios de hoje."
                    if nome == "daily_quota_exceeded" else "O serviço de e-mail atingiu o limite de envios do mês.",
                    mensal=nome == "monthly_quota_exceeded",
                )
            if resp.status_code == 429 and tentativa < 3:
                try:
                    espera = float(resp.headers.get("retry-after") or 0)
                except ValueError:
                    espera = 0
                time.sleep(min(max(espera, 1.0 + tentativa), 10))
                continue
            logger.warning("E-mail não saiu: HTTP %s %s %s", resp.status_code, nome, mensagem)
            if resp.status_code == 429:
                raise EmailEnvioError("O serviço de e-mail está recebendo pedidos demais agora. Tente de novo em alguns minutos.")
            raise EmailEnvioError(f"O serviço de e-mail recusou o envio ({mensagem or f'HTTP {resp.status_code}'}).")


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.resend_api_key:
        return EmailSenderResend(settings.resend_api_key, settings.email_remetente)
    return EmailSenderConsole()
