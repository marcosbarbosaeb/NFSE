"""Lista de espera do cadastro (2026.10.7 — item B do roteiro).

Quem não pôde criar a conta (`atendimento.avaliar`: cidade fora do Emissor
Nacional ou regime não atendido) deixa e-mail, WhatsApp e CNPJ. O motivo e a
cidade vêm da consulta da Receita feita AQUI, não do navegador. Um CNPJ fica
uma vez por motivo (pedir de novo atualiza o contato).

Quando a lista de municípios é atualizada (`data/emissor_nacional.json`) e a
cidade entra, quem esperava por ela recebe um e-mail (`avisar_cidades_novas`,
na mesma rotina do aviso do certificado).
"""
from __future__ import annotations

import datetime
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ListaEspera
from app.services import compatibilidade

logger = logging.getLogger("agenteana.lista_espera")


class ForaDaListaError(ValueError):
    """O CNPJ não precisa de lista de espera (a Ana atende, ou está inativo)."""


def entrar(db: Session, *, cnpj: str, email: str, whatsapp: str | None, veredito: dict) -> ListaEspera:
    if not veredito.get("lista_espera"):
        raise ForaDaListaError(veredito.get("mensagem") or "Esta empresa não precisa entrar na lista de espera.")
    motivo = veredito["codigo"]
    registro = db.query(ListaEspera).filter_by(cnpj=cnpj, motivo=motivo).one_or_none()
    if registro is None:
        registro = ListaEspera(cnpj=cnpj, motivo=motivo)
        db.add(registro)
    registro.email = email
    registro.whatsapp = whatsapp
    registro.razao_social = (veredito.get("razao_social") or "")[:300] or None
    registro.cod_municipio = veredito.get("cod_municipio")
    registro.cidade = veredito.get("cidade")
    registro.regime = veredito.get("regime")
    registro.avisado_em = None
    db.flush()
    return registro


def resumo_gestao(db: Session) -> dict:
    """A Gestão vê agrupado por cidade e por motivo, com as pessoas."""
    linhas = db.query(ListaEspera).order_by(ListaEspera.criado_em.desc()).all()
    por_motivo = dict(db.query(ListaEspera.motivo, func.count(ListaEspera.id)).group_by(ListaEspera.motivo).all())
    cidades: dict[str, dict] = {}
    for l in linhas:
        if l.motivo != "cidade_fora":
            continue
        c = cidades.setdefault(l.cod_municipio or "?", {"cidade": l.cidade or "Cidade não identificada", "cod_municipio": l.cod_municipio,
                                                        "pessoas": 0, "ja_no_emissor": compatibilidade.usa_emissor_nacional(l.cod_municipio) is True})
        c["pessoas"] += 1
    return {
        "total": len(linhas),
        "por_motivo": {"cidade_fora": por_motivo.get("cidade_fora", 0), "regime": por_motivo.get("regime", 0)},
        "por_cidade": sorted(cidades.values(), key=lambda c: (-c["pessoas"], c["cidade"])),
        "pessoas": [
            {"id": str(l.id), "email": l.email, "whatsapp": l.whatsapp, "cnpj": l.cnpj, "razao_social": l.razao_social,
             "cidade": l.cidade, "motivo": l.motivo, "criado_em": l.criado_em.isoformat() if l.criado_em else None,
             "avisado_em": l.avisado_em.isoformat() if l.avisado_em else None}
            for l in linhas[:500]
        ],
    }


def avisar_cidades_novas(db: Session) -> int:
    """E-mail pra quem esperava uma cidade que agora usa o Emissor Nacional."""
    from app.services import email_modelo as m
    from app.services.email import get_email_sender
    from app.services.emails import email_valido

    s = get_settings()
    pendentes = db.query(ListaEspera).filter(ListaEspera.motivo == "cidade_fora", ListaEspera.avisado_em.is_(None)).all()
    avisados = 0
    for l in pendentes:
        if compatibilidade.usa_emissor_nacional(l.cod_municipio) is not True or not email_valido(l.email):
            continue
        link = f"{s.app_base_url}/cadastro"
        cidade = l.cidade or "a sua cidade"
        try:
            get_email_sender().enviar(
                destinatario=l.email,
                assunto=f"Boa notícia: {cidade} entrou no Emissor Nacional",
                corpo_texto=(f"Oi! Aqui é a Ana.\n\nVocê pediu pra ser avisado(a): a prefeitura de {cidade} passou a usar o Emissor Nacional "
                             f"da NFS-e. Agora eu já consigo emitir as suas notas.\n\nCrie a sua conta: {link}\n"),
                corpo_html=m.moldura(
                    titulo=f"{cidade} entrou no Emissor Nacional",
                    previa="Agora a Ana já consegue emitir as suas notas.",
                    motivo="Você recebeu este e-mail porque entrou na lista de espera da Agente Ana.",
                    corpo_html=(m.paragrafo(f"Você pediu pra ser avisado(a): a prefeitura de <strong>{cidade}</strong> passou a usar o Emissor Nacional da NFS-e. Agora eu já consigo emitir as suas notas.")
                                + m.botao("Criar a minha conta", link)),
                ),
            )
        except Exception:  # noqa: BLE001 — tenta de novo na próxima volta
            logger.warning("Aviso da lista de espera não saiu", exc_info=True)
            continue
        l.avisado_em = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        avisados += 1
    return avisados
