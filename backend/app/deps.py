"""Dependências comuns das rotas — o "cadastro geral" (05/10/2026).

Quem está logado, de qual empresa (prestador) e a sessão do banco com a RLS
da empresa definida. Ficam aqui, fora de app/main.py, pra que cada módulo
(emissor, financeiro) tenha as suas rotas em arquivo próprio sem depender
um do outro: os dois dependem só daqui.

`exige_modulo`: os produtos são vendidos separadamente — a empresa só usa
as rotas dos módulos que tem ligados (`prestador.modulos`).
"""
import uuid

from fastapi import Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import definir_prestador_atual, get_db
from app.models import Prestador, Usuario
from app.services import acesso, contas
from app.services.demo import eh_email_demo

MODULOS = ("emissor", "financeiro")
NOMES_MODULOS = {"emissor": "Notas", "financeiro": "Financeiro"}


def prestador_atual_id(request: Request, db: Session = Depends(get_db)) -> uuid.UUID:
    """Marco 10 — resolve o prestador a partir da SESSÃO autenticada (não
    mais config fixa). `usuario` não tem RLS (ver docstring do modelo em
    app/models.py), por isso usa `get_db` puro aqui e não `db_sessao` —
    seria circular, já que `db_sessao` depende desta função. NUNCA aceita
    prestador_id vindo do cliente: é sempre resolvido no servidor, a partir
    de quem está logado — é essa garantia que mantém a disciplina de RLS
    válida com múltiplos usuários."""
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado — faça login.")
    usuario = db.query(Usuario).filter_by(id=uuid.UUID(usuario_id), ativo=True, email_confirmado=True).one_or_none()
    if usuario is None or not contas.validar_sessao(db, request, usuario):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão inválida — faça login novamente.")
    # Vários CNPJs no mesmo login (29/09/2026): a empresa ativa vem da
    # sessão, sempre conferida contra as empresas a que o usuário tem acesso.
    ativa = contas.empresa_ativa(db, request, usuario)
    # Contador só faz o que o dono marcou; empresa sem assinatura fica só
    # pra consulta (06/10/2026, ver app/services/acesso.py).
    acesso.conferir(db, request, usuario, ativa)
    return ativa


def usuario_logado(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Quem está logado, sem depender de empresa (rotas da conta e do
    contador, que valem pra qualquer empresa ativa)."""
    usuario_id = request.session.get("usuario_id")
    usuario = db.get(Usuario, uuid.UUID(usuario_id)) if usuario_id else None
    if usuario is None or not usuario.ativo or not contas.validar_sessao(db, request, usuario):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Não autenticado — faça login.")
    return usuario


def db_sessao(db: Session = Depends(get_db), prestador_id: uuid.UUID = Depends(prestador_atual_id)) -> Session:
    """RLS continua valendo de verdade aqui — sem isso, toda query nas
    tabelas protegidas devolve vazio (falha fechada, ver migração de RLS)."""
    definir_prestador_atual(db, prestador_id)
    return db


def modulos_da_empresa(db: Session, prestador_id: uuid.UUID) -> list[str]:
    modulos = db.query(Prestador.modulos).filter(Prestador.id == prestador_id).scalar()
    return [m for m in (modulos or []) if m in MODULOS] or ["emissor"]


def exige_modulo(nome: str):
    """Dependência de rota: 403 se a empresa não tem o módulo ligado."""

    def _conferir(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)) -> None:
        if nome not in modulos_da_empresa(db, prestador_id):
            raise HTTPException(
                status_code=403,
                detail=f"O módulo {NOMES_MODULOS.get(nome, nome)} não está ativo nesta empresa. Ative em Empresa › Mais opções.",
            )

    return _conferir


def ler_upload(arquivo: UploadFile, limite_mb: int) -> bytes:
    """Lê o arquivo enviado com teto de tamanho (antes lia tudo pra memória
    antes de conferir). As rotas de upload são `def` (não `async def`):
    ler/parsear PDF e CSV é trabalho bloqueante e roda no threadpool, sem
    travar os outros pedidos."""
    limite = limite_mb * 1024 * 1024
    dados = arquivo.file.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(status_code=413, detail=f"Arquivo grande demais (máximo {limite_mb} MB).")
    return dados


MENSAGEM_DEMO = (
    "Isso não está disponível no modo simulação — aqui nada é enviado à Receita nem a ninguém. "
    "Crie sua conta grátis para usar de verdade."
)


def exigir_conta_real(request: Request, db: Session = Depends(get_db)) -> None:
    """Ambiente de simulação (ver app/services/demo.py): recusa as rotas que
    falam com o mundo de fora — Receita, e-mail, cobrança, certificado,
    senha. Usa `usuario` (sem RLS) pra não depender da ordem das outras
    dependências."""
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        return  # a própria rota devolve o 401 de sempre
    usuario = db.get(Usuario, uuid.UUID(usuario_id))
    if usuario is not None and eh_email_demo(usuario.email):
        raise HTTPException(status_code=403, detail=MENSAGEM_DEMO)
