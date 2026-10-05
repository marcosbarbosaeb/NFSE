"""Ajuda / FAQ dentro do sistema (05/10/2026).

As perguntas e respostas moram no frontend (src/lib/faq.ts) e o guia
completo é um arquivo estático (/guia-agente-ana.md). Aqui só sai o endereço
da "IA grátis" (NotebookLM, por exemplo) carregada com esse guia — vem da
variável AJUDA_IA_URL; vazia = a tela não mostra o botão.

É da empresa, não de um módulo: vale pra qualquer combinação de produtos,
por isso fica fora de app/financeiro e sem `exige_modulo`.
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.deps import prestador_atual_id

rotas = APIRouter()


class AjudaResponse(BaseModel):
    ia_url: str | None = None


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
def api_ajuda(_prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    return {"ia_url": _link_seguro(get_settings().ajuda_ia_url)}
