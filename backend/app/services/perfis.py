"""Perfis no cadastro (2026.10.7 — `ideias/perfis-no-cadastro.md`).

"Como você costuma emitir suas notas?" — quatro jeitos de emitir (não
profissões), em `app/data/perfis.json`. A pessoa marca um ou mais (o primeiro
é o principal), escreve em "Não me encontrei" ou pula. Fica guardado por
empresa (`Prestador.perfis`). Motor e planos não mudam por perfil: nesta
versão o perfil só escolhe o atalho em destaque na tela inicial e alimenta a
Gestão (quantas empresas em cada perfil, quem pulou, "Não me encontrei" e as
buscas sem resultado — a lista de demanda pros próximos perfis).
"""
from __future__ import annotations

import datetime
import json
import re
import unicodedata
import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import PerfilBusca, Prestador

ARQUIVO = Path(__file__).resolve().parents[1] / "data" / "perfis.json"
MAX_BUSCAS = 10


class PerfilError(ValueError):
    """Mensagem pronta pra tela."""


@lru_cache(maxsize=1)
def catalogo() -> list[dict]:
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))["perfis"]


def ids() -> list[str]:
    return [p["id"] for p in catalogo()]


def _norm(texto: str) -> str:
    sem = unicodedata.normalize("NFD", texto or "")
    return re.sub(r"\s+", " ", "".join(c for c in sem if unicodedata.category(c) != "Mn").lower()).strip()


def buscar(texto: str) -> list[str]:
    """Ids dos perfis cuja lista de profissões (ou título) contém o texto."""
    alvo = _norm(texto)
    if len(alvo) < 2:
        return []
    return [p["id"] for p in catalogo() if alvo in _norm(p["titulo"]) or any(alvo in _norm(x) for x in p["profissoes"])]


def salvar(db: Session, prestador: Prestador, *, perfis: list[str] | None, outro: str | None, pulou: bool,
           buscas_sem_resultado: list[str] | None = None) -> Prestador:
    validos = ids()
    escolhidos = list(dict.fromkeys(p for p in (perfis or []) if p in validos))
    if any(p not in validos for p in (perfis or [])):
        raise PerfilError("Perfil desconhecido.")
    outro = (outro or "").strip()[:300] or None
    if not pulou and not escolhidos and not outro:
        raise PerfilError("Escolha pelo menos um jeito de emitir, conte o que você faz ou clique em “Pular”.")
    prestador.perfis = [] if pulou else escolhidos
    prestador.perfil_outro = None if pulou else outro
    prestador.perfil_pulou = bool(pulou)
    prestador.perfil_respondido_em = datetime.datetime.now(datetime.timezone.utc)
    for busca in (buscas_sem_resultado or [])[:MAX_BUSCAS]:
        b = re.sub(r"\s+", " ", (busca or "").strip())[:80]
        if len(_norm(b)) >= 3 and not buscar(b):
            db.add(PerfilBusca(id=uuid.uuid4(), texto=b))
    db.flush()
    return prestador


def principal(prestador: Prestador | None) -> dict | None:
    """O perfil principal (o primeiro marcado), com o atalho da tela inicial."""
    if prestador is None or not prestador.perfis:
        return None
    por_id = {p["id"]: p for p in catalogo()}
    p = por_id.get(prestador.perfis[0])
    return {"id": p["id"], "titulo": p["titulo"], "atalho": p.get("atalho")} if p else None


def _agrupar(textos: list[str]) -> list[dict]:
    """Agrupa por texto parecido: sem acento, minúsculo e sem plural simples."""
    grupos: dict[str, dict] = {}
    for t in textos:
        chave = " ".join(re.sub(r"(es|s)$", "", w) for w in _norm(t).split())
        g = grupos.setdefault(chave, {"texto": t.strip(), "vezes": 0, "variacoes": []})
        g["vezes"] += 1
        if t.strip() not in g["variacoes"] and len(g["variacoes"]) < 5:
            g["variacoes"].append(t.strip())
    return sorted(grupos.values(), key=lambda g: (-g["vezes"], g["texto"].lower()))


def resumo_gestao(db: Session, prestador_de_volta: uuid.UUID) -> dict:
    """Gestão: empresas por perfil (principal e qualquer), quem pulou, quem
    não respondeu, "Não me encontrei" e buscas sem resultado. `prestador` tem
    RLS: passa empresa por empresa, como a Gestão, e devolve o contexto."""
    from app.database import definir_prestador_atual

    ids_empresas = [r[0] for r in db.execute(text(
        "SELECT DISTINCT prestador_id FROM usuario WHERE prestador_id IS NOT NULL "
        "UNION SELECT DISTINCT prestador_id FROM usuario_prestador"
    )).all()]
    por_perfil = {i: {"id": i, "titulo": t, "principal": 0, "marcado": 0} for i, t in ((p["id"], p["titulo"]) for p in catalogo())}
    pularam = sem_resposta = 0
    outros: list[str] = []
    try:
        for pid in ids_empresas:
            definir_prestador_atual(db, pid)
            p = db.get(Prestador, pid)
            if p is None or p.demo or p.so_contador:
                continue
            if p.perfil_respondido_em is None:
                sem_resposta += 1
                continue
            if p.perfil_pulou:
                pularam += 1
            for n, perfil in enumerate(p.perfis or []):
                if perfil in por_perfil:
                    por_perfil[perfil]["marcado"] += 1
                    if n == 0:
                        por_perfil[perfil]["principal"] += 1
            if p.perfil_outro:
                outros.append(p.perfil_outro)
    finally:
        definir_prestador_atual(db, prestador_de_volta)
    buscas = [t for (t,) in db.query(PerfilBusca.texto).order_by(PerfilBusca.criado_em.desc()).limit(2000).all()]
    return {
        "perfis": list(por_perfil.values()), "pularam": pularam, "sem_resposta": sem_resposta,
        "nao_me_encontrei": _agrupar(outros), "buscas_sem_resultado": _agrupar(buscas),
    }
