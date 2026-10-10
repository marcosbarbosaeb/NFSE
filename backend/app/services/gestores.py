"""Gestão com usuários próprios (2026.10.7 — item F do roteiro).

Quem é gestor: o e-mail do login está na tabela `gestor` (ou, como reserva,
na variável ADMIN_EMAILS — que pode ser apagada do Railway quando a tabela
estiver como o Marcos quer). Todo gestor tem todas as permissões por
enquanto. Gestor NÃO abre documentos da empresa de ninguém
(`app/services/documentos_empresa.py`).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Gestor, Usuario
from app.services.emails import email_valido, normalizar


class GestorError(ValueError):
    """Mensagem pronta pra tela."""


def _da_variavel() -> set[str]:
    return {normalizar(e) for e in (get_settings().admin_emails or "").split(",") if e.strip()}


def _da_tabela(db: Session) -> set[str]:
    return {e for (e,) in db.query(Gestor.email).all()}


def emails(db: Session) -> set[str]:
    return _da_tabela(db) | _da_variavel()


def configurado(db: Session) -> bool:
    return bool(emails(db))


def eh_gestor(db: Session, usuario: Usuario | None) -> bool:
    return usuario is not None and normalizar(usuario.email or "") in emails(db)


def listar(db: Session) -> list[dict]:
    da_tabela = {g.email: g for g in db.query(Gestor).order_by(Gestor.adicionado_em).all() if g.email in _da_tabela(db)}
    contas = {normalizar(u.email): u for u in db.query(Usuario).filter(Usuario.email.in_(list(emails(db)) or [""])).all()}
    saida = []
    for email in sorted(emails(db)):
        g = da_tabela.get(email)
        u = contas.get(email)
        saida.append({
            "email": email, "nome": u.nome if u else None, "tem_conta": u is not None,
            "origem": "tabela" if g else "variavel",
            "adicionado_em": g.adicionado_em.isoformat() if g and g.adicionado_em else None,
            "adicionado_por": g.adicionado_por if g else None,
        })
    return saida


def adicionar(db: Session, email: str, por: str) -> Gestor:
    if not email_valido(email):
        raise GestorError("Esse e-mail não é válido.")
    email = normalizar(email)
    existente = db.get(Gestor, email)
    if existente is not None:
        return existente
    g = Gestor(email=email, adicionado_por=normalizar(por))
    db.add(g)
    db.flush()
    return g


def remover(db: Session, email: str, por: str) -> None:
    email = normalizar(email)
    if email == normalizar(por):
        raise GestorError("Você não pode tirar a si mesmo(a) da Gestão. Peça a outro gestor.")
    g = db.get(Gestor, email)
    if g is None:
        if email in _da_variavel():
            raise GestorError("Este e-mail está na variável ADMIN_EMAILS do Railway: tire de lá.")
        raise GestorError("Este e-mail não é gestor.")
    if len(emails(db)) <= 1:
        raise GestorError("A Gestão precisa de pelo menos um gestor.")
    db.delete(g)
    db.flush()
