"""Clientes do financeiro (05/10/2026): de quem o dinheiro entra.

O cadastro em si é o cadastro geral (o mesmo cliente serve aos dois
módulos — `app/services/vinculos.py`); aqui fica só o que o financeiro
precisa dele: nome, se está ativo e quanto já entrou. Quem tem só o
Financeiro cria e renomeia clientes por aqui, sem nenhum dado fiscal."""
import re
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.financeiro import listas
from app.models import PrestadorTomador


class ClienteError(Exception):
    pass


def listar(db: Session, *, ano: str) -> list[dict]:
    """Todos os clientes (ativos primeiro, depois por quanto entrou no ano)."""
    recebido: dict[str, dict] = {}
    for p in listas.listar_pagamentos(db, ano=ano, por_recebimento=True):
        chave = str(p["vinculo_id"])
        soma = recebido.setdefault(chave, {"total": 0.0, "quantos": 0, "ultimo": None})
        soma["total"] += float(p["valor"] or 0)
        soma["quantos"] += 1
        data = p.get("data_recebimento")
        if data and (soma["ultimo"] is None or str(data) > soma["ultimo"]):
            soma["ultimo"] = str(data)
    vinculos = db.query(PrestadorTomador).filter(PrestadorTomador.excluido_em.is_(None)).all()
    clientes = []
    for v in vinculos:
        soma = recebido.get(str(v.id), {"total": 0.0, "quantos": 0, "ultimo": None})
        clientes.append({
            "id": str(v.id), "nome": v.apelido, "ativo": bool(v.ativo), "so_controle": bool(v.sem_nota),
            "recebido": round(soma["total"], 2), "recebimentos": soma["quantos"], "ultimo_recebimento": soma["ultimo"],
        })
    clientes.sort(key=lambda c: (not c["ativo"], -c["recebido"], c["nome"].lower()))
    return clientes


def atualizar(db: Session, vinculo_id: uuid.UUID, *, nome: str | None = None, ativo: bool | None = None) -> dict:
    vinculo = (
        db.query(PrestadorTomador)
        .filter(PrestadorTomador.id == vinculo_id, PrestadorTomador.excluido_em.is_(None))
        .one_or_none()
    )
    if vinculo is None:
        raise ClienteError("Cliente não encontrado.")
    if nome is not None:
        nome = re.sub(r"\s+", " ", nome).strip()[:60]
        if len(nome) < 2:
            raise ClienteError("Dê um nome com pelo menos 2 letras.")
        repetido = (
            db.query(PrestadorTomador.id)
            .filter(
                func.lower(PrestadorTomador.apelido) == nome.lower(), PrestadorTomador.id != vinculo.id,
                PrestadorTomador.prestador_id == vinculo.prestador_id, PrestadorTomador.excluido_em.is_(None),
            )
            .first()
        )
        if repetido is not None:
            raise ClienteError(f"Já existe um cliente chamado “{nome}”.")
        vinculo.apelido = nome
    if ativo is not None:
        vinculo.ativo = ativo
    db.flush()
    return {"id": str(vinculo.id), "nome": vinculo.apelido, "ativo": bool(vinculo.ativo), "so_controle": bool(vinculo.sem_nota)}
