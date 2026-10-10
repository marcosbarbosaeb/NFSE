"""Aviso de vencimento do certificado por e-mail (2026.10.7 — item C do roteiro).

Uma vez por certificado, quando faltam 30 dias ou menos pra vencer, os donos
da empresa recebem um e-mail com o mesmo texto de orientação de compra da
tela (`CERTIFICADO_ORIENTACAO`). A validade avisada fica em
`certificado.aviso_vencimento_para`: certificado novo (outra validade) avisa
de novo. Roda numa linha de execução do próprio servidor (`iniciar`), de
tempos em tempos — rodar duas vezes no mesmo dia não manda dois e-mails.

Simulação e conta só de contador ficam de fora. Falha de e-mail não marca
como avisado (tenta na próxima volta) e nunca derruba nada.
"""
from __future__ import annotations

import datetime
import logging
import threading
import time
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, definir_prestador_atual
from app.models import Certificado, Prestador
from app.services.emails import email_valido
from app.tempo import hoje as hoje_br

logger = logging.getLogger("agenteana.avisos_certificado")

DIAS_ANTES = 30
INTERVALO_S = 6 * 3600


def _donos(db: Session) -> dict[uuid.UUID, list[str]]:
    """E-mails dos DONOS de cada empresa (contador não entra). Tabelas sem RLS."""
    linhas = db.execute(text("""
        SELECT u.prestador_id AS p, u.email FROM usuario u WHERE u.ativo AND u.email_confirmado
        UNION
        SELECT up.prestador_id AS p, u.email FROM usuario_prestador up JOIN usuario u ON u.id = up.usuario_id
        WHERE u.ativo AND u.email_confirmado
    """)).all()
    donos: dict[uuid.UUID, list[str]] = {}
    for prestador_id, email in linhas:
        if prestador_id and email_valido(email) and email not in donos.setdefault(prestador_id, []):
            donos[prestador_id].append(email)
    return donos


def _mensagem(prestador: Prestador, validade: datetime.date, dias: int) -> tuple[str, str, str]:
    from app.services import email_modelo as m

    s = get_settings()
    quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
    orientacao = (s.certificado_orientacao or "").strip()
    link = f"{s.app_base_url}/app/empresa?aba=certificado"
    assunto = f"O certificado digital de {prestador.razao_social[:60]} vence {quando}"
    texto = (
        f"Oi! Aqui é a Ana.\n\nO certificado digital da empresa {prestador.razao_social} vence {quando} "
        f"({validade:%d/%m/%Y}). Depois disso eu não consigo assinar nem enviar notas.\n\n"
        f"Quando tiver o certificado novo, é só enviar em Empresa › Certificado: {link}\n\n"
        + (f"{orientacao} Responda este e-mail ou fale com o suporte: {s.email_suporte}\n" if orientacao else "")
    )
    html = m.moldura(
        titulo="Seu certificado digital está vencendo",
        previa=f"Vence {quando} ({validade:%d/%m/%Y}).",
        motivo="Você recebeu este e-mail porque é dono(a) de uma empresa na Agente Ana.",
        corpo_html=(
            m.paragrafo(f"O certificado digital da empresa <strong>{prestador.razao_social}</strong> vence <strong>{quando}</strong> ({validade:%d/%m/%Y}). Depois disso eu não consigo assinar nem enviar notas.")
            + m.paragrafo("Quando tiver o certificado novo, é só enviar em Empresa › Certificado.")
            + m.botao("Enviar o certificado novo", link)
            + (m.paragrafo(f"{orientacao} Responda este e-mail ou escreva para {s.email_suporte}.", suave=True) if orientacao else "")
        ),
    )
    return assunto, texto, html


def avisar(db: Session, hoje: datetime.date | None = None) -> int:
    """Manda os avisos que faltam. Devolve quantas empresas foram avisadas.
    Passa empresa por empresa trocando o contexto da RLS (como a Gestão)."""
    from app.services.email import get_email_sender

    hoje = hoje or hoje_br()
    avisadas = 0
    for prestador_id, emails in _donos(db).items():
        try:
            definir_prestador_atual(db, prestador_id)
            prestador = db.get(Prestador, prestador_id)
            if prestador is None or prestador.demo or prestador.so_contador:
                continue
            cert = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
            if cert is None or cert.validade is None or cert.aviso_vencimento_para == cert.validade:
                continue
            dias = (cert.validade - hoje).days
            if not 0 <= dias <= DIAS_ANTES:
                continue
            assunto, corpo_texto, corpo_html = _mensagem(prestador, cert.validade, dias)
            get_email_sender().enviar(destinatario=emails, assunto=assunto, corpo_texto=corpo_texto, corpo_html=corpo_html,
                                      responder_para=get_settings().email_suporte)
            cert.aviso_vencimento_para = cert.validade
            db.commit()
            avisadas += 1
        except Exception:  # noqa: BLE001 — uma empresa com problema não para as outras
            db.rollback()
            logger.warning("Aviso de vencimento do certificado não saiu (empresa %s)", prestador_id, exc_info=True)
    return avisadas


def iniciar(intervalo_s: int = INTERVALO_S) -> None:
    def rodar():
        time.sleep(120)  # deixa o servidor subir
        while True:
            try:
                with SessionLocal() as db:
                    n = avisar(db)
                if n:
                    logger.info("Aviso de vencimento do certificado enviado a %s empresa(s)", n)
                # Lista de espera: cidade que entrou no Emissor Nacional (2026.10.7)
                from app.services import lista_espera

                with SessionLocal() as db:
                    n = lista_espera.avisar_cidades_novas(db)
                if n:
                    logger.info("Lista de espera: %s pessoa(s) avisada(s) de cidade nova no Emissor Nacional", n)
            except Exception:  # noqa: BLE001
                logger.exception("Rotina de aviso de vencimento do certificado falhou")
            time.sleep(intervalo_s)

    threading.Thread(target=rodar, daemon=True, name="aviso-certificado").start()
