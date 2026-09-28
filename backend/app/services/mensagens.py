"""
Textos das mensagens que SAEM da Agente Ana pro fornecedor (e-mail e
WhatsApp) — tudo num lugar só de propósito: Marcos avisou (23/09/2026) que
"vamos trabalhar o formato de cada uma das mensagens de saída", então quem
for lapidar o texto mexe só aqui, sem caçar string pelo código.

Cada função recebe só dados já prontos (nada de banco aqui), então dá pra
testar/ajustar o texto isolado.
"""
import re
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
    tomador_razao_social: str = ""
    ordem: str | None = None


def _competencia_br(competencia: str) -> str:
    ano, mes = competencia.split("-")
    return f"{mes}/{ano}"


def _valor_br(valor: float) -> str:
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Modelo configurável (28/09/2026) ----------------------------------------
# "É importante que os campos dessa mensagem sejam configuráveis. Tem tomador
# que pede que o assunto seja específico": o prestador define assunto/texto
# padrão e cada tomador pode ter os seus. Os códigos entre chaves abaixo são
# trocados pelos dados da nota; qualquer outro texto entre chaves fica como
# está (nada de erro por um "{" digitado sem querer).

CODIGOS_MODELO: list[tuple[str, str, str]] = [
    # (código, o que vira, exemplo)
    ("prestador", "Seu nome ou empresa", "Maria Silva ME"),
    ("tomador", "Nome do tomador (como você chama)", "Awin"),
    ("razao_social_tomador", "Razão social do tomador", "AWIN VEICULAÇÃO DE PUBLICIDADE LTDA"),
    ("competencia", "Mês/ano da nota", "09/2026"),
    ("mes", "Nome do mês", "Setembro"),
    ("ano", "Ano", "2026"),
    ("valor", "Valor da nota", "R$ 1.234,56"),
    ("descricao", "Descrição do serviço", "Locação de espaço virtual..."),
    ("ordem", "Número da ordem de pagamento", "15496516"),
    ("numero_nota", "Número da nota (DPS)", "42"),
    ("chave_acesso", "Chave de acesso da NFS-e", "3106200..."),
    ("link", "Link pra baixar a nota", "https://notas.agenteana.com.br/..."),
]

ASSUNTO_PADRAO = "Nota fiscal de serviço — {prestador} — {competencia}"
MENSAGEM_PADRAO = """Olá!

Segue a nota fiscal de serviço emitida por {prestador}.

Referente a: {descricao}
Competência: {competencia}
Valor: {valor}

A nota está em anexo e também pode ser baixada aqui: {link}

Qualquer dúvida, é só responder este e-mail.

{prestador}"""

ANEXOS_VALIDOS = ("pdf_xml", "pdf", "xml")


def valores_modelo(d: DadosMensagem) -> dict[str, str]:
    ano, mes = d.competencia.split("-")
    return {
        "prestador": d.prestador_nome,
        "tomador": d.fornecedor_apelido,
        "razao_social_tomador": d.tomador_razao_social or d.fornecedor_apelido,
        "competencia": f"{mes}/{ano}",
        "mes": _MESES[int(mes) - 1],
        "ano": ano,
        "valor": _valor_br(d.valor),
        "descricao": d.descricao,
        "ordem": d.ordem or "",
        "numero_nota": str(d.n_dps or ""),
        "chave_acesso": d.chave_acesso or "",
        "link": d.link,
    }


def renderizar_modelo(modelo: str, d: DadosMensagem) -> str:
    valores = valores_modelo(d)
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), modelo)


def email_html_de_texto(texto: str, d: DadosMensagem) -> str:
    """HTML simples a partir do texto que a pessoa escreveu: parágrafos,
    quebras de linha e o link da nota clicável."""
    blocos = [b for b in re.split(r"\n\s*\n", texto.strip()) if b.strip()]
    partes = []
    for bloco in blocos:
        html = escape(bloco).replace("\n", "<br>")
        if d.link:
            html = html.replace(escape(d.link), f'<a href="{escape(d.link)}" style="color:#4f46e5">{escape(d.link)}</a>')
        partes.append(f"<p>{html}</p>")
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px;color:#1e293b;line-height:1.5">'
        + "".join(partes)
        + '<p style="color:#94a3b8;font-size:12px">enviado pela Agente Ana</p></div>'
    )


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
        "— enviado pela Agente Ana",
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
<p>{escape(d.prestador_nome)}<br><span style="color:#94a3b8;font-size:12px">enviado pela Agente Ana</span></p>
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



def whatsapp_de_modelo(modelo: str | None, d: DadosMensagem) -> str:
    return renderizar_modelo(modelo, d) if modelo else whatsapp_texto(d)


def templatizar(texto: str, d: DadosMensagem) -> str:
    """O caminho inverso de `renderizar_modelo`: o texto que a pessoa editou
    na hora de enviar vira modelo pra próxima nota, trocando os dados DESTA
    nota (mês, valor, nomes, link...) pelos códigos — assim o "salvar as
    últimas configurações" não congela o mês de hoje no texto."""
    valores = sorted(
        ((codigo, valor) for codigo, valor in valores_modelo(d).items() if valor and len(valor) >= 3),
        key=lambda cv: len(cv[1]),
        reverse=True,
    )
    for codigo, valor in valores:
        texto = texto.replace(valor, "{" + codigo + "}")
    return texto



# E-mails gerais (contador, a própria pessoa) — texto padrão próprio.
ASSUNTO_GERAL_PADRAO = "NFS-e {numero_nota} — {razao_social_tomador} — {competencia}"
MENSAGEM_GERAL_PADRAO = """Olá!

Segue a nota fiscal de serviço emitida por {prestador} para {razao_social_tomador}.

Competência: {competencia}
Valor: {valor}
Referente a: {descricao}

A nota está em anexo e também pode ser baixada aqui: {link}

{prestador}"""
