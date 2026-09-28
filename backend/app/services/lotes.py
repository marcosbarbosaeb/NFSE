"""Ações em lote em segundo plano (29/09/2026) — "inclua o botão de enviar
todas na Shopee" e a seleção múltipla na lista de NFS-e (como no
MandaNotas): mandar todas as notas por e-mail, assinar várias de uma vez,
enviar várias à prefeitura.

Cada lote vira uma linha em `lote_acao` e roda numa thread do próprio
processo (o app roda num processo só no Railway), uma nota por vez, gravando
o progresso a cada nota — a tela acompanha por GET /api/lotes/{id}. Se o
servidor reiniciar no meio, o lote fica "interrompido" e dá pra retomar de
onde parou (a posição é feitos + falhas, a lista de notas é fixa).

E-mail: o Resend aceita poucas requisições por segundo, então há uma pausa
curta entre um envio e outro.
"""
import datetime
import logging
import threading
import time
import uuid

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, definir_prestador_atual
from app.fiscal.cliente_sefin import ClienteSefin
from app.models import Emissao, Envio, LoteAcao

logger = logging.getLogger("agenteana.lotes")

ACOES = ("email", "assinar", "submeter")
MAXIMO_POR_LOTE = 3000
PAUSA_EMAIL_S = 0.6
# Lote "executando" sem progresso há mais que isso e sem thread viva aqui =
# o servidor reiniciou no meio.
PARADO_APOS_S = 180

_rodando: set[uuid.UUID] = set()
_lock = threading.Lock()


class LoteInvalidoError(Exception):
    pass


def _elegivel(acao: str, e: Emissao, ja_enviada: bool) -> bool:
    if acao == "assinar":
        return e.estado == "montado"
    if acao == "submeter":
        return e.estado in ("assinado", "erro")
    # e-mail: nota autorizada (ou de teste) que ainda não foi enviada
    teste = (e.tomador_snapshot or {}).get("tpAmb") == "2"
    liberada = e.estado == "confirmado" or (teste and e.estado in ("montado", "assinado", "submetido"))
    return liberada and not ja_enviada


def selecionar(
    db: Session, acao: str, *, emissao_ids: list[uuid.UUID] | None = None,
    vinculo_id: uuid.UUID | None = None, competencia: str | None = None, reenviar: bool = False,
) -> list[uuid.UUID]:
    """Notas (do prestador ativo — RLS) em que a ação faz sentido, na ordem
    em que foram geradas. `reenviar=True` inclui e-mails já enviados."""
    if acao not in ACOES:
        raise LoteInvalidoError("Ação desconhecida.")
    query = db.query(Emissao).filter(Emissao.estado != "cancelada")
    if emissao_ids is not None:
        query = query.filter(Emissao.id.in_(emissao_ids))
    if vinculo_id is not None:
        query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    if competencia is not None:
        query = query.filter(Emissao.competencia == competencia)
    emissoes = query.order_by(Emissao.criado_em, Emissao.n_dps).limit(MAXIMO_POR_LOTE + 1).all()
    enviadas: set[uuid.UUID] = set()
    if acao == "email" and not reenviar and emissoes:
        enviadas = {
            i for (i,) in db.query(Envio.emissao_id).filter(
                Envio.emissao_id.in_([e.id for e in emissoes]), Envio.canal == "email", Envio.status == "enviado"
            )
        }
    return [e.id for e in emissoes if _elegivel(acao, e, e.id in enviadas)][:MAXIMO_POR_LOTE]


def criar_lote(db: Session, prestador_id: uuid.UUID, acao: str, ids: list[uuid.UUID]) -> LoteAcao:
    if not ids:
        raise LoteInvalidoError("Nenhuma nota selecionada está pronta pra essa ação.")
    ativo = (
        db.query(LoteAcao)
        .filter(LoteAcao.status.in_(("fila", "executando")))
        .order_by(LoteAcao.criado_em.desc())
        .first()
    )
    if ativo is not None and not _parado(ativo):
        raise LoteInvalidoError("Já tem uma ação em lote rodando — espere terminar ou cancele.")
    lote = LoteAcao(
        id=uuid.uuid4(), prestador_id=prestador_id, acao=acao, status="fila",
        total=len(ids), emissao_ids=[str(i) for i in ids], erros=[],
    )
    db.add(lote)
    db.flush()
    return lote


def _parado(lote: LoteAcao) -> bool:
    if lote.status not in ("fila", "executando") or lote.id in _rodando:
        return False
    referencia = lote.atualizado_em or lote.criado_em
    if referencia is None:
        return False
    return (datetime.datetime.now(datetime.timezone.utc) - referencia).total_seconds() > PARADO_APOS_S


def atualizar_parado(db: Session, lote: LoteAcao) -> LoteAcao:
    if _parado(lote):
        lote.status = "interrompido"
        db.flush()
    return lote


def iniciar(lote_id: uuid.UUID, prestador_id: uuid.UUID, base_url: str) -> None:
    """Dispara a thread (depois do commit que criou o lote)."""
    with _lock:
        if lote_id in _rodando:
            return
        _rodando.add(lote_id)
    threading.Thread(target=_executar, args=(lote_id, prestador_id, base_url), daemon=True, name=f"lote-{lote_id}").start()


def _executar(lote_id: uuid.UUID, prestador_id: uuid.UUID, base_url: str) -> None:
    db = SessionLocal()

    # A RLS usa SET LOCAL (vale só na transação): como o lote grava o
    # progresso a cada nota (commit), toda transação nova precisa do contexto.
    @event.listens_for(db, "after_begin")
    def _contexto(session, transaction, connection):
        connection.execute(text("SELECT set_config('app.current_prestador_id', :p, true)"), {"p": str(prestador_id)})

    try:
        definir_prestador_atual(db, prestador_id)
        lote = db.get(LoteAcao, lote_id)
        if lote is None:
            return
        lote.status = "executando"
        db.commit()
        processar(db, lote, prestador_id, base_url)
    except Exception:  # noqa: BLE001 — a thread nunca pode morrer calada
        logger.exception("Lote %s parou com erro", lote_id)
        db.rollback()
        definir_prestador_atual(db, prestador_id)
        lote = db.get(LoteAcao, lote_id)
        if lote is not None and lote.status == "executando":
            lote.status = "interrompido"
            db.commit()
    finally:
        with _lock:
            _rodando.discard(lote_id)
        db.close()


def _executor(db: Session, acao: str, prestador_id: uuid.UUID, base_url: str):
    """Função que faz a ação numa nota e devolve None (ok) ou o motivo da falha."""
    from app.services.certificados import CertificadoNaoEncontradoError, carregar_certificado
    from app.services.envio_direto import EmailIndisponivelError, enviar_email
    from app.services.motor_emissao import TransicaoInvalidaError, assinar, submeter

    if acao == "email":
        def fazer(e: Emissao) -> str | None:
            try:
                envio = enviar_email(db, e, prestador_id, base_url)
            except EmailIndisponivelError as exc:
                return str(exc)
            time.sleep(PAUSA_EMAIL_S)
            return None if envio.status == "enviado" else (envio.erro or "Falha no envio")
        return fazer

    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
    except CertificadoNaoEncontradoError:
        return lambda e: "Nenhum certificado carregado — envie o .pfx em Configurações."
    clientes: dict[str, ClienteSefin] = {}

    def fazer(e: Emissao) -> str | None:
        try:
            if acao == "assinar":
                assinar(db, e, private_key, cert)
                return None
            tp = (e.tomador_snapshot or {}).get("tpAmb", "2")
            cliente = clientes.setdefault(tp, ClienteSefin(private_key, cert, tp))
            submeter(db, e, cliente)
            return None if e.estado == "confirmado" else (e.erro_detalhe or "Recusada pela prefeitura")
        except TransicaoInvalidaError as exc:
            return str(exc)
    return fazer


def processar(db: Session, lote: LoteAcao, prestador_id: uuid.UUID, base_url: str) -> LoteAcao:
    """Processa as notas que faltam (síncrono — a thread chama isto; os
    testes também)."""
    fazer = _executor(db, lote.acao, prestador_id, base_url)
    ids = list(lote.emissao_ids)
    for posicao in range(lote.feitos + lote.falhas, len(ids)):
        db.refresh(lote)
        if lote.status == "cancelado":
            break
        emissao = db.get(Emissao, uuid.UUID(ids[posicao]))
        erro = "Nota não encontrada." if emissao is None else None
        if emissao is not None:
            try:
                erro = fazer(emissao)
            except Exception as exc:  # noqa: BLE001 — uma nota não derruba o lote
                logger.exception("Lote %s: falha na nota %s", lote.id, ids[posicao])
                db.rollback()
                definir_prestador_atual(db, prestador_id)
                lote = db.get(LoteAcao, lote.id)
                erro = f"Erro inesperado ({type(exc).__name__})."
        if erro:
            lote.falhas += 1
            nome = ((emissao.tomador_snapshot or {}).get("razao_social") if emissao else None) or ""
            lote.erros = [*lote.erros, {"emissao_id": ids[posicao], "nome": nome[:120], "erro": str(erro)[:300]}]
        else:
            lote.feitos += 1
        lote.atualizado_em = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    if lote.status != "cancelado":
        lote.status = "concluido"
    lote.concluido_em = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return lote


def resumo(lote: LoteAcao) -> dict:
    return {
        "id": lote.id, "acao": lote.acao, "status": lote.status, "total": lote.total,
        "feitos": lote.feitos, "falhas": lote.falhas, "erros": lote.erros[-200:],
        "criado_em": lote.criado_em, "concluido_em": lote.concluido_em,
    }
