"""Notas a receber x recebidas, de TODOS os meses — pedido do Marcos
(28/09/2026): "Notas a receber / Notas recebidas (total), existem diversos
pagamentos que ficam pendentes"; "notas abertas há mais de dois meses também
devem entrar no Precisa da sua atenção"; "nos recebimentos coloque os
pagamentos também".

A baixa é POR NOTA desde 03/10/2026 (ver `Baixas`): cada recebimento fica
ligado à nota que ele paga. Só o histórico sem nota (planilha, conciliação)
continua valendo pro mês inteiro do tomador.
"""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Emissao, PagamentoRecebido, PrestadorTomador
from app.tempo import data_local, hoje as hoje_br

# O que já saiu como nota (montado = gerada, ainda sem assinar). Rascunho,
# erro, cancelada e substituída não entram na conta de "a receber".
ESTADOS_COBRAVEIS = ("montado", "assinado", "submetido", "confirmado")
DIAS_ABERTA_ALERTA = 60


class Baixas:
    """Quem está pago (03/10/2026, "a baixa tem que ser por nota"):

    - pagamento ligado a uma nota (`emissao_id`) dá baixa só nela;
    - pagamento ANTIGO (`mes_inteiro`: planilha, conciliação, baixas de antes
      da baixa por nota) vale pro mês inteiro daquele tomador;
    - recebimento novo sem nota não dá baixa em nada: é um "recebimento sem
      nota" até a pessoa gerar a nota dele ou ligá-lo a uma (05/10/2026 —
      a Amazon paga em setembro a nota que só sai em outubro).
    """

    def __init__(self, db: Session):
        self.notas: set[uuid.UUID] = set()
        self.meses: set[tuple[uuid.UUID, str]] = set()
        # mês em que alguma nota do tomador foi paga (vendedores da Shopee:
        # a Shopee paga tudo junto na nota dela)
        self.meses_com_nota_paga: set[tuple[uuid.UUID, str]] = set()
        linhas = db.query(
            PagamentoRecebido.emissao_id, PagamentoRecebido.prestador_tomador_id, PagamentoRecebido.competencia,
            PagamentoRecebido.mes_inteiro,
        ).distinct()
        for emissao_id, vinculo_id, competencia, mes_inteiro in linhas:
            if emissao_id is not None:
                self.notas.add(emissao_id)
                self.meses_com_nota_paga.add((vinculo_id, competencia))
            elif mes_inteiro:
                self.meses.add((vinculo_id, competencia))

    def paga(self, emissao_id: uuid.UUID, vinculo_id: uuid.UUID, competencia: str) -> bool:
        return emissao_id in self.notas or (vinculo_id, competencia) in self.meses

    def mes_pago(self, vinculo_id: uuid.UUID, competencia: str) -> bool:
        chave = (vinculo_id, competencia)
        return chave in self.meses or chave in self.meses_com_nota_paga


def _notas(db: Session) -> list[dict]:
    """Uma linha por nota cobrável. Só as colunas necessárias (nada de
    XML/snapshot)."""
    emissoes = (
        db.query(
            Emissao.id, Emissao.prestador_tomador_id, Emissao.competencia, Emissao.estado,
            Emissao.valor, Emissao.criado_em, Emissao.n_dps, PrestadorTomador.apelido,
        )
        .join(PrestadorTomador, PrestadorTomador.id == Emissao.prestador_tomador_id)
        # Notas de vendedores da Shopee não têm cobrança própria: a Shopee
        # paga tudo junto na nota dela (01/10/2026).
        .filter(Emissao.estado.in_(ESTADOS_COBRAVEIS), Emissao.tomador_documento.is_(None))
        .order_by(Emissao.competencia, Emissao.criado_em, Emissao.n_dps)
        .all()
    )
    return [
        {
            "vinculo_id": e.prestador_tomador_id, "apelido": e.apelido, "competencia": e.competencia, "emissao_id": e.id,
            "estado": e.estado, "valor": e.valor, "quantidade": 1, "emitida_em": e.criado_em, "n_dps": e.n_dps,
        }
        for e in emissoes
    ]


def calcular(db: Session) -> tuple[list[dict], Baixas]:
    """Notas + baixas, pra reaproveitar numa mesma tela."""
    return _notas(db), Baixas(db)


def nota_do_recebimento(db: Session, vinculo_id: uuid.UUID, competencia: str, valor) -> uuid.UUID | None:
    """Qual nota um recebimento de (tomador, mês, valor) paga, quando a
    pessoa não escolheu: entre as EM ABERTO do tomador naquele mês, a do
    mesmo valor; senão a de valor mais próximo. Sem nota em aberto no mês =
    None: é dinheiro que caiu antes da nota (nunca cai numa nota já paga)."""
    notas, baixas = calcular(db)
    abertas = [
        n for n in notas
        if n["vinculo_id"] == vinculo_id and n["competencia"] == competencia
        and not baixas.paga(n["emissao_id"], vinculo_id, competencia)
    ]
    if not abertas:
        return None
    alvo = Decimal(str(valor))
    return min(abertas, key=lambda n: abs(n["valor"] - alvo))["emissao_id"]


def recebimentos_sem_nota(db: Session, desde: str | None = None) -> list[dict]:
    """O lado contrário do "a receber": dinheiro que caiu sem nota — caso do
    Mercado Livre e da Amazon, que pagam antes e a nota sai depois. A tela
    oferece gerar a nota daquele recebimento (POST /api/dps com
    pagamento_id) ou ligá-lo a uma nota que já existe.

    Recebimento novo sem nota entra sempre. Pagamento antigo (`mes_inteiro`)
    só quando o tomador não tem nota nenhuma naquele mês."""
    com_nota = {
        (v, c) for v, c in db.query(Emissao.prestador_tomador_id, Emissao.competencia)
        .filter(Emissao.estado.notin_(("cancelada", "substituida")), Emissao.tomador_documento.is_(None)).distinct()
    }
    query = (
        db.query(PagamentoRecebido, PrestadorTomador.apelido)
        .join(PrestadorTomador, PrestadorTomador.id == PagamentoRecebido.prestador_tomador_id)
        .filter(PrestadorTomador.sem_nota.is_(False), PagamentoRecebido.emissao_id.is_(None))
    )
    if desde:
        query = query.filter(PagamentoRecebido.competencia >= desde)
    grupos: dict[tuple, dict] = {}
    for p, apelido in query.order_by(PagamentoRecebido.competencia, PagamentoRecebido.criado_em):
        mes = (p.prestador_tomador_id, p.competencia)
        if p.mes_inteiro and mes in com_nota:
            continue
        # Recebimento novo: uma linha por recebimento (cada um pode virar uma
        # nota). Histórico: junto por tomador + mês, como antes.
        chave = mes if p.mes_inteiro else (p.id,)
        g = grupos.setdefault(chave, {
            "pagamento_id": p.id, "vinculo_id": p.prestador_tomador_id, "apelido": apelido,
            "competencia": p.competencia, "valor": Decimal(0), "data_recebimento": p.data_recebimento,
            "chave": f"semnota:{p.prestador_tomador_id}:{p.competencia}" if p.mes_inteiro else f"semnota:{p.id}",
        })
        g["valor"] += p.valor
    return [{**g, "valor": float(g["valor"])} for g in grupos.values()]


def notas_em_aberto(db: Session, hoje: datetime.date | None = None, base: tuple | None = None) -> list[dict]:
    """Notas sem baixa, da mais antiga pra mais nova."""
    hoje = hoje or hoje_br()
    notas, baixas = base or calcular(db)
    abertas = []
    for g in notas:
        if baixas.paga(g["emissao_id"], g["vinculo_id"], g["competencia"]):
            continue
        emitida = data_local(g["emitida_em"]) or hoje
        abertas.append({**g, "valor": float(g["valor"]), "emitida_em": emitida, "dias_em_aberto": (hoje - emitida).days})
    return sorted(abertas, key=lambda g: (g["competencia"], g["apelido"]))


def totais(db: Session, base: tuple | None = None) -> dict:
    notas, baixas = base or calcular(db)
    a_receber, qtd_aberta, qtd_recebida = Decimal(0), 0, 0
    for g in notas:
        if baixas.paga(g["emissao_id"], g["vinculo_id"], g["competencia"]):
            qtd_recebida += 1
        else:
            a_receber += g["valor"]
            qtd_aberta += 1
    recebido = db.query(func.coalesce(func.sum(PagamentoRecebido.valor), 0)).scalar()
    return {
        "a_receber_total": float(a_receber),
        "notas_a_receber": qtd_aberta,
        "recebido_total": float(recebido or 0),
        "notas_recebidas": qtd_recebida,
    }


def avisos_abertas_ha_muito(db: Session, hoje: datetime.date | None = None, limite: int = 5, base: tuple | None = None) -> list[dict]:
    antigas = [g for g in notas_em_aberto(db, hoje, base) if g["dias_em_aberto"] > DIAS_ABERTA_ALERTA]
    avisos = []
    for g in antigas[:limite]:
        ano, mes = g["competencia"].split("-")
        valor = f"R$ {g['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        avisos.append({
            "tipo": "nota_aberta_antiga",
            "titulo": g["apelido"],
            "mensagem": f"Nota de {mes}/{ano} ({valor}) sem pagamento há {g['dias_em_aberto']} dias.",
            "link": "/app/financeiro#a-receber",
            "link_label": "Dar baixa ou cobrar",
        })
    if len(antigas) > limite:
        avisos.append({
            "tipo": "nota_aberta_antiga",
            "titulo": f"Mais {len(antigas) - limite} nota(s) em aberto há mais de dois meses",
            "mensagem": "Veja a lista completa em Financeiro › A receber.",
            "link": "/app/financeiro#a-receber",
            "link_label": "Ver todas",
        })
    return avisos


def conciliar(db: Session, prestador_id: uuid.UUID, pares: list[tuple[uuid.UUID, str]]) -> int:
    """Dá baixa sem valor (origem 'conciliacao') nas notas em aberto dos
    (tomador, mês) pedidos — eram controladas em outra plataforma; saem do
    "a receber" sem mexer no total recebido."""
    alvo = set(pares)
    feitos = 0
    for n in notas_em_aberto(db):
        if (n["vinculo_id"], n["competencia"]) not in alvo:
            continue
        db.add(PagamentoRecebido(
            id=uuid.uuid4(), prestador_tomador_id=n["vinculo_id"], prestador_id=prestador_id, competencia=n["competencia"],
            valor=Decimal(0), origem="conciliacao", emissao_id=n["emissao_id"],
        ))
        feitos += 1
    db.flush()
    return feitos


def desfazer_baixa(db: Session, emissao: Emissao) -> int:
    """Desfaz a baixa de UMA nota. Pagamento ligado a ela é apagado. Se ela
    estava coberta por um pagamento do mês inteiro (histórico), ele passa a
    valer só pras outras notas do mês: fica ligado a uma delas e as demais
    ganham uma baixa sem valor — o total recebido não muda."""
    vinculo_id, competencia = emissao.prestador_tomador_id, emissao.competencia
    removidos = (
        db.query(PagamentoRecebido).filter(PagamentoRecebido.emissao_id == emissao.id).delete(synchronize_session=False)
    )
    do_mes = (
        db.query(PagamentoRecebido)
        .filter(
            PagamentoRecebido.prestador_tomador_id == vinculo_id, PagamentoRecebido.competencia == competencia,
            PagamentoRecebido.emissao_id.is_(None), PagamentoRecebido.mes_inteiro.is_(True),
        )
        .order_by(PagamentoRecebido.criado_em)
        .all()
    )
    if not do_mes:
        db.flush()
        return removidos
    outras = [
        n for n in _notas(db)
        if n["vinculo_id"] == vinculo_id and n["competencia"] == competencia and n["emissao_id"] != emissao.id
    ]
    if not outras:
        for p in do_mes:
            db.delete(p)
        db.flush()
        return removidos + len(do_mes)
    ja_ligadas = {
        e for (e,) in db.query(PagamentoRecebido.emissao_id).filter(PagamentoRecebido.emissao_id.in_([n["emissao_id"] for n in outras]))
    }
    for p in do_mes:
        p.emissao_id = outras[0]["emissao_id"]
        p.mes_inteiro = False
    ja_ligadas.add(outras[0]["emissao_id"])
    for n in outras[1:]:
        if n["emissao_id"] in ja_ligadas:
            continue
        db.add(PagamentoRecebido(
            id=uuid.uuid4(), prestador_tomador_id=vinculo_id, prestador_id=emissao.prestador_id, competencia=competencia,
            valor=Decimal(0), origem="conciliacao", emissao_id=n["emissao_id"],
        ))
    db.flush()
    return removidos + 1
