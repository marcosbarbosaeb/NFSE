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
import html
import logging
import threading
import time
import uuid

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, definir_prestador_atual
from app.fiscal.cliente_sefin import ClienteSefin
from app.models import Emissao, Envio, LoteAcao, LoteFila

logger = logging.getLogger("agenteana.lotes")

ACOES = ("email", "email_geral", "assinar", "submeter", "completo")
# Lote "completo" (05/10/2026): a sequência inteira numa nota só — assina,
# envia à prefeitura e manda pro tomador — sem a pessoa ficar olhando.
PASSOS = ("assinar", "submeter", "email")
MAXIMO_POR_LOTE = 3000
PAUSA_EMAIL_S = 0.6
# Lote "executando" sem progresso há mais que isso e sem thread viva aqui =
# o servidor reiniciou no meio.
PARADO_APOS_S = 180

_rodando: set[uuid.UUID] = set()
_lock = threading.Lock()


class LoteInvalidoError(Exception):
    pass


def _recebe_por_email(e: Emissao) -> bool:
    """Vendedor de relatório recebe sempre por e-mail; tomador cadastrado,
    só se o e-mail é uma das formas de envio dele."""
    from app.services.envio_direto import formas_de_envio

    return bool(e.tomador_documento) or e.vinculo is None or "email" in formas_de_envio(e.vinculo)


def _elegivel(acao: str, e: Emissao, ja_enviada: bool, passos: tuple[str, ...] = PASSOS) -> bool:
    if acao == "completo":
        if e.estado == "montado":
            return "assinar" in passos
        if e.estado in ("assinado", "erro", "submetido"):
            return "submeter" in passos
        return "email" in passos and _elegivel("email", e, ja_enviada)
    if acao == "assinar":
        return e.estado == "montado"
    if acao == "submeter":
        return e.estado in ("assinado", "erro")
    # e-mail: nota autorizada (ou de teste) que ainda não foi enviada — e,
    # pro fornecedor, só de quem recebe por e-mail (portal/WhatsApp/"não
    # precisa" ficam de fora).
    teste = (e.tomador_snapshot or {}).get("tpAmb") == "2"
    liberada = e.estado == "confirmado" or (teste and e.estado in ("montado", "assinado", "submetido"))
    if acao == "email" and not _recebe_por_email(e):
        return False
    return liberada and not ja_enviada


def selecionar(
    db: Session, acao: str, *, emissao_ids: list[uuid.UUID] | None = None,
    vinculo_id: uuid.UUID | None = None, competencia: str | None = None, reenviar: bool = False,
    passos: tuple[str, ...] = PASSOS, so_avulsas: bool = False,
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
    if so_avulsas:  # só as notas de vendedores de relatório (Shopee)
        query = query.filter(Emissao.tomador_documento.isnot(None))
    emissoes = query.order_by(Emissao.criado_em, Emissao.n_dps).limit(MAXIMO_POR_LOTE + 1).all()
    enviadas: set[uuid.UUID] = set()
    if acao in ("email", "email_geral", "completo") and not reenviar and emissoes:
        canal = "email" if acao == "completo" else acao
        enviadas = _ja_enviadas(db, [e.id for e in emissoes], canal)
    return [e.id for e in emissoes if _elegivel(acao, e, e.id in enviadas, passos)][:MAXIMO_POR_LOTE]


def _ja_enviadas(db: Session, ids: list[uuid.UUID], canal: str) -> set[uuid.UUID]:
    enviadas: set[uuid.UUID] = set()
    for inicio in range(0, len(ids), 500):  # IN (...) em pedaços
        enviadas.update(
            i for (i,) in db.query(Envio.emissao_id).filter(
                Envio.emissao_id.in_(ids[inicio:inicio + 500]), Envio.canal == canal, Envio.status == "enviado"
            )
        )
    return enviadas


def normalizar_passos(passos) -> tuple[str, ...]:
    """Cada passo depende do anterior: "email" sem "submeter" não existe."""
    pedidos = [p for p in PASSOS if p in (passos or PASSOS)]
    validos: list[str] = []
    for p in PASSOS:
        if p not in pedidos:
            break
        validos.append(p)
    return tuple(validos) or ("assinar",)


def criar_lote(
    db: Session, prestador_id: uuid.UUID, acao: str, ids: list[uuid.UUID],
    passos: tuple[str, ...] | None = None, base_url: str = "",
) -> LoteAcao:
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
        opcoes={"passos": list(normalizar_passos(passos))} if acao == "completo" else None,
        relatorio={} if acao == "completo" else None,
    )
    db.add(lote)
    db.flush()
    # Fila sem RLS: é por ela que o servidor retoma o lote se reiniciar.
    db.add(LoteFila(lote_id=lote.id, prestador_id=prestador_id, base_url=base_url[:300]))
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


def retomar_pendentes() -> int:
    """Chamado quando o servidor sobe: os lotes que estavam rodando quando
    ele parou (deploy, reinício) continuam de onde pararam, sozinhos — "a
    partir do ok dela rodamos em segundo plano, mesmo que ela feche o
    programa" (05/10/2026). A fila não tem RLS, então dá pra ler sem
    empresa ativa; cada lote roda com a RLS da empresa dele."""
    db = SessionLocal()
    try:
        pendentes = [(f.lote_id, f.prestador_id, f.base_url) for f in db.query(LoteFila).order_by(LoteFila.criado_em)]
    except Exception:  # noqa: BLE001 — subir o servidor nunca depende disto
        logger.exception("Não deu pra ler a fila de lotes")
        return 0
    finally:
        db.close()
    for lote_id, prestador_id, base in pendentes:
        iniciar(lote_id, prestador_id, base)
    return len(pendentes)


def _sair_da_fila(db: Session, lote_id: uuid.UUID) -> None:
    db.query(LoteFila).filter(LoteFila.lote_id == lote_id).delete(synchronize_session=False)


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
        if lote is None or lote.status not in ("fila", "executando"):
            # Cancelado/concluído enquanto estava na fila: só limpa.
            _sair_da_fila(db, lote_id)
            db.commit()
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
            _sair_da_fila(db, lote_id)
            db.commit()
    finally:
        with _lock:
            _rodando.discard(lote_id)
        db.close()


def _executor(db: Session, lote: LoteAcao, prestador_id: uuid.UUID, base_url: str):
    """Função que faz a ação numa nota e devolve None (ok) ou o motivo da
    falha. No lote "completo" ela também conta o que fez em cada passo
    (`contar`), pro relatório do fim."""
    from app.services.certificados import CertificadoNaoEncontradoError, carregar_certificado
    from app.services.envio_direto import EmailIndisponivelError, enviar_email
    from app.services.motor_emissao import (
        MARCA_FALHA_COMUNICACAO, TransicaoInvalidaError, assinar, corrigir_e_reenviar, recusa_corrigivel, recusa_de_cep, submeter,
    )

    acao = lote.acao

    def contar(chave: str) -> None:
        lote.relatorio = {**(lote.relatorio or {}), chave: (lote.relatorio or {}).get(chave, 0) + 1}

    def mandar_email(e: Emissao) -> str | None:
        try:
            envio = enviar_email(db, e, prestador_id, base_url)
        except EmailIndisponivelError as exc:
            return str(exc)
        time.sleep(PAUSA_EMAIL_S)
        return None if envio.status == "enviado" else (envio.erro or "Falha no envio")

    if acao == "email_geral":
        from app.services.envio_direto import enviar_geral

        def fazer_geral(e: Emissao) -> str | None:
            try:
                envio = enviar_geral(db, e, prestador_id, base_url)
            except EmailIndisponivelError as exc:
                return str(exc)
            time.sleep(PAUSA_EMAIL_S)
            return None if envio.status == "enviado" else (envio.erro or "Falha no envio")
        return fazer_geral

    if acao == "email":
        return mandar_email

    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
    except CertificadoNaoEncontradoError:
        return lambda e: "Nenhum certificado carregado — envie o .pfx em Empresa › Certificado."
    clientes: dict[str, ClienteSefin] = {}

    def cliente_de(e: Emissao) -> ClienteSefin:
        tp = (e.tomador_snapshot or {}).get("tpAmb", "2")
        return clientes.setdefault(tp, ClienteSefin(private_key, cert, tp))

    def enviar_a_prefeitura(e: Emissao) -> str | None:
        """Envia; recusa que a Ana conserta sozinha (hora, CEP) ganha UMA
        nova tentativa já consertada."""
        if e.estado == "erro" and recusa_corrigivel(e.erro_detalhe):
            cep = recusa_de_cep(e.erro_detalhe)
            corrigir_e_reenviar(db, e, private_key, cert, cliente_de(e))
            if cep and e.estado == "confirmado" and acao == "completo":
                contar("cep_corrigido")
        else:
            submeter(db, e, cliente_de(e))
            if e.estado == "erro" and recusa_corrigivel(e.erro_detalhe):
                cep = recusa_de_cep(e.erro_detalhe)
                corrigir_e_reenviar(db, e, private_key, cert, cliente_de(e))
                if cep and e.estado == "confirmado" and acao == "completo":
                    contar("cep_corrigido")
        return None if e.estado == "confirmado" else (e.erro_detalhe or "Recusada pela prefeitura")

    if acao != "completo":
        def fazer(e: Emissao) -> str | None:
            try:
                if acao == "assinar":
                    assinar(db, e, private_key, cert)
                    return None
                return enviar_a_prefeitura(e)
            except TransicaoInvalidaError as exc:
                return str(exc)
        return fazer

    passos = normalizar_passos((lote.opcoes or {}).get("passos"))

    def fazer_tudo(e: Emissao) -> str | None:
        try:
            if e.estado == "montado" and "assinar" in passos:
                assinar(db, e, private_key, cert)
                contar("assinadas")
            if "submeter" in passos and e.estado in ("assinado", "erro", "submetido"):
                if e.estado == "submetido":
                    # O servidor caiu no meio do envio desta nota: ela pode
                    # ter chegado à Receita — `submeter` confere antes.
                    e.estado = "erro"
                    e.erro_detalhe = f"{MARCA_FALHA_COMUNICACAO} O envio foi interrompido no meio."
                    db.flush()
                motivo = enviar_a_prefeitura(e)
                if motivo:
                    contar("recusadas")
                    return f"Prefeitura: {motivo}"
                contar("autorizadas")
        except TransicaoInvalidaError as exc:
            return str(exc)
        if "email" not in passos or e.estado != "confirmado":
            return None
        if not _recebe_por_email(e):
            contar("sem_envio_por_email")  # recebe por portal/WhatsApp/não precisa: não é falha
            return None
        if _ja_enviadas(db, [e.id], "email"):
            return None
        motivo = mandar_email(e)
        if motivo:
            contar("email_falhou")
            return f"E-mail: {motivo}"
        contar("enviadas")
        return None
    return fazer_tudo


def processar(db: Session, lote: LoteAcao, prestador_id: uuid.UUID, base_url: str) -> LoteAcao:
    """Processa as notas que faltam (síncrono — a thread chama isto; os
    testes também)."""
    fazer = _executor(db, lote, prestador_id, base_url)
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
                emissao = db.get(Emissao, uuid.UUID(ids[posicao]))
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
    _sair_da_fila(db, lote.id)
    db.commit()
    if lote.acao == "completo" and lote.status == "concluido":
        _avisar_por_email(db, lote, prestador_id, base_url)
    return lote


NOMES_DO_RELATORIO = (
    ("assinadas", "assinadas"),
    ("autorizadas", "autorizadas pela prefeitura"),
    ("cep_corrigido", "com o CEP corrigido automaticamente"),
    ("enviadas", "enviadas por e-mail"),
    ("sem_envio_por_email", "que não vão por e-mail (portal, WhatsApp ou não precisa)"),
    ("recusadas", "recusadas pela prefeitura"),
    ("email_falhou", "com falha no e-mail"),
)


def texto_do_relatorio(lote: LoteAcao) -> list[str]:
    """Linhas do relatório de status, em português de gente."""
    relatorio = lote.relatorio or {}
    linhas = [f"{relatorio[chave]} {nome}" for chave, nome in NOMES_DO_RELATORIO if relatorio.get(chave)]
    return linhas or ([f"{lote.feitos} concluída(s)"] if lote.feitos else [])


def _avisar_por_email(db: Session, lote: LoteAcao, prestador_id: uuid.UUID, base_url: str) -> None:
    """Relatório do lote pro e-mail de quem usa a conta — ela pode ter
    fechado a página. Qualquer falha aqui é só registrada: o relatório
    também fica na tela Notas em lote."""
    try:
        from app.models import Prestador, Usuario, UsuarioPrestador
        from app.services.email import get_email_sender

        usuario = (
            db.query(Usuario).join(UsuarioPrestador, UsuarioPrestador.usuario_id == Usuario.id)
            .filter(UsuarioPrestador.prestador_id == prestador_id).order_by(Usuario.criado_em).first()
        )
        prestador = db.get(Prestador, prestador_id)
        if usuario is None or not usuario.email:
            return
        linhas = texto_do_relatorio(lote)
        falhas = (
            f"\n{lote.falhas} nota(s) precisam da sua atenção — o motivo de cada uma está no relatório."
            if lote.falhas else "\nNenhuma nota ficou pra trás."
        )
        link = f"{base_url.rstrip('/')}/app/nfse/lote?relatorio={lote.id}" if base_url else ""
        texto = (
            f"Terminei o processamento das {lote.total} notas em lote"
            f"{' de ' + prestador.razao_social if prestador else ''}.\n\n"
            + "\n".join(f"• {linha}" for linha in linhas) + "\n" + falhas
            + (f"\n\nVer o relatório completo: {link}" if link else "")
            + "\n\n— Ana"
        )
        get_email_sender().enviar(
            destinatario=[usuario.email],
            assunto=f"Notas em lote: {lote.feitos} de {lote.total} concluídas" + (f", {lote.falhas} com pendência" if lote.falhas else ""),
            corpo_texto=texto,
            corpo_html="<p>" + html.escape(texto).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Não deu pra avisar por e-mail o fim do lote %s", lote.id)


def resumo(lote: LoteAcao) -> dict:
    return {
        "id": lote.id, "acao": lote.acao, "status": lote.status, "total": lote.total,
        "feitos": lote.feitos, "falhas": lote.falhas, "erros": lote.erros[-200:],
        "criado_em": lote.criado_em, "concluido_em": lote.concluido_em,
        "passos": list(normalizar_passos((lote.opcoes or {}).get("passos"))) if lote.acao == "completo" else [],
        "relatorio": lote.relatorio or {},
        "linhas_relatorio": texto_do_relatorio(lote) if lote.acao == "completo" else [],
    }
