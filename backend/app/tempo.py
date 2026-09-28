"""Data de "hoje" no fuso do Brasil.

O servidor (Railway) roda em UTC: a partir das 21h de Brasília o
`date.today()` já é o dia seguinte — no último dia do mês isso virava a
competência do mês que vem, avisos de "hoje é o dia de gerar" no dia errado
etc. Tudo que depende do dia de hoje usa `hoje()` daqui.
"""
import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime.datetime:
    return datetime.datetime.now(FUSO)


def hoje() -> datetime.date:
    return agora().date()


def data_local(momento: datetime.datetime | None) -> datetime.date | None:
    """Timestamp do banco (UTC) -> dia no Brasil."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone(FUSO).date()
