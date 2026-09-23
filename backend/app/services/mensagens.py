"""
Textos das mensagens que SAEM do NotaFácil pro fornecedor (e-mail e
WhatsApp) — tudo num lugar só de propósito: Marcos avisou (23/09/2026) que
"vamos trabalhar o formato de cada uma das mensagens de saída", então quem
for lapidar o texto mexe só aqui, sem caçar string pelo código.

Cada função recebe só dados já prontos (nada de banco aqui), então dá pra
testar/ajustar o texto isolado.
"""
from dataclasses import dataclass
from html import escape


@dataclass
class DadosMensagem:
    prestador_nome: str
    fornecedor_apelido: str
    descricao: str
    competencia: str  # AAAA-MM
    valor: float
    n_dps: int
    chave_acesso: str | None
    link: str


def _competencia_br(competencia: str) -> str:
    ano, mes = competencia.split("-")
    return f"{mes}/{ano}"


def _valor_br(valor: float) -> str:
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def email_assunto(d: DadosMensagem) -> str:
    return f"Nota fiscal de serviço — {d.prestador_nome} — {_competencia_br(d.competencia)}"


def email_texto(d: DadosMensagem) -> str:
    linhas = [
        "Olá!",
        "",
        f"Segue a nota fiscal de serviço emitida por {d.prestador_nome}.",
        "",
        f"Referente a: {d.descricao}",
        f"Competência: {_competencia_br(d.competencia)}",
        f"Valor: {_valor_br(d.valor)}",
    ]
    if d.chave_acesso:
        linhas.append(f"Chave de acesso: {d.chave_acesso}")
    linhas += [
        "",
        f"A nota está em anexo e também pode ser baixada aqui: {d.link}",
        "",
        "Qualquer dúvida, é só responder este e-mail.",
        "",
        f"{d.prestador_nome}",
        "— enviado pelo NotaFácil",
    ]
    return "\n".join(linhas)


def email_html(d: DadosMensagem) -> str:
    chave = f"<p style='margin:0'><b>Chave de acesso:</b> {escape(d.chave_acesso)}</p>" if d.chave_acesso else ""
    return f"""<div style="font-family:Arial,sans-serif;font-size:14px;color:#1e293b;line-height:1.5">
<p>Olá!</p>
<p>Segue a nota fiscal de serviço emitida por <b>{escape(d.prestador_nome)}</b>.</p>
<div style="background:#f1f5f9;border-radius:8px;padding:12px 16px;margin:16px 0">
<p style="margin:0"><b>Referente a:</b> {escape(d.descricao)}</p>
<p style="margin:0"><b>Competência:</b> {_competencia_br(d.competencia)}</p>
<p style="margin:0"><b>Valor:</b> {_valor_br(d.valor)}</p>
{chave}
</div>
<p>A nota está em anexo e também pode ser baixada
<a href="{escape(d.link)}" style="color:#4f46e5">neste link</a>.</p>
<p>Qualquer dúvida, é só responder este e-mail.</p>
<p>{escape(d.prestador_nome)}<br><span style="color:#94a3b8;font-size:12px">enviado pelo NotaFácil</span></p>
</div>"""


def whatsapp_texto(d: DadosMensagem) -> str:
    linhas = [
        "Olá! Tudo bem?",
        f"Segue a nota fiscal de serviço de {_competencia_br(d.competencia)} "
        f"({_valor_br(d.valor)}) — {d.descricao}.",
        "",
        f"Baixe aqui: {d.link}",
    ]
    if d.chave_acesso:
        linhas += ["", f"Chave de acesso: {d.chave_acesso}"]
    linhas += ["", d.prestador_nome]
    return "\n".join(linhas)
