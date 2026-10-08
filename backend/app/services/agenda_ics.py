"""Link de assinatura do calendário (08/10/2026).

"Podemos colocar a opção de integrar a agenda ao Google Agenda e ela carregar
as coisas lá no Google Agenda da pessoa." O jeito mais simples e sem pedir
permissão nenhuma ao Google: um endereço .ics secreto por empresa, que a
pessoa cola uma vez em "Adicionar agenda › Do URL" (Google), "Assinar
calendário" (Outlook) ou "Nova assinatura" (Apple). O próprio app de agenda
busca o endereço de tempos em tempos (o Google demora algumas horas).

O endereço não pede login: quem tem o link vê os eventos (títulos, datas e
valores previstos). Por isso ele é longo, aleatório e pode ser trocado
("Gerar um novo link") — o antigo para de funcionar na hora.
"""
from __future__ import annotations

import datetime
import secrets
import uuid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AssinaturaAgenda
from app.tempo import hoje as hoje_br

# Quanto do calendário vai no arquivo: um mês pra trás e seis pra frente.
DIAS_ANTES = 31
DIAS_DEPOIS = 190

_ROTULO = {
    "prazo_emissao": "Gerar nota",
    "recebimento_previsto": "Previsão de recebimento",
    "recebimento_confirmado": "Recebido",
    "revisar_aliquota": "Revisar alíquota",
}

_LINK = {
    "prazo_emissao": "/app/nfse",
    "recebimento_previsto": "/app/financeiro/conciliacao",
    "recebimento_confirmado": "/app/financeiro",
    "revisar_aliquota": "/app/empresa?aba=emitente",
    "manual": "/app/calendario",
}


def _endereco(token: str) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/api/agenda/{token}.ics"


def link(db: Session, prestador_id: uuid.UUID, *, criar: bool = True) -> str | None:
    atual = db.get(AssinaturaAgenda, prestador_id)
    if atual is None:
        if not criar:
            return None
        atual = AssinaturaAgenda(prestador_id=prestador_id, token=secrets.token_urlsafe(32))
        db.add(atual)
        db.flush()
    return _endereco(atual.token)


def trocar_link(db: Session, prestador_id: uuid.UUID) -> str:
    atual = db.get(AssinaturaAgenda, prestador_id)
    if atual is None:
        return link(db, prestador_id)
    atual.token = secrets.token_urlsafe(32)
    db.flush()
    return _endereco(atual.token)


def empresa_do_token(db: Session, token: str) -> uuid.UUID | None:
    if not token or len(token) > 64:
        return None
    achado = db.query(AssinaturaAgenda.prestador_id).filter(AssinaturaAgenda.token == token).first()
    return achado[0] if achado else None


def _escapar(texto: str) -> str:
    return (
        (texto or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")
    )


def _dobrar(linha: str) -> str:
    """RFC 5545: linha de no máximo 75 bytes; o resto continua com um espaço."""
    bruto = linha.encode("utf-8")
    if len(bruto) <= 75:
        return linha
    partes, atual = [], b""
    for ch in linha:
        b = ch.encode("utf-8")
        if len(atual) + len(b) > (75 if not partes else 74):
            partes.append(atual.decode("utf-8"))
            atual = b""
        atual += b
    partes.append(atual.decode("utf-8"))
    return "\r\n ".join(partes)


def _brl(valor) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_ics(eventos: list[dict], *, nome_empresa: str, agora: datetime.datetime | None = None) -> str:
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    carimbo = agora.strftime("%Y%m%dT%H%M%SZ")
    base = get_settings().app_base_url.rstrip("/")
    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agente Ana//Calendario//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escapar(f'Agente Ana — {nome_empresa}')}",
        "X-WR-TIMEZONE:America/Sao_Paulo",
        # pedido (nem todo app respeita) pra buscar de novo a cada 6 horas
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for ev in eventos:
        dia: datetime.date = ev["data"]
        tipo = ev["tipo"]
        if tipo == "manual":
            titulo = ev["titulo"]
            uid = f"manual-{ev.get('id')}"
        else:
            quem = ev.get("apelido")
            titulo = f"{_ROTULO.get(tipo, ev['titulo'])} — {quem}" if quem else ev["titulo"]
            uid = f"{tipo}-{ev.get('chave') or ev.get('id') or dia.isoformat()}-{ev.get('vinculo_id') or ''}"
        if ev.get("valor") is not None:
            titulo = f"{titulo} ({_brl(ev['valor'])})"
        descricao = [ev.get("descricao") or "", f"Abrir na Agente Ana: {base}{_LINK.get(tipo, '/app/calendario')}"]
        linhas += [
            "BEGIN:VEVENT",
            f"UID:{_escapar(uid)}@agenteana.com.br",
            f"DTSTAMP:{carimbo}",
            f"DTSTART;VALUE=DATE:{dia:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dia + datetime.timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_escapar(titulo)}",
            f"DESCRIPTION:{_escapar(chr(10).join(d for d in descricao if d))}",
            f"URL:{base}{_LINK.get(tipo, '/app/calendario')}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(_dobrar(l) for l in linhas) + "\r\n"


def intervalo(hoje: datetime.date | None = None) -> tuple[datetime.date, datetime.date]:
    hoje = hoje or hoje_br()
    return hoje - datetime.timedelta(days=DIAS_ANTES), hoje + datetime.timedelta(days=DIAS_DEPOIS)
