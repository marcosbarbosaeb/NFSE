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

ACOES = ("email", "email_geral", "assinar", "submeter", "completo", "drive")
# Canais que contam como "a nota já chegou ao tomador" — inclusive as
# importadas, que entram marcadas como entregues por fora.
CANAIS_ENTREGA = ("email", "whatsapp", "direto_fornecedor")
# Lote que bateu na cota do serviço de e-mail espera e tenta de novo.
ESPERA_COTA_H = 6
MAXIMO_ESPERAS = 28
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


def _tem_email(e: Emissao) -> bool:
    from app.services.envio_direto import destinos_email

    return bool(destinos_email(e, e.vinculo))


def _motivo_sem_email(e: Emissao) -> str:
    """Por que esta nota não tem pra onde mandar (aviso, não falha)."""
    from app.services.emails import separar

    if e.tomador_documento:
        ruim = (e.tomador_snapshot or {}).get("email_invalido")
        return f"O e-mail do vendedor no relatório (“{ruim}”) não é válido." if ruim else "O vendedor não informou e-mail no relatório."
    v = e.vinculo
    escritos = separar([v.email_para or "", v.email_contato or ""])[1] if v is not None else []
    if escritos:
        return f"O e-mail cadastrado no tomador (“{escritos[0]}”) não é válido. Corrija em Tomadores."
    return "Tomador sem e-mail cadastrado."


def _elegivel(acao: str, e: Emissao, ja_enviada: bool, passos: tuple[str, ...] = PASSOS) -> bool:
    if acao == "drive":
        return e.estado == "confirmado"
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
    if acao == "email" and not (_recebe_por_email(e) and _tem_email(e)):
        return False  # sem e-mail não há o que mandar (não é falha: ver `andamento`)
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
        # "Já enviada" = entregue ao tomador por QUALQUER caminho (e-mail,
        # WhatsApp, marcada como entregue — é o caso das notas importadas).
        # Antes só olhava o canal e-mail, e um lote reenviou notas antigas.
        canais = ("email_geral",) if acao == "email_geral" else CANAIS_ENTREGA
        enviadas = _ja_enviadas(db, [e.id for e in emissoes], canais)
    return [e.id for e in emissoes if _elegivel(acao, e, e.id in enviadas, passos)][:MAXIMO_POR_LOTE]


def _ja_enviadas(db: Session, ids: list[uuid.UUID], canais: tuple[str, ...] = CANAIS_ENTREGA) -> set[uuid.UUID]:
    enviadas: set[uuid.UUID] = set()
    for inicio in range(0, len(ids), 500):  # IN (...) em pedaços
        enviadas.update(
            i for (i,) in db.query(Envio.emissao_id).filter(
                Envio.emissao_id.in_(ids[inicio:inicio + 500]), Envio.canal.in_(canais), Envio.status == "enviado"
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
    passos: tuple[str, ...] | None = None, base_url: str = "", opcoes: dict | None = None,
    aguardar_ate: datetime.datetime | None = None,
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
        opcoes={**({"passos": list(normalizar_passos(passos))} if acao == "completo" else {}), **(opcoes or {})},
        relatorio={},
    )
    if aguardar_ate is not None:
        lote.status = "aguardando"
    db.add(lote)
    db.flush()
    # Fila sem RLS: é por ela que o servidor retoma o lote se reiniciar.
    db.add(LoteFila(lote_id=lote.id, prestador_id=prestador_id, base_url=base_url[:300], retomar_em=aguardar_ate))
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
    agora = datetime.datetime.now(datetime.timezone.utc)
    try:
        pendentes = [
            (f.lote_id, f.prestador_id, f.base_url) for f in db.query(LoteFila).order_by(LoteFila.criado_em)
            if f.retomar_em is None or f.retomar_em <= agora  # os que esperam a cota voltam na hora marcada
        ]
    except Exception:  # noqa: BLE001 — subir o servidor nunca depende disto
        logger.exception("Não deu pra ler a fila de lotes")
        return 0
    finally:
        db.close()
    for lote_id, prestador_id, base in pendentes:
        iniciar(lote_id, prestador_id, base)
    return len(pendentes)


def iniciar_relogio(intervalo_s: int = 600) -> None:
    """Thread que, de tempos em tempos, retoma os lotes que estavam
    esperando a cota de e-mail voltar (e qualquer um que ficou pra trás)."""
    def rodar():
        while True:
            time.sleep(intervalo_s)
            try:
                retomar_pendentes()
            except Exception:  # noqa: BLE001
                logger.exception("Relógio dos lotes falhou")
    threading.Thread(target=rodar, daemon=True, name="lotes-relogio").start()


def _esperar_cota(db: Session, lote: LoteAcao, mensal: bool) -> None:
    """O serviço de e-mail atingiu o limite: o lote fica aguardando e volta
    sozinho. Depois de MAXIMO_ESPERAS tentativas, para e avisa."""
    esperas = int((lote.opcoes or {}).get("esperas", 0)) + 1
    lote.opcoes = {**(lote.opcoes or {}), "esperas": esperas, "cota_mensal": bool(mensal)}
    fila = db.get(LoteFila, lote.id)
    if esperas > MAXIMO_ESPERAS:
        lote.status = "interrompido"
        if fila is not None:
            db.delete(fila)
        return
    quando = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24 if mensal else ESPERA_COTA_H)
    lote.status = "aguardando"
    if fila is None:
        db.add(LoteFila(lote_id=lote.id, prestador_id=lote.prestador_id, base_url="", retomar_em=quando))
    else:
        fila.retomar_em = quando


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
        if lote is None or lote.status not in ("fila", "executando", "aguardando"):
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
    from app.services.envio_direto import EmailCotaError, EmailIndisponivelError, enviar_email
    from app.services.motor_emissao import (
        MARCA_FALHA_COMUNICACAO, TransicaoInvalidaError, assinar, corrigir_e_reenviar, recusa_corrigivel, recusa_de_cep, submeter,
    )

    acao = lote.acao

    def contar(chave: str) -> None:
        lote.relatorio = {**(lote.relatorio or {}), chave: (lote.relatorio or {}).get(chave, 0) + 1}

    def avisar(e: Emissao, texto: str) -> None:
        """Algo que não é falha, mas a pessoa precisa saber (ex.: vendedor sem e-mail)."""
        nome = ((e.tomador_snapshot or {}).get("razao_social") or "")[:120]
        avisos = list((lote.opcoes or {}).get("avisos") or [])
        avisos.append({"emissao_id": str(e.id), "nome": nome, "aviso": texto[:200]})
        lote.opcoes = {**(lote.opcoes or {}), "avisos": avisos[-500:]}

    def mandar_email(e: Emissao) -> str | None:
        if not _tem_email(e):
            # Cadastro sem e-mail não é erro do sistema nem falha do lote.
            contar("sem_email")
            avisar(e, _motivo_sem_email(e))
            return None
        try:
            envio = enviar_email(db, e, prestador_id, base_url)
        except EmailCotaError:
            raise
        except EmailIndisponivelError as exc:
            return str(exc)
        time.sleep(PAUSA_EMAIL_S)
        if envio.status == "enviado":
            contar("enviadas")
            return None
        contar("email_falhou")
        return envio.erro or "Falha no envio"

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

    if acao == "drive":
        from app.services.drive import ClienteDrive, DriveFalhaError, DriveNaoConectadoError
        from app.services.pacote import arquivos_da_nota

        try:
            cliente_drive = ClienteDrive(db, prestador_id)
        except (DriveNaoConectadoError, DriveFalhaError) as exc:
            motivo_drive = str(exc)
            return lambda e: motivo_drive
        conteudo = (lote.opcoes or {}).get("conteudo") or "ambos"

        def subir(e: Emissao) -> str | None:
            try:
                apelido = (e.vinculo.apelido if e.vinculo is not None else None) or "Notas"
                pasta = cliente_drive.pasta_do_mes(apelido, e.competencia)
                if not (lote.opcoes or {}).get("link"):
                    lote.opcoes = {**(lote.opcoes or {}), "link": cliente_drive.link_da_pasta(pasta)}
                arquivos = arquivos_da_nota(db, e, conteudo)
                if not arquivos:
                    return "Esta nota ainda não tem arquivo pra subir."
                for nome, dados, tipo in arquivos:
                    cliente_drive.enviar(pasta, nome, dados, tipo)
                contar("no_drive")
                return None
            except (DriveNaoConectadoError, DriveFalhaError) as exc:
                return str(exc)
        return subir

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
    cota = {"esgotada": False, "mensal": False}

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
        if _ja_enviadas(db, [e.id]):
            return None
        if cota["esgotada"]:
            # O serviço de e-mail já avisou que não aceita mais hoje: as
            # notas seguem sendo assinadas e autorizadas; o e-mail fica pra
            # um lote que volta sozinho depois (ver `processar`).
            contar("email_adiado")
            lote.opcoes = {**(lote.opcoes or {}), "adiadas": [*((lote.opcoes or {}).get("adiadas") or []), str(e.id)]}
            return None
        try:
            motivo = mandar_email(e)
        except EmailCotaError as exc:
            cota["esgotada"], cota["mensal"] = True, exc.mensal
            lote.opcoes = {**(lote.opcoes or {}), "cota_mensal": exc.mensal}
            return fazer_tudo(e)
        return f"E-mail: {motivo}" if motivo else None
    return fazer_tudo


class _CotaDeEmail(Exception):
    def __init__(self, mensal: bool):
        self.mensal = mensal


def processar(db: Session, lote: LoteAcao, prestador_id: uuid.UUID, base_url: str) -> LoteAcao:
    """Processa as notas que faltam (síncrono — a thread chama isto; os
    testes também)."""
    from app.services.envio_direto import EmailCotaError

    acao_bruta = _executor(db, lote, prestador_id, base_url)

    def fazer(e: Emissao) -> str | None:
        try:
            return acao_bruta(e)
        except EmailCotaError as exc:
            raise _CotaDeEmail(exc.mensal) from exc

    if lote.status == "aguardando":
        lote.status = "executando"
        fila = db.get(LoteFila, lote.id)
        if fila is not None:
            fila.retomar_em = None
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
            except _CotaDeEmail as exc:
                # Lote só de e-mail: para aqui (esta nota não conta) e volta sozinho.
                _esperar_cota(db, lote, exc.mensal)
                lote.relatorio = {**(lote.relatorio or {}), "aguardando_cota": len(ids) - posicao}
                lote.atualizado_em = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                return lote
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
    lote.relatorio = {k: v for k, v in (lote.relatorio or {}).items() if k != "aguardando_cota"}
    _sair_da_fila(db, lote.id)
    adiadas = [uuid.UUID(i) for i in (lote.opcoes or {}).get("adiadas") or []]
    if adiadas and lote.status == "concluido":
        # Os e-mails que a cota não deixou sair viram um lote que espera e
        # volta sozinho — a pessoa não precisa lembrar de nada.
        mensal = bool((lote.opcoes or {}).get("cota_mensal"))
        quando = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24 if mensal else ESPERA_COTA_H)
        db.flush()
        criar_lote(db, prestador_id, "email", adiadas, base_url=base_url, opcoes={"cota_mensal": mensal, "continuacao_de": str(lote.id)}, aguardar_ate=quando)
    db.commit()
    if lote.acao == "completo" and lote.status == "concluido":
        _avisar_por_email(db, lote, prestador_id, base_url)
    return lote


NOMES_DO_RELATORIO = (
    ("assinadas", "assinadas"),
    ("autorizadas", "autorizadas pela prefeitura"),
    ("cep_corrigido", "com o CEP corrigido automaticamente"),
    ("enviadas", "enviadas por e-mail"),
    ("no_drive", "guardadas no Google Drive"),
    ("sem_email", "sem e-mail informado (não deu pra enviar — não é falha)"),
    ("email_adiado", "com o e-mail adiado: o serviço de e-mail atingiu o limite de hoje e eu continuo sozinha depois"),
    ("aguardando_cota", "esperando o limite do serviço de e-mail voltar"),
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
        from app.services.emails import email_valido

        if not email_valido(usuario.email):
            # 09/10/2026: antes o serviço de e-mail recusava (422) e virava erro no
            # registro. Agora o aviso aparece no relatório do lote, na tela.
            logger.warning("Aviso de fim do lote %s não enviado: e-mail da conta com formato inválido", lote.id)
            lote.opcoes = {
                **(lote.opcoes or {}),
                "aviso_conta": (
                    f"Não consegui te mandar o resumo deste lote por e-mail: o e-mail da sua conta (“{usuario.email}”) "
                    "não é um endereço válido. Corrija em Minha conta."
                ),
            }
            db.commit()
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
    except Exception as exc:  # noqa: BLE001
        from app.services.email import EmailEnvioError

        if isinstance(exc, EmailEnvioError):
            # recusa do serviço de e-mail: não é defeito do sistema
            logger.warning("Aviso de fim do lote %s não saiu por e-mail: %s", lote.id, exc)
        else:
            logger.exception("Não deu pra avisar por e-mail o fim do lote %s", lote.id)


def falhas_resolvidas(db: Session, lote: LoteAcao) -> set[str]:
    """Ids das notas que falharam NESTE lote mas já foram resolvidas depois
    (corrigidas e autorizadas, ou entregues) — pra tela não continuar
    acusando pendência que não existe mais (05/10/2026)."""
    ids = list({e["emissao_id"] for e in lote.erros})
    if not ids:
        return set()
    uuids = [uuid.UUID(i) for i in ids]
    notas = {str(e.id): e for e in db.query(Emissao).filter(Emissao.id.in_(uuids[:1000]))}
    entregues = {str(i) for i in _ja_enviadas(db, uuids[:1000])}
    resolvidas: set[str] = set()
    for erro in lote.erros:
        chave = erro["emissao_id"]
        nota = notas.get(chave)
        if nota is None or nota.estado == "cancelada":
            resolvidas.add(chave)  # nota apagada/cancelada: não há mais o que fazer
        elif lote.acao == "assinar":
            if nota.estado != "montado":
                resolvidas.add(chave)
        elif lote.acao == "submeter" or (lote.acao == "completo" and not str(erro.get("erro", "")).startswith("E-mail:")):
            if nota.estado == "confirmado":
                resolvidas.add(chave)
        elif lote.acao in ("email", "completo"):
            if chave in entregues:
                resolvidas.add(chave)
    return resolvidas


def resumo(lote: LoteAcao, db: Session | None = None) -> dict:
    opcoes = lote.opcoes or {}
    resolvidas = falhas_resolvidas(db, lote) if db is not None and lote.status not in ("fila", "executando") else set()
    erros = [e for e in lote.erros if e["emissao_id"] not in resolvidas]
    return {
        "id": lote.id, "acao": lote.acao, "status": lote.status, "total": lote.total,
        "feitos": lote.feitos, "falhas": lote.falhas, "erros": erros[-200:],
        "criado_em": lote.criado_em, "concluido_em": lote.concluido_em,
        "passos": list(normalizar_passos(opcoes.get("passos"))) if lote.acao == "completo" else [],
        "relatorio": {k: v for k, v in (lote.relatorio or {}).items() if isinstance(v, int)},
        "linhas_relatorio": texto_do_relatorio(lote),
        # O que ainda está pendente de verdade (falhas menos as já resolvidas).
        "pendentes": len(erros), "resolvidas": len(lote.erros) - len(erros),
        "avisos": (opcoes.get("avisos") or [])[-200:],
        "aviso_conta": opcoes.get("aviso_conta"),
        "link": opcoes.get("link"),
        "cota_mensal": bool(opcoes.get("cota_mensal")),
    }


def andamento(db: Session, vinculo_id: uuid.UUID | None = None, competencia: str | None = None) -> dict:
    """Em que pé está o lote de um mês (05/10/2026: "aqui é seguir o passo a
    passo sequencial e automatizar tudo"): quantas notas em cada etapa, o
    que falta e o que precisa de atenção — a tela mostra UM botão."""
    from sqlalchemy import func as sa_func

    base = db.query(Emissao).filter(Emissao.tomador_documento.isnot(None), Emissao.estado != "cancelada")
    if vinculo_id is not None:
        base = base.filter(Emissao.prestador_tomador_id == vinculo_id)
    meses = [
        {"competencia": c, "vinculo_id": v, "notas": n}
        for c, v, n in base.with_entities(Emissao.competencia, Emissao.prestador_tomador_id, sa_func.count())
        .group_by(Emissao.competencia, Emissao.prestador_tomador_id).order_by(Emissao.competencia.desc()).limit(24)
    ]
    if competencia is None and meses:
        competencia, vinculo_id = meses[0]["competencia"], vinculo_id or meses[0]["vinculo_id"]
    vazio = {"meses": meses, "competencia": competencia, "vinculo_id": vinculo_id, "total": 0}
    if competencia is None:
        return vazio
    notas = base.filter(Emissao.competencia == competencia)
    if vinculo_id is not None:
        notas = notas.filter(Emissao.prestador_tomador_id == vinculo_id)
    notas = notas.order_by(Emissao.n_dps).limit(MAXIMO_POR_LOTE).all()
    if not notas:
        return vazio
    entregues = _ja_enviadas(db, [e.id for e in notas])
    por_estado = {"montado": 0, "assinado": 0, "erro": 0, "confirmado": 0, "submetido": 0, "rascunho": 0}
    recusadas, sem_email, a_enviar, valor = [], [], 0, 0.0
    for e in notas:
        por_estado[e.estado] = por_estado.get(e.estado, 0) + 1
        valor += float(e.valor)
        snap = e.tomador_snapshot or {}
        if e.estado == "erro" and len(recusadas) < 20:
            from app.services.motor_emissao import motivo_da_recusa, recusa_corrigivel

            recusadas.append({
                "emissao_id": e.id, "nome": (snap.get("razao_social") or "")[:120],
                "motivo": motivo_da_recusa(e.erro_detalhe), "corrigivel": recusa_corrigivel(e.erro_detalhe),
            })
        if e.estado == "confirmado" and e.id not in entregues:
            if _tem_email(e):
                a_enviar += 1
            elif len(sem_email) < 50:
                sem_email.append({"emissao_id": e.id, "nome": (snap.get("razao_social") or "")[:120]})
    total = len(notas)
    autorizadas = por_estado["confirmado"]
    enviadas = sum(1 for e in notas if e.id in entregues)
    a_assinar = por_estado["montado"] + por_estado["rascunho"]
    a_prefeitura = por_estado["assinado"] + por_estado["erro"] + por_estado["submetido"]
    ativo = (
        db.query(LoteAcao).filter(LoteAcao.status.in_(("fila", "executando", "aguardando")))
        .order_by(LoteAcao.criado_em.desc()).first()
    )
    etapa = (
        "assinar" if a_assinar else "prefeitura" if a_prefeitura else "enviar" if a_enviar else "pacote"
    )
    # "Guardar os arquivos" é opcional (08/10/2026): a pessoa baixa/manda/guarda
    # ou só marca como concluído — fica anotado por tomador + mês.
    from app.models import AjusteEvento

    dono = vinculo_id or notas[0].prestador_tomador_id
    pacote_feito = db.query(AjusteEvento.id).filter_by(tipo="pendencia", chave=f"pacote:{dono}:{competencia}", oculto=True).first() is not None
    return {
        "meses": meses, "competencia": competencia, "vinculo_id": vinculo_id or notas[0].prestador_tomador_id,
        "total": total, "valor": round(valor, 2),
        "assinadas": total - a_assinar, "autorizadas": autorizadas, "enviadas": enviadas,
        "a_assinar": a_assinar, "a_prefeitura": a_prefeitura, "a_enviar": a_enviar,
        "recusadas": recusadas, "total_recusadas": por_estado["erro"],
        "sem_email": sem_email, "total_sem_email": sum(
            1 for e in notas if e.estado == "confirmado" and e.id not in entregues and not _tem_email(e)
        ),
        "etapa": etapa, "pacote_feito": pacote_feito,
        # Tudo o que dependia do sistema foi feito? (vendedor sem e-mail não segura o "regular")
        "regular": a_assinar == 0 and a_prefeitura == 0 and a_enviar == 0,
        "lote_ativo": resumo(ativo) if ativo is not None and not _parado(ativo) else None,
    }
