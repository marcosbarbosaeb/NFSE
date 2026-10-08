"""Pasta do mês — rotas (08/10/2026). Regras em app/services/pasta.py.

As mesmas rotas existem em dois endereços:
- `/api/pasta/...` — a empresa aberta na sessão (o dono, ou o contador que
  "entrou" na empresa);
- `/api/contador/atendimentos/{acesso_id}/pasta/...` — o contador pelo painel
  dele, sem entrar na empresa (como o pacote do mês em app/contador.py).

O lado de quem está falando (`empresa` ou `contador`) é decidido aqui, nunca
vem do navegador.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import definir_prestador_atual, get_db
from app.deps import db_sessao, prestador_atual_id, usuario_logado
from app.models import AcessoContador, Prestador, Usuario
from app.services import acesso, pasta

rotas = APIRouter()


@dataclass
class Contexto:
    db: Session
    prestador_id: uuid.UUID
    usuario: Usuario
    papel: str  # empresa | contador


def _da_empresa_aberta(
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id), usuario: Usuario = Depends(usuario_logado),
) -> Contexto:
    papel, _ = acesso.papel(db, usuario, prestador_id)
    return Contexto(db, prestador_id, usuario, "contador" if papel == "contador" else "empresa")


def _do_painel_do_contador(acesso_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado)) -> Contexto:
    meu = db.get(AcessoContador, acesso_id)
    if meu is None or meu.usuario_id != usuario.id or meu.status != "ativo":
        raise HTTPException(status_code=404, detail="Você não atende esta empresa.")
    definir_prestador_atual(db, meu.prestador_id)
    return Contexto(db, meu.prestador_id, usuario, "contador")


def _erro(exc: pasta.PastaError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


class PedidoRequest(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = Field(default=None, max_length=400)
    tipo: str = "arquivo"


class EditarPedidoRequest(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    descricao: str | None = Field(default=None, max_length=400)


class MarcarRequest(BaseModel):
    pedido_id: uuid.UUID
    competencia: str = Field(min_length=7, max_length=7)
    situacao: str | None = None


class MensagemRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=pasta.LIMITE_TEXTO)
    competencia: str | None = Field(default=None, max_length=7)


def _registrar(prefixo: str, contexto) -> None:
    @rotas.get(prefixo)
    def ver(competencia: str | None = None, ctx: Contexto = Depends(contexto)):
        """A pasta do mês (padrão: o mês passado), a conversa e o que é novo."""
        try:
            comp = pasta.validar_competencia(competencia)
        except pasta.PastaError as exc:
            raise _erro(exc)
        empresa = ctx.db.get(Prestador, ctx.prestador_id)
        resposta = {
            "papel": ctx.papel,
            "empresa": (empresa.nome_fantasia or empresa.razao_social) if empresa else "",
            "mes": pasta.do_mes(ctx.db, ctx.prestador_id, comp),
            "mensagens": pasta.mensagens(ctx.db),
            "novidades": pasta.novidades(ctx.db, ctx.prestador_id, ctx.usuario.id, ctx.papel),
            "tem_contador": ctx.papel == "contador" or pasta.tem_contador(ctx.db, ctx.prestador_id),
            "sugestoes": pasta.SUGESTOES,
        }
        return resposta

    @rotas.get(f"{prefixo}/novidades")
    def so_novidades(ctx: Contexto = Depends(contexto)):
        """Leve, pro selo do menu: o que o outro lado mandou desde a última visita."""
        return {
            **pasta.novidades(ctx.db, ctx.prestador_id, ctx.usuario.id, ctx.papel),
            "tem_contador": ctx.papel == "contador" or pasta.tem_contador(ctx.db, ctx.prestador_id),
        }

    @rotas.post(f"{prefixo}/lido")
    def lido(ctx: Contexto = Depends(contexto)):
        pasta.marcar_lido(ctx.db, ctx.prestador_id, ctx.usuario.id)
        ctx.db.commit()
        return {"ok": True}

    @rotas.post(f"{prefixo}/pedidos")
    def novo_pedido(req: PedidoRequest, ctx: Contexto = Depends(contexto)):
        try:
            p = pasta.criar_pedido(ctx.db, ctx.prestador_id, ctx.usuario, titulo=req.titulo, descricao=req.descricao, tipo=req.tipo)
        except pasta.PastaError as exc:
            raise _erro(exc)
        resposta = {"id": p.id}
        ctx.db.commit()
        return resposta

    @rotas.post(f"{prefixo}/pedidos/sugestoes")
    def sugestoes(ctx: Contexto = Depends(contexto)):
        lista = pasta.usar_sugestoes(ctx.db, ctx.prestador_id, ctx.usuario)
        resposta = {"pedidos": len(lista)}
        ctx.db.commit()
        return resposta

    @rotas.patch(f"{prefixo}/pedidos/{{pedido_id}}")
    def editar_pedido(pedido_id: uuid.UUID, req: EditarPedidoRequest, ctx: Contexto = Depends(contexto)):
        try:
            pasta.editar_pedido(ctx.db, pedido_id, titulo=req.titulo, descricao=req.descricao)
        except pasta.PastaError as exc:
            raise _erro(exc)
        ctx.db.commit()
        return {"ok": True}

    @rotas.delete(f"{prefixo}/pedidos/{{pedido_id}}")
    def tirar_pedido(pedido_id: uuid.UUID, ctx: Contexto = Depends(contexto)):
        try:
            pasta.tirar_pedido(ctx.db, pedido_id)
        except pasta.PastaError as exc:
            raise _erro(exc)
        ctx.db.commit()
        return {"ok": True}

    @rotas.post(f"{prefixo}/marcar")
    def marcar(req: MarcarRequest, ctx: Contexto = Depends(contexto)):
        try:
            comp = pasta.validar_competencia(req.competencia)
            # "não teve neste mês" é da empresa; "conferido" é do contador
            if req.situacao == "conferido" and ctx.papel != "contador":
                raise pasta.PastaError("Só o contador marca como conferido.", 403)
            pasta.marcar(ctx.db, ctx.prestador_id, ctx.usuario, req.pedido_id, comp, req.situacao)
        except pasta.PastaError as exc:
            raise _erro(exc)
        ctx.db.commit()
        return {"ok": True}

    @rotas.post(f"{prefixo}/arquivos")
    async def enviar(
        request: Request,
        competencia: str = Form(...),
        pedido_id: str | None = Form(default=None),
        arquivo: UploadFile = File(...),
        ctx: Contexto = Depends(contexto),
    ):
        # lê no máximo o limite + 1 byte: arquivo maior é recusado sem ir todo pra memória
        conteudo = await arquivo.read(pasta.LIMITE_ARQUIVO + 1)
        try:
            comp = pasta.validar_competencia(competencia)
            pid = uuid.UUID(pedido_id) if pedido_id else None
            a = pasta.enviar_arquivo(
                ctx.db, ctx.prestador_id, ctx.usuario, ctx.papel, competencia=comp, pedido_id=pid,
                nome=arquivo.filename or "arquivo", tipo_mime=arquivo.content_type, conteudo=conteudo,
            )
        except ValueError:
            raise HTTPException(status_code=422, detail="Item da lista inválido.")
        except pasta.PastaError as exc:
            raise _erro(exc)
        resposta = {"id": a.id, "nome": a.nome, "tamanho": a.tamanho}
        ctx.db.commit()
        return resposta

    @rotas.get(f"{prefixo}/arquivos/{{arquivo_id}}")
    def baixar(arquivo_id: uuid.UUID, ctx: Contexto = Depends(contexto)):
        try:
            a = pasta.arquivo(ctx.db, arquivo_id)
        except pasta.PastaError as exc:
            raise _erro(exc)
        conteudo, nome, tipo = a.conteudo, a.nome, a.tipo_mime
        return Response(
            content=conteudo, media_type=tipo or "application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome)}", "X-Content-Type-Options": "nosniff"},
        )

    @rotas.delete(f"{prefixo}/arquivos/{{arquivo_id}}")
    def apagar(arquivo_id: uuid.UUID, ctx: Contexto = Depends(contexto)):
        try:
            pasta.apagar_arquivo(ctx.db, arquivo_id)
        except pasta.PastaError as exc:
            raise _erro(exc)
        ctx.db.commit()
        return {"ok": True}

    @rotas.post(f"{prefixo}/mensagens")
    def escrever(req: MensagemRequest, ctx: Contexto = Depends(contexto)):
        try:
            comp = pasta.validar_competencia(req.competencia) if req.competencia else None
            m = pasta.escrever(ctx.db, ctx.prestador_id, ctx.usuario, ctx.papel, req.texto, comp)
        except pasta.PastaError as exc:
            raise _erro(exc)
        resposta = {"id": m.id}
        ctx.db.commit()
        return resposta


_registrar("/api/pasta", _da_empresa_aberta)
_registrar("/api/contador/atendimentos/{acesso_id}/pasta", _do_painel_do_contador)
