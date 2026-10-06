"""Contador — rotas (06/10/2026). Regras em app/services/acesso.py.

Dois lados:
- a EMPRESA (Empresa › Contador): convida pelo e-mail, marca o que ele pode
  fazer, muda, tira e vê o que foi feito. Só o dono chega aqui (o próprio
  `acesso.conferir` recusa o contador em /api/contador/acessos e /historico).
- o CONTADOR (Empresas que atendo): convites pra aceitar e a lista das
  empresas dele. Não dependem da empresa ativa.
"""
import html
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.deps import db_sessao, exigir_conta_real, prestador_atual_id, usuario_logado
from app.services.email import EmailEnvioError, get_email_sender
from app.models import Prestador, Usuario
from app.services import acesso, contas

logger = logging.getLogger("agenteana.contador")

rotas = APIRouter()


class ConvidarRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    permissoes: list[str] = Field(default_factory=list, max_length=10)


class PermissoesRequest(BaseModel):
    permissoes: list[str] = Field(default_factory=list, max_length=10)


def _erro(exc: acesso.AcessoError, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


def _catalogo() -> list[dict]:
    return [{"id": chave, "nome": nome, "descricao": descricao} for chave, (nome, descricao) in acesso.PERMISSOES.items()]


def _avisar_contador(empresa: str, quem: Usuario, email: str, permissoes: list[str]) -> bool:
    """E-mail do convite. Falhar o envio não desfaz o convite: ele aparece
    pro contador assim que entrar com aquele e-mail."""
    s = get_settings()
    base = s.app_base_url.rstrip("/")
    pode = ["Ver as notas e o financeiro"] + [acesso.PERMISSOES[p][0] for p in permissoes]
    de = quem.nome or quem.email
    texto = (
        f"{de} convidou você para cuidar da empresa {empresa} na Agente Ana.\n\n"
        "O que você vai poder fazer:\n" + "\n".join(f"- {p}" for p in pode) + "\n\n"
        f"Se você já tem conta com este e-mail, entre e aceite o convite: {base}/app/atendimentos\n"
        f"Se ainda não tem, crie a sua (use este mesmo e-mail): {base}/cadastro\n"
    )
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:15px;color:#1e293b;line-height:1.5'>"
        f"<p><strong>{html.escape(de)}</strong> convidou você para cuidar da empresa "
        f"<strong>{html.escape(empresa)}</strong> na Agente Ana.</p>"
        "<p>O que você vai poder fazer:</p><ul>" + "".join(f"<li>{html.escape(p)}</li>" for p in pode) + "</ul>"
        f"<p><a href='{base}/app/atendimentos' style='background:#4f46e5;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none'>Ver o convite</a></p>"
        f"<p style='color:#64748b;font-size:13px'>Ainda não tem conta? <a href='{base}/cadastro'>Crie a sua</a> usando este mesmo e-mail — o convite aparece assim que você entrar.</p></div>"
    )
    try:
        get_email_sender().enviar(
            destinatario=email, assunto=f"{de} convidou você para cuidar de {empresa} na Agente Ana",
            corpo_texto=texto, corpo_html=corpo, responder_para=quem.email,
        )
        return True
    except EmailEnvioError:
        logger.exception("Falha ao enviar o convite de contador")
        return False


# --- lado da empresa ---------------------------------------------------------


@rotas.get("/api/contador/acessos")
def api_acessos(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    return {
        "permissoes": _catalogo(),
        "acessos": acesso.listar_da_empresa(db, prestador_id),
        "historico": acesso.historico(db, prestador_id, 30),
    }


@rotas.post("/api/contador/acessos", dependencies=[Depends(exigir_conta_real)])
def api_convidar(
    req: ConvidarRequest, db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id), quem: Usuario = Depends(usuario_logado),
):
    try:
        novo = acesso.convidar(db, prestador_id, quem, req.email, req.permissoes)
    except acesso.AcessoError as exc:
        raise _erro(exc, 409)
    definir_prestador_atual(db, prestador_id)
    empresa = db.get(Prestador, prestador_id).razao_social
    resposta = {"acesso": acesso._para_dono(db, novo)}
    email, permissoes = novo.email, list(novo.permissoes)
    db.commit()
    resposta["email_enviado"] = _avisar_contador(empresa, quem, email, permissoes)
    return resposta


@rotas.patch("/api/contador/acessos/{acesso_id}")
def api_mudar_permissoes(acesso_id: uuid.UUID, req: PermissoesRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    try:
        alterado = acesso.mudar_permissoes(db, prestador_id, acesso_id, req.permissoes)
    except acesso.AcessoError as exc:
        raise _erro(exc, 404)
    resposta = acesso._para_dono(db, alterado)
    db.commit()
    return resposta


@rotas.delete("/api/contador/acessos/{acesso_id}")
def api_tirar_acesso(acesso_id: uuid.UUID, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    try:
        acesso.remover(db, prestador_id, acesso_id)
    except acesso.AcessoError as exc:
        raise _erro(exc, 404)
    db.commit()
    return {"ok": True}


@rotas.get("/api/contador/historico")
def api_historico(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    return acesso.historico(db, prestador_id, 300)


# --- lado do contador --------------------------------------------------------


@rotas.get("/api/contador/atendimentos")
def api_atendimentos(request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado)):
    ativa = contas.empresa_ativa(db, request, usuario)
    return {"permissoes": _catalogo(), "ativa": ativa, **acesso.do_contador(db, usuario, ativa)}


@rotas.post("/api/contador/convites/{acesso_id}/aceitar")
def api_aceitar(acesso_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado)):
    try:
        aceito = acesso.aceitar(db, usuario, acesso_id)
    except acesso.AcessoError as exc:
        raise _erro(exc, 404)
    resposta = {"prestador_id": aceito.prestador_id}
    db.commit()
    return resposta


@rotas.post("/api/contador/convites/{acesso_id}/recusar")
def api_recusar(acesso_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado)):
    try:
        acesso.recusar(db, usuario, acesso_id)
    except acesso.AcessoError as exc:
        raise _erro(exc, 404)
    db.commit()
    return {"ok": True}


@rotas.delete("/api/contador/atendimentos/{acesso_id}")
def api_sair(acesso_id: uuid.UUID, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado)):
    """O contador deixa de atender a empresa. Se estava nela, volta pra dele."""
    try:
        prestador_id = acesso.sair(db, usuario, acesso_id)
    except acesso.AcessoError as exc:
        raise _erro(exc, 404)
    if request.session.get("prestador_id") == str(prestador_id):
        request.session["prestador_id"] = str(usuario.prestador_id)
    db.commit()
    return {"ok": True}
