"""
Listagens por linha (com id) — Marco 14 do plano: as telas novas de
NFS-e/Recebimentos/Despesas precisam de uma lista navegável (uma linha por
nota/pagamento/despesa, com id pra abrir o detalhe), diferente de
app/services/painel_status.py (agrega o ano inteiro, fornecedor×mês, sem
id nenhum — bom pro resumo, ruim pra abrir um registro específico) e de
app/services/dashboard.py (só a competência corrente).

Mesma disciplina de RLS das demais consultas: toda query aqui presume que
`definir_prestador_atual` já rodou na sessão (ver db_sessao em app/main.py)
— os filtros de prestador vêm de graça da RLS, nunca de um WHERE explícito
nestas tabelas.
"""
import datetime
import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models import Despesa, Emissao, Envio, PagamentoRecebido, PrestadorTomador
from app.services.dashboard import ESTADO_NFSE_LABEL


def _pares_com_pagamento(db: Session) -> set[tuple[uuid.UUID, str]]:
    """Todos os pares (vínculo, competência) que já têm AO MENOS UM
    PagamentoRecebido — mesma aproximação do dashboard (app/services/
    dashboard._tem_pagamento): um pagamento parcial já conta como
    'recebido'. Carregado uma vez só (RLS já limita ao prestador atual;
    volume é pequeno, um prestador não tem milhares de pagamentos), em vez
    de uma query por emissão."""
    linhas = db.query(PagamentoRecebido.prestador_tomador_id, PagamentoRecebido.competencia).distinct()
    return {(vinculo_id, competencia) for vinculo_id, competencia in linhas}


def listar_emissoes(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    estado: str | None = None,
    pagamento: str | None = None,
) -> list[dict]:
    """`pagamento`: None = sem filtro; "recebido" só as com algum
    PagamentoRecebido pro mesmo vínculo+competência; "pendente" as sem
    nenhum — item 3 do Marco 16 (Marcos: "é importante a pessoa confrontar
    notas emitidas com notas pagas"). Aplica-se independente do estado da
    emissão (mesmo uma cancelada mostra o cruzamento como está, sem
    esconder inconsistência)."""
    query = (
        db.query(Emissao)
        .options(joinedload(Emissao.vinculo).joinedload(PrestadorTomador.tomador))
        # Desempate por n_dps (sequencial por prestador+série, ver
        # motor_emissao._proximo_ndps) além de criado_em: dentro de uma
        # MESMA transação — o caso comum é a importação de CSV, que gera
        # várias emissões em lote — `criado_em` (server_default=now())
        # fica CONGELADO no início da transação no Postgres, então todas as
        # linhas do lote nascem com o mesmo timestamp; sem o desempate, a
        # ordem dentro do lote ficaria arbitrária.
        .order_by(Emissao.criado_em.desc(), Emissao.n_dps.desc())
    )
    if ano:
        query = query.filter(Emissao.competencia.like(f"{ano}-%"))
    if vinculo_id:
        query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    if estado:
        query = query.filter(Emissao.estado == estado)

    pares_pagos = _pares_com_pagamento(db)
    emissoes = query.all()
    # Último envio de cada nota (e-mail/WhatsApp/...) numa query só.
    ultimo_envio: dict[uuid.UUID, str] = {}
    if emissoes:
        for emissao_id, status in (
            db.query(Envio.emissao_id, Envio.status)
            .filter(Envio.emissao_id.in_([e.id for e in emissoes]))
            .order_by(Envio.criado_em)
        ):
            if ultimo_envio.get(emissao_id) != "enviado":
                ultimo_envio[emissao_id] = status
    linhas = [
        {
            "id": e.id,
            "vinculo_id": e.prestador_tomador_id,
            "apelido": e.vinculo.apelido,
            # Shopee: o tomador é o vendedor da nota, não o do vínculo.
            "tomador_razao_social": (e.tomador_snapshot or {}).get("razao_social") if e.tomador_documento else e.vinculo.tomador.razao_social,
            "competencia": e.competencia,
            "valor": float(e.valor),
            "serie": e.serie,
            "n_dps": e.n_dps,
            "estado": e.estado,
            "estado_label": ESTADO_NFSE_LABEL.get(e.estado, e.estado),
            "criado_em": e.criado_em,
            "pagamento_recebido": (e.prestador_tomador_id, e.competencia) in pares_pagos,
            "envio_status": ultimo_envio.get(e.id),
            "tem_pdf": e.estado == "confirmado",
            "tem_email": bool((e.tomador_snapshot or {}).get("email") if e.tomador_documento else (e.vinculo.email_para or e.vinculo.email_contato)),
            "homologacao": (e.tomador_snapshot or {}).get("tpAmb") == "2",
            "avulsa": bool(e.tomador_documento),
        }
        for e in emissoes
    ]
    if pagamento == "recebido":
        linhas = [l for l in linhas if l["pagamento_recebido"]]
    elif pagamento == "pendente":
        linhas = [l for l in linhas if not l["pagamento_recebido"]]
    return linhas


def listar_pagamentos(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    por_recebimento: bool = False,
) -> list[dict]:
    """`por_recebimento`: filtra o ano pela data em que o dinheiro caiu
    (sem data, pela competência) — é assim que o Financeiro soma; antes uma
    nota de dezembro paga em janeiro sumia dos dois anos.

    `PagamentoRecebido` não tem relationship pro vínculo (ver
    app/models.py) — join explícito com `PrestadorTomador` só pra buscar o
    apelido de exibição."""
    query = (
        db.query(PagamentoRecebido, PrestadorTomador.apelido)
        .join(PrestadorTomador, PagamentoRecebido.prestador_tomador_id == PrestadorTomador.id)
        .order_by(PagamentoRecebido.criado_em.desc())
    )
    if ano and por_recebimento:
        inicio, fim = datetime.date(int(ano), 1, 1), datetime.date(int(ano), 12, 31)
        query = query.filter(
            or_(
                PagamentoRecebido.data_recebimento.between(inicio, fim),
                and_(PagamentoRecebido.data_recebimento.is_(None), PagamentoRecebido.competencia.like(f"{ano}-%")),
            )
        )
    elif ano:
        query = query.filter(PagamentoRecebido.competencia.like(f"{ano}-%"))
    if vinculo_id:
        query = query.filter(PagamentoRecebido.prestador_tomador_id == vinculo_id)

    return [
        {
            "id": p.id,
            "apelido": apelido,
            "competencia": p.competencia,
            "valor": float(p.valor),
            "data_recebimento": p.data_recebimento,
        }
        for p, apelido in query.all()
    ]


def listar_despesas(db: Session, *, ano: str | None = None) -> list[dict]:
    query = db.query(Despesa).order_by(Despesa.criado_em.desc())
    if ano:
        query = query.filter(Despesa.competencia.like(f"{ano}-%"))
    return [
        {"id": d.id, "categoria": d.categoria, "competencia": d.competencia, "valor": float(d.valor)}
        for d in query.all()
    ]
