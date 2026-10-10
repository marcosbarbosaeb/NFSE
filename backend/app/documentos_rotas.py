"""Documentos da empresa — rotas (2026.10.7). Regras em
app/services/documentos_empresa.py.

Só na empresa aberta na sessão: o dono, ou o contador que entrou na empresa
E tem a permissão "documentos" — sem ela, nem ver (a exceção ao "ver é
sempre livre"). Apagar e ver o registro de acessos: só o dono. A Gestão não
tem rota pra cá.
"""
from __future__ import annotations

import datetime
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import db_sessao, exigir_conta_real, ler_upload, prestador_atual_id, usuario_logado
from app.models import Usuario
from app.services import acesso
from app.services import documentos_empresa as docs

rotas = APIRouter()


class Ctx:
    def __init__(self, db: Session, prestador_id: uuid.UUID, usuario: Usuario, papel: str, permissoes: list[str]):
        self.db, self.prestador_id, self.usuario, self.papel, self.permissoes = db, prestador_id, usuario, papel, permissoes

    @property
    def lado(self) -> str:
        return "empresa" if self.papel == "dono" else "contador"


def _ctx(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id), usuario: Usuario = Depends(usuario_logado)) -> Ctx:
    # Conferido de novo aqui (não só no login da empresa): quem não é dono nem
    # contador desta empresa — inclusive gestor — nunca abre estes documentos.
    if acesso.eh_dono(db, usuario, prestador_id):
        papel, permissoes = "dono", list(acesso.PERMISSOES)
    else:
        a = acesso.acesso_de_contador(db, usuario.id, prestador_id)
        papel, permissoes = ("contador", list(a.permissoes or [])) if a is not None else ("ninguem", [])
    if not docs.pode_ver(papel, permissoes):
        raise HTTPException(status_code=403, detail="Os documentos da empresa só aparecem pra quem o dono liberou (permissão “Documentos da empresa”).")
    return Ctx(db, prestador_id, usuario, papel, permissoes)


def _so_dono(ctx: Ctx = Depends(_ctx)) -> Ctx:
    if ctx.papel != "dono":
        raise HTTPException(status_code=403, detail="Só quem é dono da empresa pode fazer isso.")
    return ctx


def _erro(exc: docs.DocumentoError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


def _data(texto: str | None) -> datetime.date | None:
    if not texto:
        return None
    try:
        return datetime.date.fromisoformat(texto[:10])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Data de validade inválida.") from exc


@rotas.get("/api/documentos")
def listar(ctx: Ctx = Depends(_ctx)):
    return {
        "papel": ctx.lado,
        "pode_apagar": ctx.papel == "dono",
        "documentos": docs.listar(ctx.db, ctx.prestador_id),
        "uso": {"bytes": docs.uso(ctx.db, ctx.prestador_id), "limite_mb": docs.LIMITE_EMPRESA_MB, "limite_arquivo_mb": docs.LIMITE_ARQUIVO_MB},
        "tipos": [{"id": k, "rotulo": v} for k, v in docs.TIPOS.items()],
        "contadores_sem_permissao": docs.contadores_sem_permissao(ctx.db, ctx.prestador_id) if ctx.papel == "dono" else [],
    }


@rotas.post("/api/documentos", dependencies=[Depends(exigir_conta_real)])
def enviar(
    tipo: str = Form(...), nome: str | None = Form(None), validade: str | None = Form(None),
    arquivo: UploadFile = File(...), ctx: Ctx = Depends(_ctx),
):
    dados = ler_upload(arquivo, docs.LIMITE_ARQUIVO_MB)
    try:
        doc = docs.enviar(ctx.db, ctx.prestador_id, ctx.usuario, ctx.lado, tipo=tipo, nome=nome, nome_arquivo=arquivo.filename or "",
                          tipo_mime=arquivo.content_type, dados=dados, validade=_data(validade))
    except docs.DocumentoError as exc:
        raise _erro(exc)
    resposta = {"id": str(doc.id)}
    ctx.db.commit()
    return resposta


@rotas.post("/api/documentos/{documento_id}/substituir", dependencies=[Depends(exigir_conta_real)])
def substituir(
    documento_id: uuid.UUID, validade: str | None = Form(None), manter_validade: bool = Form(True),
    arquivo: UploadFile = File(...), ctx: Ctx = Depends(_ctx),
):
    dados = ler_upload(arquivo, docs.LIMITE_ARQUIVO_MB)
    try:
        docs.substituir(ctx.db, documento_id, ctx.usuario, ctx.lado, nome_arquivo=arquivo.filename or "", tipo_mime=arquivo.content_type,
                        dados=dados, validade=_data(validade), manter_validade=manter_validade)
    except docs.DocumentoError as exc:
        raise _erro(exc)
    ctx.db.commit()
    return {"ok": True}


class EditarDocumentoRequest(BaseModel):
    tipo: str | None = Field(default=None, max_length=30)
    nome: str | None = Field(default=None, max_length=200)
    validade: datetime.date | None = None
    sem_validade: bool = False


@rotas.patch("/api/documentos/{documento_id}")
def editar(documento_id: uuid.UUID, req: EditarDocumentoRequest, ctx: Ctx = Depends(_ctx)):
    try:
        docs.editar(ctx.db, documento_id, tipo=req.tipo, nome=req.nome, validade=req.validade, limpar_validade=req.sem_validade)
    except docs.DocumentoError as exc:
        raise _erro(exc)
    ctx.db.commit()
    return {"ok": True}


@rotas.delete("/api/documentos/{documento_id}")
def apagar(documento_id: uuid.UUID, ctx: Ctx = Depends(_so_dono)):
    try:
        docs.apagar(ctx.db, documento_id)
    except docs.DocumentoError as exc:
        raise _erro(exc)
    ctx.db.commit()
    return {"ok": True}


@rotas.get("/api/documentos/{documento_id}/arquivo")
def arquivo(documento_id: uuid.UUID, baixar: bool = False, ctx: Ctx = Depends(_ctx)):
    """Abre (no navegador) ou baixa. Fica no registro de acessos."""
    try:
        doc = docs.abrir(ctx.db, documento_id, ctx.usuario, ctx.lado, baixar)
    except docs.DocumentoError as exc:
        raise _erro(exc)
    conteudo, tipo, nome = doc.conteudo, doc.tipo_mime, doc.nome_arquivo
    ctx.db.commit()
    modo = "attachment" if baixar else "inline"
    return Response(content=conteudo, media_type=tipo, headers={
        "Content-Disposition": f"{modo}; filename*=UTF-8''{quote(nome)}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })


@rotas.get("/api/documentos/{documento_id}/acessos")
def acessos(documento_id: uuid.UUID, ctx: Ctx = Depends(_so_dono)):
    try:
        return {"acessos": docs.acessos(ctx.db, documento_id)}
    except docs.DocumentoError as exc:
        raise _erro(exc)
