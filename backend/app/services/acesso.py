"""Quem pode fazer o quê numa empresa (06/10/2026).

Duas travas, conferidas no mesmo lugar (`conferir`, chamada por
`deps.prestador_atual_id` — toda rota de empresa passa por lá):

1. **Contador.** "O contador deve fazer tudo pelo cliente... a conta
   cliente autoriza o que quer que o contador faça... só ver, conciliar,
   emitir nota e por aí vai." O dono convida pelo e-mail e marca as
   permissões (`PERMISSOES`). Ver é sempre liberado; o resto, só o que foi
   marcado. Cada rota que muda algo está em `REGRAS` — rota nova que não
   estiver lá é RECUSADA pro contador (e `tests/test_contador.py` acusa).
   O que o contador faz fica registrado (`RegistroContador`, só o título).

2. **Sem assinatura.** Com `BLOQUEIO_ATIVO`, empresa cujo teste acabou fica
   só pra consulta: ver e baixar o que é dela, assinar, apagar os dados.

O dono continua em `usuario_prestador`; o contador fica em `acesso_contador`
— nada do que trata "dono" (apagar empresa/conta, assinatura) enxerga ele.
"""
from __future__ import annotations

import datetime
import re
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import AcessoContador, Assinatura, Prestador, RegistroContador, Usuario, UsuarioPrestador

# id -> (nome na tela, explicação)
PERMISSOES: dict[str, tuple[str, str]] = {
    "emitir": ("Gerar e cancelar notas", "Criar, assinar, enviar à prefeitura e cancelar notas — uma a uma ou em lote."),
    "enviar": ("Enviar notas aos clientes", "Mandar as notas por e-mail, WhatsApp ou Google Drive e marcar como enviadas."),
    "tomadores": ("Cadastrar e editar tomadores", "Incluir, alterar e arquivar os clientes para quem a empresa emite."),
    "financeiro": ("Lançar e conciliar no Financeiro", "Registrar recebimentos e despesas, importar extrato, conciliar e fechar o mês."),
    "empresa": ("Alterar dados da empresa", "Dados cadastrais, alíquota, certificado A1 e preferências de emissão."),
}

LIVRE = "livre"  # não muda nada (prévia, busca): qualquer contador
NUNCA = "nunca"  # só o dono

_MUDA = "POST|PUT|PATCH|DELETE"
# (métodos, caminho, permissão, o que fica no registro). A primeira que casar vale.
_REGRAS_BRUTAS: list[tuple[str, str, str, str]] = [
    # só o dono
    ("GET|" + _MUDA, r"/api/contador/(acessos|historico)(/.*)?", NUNCA, ""),
    (_MUDA, r"/api/assinatura/.*", NUNCA, ""),
    ("DELETE", r"/api/empresa", NUNCA, ""),
    (_MUDA, r"/api/dados/limpar", NUNCA, ""),
    (_MUDA, r"/api/importar/nacional/limpar", NUNCA, ""),
    (_MUDA, r"/api/parceiros(/.*)?", NUNCA, ""),
    (_MUDA, r"/api/gestao/.*", NUNCA, ""),
    (_MUDA, r"/api/vinculos/publicar-sugestoes", NUNCA, ""),
    ("PUT", r"/api/empresa/modulos", NUNCA, ""),
    # não mudam nada
    ("POST", r"/api/cep/buscar", LIVRE, ""),
    ("POST", r"/api/uso/tela", LIVRE, ""),
    ("POST", r"/api/ajuda/perguntar", LIVRE, ""),
    ("POST", r"/api/lista-espera", LIVRE, ""),
    ("POST", r"/api/dps/[^/]+/explicar-recusa", LIVRE, ""),
    ("POST", r"/api/dps/conferir", LIVRE, ""),
    ("POST", r"/api/lotes/previa", LIVRE, ""),
    ("POST", r"/api/shopee/previa", LIVRE, ""),
    ("POST", r"/api/importar/planilha/previa", LIVRE, ""),
    ("POST", r"/api/recebimentos/extrato", LIVRE, ""),
    ("POST", r"/api/tomadores/ler-nota", LIVRE, ""),
    ("POST", r"/api/vinculos/[^/]+/identificar", LIVRE, ""),
    # enviar notas
    ("POST", r"/api/dps/[^/]+/enviar-email", "enviar", "Enviou uma nota por e-mail"),
    ("POST", r"/api/dps/[^/]+/enviar-geral", "enviar", "Enviou uma nota por e-mail"),
    ("POST", r"/api/dps/[^/]+/whatsapp", "enviar", "Preparou o envio de uma nota por WhatsApp"),
    ("POST", r"/api/dps/[^/]+/drive", "enviar", "Guardou uma nota no Google Drive"),
    ("POST", r"/api/dps/[^/]+/envios", "enviar", "Registrou o envio de uma nota"),
    ("POST", r"/api/dps/[^/]+/marcar-enviada", "enviar", "Marcou uma nota como enviada"),
    ("POST", r"/api/envios/[^/]+/marcar-(enviado|falha)", "enviar", "Atualizou o envio de uma nota"),
    ("POST", r"/api/pacote/email", "enviar", "Enviou um pacote de notas por e-mail"),
    # gerar / cancelar notas
    ("POST", r"/api/dps", "emitir", "Criou uma nota"),
    ("POST", r"/api/dps/importar-csv", "emitir", "Criou notas a partir de uma planilha"),
    ("POST", r"/api/dps/[^/]+/assinar", "emitir", "Assinou uma nota"),
    ("POST", r"/api/dps/[^/]+/submeter", "emitir", "Enviou uma nota à prefeitura"),
    ("POST", r"/api/dps/[^/]+/corrigir-reenviar", "emitir", "Corrigiu e reenviou uma nota"),
    ("POST", r"/api/dps/[^/]+/cancelar", "emitir", "Cancelou uma nota"),
    ("POST", r"/api/dps/[^/]+/origem", "emitir", "Alterou a origem de uma nota"),
    ("PATCH", r"/api/dps/[^/]+/tomador", "emitir", "Alterou o tomador de uma nota"),
    ("DELETE", r"/api/dps/[^/]+", "emitir", "Apagou um rascunho de nota"),
    ("POST", r"/api/shopee/gerar", "emitir", "Gerou notas em lote (relatório)"),
    ("POST", r"/api/awin/ordem", "emitir", "Leu uma ordem de faturamento"),
    ("POST", r"/api/lotes", "emitir", "Iniciou uma ação em lote"),
    ("POST", r"/api/lotes/[^/]+/(cancelar|refazer-falhas|retomar)", "emitir", "Mexeu numa ação em lote"),
    ("POST", r"/api/importar/nacional(/buscar)?", "emitir", "Importou notas do Emissor Nacional"),
    ("POST", r"/api/importar/nacional/desfazer", "emitir", "Desfez uma importação do Emissor Nacional"),
    # tomadores
    ("POST", r"/api/vinculos", "tomadores", "Cadastrou um tomador"),
    ("PATCH|DELETE", r"/api/vinculos/[^/]+(/tomador)?", "tomadores", "Alterou um tomador"),
    ("POST", r"/api/vinculos/controle", "tomadores", "Alterou o controle de um cliente"),
    ("POST|PATCH", r"/api/financeiro/clientes(/[^/]+)?", "tomadores", "Alterou um cliente"),
    # financeiro
    (_MUDA, r"/api/pagamentos(/[^/]+)?", "financeiro", "Alterou um recebimento"),
    ("POST", r"/api/recebimentos/extrato/confirmar", "financeiro", "Importou um extrato"),
    ("POST", r"/api/financeiro/importacoes/desfazer", "financeiro", "Desfez uma importação do financeiro"),
    ("POST", r"/api/conciliacao/.*", "financeiro", "Conciliou lançamentos"),
    (_MUDA, r"/api/despesas(/[^/]+)?", "financeiro", "Alterou uma despesa"),
    ("POST", r"/api/financeiro/conciliar", "financeiro", "Conciliou notas e recebimentos"),
    (_MUDA, r"/api/financeiro/contas-fixas(/[^/]+)?", "financeiro", "Alterou uma conta fixa"),
    (_MUDA, r"/api/financeiro/rotinas(/.*)?", "financeiro", "Alterou as rotinas do mês"),
    (_MUDA, r"/api/financeiro/anotacoes(/[^/]+)?", "financeiro", "Alterou uma anotação"),
    ("POST", r"/api/importar/planilha", "financeiro", "Importou uma planilha de controle"),
    ("POST", r"/api/calendario/assinatura/novo", "empresa", "Trocou o link da agenda"),
    (_MUDA, r"/api/calendario/.*", "financeiro", "Alterou a agenda"),
    # Pasta do mês: é justamente o lugar de troca com o contador
    (_MUDA, r"/api/pasta(/.*)?", LIVRE, ""),
    ("POST", r"/api/painel/pendencias/ignorar", "financeiro", "Marcou uma pendência como resolvida"),
    # dados da empresa
    ("PATCH", r"/api/prestador(/.*)?", "empresa", "Alterou os dados da empresa"),
    ("POST", r"/api/prestador/completar-pelo-cnpj", "empresa", "Completou os dados da empresa pelo CNPJ"),
    ("POST", r"/api/certificado", "empresa", "Trocou o certificado A1"),
    ("POST|DELETE", r"/api/drive(/conectar)?", "empresa", "Alterou a ligação com o Google Drive"),
]
REGRAS = [(set(m.split("|")), re.compile(c + r"/?"), p, r) for m, c, p, r in _REGRAS_BRUTAS]

# Com a empresa sem assinatura, isto continua funcionando (além de ver tudo).
_LIVRE_SEM_ASSINATURA = re.compile(
    r"/api/(assinatura/.*|empresa|dados/limpar|cep/buscar|contador/acessos(/.*)?|drive)/?"
)

# Na "casa" da conta só de contador só se mexe no nome do escritório e na exclusão.
_LIVRE_NA_CONTA_DE_CONTADOR = re.compile(r"/api/(prestador|empresa|cep/buscar)/?")

MENSAGEM_BLOQUEIO = {
    "teste_acabou": "O teste grátis desta empresa terminou. Pra continuar gerando notas e lançando, assine um plano em Minha conta › Assinatura.",
    "cancelada": "A assinatura desta empresa foi encerrada. Pra voltar a usar, assine de novo em Minha conta › Assinatura.",
    "sem_assinatura": "Esta empresa está sem assinatura. Assine um plano em Minha conta › Assinatura.",
    "bloqueada": "Esta conta foi bloqueada pela equipe da Agente Ana e está só pra consulta. Fale com o suporte pra voltar a usar.",
}


class AcessoError(Exception):
    pass


def classificar(metodo: str, caminho: str) -> tuple[str, str]:
    """(permissão exigida do contador, título pro registro). GET sem regra
    é livre; qualquer outra coisa sem regra é só do dono."""
    metodo = metodo.upper()
    for metodos, padrao, permissao, rotulo in REGRAS:
        if metodo in metodos and padrao.fullmatch(caminho):
            return permissao, rotulo
    return (LIVRE, "") if metodo in ("GET", "HEAD", "OPTIONS") else (NUNCA, "")


# --- papel de quem está logado ----------------------------------------------


def eh_dono(db: Session, usuario: Usuario, prestador_id: uuid.UUID) -> bool:
    return usuario.prestador_id == prestador_id or db.get(UsuarioPrestador, (usuario.id, prestador_id)) is not None


def acesso_de_contador(db: Session, usuario_id: uuid.UUID, prestador_id: uuid.UUID) -> AcessoContador | None:
    return db.query(AcessoContador).filter_by(usuario_id=usuario_id, prestador_id=prestador_id, status="ativo").one_or_none()


def papel(db: Session, usuario: Usuario, prestador_id: uuid.UUID) -> tuple[str, list[str]]:
    """("dono", todas) ou ("contador", as que o dono marcou)."""
    if eh_dono(db, usuario, prestador_id):
        return "dono", list(PERMISSOES)
    acesso = acesso_de_contador(db, usuario.id, prestador_id)
    if acesso is None:
        return "dono", list(PERMISSOES)  # não deveria acontecer: empresa_ativa já conferiu
    return "contador", [p for p in PERMISSOES if p in (acesso.permissoes or [])]


def eh_so_contador(db: Session, prestador_id: uuid.UUID) -> bool:
    """A empresa é a "casa" de uma conta só de contador?"""
    definir_prestador_atual(db, prestador_id)
    return bool(db.query(Prestador.so_contador).filter(Prestador.id == prestador_id).scalar())


# Fase sem cobrança (o Stripe ainda não recebe): depois do teste, quem
# autoriza o uso é a equipe — a pessoa pede a liberação, não "assina".
MENSAGEM_SEM_COBRANCA = (
    "O teste grátis desta empresa terminou. Nesta fase, quem libera o uso é a equipe da Agente Ana: "
    "peça a liberação em Minha conta › Assinatura (é um clique) e a gente te chama no WhatsApp."
)


def mensagem_do_bloqueio(motivo: str) -> str | None:
    from app.services.billing import cobranca_ativa

    if motivo != "bloqueada" and motivo in MENSAGEM_BLOQUEIO and not cobranca_ativa():
        return MENSAGEM_SEM_COBRANCA
    return MENSAGEM_BLOQUEIO.get(motivo)


MENSAGEM_SO_CONTADOR = "Esta é uma conta de contador: aqui não há notas nem lançamentos. Abra a empresa de um cliente em “Painel do contador”."


def situacao(db: Session, prestador_id: uuid.UUID) -> dict:
    """Situação da assinatura da empresa + se o bloqueio está valendo."""
    from app.services.billing import cobranca_ativa, situacao_do_acesso

    if eh_so_contador(db, prestador_id):
        # Conta só de contador não tem teste nem assinatura: nunca "vence".
        return {"liberado": True, "motivo": "contador", "ate": None, "dias_restantes": None,
                "bloqueio_ativo": get_settings().bloqueio_ativo, "bloqueado": False, "mensagem": None}
    definir_prestador_atual(db, prestador_id)
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    s = situacao_do_acesso(assinatura)
    ligado = get_settings().bloqueio_ativo
    bloqueado = s["motivo"] == "bloqueada" or (ligado and not s["liberado"])
    return {
        **s, "ate": s["ate"].isoformat() if s["ate"] else None,
        "bloqueio_ativo": ligado,
        # Bloqueio manual da Gestão vale sempre; o de "sem assinatura", só com BLOQUEIO_ATIVO.
        "bloqueado": bloqueado,
        "mensagem": mensagem_do_bloqueio(s["motivo"]) if bloqueado else None,
        # sem cobrança no ar, a saída do bloqueio é pedir a liberação à equipe
        "cobranca_ativa": cobranca_ativa(),
        "liberacao_pedida_em": assinatura.liberacao_pedida_em.isoformat() if assinatura is not None and assinatura.liberacao_pedida_em else None,
    }


def conferir(db: Session, request, usuario: Usuario, prestador_id: uuid.UUID) -> None:
    """Recusa (403) o que o contador não pode e (402) o que a empresa sem
    assinatura não pode. Chamada em toda rota de empresa."""
    from app.services.demo import eh_email_demo

    metodo, caminho = request.method.upper(), request.url.path
    if not eh_dono(db, usuario, prestador_id):
        acesso = acesso_de_contador(db, usuario.id, prestador_id)
        permissao, rotulo = classificar(metodo, caminho)
        if acesso is None or permissao == NUNCA:
            raise HTTPException(status_code=403, detail="Isso só quem é dono da empresa pode fazer. Você está nela como contador(a).")
        if permissao != LIVRE:
            if permissao not in (acesso.permissoes or []):
                raise HTTPException(
                    status_code=403,
                    detail=f"A empresa não liberou isso pra você: “{PERMISSOES[permissao][0]}”. Peça a quem te convidou pra marcar essa permissão.",
                )
            if rotulo:
                # Entra na mesma transação da rota: só fica se ela der commit.
                db.add(RegistroContador(id=uuid.uuid4(), prestador_id=prestador_id, usuario_id=usuario.id, email=usuario.email, acao=rotulo))
    if metodo in ("GET", "HEAD", "OPTIONS"):
        return
    # Na "casa" da conta só de contador não se cria nada (não é empresa).
    if eh_so_contador(db, prestador_id) and not _LIVRE_NA_CONTA_DE_CONTADOR.fullmatch(caminho):
        raise HTTPException(status_code=403, detail=MENSAGEM_SO_CONTADOR)
    if _LIVRE_SEM_ASSINATURA.fullmatch(caminho) or eh_email_demo(usuario.email):
        return
    if not get_settings().bloqueio_ativo:
        # Sem o bloqueio geral, só trava quem a Gestão bloqueou na mão
        # (consulta leve: uma coluna).
        definir_prestador_atual(db, prestador_id)
        if db.query(Assinatura.bloqueada_em).filter_by(prestador_id=prestador_id).scalar() is not None:
            raise HTTPException(status_code=402, detail=MENSAGEM_BLOQUEIO["bloqueada"])
        return
    s = situacao(db, prestador_id)
    if s["bloqueado"]:
        raise HTTPException(status_code=402, detail=s["mensagem"])


# --- o dono administra quem entra -------------------------------------------


def _limpar_permissoes(permissoes: list[str]) -> list[str]:
    return [p for p in PERMISSOES if p in set(permissoes or [])]


def _para_dono(db: Session, a: AcessoContador) -> dict:
    usuario = db.get(Usuario, a.usuario_id) if a.usuario_id else None
    return {
        "id": a.id, "email": a.email, "nome": usuario.nome if usuario else None, "status": a.status,
        "permissoes": _limpar_permissoes(a.permissoes), "criado_em": a.criado_em, "aceito_em": a.aceito_em,
    }


def listar_da_empresa(db: Session, prestador_id: uuid.UUID) -> list[dict]:
    linhas = db.query(AcessoContador).filter_by(prestador_id=prestador_id).order_by(AcessoContador.criado_em).all()
    return [_para_dono(db, a) for a in linhas]


def convidar(db: Session, prestador_id: uuid.UUID, quem: Usuario, email: str, permissoes: list[str]) -> AcessoContador:
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AcessoError("Confira o e-mail do contador.")
    if email == (quem.email or "").lower():
        raise AcessoError("Esse é o seu próprio e-mail — você já tem acesso total à empresa.")
    existente_usuario = db.query(Usuario).filter_by(email=email).one_or_none()
    if existente_usuario is not None and eh_dono(db, existente_usuario, prestador_id):
        raise AcessoError("Essa pessoa já é dona desta empresa aqui na Ana.")
    if db.query(AcessoContador).filter_by(prestador_id=prestador_id, email=email).one_or_none() is not None:
        raise AcessoError("Esse e-mail já foi convidado. Você pode mudar as permissões dele na lista.")
    acesso = AcessoContador(
        id=uuid.uuid4(), prestador_id=prestador_id, email=email, permissoes=_limpar_permissoes(permissoes),
        status="pendente", convidado_por=quem.email,
    )
    db.add(acesso)
    db.flush()
    return acesso


def _da_empresa(db: Session, prestador_id: uuid.UUID, acesso_id: uuid.UUID) -> AcessoContador:
    acesso = db.get(AcessoContador, acesso_id)
    if acesso is None or acesso.prestador_id != prestador_id:
        raise AcessoError("Acesso não encontrado.")
    return acesso


def mudar_permissoes(db: Session, prestador_id: uuid.UUID, acesso_id: uuid.UUID, permissoes: list[str]) -> AcessoContador:
    acesso = _da_empresa(db, prestador_id, acesso_id)
    acesso.permissoes = _limpar_permissoes(permissoes)
    db.flush()
    return acesso


def remover(db: Session, prestador_id: uuid.UUID, acesso_id: uuid.UUID) -> None:
    from app.services import parceiros

    acesso = _da_empresa(db, prestador_id, acesso_id)
    parceiros.desvincular_contador(db, acesso.usuario_id, prestador_id)
    db.delete(acesso)
    db.flush()


def historico(db: Session, prestador_id: uuid.UUID, limite: int = 100) -> list[dict]:
    linhas = (
        db.query(RegistroContador).filter_by(prestador_id=prestador_id)
        .order_by(RegistroContador.quando.desc()).limit(limite).all()
    )
    return [{"id": r.id, "email": r.email, "acao": r.acao, "quando": r.quando} for r in linhas]


# --- o contador -------------------------------------------------------------


def _empresa(db: Session, prestador_id: uuid.UUID) -> Prestador | None:
    definir_prestador_atual(db, prestador_id)
    return db.get(Prestador, prestador_id)


def tem_algo(db: Session, usuario: Usuario) -> bool:
    """Mostra "Painel do contador" no menu? (atende alguém ou tem convite)."""
    return db.query(AcessoContador.id).filter(
        (AcessoContador.usuario_id == usuario.id) | ((AcessoContador.email == usuario.email) & (AcessoContador.status == "pendente"))
    ).first() is not None


def do_contador(db: Session, usuario: Usuario, voltar_para: uuid.UUID) -> dict:
    """Convites esperando resposta e empresas que este login atende. Lê o
    nome de cada empresa trocando o contexto e devolve o contexto no fim."""
    from app.services import raio_x
    from app.services.prontidao import prontidao

    convites, clientes = [], []
    try:
        pendentes = db.query(AcessoContador).filter_by(email=usuario.email, status="pendente").order_by(AcessoContador.criado_em).all()
        ativos = db.query(AcessoContador).filter_by(usuario_id=usuario.id, status="ativo").order_by(AcessoContador.aceito_em).all()
        for a in pendentes:
            p = _empresa(db, a.prestador_id)
            if p is not None:
                convites.append({
                    "id": a.id, "empresa": p.razao_social, "cnpj": p.cpf_cnpj, "convidado_por": a.convidado_por,
                    "permissoes": _limpar_permissoes(a.permissoes), "criado_em": a.criado_em,
                })
        for a in ativos:
            p = _empresa(db, a.prestador_id)
            if p is None:
                continue
            pronta = prontidao(db, a.prestador_id)
            modulos = list(p.modulos or []) or ["emissor"]
            do_financeiro: dict = {}
            pendencias = _pendencias_da_empresa(db, a.prestador_id, modulos, do_financeiro)
            sit = situacao(db, a.prestador_id)
            raio = _raio_x(db, a.prestador_id, do_financeiro)
            pasta_do_mes = _pasta_da_empresa(db, a.prestador_id, usuario.id)
            clientes.append({
                "raio_x": raio, "alertas": raio_x.alertas(raio, bloqueada=bool(sit.get("bloqueado"))) if raio else [],
                "pendencias": pendencias, "total_pendencias": sum(x["quantidade"] for x in pendencias),
                "id": a.id, "prestador_id": a.prestador_id, "empresa": p.razao_social, "nome_fantasia": p.nome_fantasia, "cnpj": p.cpf_cnpj,
                "permissoes": _limpar_permissoes(a.permissoes), "desde": a.aceito_em, "modulos": list(p.modulos or []),
                "pode_emitir": bool(pronta.get("pode_emitir")), "aviso": pronta.get("motivo"),
                "situacao": sit,
                "dono": _dono_da_empresa(db, a.prestador_id),
                "pasta": pasta_do_mes,
            })
    finally:
        definir_prestador_atual(db, voltar_para)
    return {"convites": convites, "clientes": clientes, "resumo": raio_x.resumo(clientes)}


def _dono_da_empresa(db: Session, prestador_id: uuid.UUID) -> dict | None:
    """Com quem o contador fala nesta empresa: o primeiro dono (nome, e-mail
    e o WhatsApp do cadastro). Foi ele quem convidou o contador."""
    dono = (
        db.query(Usuario).join(UsuarioPrestador, UsuarioPrestador.usuario_id == Usuario.id)
        .filter(UsuarioPrestador.prestador_id == prestador_id).order_by(Usuario.criado_em).first()
    )
    return {"nome": dono.nome, "email": dono.email, "telefone": dono.telefone} if dono is not None else None


def _pasta_da_empresa(db: Session, prestador_id: uuid.UUID, usuario_id: uuid.UUID) -> dict | None:
    """Pasta do mês (app/services/pasta.py) pro painel do contador: quantos
    itens do mês passado faltam e o que a empresa mandou de novo."""
    import logging

    from app.services import pasta

    try:
        with db.begin_nested():
            definir_prestador_atual(db, prestador_id)
            comp = pasta.competencia_padrao()
            mes = pasta.do_mes(db, prestador_id, comp)
            return {"competencia": comp, **mes["resumo"], "novidades": pasta.novidades(db, prestador_id, usuario_id, "contador")}
    except Exception:  # noqa: BLE001
        logging.getLogger("agenteana.contador").exception("Falha na pasta da empresa %s", prestador_id)
        return None


def _raio_x(db: Session, prestador_id: uuid.UUID, do_financeiro: dict) -> dict | None:
    """Os números da empresa pro painel do contador (app/services/raio_x.py).
    Uma empresa com problema não derruba as outras."""
    import logging

    from app.services import raio_x
    from app.tempo import hoje as hoje_br

    try:
        with db.begin_nested():
            definir_prestador_atual(db, prestador_id)
            return raio_x.da_empresa(db, db.get(Prestador, prestador_id), hoje_br(), do_financeiro)
    except Exception:  # noqa: BLE001
        logging.getLogger("agenteana.contador").exception("Falha no raio-x da empresa %s", prestador_id)
        return None


def _pendencias_da_empresa(db: Session, prestador_id: uuid.UUID, modulos: list[str], do_financeiro: dict | None = None) -> list[dict]:
    """O que tem pra fazer nesta empresa, sem precisar entrar nela — as mesmas
    pendências da Visão geral dela (notas pra gerar, assinar, enviar,
    recusadas) e da Conciliação. Só títulos e quantidades. Uma empresa com
    problema não derruba a lista das outras."""
    import logging

    itens: list[dict] = []
    try:
        with db.begin_nested():
            definir_prestador_atual(db, prestador_id)
            if "emissor" in modulos:
                from app.services.dashboard import proximos

                for pend in proximos(db, prestador_id)["pendencias"]:
                    itens.append({
                        "tipo": pend["tipo"], "titulo": pend["titulo"], "link": pend.get("link") or "/app/nfse",
                        "quantidade": len(pend["itens"]) if pend.get("itens") else _quantidade_no_titulo(pend["titulo"]),
                        "atrasada": bool(pend.get("atrasada")) or pend["tipo"] == "erro",
                    })
            if "financeiro" in modulos:
                # O financeiro responde pelo que é dele (app/eventos.py): o
                # emissor não importa nada de app/financeiro.
                from app import eventos

                # (o financeiro devolve também o fechamento do mês e o dinheiro
                # sem nota, que o raio-x usa — `do_financeiro`)
                for grupo in eventos.coletar("resumo_pro_contador", db, prestador_id=prestador_id):
                    itens.extend(grupo["pendencias"])
                    if do_financeiro is not None:
                        do_financeiro.update({k: v for k, v in grupo.items() if k != "pendencias"})
    except Exception:  # noqa: BLE001 — a lista do contador não pode cair por causa de uma empresa
        logging.getLogger("agenteana.contador").exception("Falha ao levantar as pendências da empresa %s", prestador_id)
        return [{"tipo": "indisponivel", "titulo": "Não consegui levantar as pendências agora", "link": "/app", "quantidade": 0, "atrasada": False}]
    return itens


def _quantidade_no_titulo(titulo: str) -> int:
    """"Assinar 3 notas" -> 3; "Assinar a nota de Fulano" -> 1."""
    achado = re.search(r"\b(\d+)\b", titulo)
    return int(achado.group(1)) if achado else 1


def _convite_do_usuario(db: Session, usuario: Usuario, acesso_id: uuid.UUID) -> AcessoContador:
    acesso = db.get(AcessoContador, acesso_id)
    if acesso is None or acesso.status != "pendente" or acesso.email != usuario.email:
        raise AcessoError("Convite não encontrado. Ele pode ter sido cancelado.")
    return acesso


def aceitar(db: Session, usuario: Usuario, acesso_id: uuid.UUID) -> AcessoContador:
    """Só o dono do e-mail convidado (com e-mail confirmado) aceita."""
    if not usuario.email_confirmado:
        raise AcessoError("Confirme o seu e-mail antes de aceitar o convite.")
    acesso = _convite_do_usuario(db, usuario, acesso_id)
    acesso.usuario_id = usuario.id
    acesso.status = "ativo"
    acesso.aceito_em = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    # Bonificação: a empresa entra na parceria do contador enquanto ele a atender.
    from app.services import parceiros

    empresa = _empresa(db, acesso.prestador_id)
    assinatura = db.query(Assinatura.status).filter_by(prestador_id=acesso.prestador_id).scalar()
    parceiros.vincular_contador(db, usuario, acesso.prestador_id, empresa.razao_social if empresa else None, assinatura)
    return acesso


def recusar(db: Session, usuario: Usuario, acesso_id: uuid.UUID) -> None:
    db.delete(_convite_do_usuario(db, usuario, acesso_id))
    db.flush()


def sair(db: Session, usuario: Usuario, acesso_id: uuid.UUID) -> uuid.UUID:
    """O contador deixa de atender a empresa. Devolve o id da empresa."""
    acesso = db.get(AcessoContador, acesso_id)
    if acesso is None or acesso.usuario_id != usuario.id:
        raise AcessoError("Acesso não encontrado.")
    from app.services import parceiros

    prestador_id = acesso.prestador_id
    parceiros.desvincular_contador(db, usuario.id, prestador_id)
    db.delete(acesso)
    db.flush()
    return prestador_id
