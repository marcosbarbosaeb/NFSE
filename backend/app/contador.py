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
    link_cadastro = f"{base}/cadastro?tipo=contador"
    pode = ["Ver as notas e o financeiro"] + [acesso.PERMISSOES[p][0] for p in permissoes]
    de = quem.nome or quem.email
    texto = (
        f"{de} convidou você para cuidar da empresa {empresa} na Agente Ana.\n\n"
        "O que você vai poder fazer:\n" + "\n".join(f"- {p}" for p in pode) + "\n\n"
        f"Se você já tem conta com este e-mail, entre e aceite o convite: {base}/app/atendimentos\n"
        f"Se ainda não tem, crie a sua conta de contador (grátis, sem CNPJ), com este mesmo e-mail: {link_cadastro}\n"
    )
    from app.services import email_modelo as m

    corpo = m.moldura(
        titulo=f"Convite pra cuidar de {empresa}",
        previa=f"{de} convidou você na Agente Ana.",
        menu=m.MENU_CONTADOR,
        motivo=f"Você recebeu este e-mail porque {de} informou o seu endereço como contador(a) da empresa na Agente Ana.",
        corpo_html=(
            m.paragrafo(f"<strong>{html.escape(de)}</strong> convidou você pra cuidar da empresa <strong>{html.escape(empresa)}</strong> na Agente Ana.")
            + m.paragrafo("O que você vai poder fazer lá:")
            + '<ul style="margin:0 0 14px;padding-left:20px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.7;color:#1e293b">'
            + "".join(f"<li>{html.escape(p)}</li>" for p in pode) + "</ul>"
            + m.botao("Ver o convite", f"{base}/app/atendimentos")
            + m.paragrafo(
                f'Ainda não tem conta? <a href="{link_cadastro}" style="color:#e11d74">Crie a sua conta de contador</a> — é grátis e não pede CNPJ. '
                "Use este mesmo e-mail: o convite aparece assim que você entrar.", suave=True)
        ),
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
    from app.services import parceiros

    return {
        "permissoes": _catalogo(), "ativa": ativa, **acesso.do_contador(db, usuario, ativa),
        # Bonificação do contador (parceria): aparece depois do primeiro cliente.
        "bonificacao": parceiros.resumo_do_contador(db, usuario.id),
    }


@rotas.get("/api/contador/atendimentos/{acesso_id}/pacote", responses={404: {"description": "Sem notas"}})
def api_pacote_do_cliente(
    acesso_id: uuid.UUID, competencia: str, request: Request,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_logado),
):
    """Fechamento do mês (07/10/2026): o .zip com os XMLs e PDFs das notas
    de um cliente numa competência, sem precisar entrar na empresa dele.
    Fica no histórico que o dono vê."""
    import re

    from fastapi.responses import Response

    from app.models import RegistroContador
    from app.services import pacote

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    meu = db.get(acesso.AcessoContador, acesso_id)
    if meu is None or meu.usuario_id != usuario.id or meu.status != "ativo":
        raise HTTPException(status_code=404, detail="Você não atende esta empresa.")
    voltar = contas.empresa_ativa(db, request, usuario)
    try:
        definir_prestador_atual(db, meu.prestador_id)
        empresa = db.get(Prestador, meu.prestador_id)
        emissoes = pacote.selecionar(db, competencia=competencia, so_autorizadas=True)
        conteudo, quantas = pacote.montar_zip(db, emissoes, "ambos")
        if not quantas:
            raise HTTPException(status_code=404, detail="Esta empresa não tem nota autorizada nesse mês.")
        cnpj = "".join(c for c in empresa.cpf_cnpj if c.isalnum())
        mes = f"{competencia[5:]}/{competencia[:4]}"
        db.add(RegistroContador(
            id=uuid.uuid4(), prestador_id=meu.prestador_id, usuario_id=usuario.id, email=usuario.email,
            acao=f"Baixou as notas de {mes} ({quantas})",
        ))
        db.flush()
    finally:
        definir_prestador_atual(db, voltar)
    db.commit()
    return Response(
        content=conteudo, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="notas-{cnpj}-{competencia}.zip"'},
    )


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
