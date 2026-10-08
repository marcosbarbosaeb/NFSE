"""Moldura dos e-mails da plataforma (07/10/2026).

"Vamos melhorar esse e-mail de quando a pessoa faz o cadastro, ele está muito
cru — colocar uma logo e melhorar o visual pra dar mais credibilidade."

Uma moldura só pros e-mails que a Ana manda em nome dela mesma (confirmação
de cadastro, código de acesso, convite do contador): topo com a marca, menu,
título, texto, botão e rodapé. HTML de e-mail é das antigas de propósito
(tabelas e estilo na própria tag): é o que Gmail, Outlook e celular mostram
igual. Os e-mails de NOTA pro tomador não passam por aqui — esses são o
modelo de cada empresa.
"""
from __future__ import annotations

import html

from app.config import get_settings

_AZUL = "#1e2a5e"   # barra lateral do painel
_ROSA = "#e11d74"   # botões de ação
_TEXTO = "#1e293b"
_SUAVE = "#64748b"

# (rótulo, caminho) — o menu no topo do e-mail.
MENU_CLIENTE = (("Entrar", "/entrar"), ("Convide seu contador", "/app/empresa?aba=contador"), ("Ajuda", "/app/ajuda"))
MENU_CONTADOR = (("Entrar", "/entrar"), ("Painel do contador", "/app/atendimentos"), ("Ajuda", "/app/ajuda"))


def _base() -> str:
    return get_settings().app_base_url.rstrip("/")


def botao(texto: str, url: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr>'
        f'<td bgcolor="{_ROSA}" style="border-radius:10px">'
        f'<a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:13px 26px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:15px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:10px">{html.escape(texto)}</a>'
        "</td></tr></table>"
    )


def paragrafo(texto_html: str, suave: bool = False) -> str:
    """`texto_html` já vem escapado por quem chama (pode ter <strong>, <a>)."""
    cor, tamanho = (_SUAVE, "13px") if suave else (_TEXTO, "15px")
    return f'<p style="margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:{tamanho};line-height:1.55;color:{cor}">{texto_html}</p>'


def moldura(*, titulo: str, corpo_html: str, previa: str = "", menu: tuple[tuple[str, str], ...] = MENU_CLIENTE, motivo: str = "") -> str:
    """O e-mail inteiro. `previa` é a frase que aparece ao lado do assunto na
    caixa de entrada; `motivo` explica no rodapé por que a pessoa recebeu."""
    s = get_settings()
    base = _base()
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="{base}{caminho}" style="color:#c7d2fe;text-decoration:none">{html.escape(rotulo)}</a>' for rotulo, caminho in menu
    )
    suporte = html.escape(s.email_suporte or "suporte@agenteana.com.br")
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Agente Ana</title></head>'
        '<body style="margin:0;padding:0;background:#f1f5f9">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#f1f5f9">{html.escape(previa)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f5f9"><tr><td align="center" style="padding:28px 12px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px">'
        # topo: marca + menu
        f'<tr><td bgcolor="{_AZUL}" style="padding:22px 28px 16px;border-radius:16px 16px 0 0">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding-right:12px"><img src="{base}/ana-email.png" width="48" height="48" alt="Agente Ana" style="display:block;border-radius:12px;border:0"></td>'
        '<td style="font-family:Arial,Helvetica,sans-serif;font-size:20px;color:#ffffff">Agente <strong style="color:#f9a8d4">Ana</strong>'
        '<div style="font-size:12px;color:#a5b4fc;padding-top:2px">Notas fiscais e financeiro no automático</div></td>'
        "</tr></table></td></tr>"
        f'<tr><td bgcolor="{_AZUL}" style="padding:0 28px 16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;border-top:1px solid #33407a">'
        f'<div style="padding-top:12px;color:#6b78b8">{links}</div></td></tr>'
        # miolo
        '<tr><td bgcolor="#ffffff" style="padding:30px 28px 22px">'
        f'<h1 style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.3;color:{_TEXTO}">{html.escape(titulo)}</h1>'
        f"{corpo_html}"
        "</td></tr>"
        # rodapé
        '<tr><td bgcolor="#f8fafc" style="padding:18px 28px;border-radius:0 0 16px 16px;border-top:1px solid #e2e8f0;'
        f'font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:{_SUAVE}">'
        f'{html.escape(motivo) + "<br>" if motivo else ""}'
        f'Dúvidas? Fale com a gente: <a href="mailto:{suporte}" style="color:{_SUAVE}">{suporte}</a><br>'
        f'Agente Ana · <a href="https://agenteana.com.br" style="color:{_SUAVE}">agenteana.com.br</a>'
        "</td></tr></table></td></tr></table></body></html>"
    )


def link_que_nao_abre(url: str) -> str:
    """Pra quem o botão não funciona (e-mail corporativo, leitor antigo)."""
    seguro = html.escape(url, quote=True)
    return paragrafo(f'Se o botão não abrir, copie e cole este endereço no navegador:<br><a href="{seguro}" style="color:{_SUAVE};word-break:break-all">{seguro}</a>', suave=True)
