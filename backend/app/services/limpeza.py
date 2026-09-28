"""
"Limpar dados" em Configurações — pedido do Marcos (28/09/2026): limpar
tomadores, notas, calendário, recebimentos e despesas, cada um por conta.

Tudo roda com a RLS da sessão (só apaga dado do prestador logado) e ainda
filtra por prestador_id explicitamente onde a tabela tem a coluna — defesa
em profundidade, igual ao resto dos services.

Uma exceção de propósito, pra não criar problema fiscal: nota que JÁ FOI
ENVIADA à Receita (submetida, confirmada, cancelada ou substituída) é um
documento fiscal de verdade — não some daqui. Apagar ela também faria o
sequencial de nDPS voltar pra trás e a próxima nota sair com um número já
usado (a Sefin rejeita). "Limpar notas" apaga só o que nunca saiu do
sistema (rascunho, montada, assinada, com erro). Pelo mesmo motivo, um
tomador que ainda tem nota fica arquivado em vez de apagado (ver
excluir_vinculo em app/services/vinculos.py).
"""
import uuid

from sqlalchemy.orm import Session

from app.models import AjusteEvento, Despesa, Emissao, Envio, EventoManual, PagamentoRecebido, PrestadorTomador
from app.services.vinculos import excluir_vinculo

CATEGORIAS = ("nfse", "recebimentos", "despesas", "calendario", "tomadores")
ESTADOS_APAGAVEIS = ("rascunho", "montado", "assinado", "erro")


def limpar_dados(db: Session, prestador_id: uuid.UUID, categorias: list[str]) -> dict[str, int]:
    """Não dá commit. Ordem fixa (notas antes de tomadores) pra que "limpar
    tudo" apague os tomadores de verdade em vez de só arquivá-los."""
    invalidas = set(categorias) - set(CATEGORIAS)
    if invalidas:
        raise ValueError(f"Categoria desconhecida: {', '.join(sorted(invalidas))}")
    resultado: dict[str, int] = {}

    if "nfse" in categorias:
        ids = [
            e.id
            for e in db.query(Emissao.id).filter(
                Emissao.prestador_id == prestador_id, Emissao.estado.in_(ESTADOS_APAGAVEIS)
            )
        ]
        if ids:
            db.query(Envio).filter(Envio.emissao_id.in_(ids)).delete(synchronize_session=False)
            db.query(AjusteEvento).filter(
                AjusteEvento.tipo == "recebimento_previsto", AjusteEvento.chave.in_([str(i) for i in ids])
            ).delete(synchronize_session=False)
            db.query(Emissao).filter(Emissao.id.in_(ids)).delete(synchronize_session=False)
        resultado["nfse"] = len(ids)
        resultado["nfse_mantidas"] = (
            db.query(Emissao.id).filter(Emissao.prestador_id == prestador_id).count()
        )

    if "recebimentos" in categorias:
        resultado["recebimentos"] = (
            db.query(PagamentoRecebido)
            .filter(PagamentoRecebido.prestador_id == prestador_id)
            .delete(synchronize_session=False)
        )

    if "despesas" in categorias:
        resultado["despesas"] = (
            db.query(Despesa).filter(Despesa.prestador_id == prestador_id).delete(synchronize_session=False)
        )

    if "calendario" in categorias:
        manuais = db.query(EventoManual).filter(EventoManual.prestador_id == prestador_id).delete(synchronize_session=False)
        ajustes = db.query(AjusteEvento).filter(AjusteEvento.prestador_id == prestador_id).delete(synchronize_session=False)
        resultado["calendario"] = manuais + ajustes

    if "tomadores" in categorias:
        apagados = arquivados = 0
        vinculos = (
            db.query(PrestadorTomador)
            .filter(PrestadorTomador.prestador_id == prestador_id, PrestadorTomador.excluido_em.is_(None))
            .all()
        )
        for vinculo in vinculos:
            if excluir_vinculo(db, vinculo) == "apagado":
                apagados += 1
            else:
                arquivados += 1
        resultado["tomadores"] = apagados + arquivados
        resultado["tomadores_arquivados"] = arquivados

    db.flush()
    db.expire_all()
    return resultado
