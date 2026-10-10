"""Ajuda / FAQ dentro do sistema (05/10/2026; IA do Claude em 2026.10.7).

As perguntas e respostas moram no frontend (src/lib/faq.ts). O guia completo
(`app/data/guia-agente-ana.md`) não é público.

- Com a IA ligada (`IA_ATIVA` + `ANTHROPIC_API_KEY`, ver `app/services/ia.py`),
  a tela mostra o "Pergunte à Ana": `POST /api/ajuda/perguntar`.
- Com a IA desligada, continua o link externo de antes (`AJUDA_IA_URL`); vazio
  = a tela não mostra o botão.

É da empresa, não de um módulo: vale pra qualquer combinação de produtos,
por isso fica fora de app/financeiro e sem `exige_modulo`.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import db_sessao, prestador_atual_id, usuario_logado
from app.models import Usuario
from app.services import acesso, ia
from app.services.demo import eh_email_demo

rotas = APIRouter()


class AjudaResponse(BaseModel):
    ia_url: str | None = None
    ia_ativa: bool = False
    ia_restantes: int | None = None
    ia_limite: int | None = None


class PerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=1, max_length=ia.MAX_PERGUNTA)
    tela: str | None = Field(default=None, max_length=300)


class PerguntaResponse(BaseModel):
    situacao: str
    texto: str | None = None
    restantes: int | None = None


def _link_seguro(valor: str) -> str | None:
    """Só aceita endereço https:// (o link abre em nova aba pro cliente):
    qualquer outra coisa — http, javascript:, texto solto — vira "sem link"."""
    link = (valor or "").strip()
    if not link.lower().startswith("https://") or len(link) <= len("https://"):
        return None
    if any(c.isspace() for c in link):
        return None
    return link


@rotas.get("/api/ajuda", response_model=AjudaResponse)
def api_ajuda(
    _prestador_id: uuid.UUID = Depends(prestador_atual_id),
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(db_sessao),
):
    # Simulação (pública) não gasta IA: fica como sem IA.
    if ia.ligada() and not eh_email_demo(usuario.email):
        return {"ia_url": None, "ia_ativa": True, "ia_restantes": ia.restantes(db, usuario.id), "ia_limite": ia.limite_diario()}
    return {"ia_url": _link_seguro(get_settings().ajuda_ia_url), "ia_ativa": False}


@rotas.post("/api/ajuda/perguntar", response_model=PerguntaResponse)
def api_ajuda_perguntar(
    req: PerguntaRequest,
    request: Request,
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(db_sessao),
):
    """Sempre 200: a tela decide o que mostrar pela `situacao` (ok, nao_sei,
    contador, limite, desligada, falha). A IA nunca derruba a Ajuda."""
    if eh_email_demo(usuario.email):
        return {"situacao": "desligada"}
    perfil, _ = acesso.papel(db, usuario, prestador_id)
    r = ia.perguntar(db, usuario_id=usuario.id, prestador_id=prestador_id, pergunta=req.pergunta, tela=req.tela, perfil=perfil)
    return {"situacao": r.situacao, "texto": r.texto, "restantes": r.restantes}
