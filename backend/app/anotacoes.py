"""Anotações: abas/notas livres que a pessoa cria (05/10/2026).

Nasceram no Financeiro, mas são da EMPRESA, não de um módulo: quem tem só o
emissor também anota na Visão geral. Por isso as rotas ficam aqui, fora de
app/financeiro, sem `exige_modulo` — dependem só do cadastro geral
(app/deps.py). O endereço continua /api/financeiro/anotacoes (o que a tela
já usava).

Cada anotação diz em que telas aparece (`telas`): "financeiro",
"visao_geral" ou as duas.
"""
import re
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import db_sessao, prestador_atual_id
from app.models import Anotacao

rotas = APIRouter()

# Cada anotação tem um formato: "texto" (livre, na coluna `texto`), "lista"
# (itens com tique) ou "tabela" (controle com colunas e total). O conteúdo
# da lista e da tabela fica em `dados` (JSONB), sempre conferido aqui.
_ANOTACAO_FORMATOS = ("texto", "lista", "tabela")
_ANOTACAO_TIPOS_COLUNA = ("texto", "valor", "data")
_ANOTACAO_MAX_ITENS = 200
_ANOTACAO_MAX_COLUNAS = 8
_ANOTACAO_MAX_LINHAS = 300
_ANOTACAO_MAX_TEXTO_ITEM = 500
_ANOTACAO_MAX_NOME_COLUNA = 40
_ANOTACAO_MAX_VALOR = Decimal("99999999999.99")
_ANOTACAO_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
# Telas em que uma anotação pode aparecer (na ordem em que são guardadas).
_ANOTACAO_TELAS = ("financeiro", "visao_geral")


class _AnotacaoRequest(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=80)
    texto: str | None = Field(default=None, max_length=20000)
    formato: str | None = Field(default=None, max_length=20)
    dados: dict | None = None
    # Onde a nota aparece: ["financeiro"], ["visao_geral"] ou as duas.
    telas: list[str] | None = Field(default=None, max_length=4)


def _anotacao_invalida(mensagem: str = "Não deu pra entender o conteúdo da anotação.") -> HTTPException:
    return HTTPException(status_code=422, detail=mensagem)


def _anotacao_celula(tipo: str, valor):
    """Uma célula da tabela, já no jeito de guardar: texto → str; valor →
    número (ou None se vazio); data → "AAAA-MM-DD" (ou "" se vazia)."""
    if isinstance(valor, bool) or isinstance(valor, (list, dict)):
        raise _anotacao_invalida()
    if tipo == "texto":
        return "" if valor is None else str(valor)[:_ANOTACAO_MAX_TEXTO_ITEM]
    if tipo == "valor":
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        try:
            numero = Decimal(str(valor).strip())
        except ArithmeticError:
            raise _anotacao_invalida("Tem um valor em dinheiro que não deu pra entender.") from None
        if not numero.is_finite() or abs(numero) > _ANOTACAO_MAX_VALOR:
            raise _anotacao_invalida("Tem um valor em dinheiro grande demais.")
        return float(round(numero, 2))
    # data
    if valor is None or valor == "":
        return ""
    if not isinstance(valor, str) or not _ANOTACAO_DATA.fullmatch(valor):
        raise _anotacao_invalida("Tem uma data que não deu pra entender.")
    try:
        date.fromisoformat(valor)
    except ValueError:
        raise _anotacao_invalida("Tem uma data que não existe.") from None
    return valor


def _anotacao_dados(formato: str, dados: dict | None) -> dict | None:
    """Confere e arruma o conteúdo de uma lista ou tabela (limites de
    tamanho, tipos). Formato "texto" não tem `dados`."""
    if formato == "texto":
        return None
    dados = dados or {}
    if formato == "lista":
        itens = dados.get("itens", [])
        if not isinstance(itens, list):
            raise _anotacao_invalida()
        if len(itens) > _ANOTACAO_MAX_ITENS:
            raise _anotacao_invalida(f"A lista pode ter até {_ANOTACAO_MAX_ITENS} itens. Apague algum pra colocar outro.")
        saida = []
        for item in itens:
            if not isinstance(item, dict) or not isinstance(item.get("texto", ""), str):
                raise _anotacao_invalida()
            saida.append({"texto": item.get("texto", "")[:_ANOTACAO_MAX_TEXTO_ITEM], "feito": item.get("feito") is True})
        return {"itens": saida}

    colunas = dados.get("colunas")
    if colunas is None:
        colunas = [{"nome": "Anotação", "tipo": "texto"}]
    linhas = dados.get("linhas", [])
    if not isinstance(colunas, list) or not isinstance(linhas, list):
        raise _anotacao_invalida()
    if not colunas:
        raise _anotacao_invalida("A tabela precisa de pelo menos uma coluna.")
    if len(colunas) > _ANOTACAO_MAX_COLUNAS:
        raise _anotacao_invalida(f"A tabela pode ter até {_ANOTACAO_MAX_COLUNAS} colunas.")
    if len(linhas) > _ANOTACAO_MAX_LINHAS:
        raise _anotacao_invalida(f"A tabela pode ter até {_ANOTACAO_MAX_LINHAS} linhas. Apague alguma pra colocar outra.")
    colunas_ok = []
    for coluna in colunas:
        if not isinstance(coluna, dict) or not isinstance(coluna.get("nome", ""), str):
            raise _anotacao_invalida()
        if coluna.get("tipo") not in _ANOTACAO_TIPOS_COLUNA:
            raise _anotacao_invalida("Tipo de coluna desconhecido. Use texto, valor ou data.")
        colunas_ok.append({"nome": coluna.get("nome", "").strip()[:_ANOTACAO_MAX_NOME_COLUNA], "tipo": coluna["tipo"]})
    linhas_ok = []
    for linha in linhas:
        if not isinstance(linha, list):
            raise _anotacao_invalida()
        # Linha mais curta que o cabeçalho ganha células vazias; sobra é cortada.
        linhas_ok.append([
            _anotacao_celula(coluna["tipo"], linha[i] if i < len(linha) else None)
            for i, coluna in enumerate(colunas_ok)
        ])
    return {"colunas": colunas_ok, "linhas": linhas_ok}


def _anotacao_formato(formato: str | None) -> str | None:
    if formato is not None and formato not in _ANOTACAO_FORMATOS:
        raise _anotacao_invalida("Formato de anotação desconhecido. Use texto, lista ou tabela.")
    return formato


def _anotacao_telas(telas: list[str] | None) -> list[str] | None:
    """Confere a lista de telas (sem repetir, na ordem de sempre). Uma nota
    sempre aparece em pelo menos uma tela — senão ela some sem ser apagada."""
    if telas is None:
        return None
    if any(t not in _ANOTACAO_TELAS for t in telas):
        raise _anotacao_invalida("Tela desconhecida. A anotação pode ficar no Financeiro, na Visão geral ou nas duas.")
    escolhidas = [t for t in _ANOTACAO_TELAS if t in telas]
    if not escolhidas:
        raise _anotacao_invalida("A anotação precisa aparecer em pelo menos uma tela. Pra tirar de vez, apague a anotação.")
    return escolhidas


def _anotacao_dict(a: Anotacao) -> dict:
    return {
        "id": str(a.id), "titulo": a.titulo, "texto": a.texto,
        "formato": a.formato or "texto", "dados": a.dados, "atualizado_em": a.atualizado_em,
        # Nota de antes das telas (ou coluna vazia): fica onde sempre esteve.
        "telas": [t for t in _ANOTACAO_TELAS if t in (a.telas or [])] or ["financeiro"],
    }


@rotas.get("/api/financeiro/anotacoes")
def api_listar_anotacoes(db: Session = Depends(db_sessao)):
    return [_anotacao_dict(a) for a in db.query(Anotacao).order_by(Anotacao.ordem, Anotacao.criado_em)]


@rotas.post("/api/financeiro/anotacoes")
def api_criar_anotacao(req: _AnotacaoRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    if db.query(Anotacao).count() >= 30:
        raise HTTPException(status_code=422, detail="Dá pra ter até 30 anotações. Apague alguma pra criar outra.")
    formato = _anotacao_formato(req.formato) or "texto"
    dados = _anotacao_dados(formato, req.dados)
    telas = _anotacao_telas(req.telas) or ["financeiro"]
    ordem = (db.query(func.max(Anotacao.ordem)).scalar() or 0) + 1
    nota = Anotacao(
        id=uuid.uuid4(), prestador_id=prestador_id, titulo=(req.titulo or "Nova anotação").strip()[:80],
        texto=req.texto or "", formato=formato, dados=dados, ordem=ordem, telas=telas,
    )
    db.add(nota)
    db.flush()
    resposta = _anotacao_dict(nota)
    db.commit()
    return resposta


@rotas.patch("/api/financeiro/anotacoes/{anotacao_id}")
def api_atualizar_anotacao(anotacao_id: uuid.UUID, req: _AnotacaoRequest, db: Session = Depends(db_sessao)):
    nota = db.get(Anotacao, anotacao_id)
    if nota is None:
        raise HTTPException(status_code=404, detail="Anotação não encontrada.")
    if req.titulo is not None:
        nota.titulo = req.titulo.strip()[:80] or nota.titulo
    if req.texto is not None:
        nota.texto = req.texto
    telas = _anotacao_telas(req.telas)
    if telas is not None:
        nota.telas = telas
    formato_novo = _anotacao_formato(req.formato)
    if formato_novo is not None or req.dados is not None:
        formato = formato_novo or nota.formato or "texto"
        # Sem `dados` no pedido: mantém o que já tinha se o formato é o mesmo;
        # se mudou, começa vazio (a tela manda o conteúdo já convertido).
        bruto = req.dados if req.dados is not None else (nota.dados if formato == nota.formato else None)
        nota.dados = _anotacao_dados(formato, bruto)
        nota.formato = formato
    db.flush()
    resposta = _anotacao_dict(nota)
    db.commit()
    return resposta


@rotas.delete("/api/financeiro/anotacoes/{anotacao_id}")
def api_apagar_anotacao(anotacao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    nota = db.get(Anotacao, anotacao_id)
    if nota is None:
        raise HTTPException(status_code=404, detail="Anotação não encontrada.")
    db.delete(nota)
    db.commit()
    return {"ok": True}
