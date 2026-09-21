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
import logging

import requests

from app.config import get_settings

logger = logging.getLogger("notafacil.email")


class EmailEnvioError(Exception):
    """Falha ao mandar o e-mail pro provedor (rede, API fora do ar, chave
    inválida...). Deliberadamente uma exceção À PARTE dos erros de negócio
    do cadastro (ver app/services/cadastro.py) — a conta já foi criada no
    banco nesse ponto; falhar o e-mail não deve reverter o cadastro (o
    usuário pode pedir reenvio depois), só precisa ser visível em log."""


class EmailSender:
    def enviar(self, *, destinatario: str, assunto: str, corpo_texto: str, corpo_html: str) -> None:
        raise NotImplementedError


class EmailSenderConsole(EmailSender):
    """Default enquanto não existe RESEND_API_KEY configurada (dev local e
    testes) — nunca faz uma chamada de rede."""

    def enviar(self, *, destinatario: str, assunto: str, corpo_texto: str, corpo_html: str) -> None:
        logger.info("=== E-MAIL (modo console — RESEND_API_KEY não configurada) ===")
        logger.info("Para: %s", destinatario)
        logger.info("Assunto: %s", assunto)
        logger.info("%s", corpo_texto)
        logger.info("=== fim do e-mail ===")


class EmailSenderResend(EmailSender):
    _URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, remetente: str):
        self._api_key = api_key
        self._remetente = remetente

    def enviar(self, *, destinatario: str, assunto: str, corpo_texto: str, corpo_html: str) -> None:
        try:
            resp = requests.post(
                self._URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._remetente,
                    "to": [destinatario],
                    "subject": assunto,
                    "text": corpo_texto,
                    "html": corpo_html,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise EmailEnvioError(f"Falha ao enviar e-mail via Resend: {exc}") from exc


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.resend_api_key:
        return EmailSenderResend(settings.resend_api_key, settings.email_remetente)
    return EmailSenderConsole()
