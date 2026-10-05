"""Conciliação do extrato (05/10/2026) — pedido do Marcos: "se a pessoa
importar e não classificar, é interessante que ela consiga acessar uma aba
com lançamentos não classificados"; "uma tela com o importado de um lado e o
pendente do outro, de forma que o que não for baixado automaticamente possa
fazer a conciliação de receita e despesa manual".

Toda linha do extrato importado vira um `LancamentoBancario`. Na revisão da
importação a pessoa classifica o que quiser; o resto fica pendente e aparece
aqui, lado a lado com o que está em aberto no sistema:

- entrada (receita)  x  notas a receber        -> vira recebimento ligado à nota
- saída (despesa)    x  contas do mês a pagar  -> a conta fica paga

Quando não há par (dinheiro que caiu sem nota, despesa que não estava
prevista), a pessoa classifica na hora: tomador ou categoria.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Despesa, LancamentoBancario, PagamentoRecebido, PrestadorTomador
from app.financeiro import a_receber, classificar_extrato
from app.financeiro.pagamentos import registrar_pagamento


class ConciliacaoError(Exception):
    pass


def _texto(descricao: str | None) -> str:
    return " ".join((descricao or "").split())[:300] or "(sem descrição)"


def _centavos(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _pendente():
    """Pendente de verdade: nunca classificado, ou classificado mas o
    recebimento/despesa foi apagado depois."""
    return or_(
        LancamentoBancario.status == "pendente",
        and_(
            LancamentoBancario.status == "conciliado",
            LancamentoBancario.pagamento_id.is_(None), LancamentoBancario.despesa_id.is_(None),
        ),
    )


def guardar(db: Session, prestador_id: uuid.UUID, linhas: list[dict], arquivo: str | None = None) -> list[LancamentoBancario]:
    """Um lançamento por linha ({data, descricao, valor, credito}), na mesma
    ordem. Reimportar o mesmo extrato não duplica: a linha é reconhecida por
    data + valor + sentido + texto (e a posição, quando há duas iguais)."""
    vistos: dict[tuple, int] = {}
    saida = []
    for linha in linhas:
        descricao, valor = _texto(linha.get("descricao")), _centavos(linha["valor"])
        chave = (linha.get("data"), valor, bool(linha["credito"]), descricao)
        seq = vistos.get(chave, 0)
        vistos[chave] = seq + 1
        consulta = db.query(LancamentoBancario).filter(
            LancamentoBancario.valor == valor, LancamentoBancario.credito.is_(bool(linha["credito"])),
            LancamentoBancario.descricao == descricao, LancamentoBancario.seq == seq,
        )
        consulta = consulta.filter(
            LancamentoBancario.data == linha["data"] if linha.get("data") else LancamentoBancario.data.is_(None)
        )
        lanc = consulta.first()
        if lanc is None:
            lanc = LancamentoBancario(
                id=uuid.uuid4(), prestador_id=prestador_id, data=linha.get("data"), descricao=descricao, valor=valor,
                credito=bool(linha["credito"]), chave=classificar_extrato.chave_da_descricao(descricao), seq=seq,
                status="pendente", arquivo=(arquivo or "")[:200] or None,
            )
            db.add(lanc)
        saida.append(lanc)
    db.flush()
    return saida


def marcar(lanc: LancamentoBancario, *, pagamento_id: uuid.UUID | None = None, despesa_id: uuid.UUID | None = None) -> None:
    lanc.status = "conciliado"
    lanc.pagamento_id, lanc.despesa_id = pagamento_id, despesa_id
    lanc.credito = pagamento_id is not None


def contar_pendentes(db: Session) -> int:
    return db.query(LancamentoBancario.id).filter(_pendente()).count()


def _contas_a_pagar(db: Session) -> list[dict]:
    contas = (
        db.query(Despesa).filter(Despesa.pago.is_(False))
        .order_by(Despesa.competencia, Despesa.vencimento.nulls_last(), Despesa.categoria).all()
    )
    return [
        {
            "id": d.id, "nome": d.descricao or d.categoria, "categoria": d.categoria, "tipo": d.tipo,
            "competencia": d.competencia, "vencimento": d.vencimento, "valor": float(d.valor),
        }
        for d in contas
    ]


def painel(db: Session) -> dict:
    """Tudo que a tela precisa: lançamentos pendentes (com sugestão), notas a
    receber e contas a pagar."""
    pendentes = (
        db.query(LancamentoBancario).filter(_pendente())
        .order_by(LancamentoBancario.data.desc().nulls_last(), LancamentoBancario.criado_em.desc()).all()
    )
    contas = _contas_a_pagar(db)
    sugestoes = classificar_extrato.sugerir(db, pendentes, conferir_repetidos=False)
    apelidos = {v.id: v.apelido for v in db.query(PrestadorTomador)}
    notas = [
        {**n, "apelido": apelidos.get(n["vinculo_id"], "")} for n in classificar_extrato.notas_para_escolher(db)
    ]
    usadas: set[uuid.UUID] = set()
    lancamentos = []
    for lanc, sug in zip(pendentes, sugestoes):
        conta_id = None
        if not sug["credito"]:
            # conta a pagar do mesmo valor (uma só) — ou, sem valor igual, a
            # única da categoria lembrada naquele mês
            iguais = [c for c in contas if c["id"] not in usadas and abs(Decimal(str(c["valor"])) - lanc.valor) < Decimal("0.005")]
            mes = f"{lanc.data.year:04d}-{lanc.data.month:02d}" if lanc.data else None
            if len(iguais) != 1 and sug["origem_sugestao"] == "lembrado":
                iguais = [
                    c for c in contas
                    if c["id"] not in usadas and c["categoria"] == sug["categoria"] and (mes is None or c["competencia"] == mes)
                ]
            if len(iguais) == 1:
                conta_id = iguais[0]["id"]
                usadas.add(conta_id)
        lancamentos.append({
            "id": lanc.id, "data": lanc.data, "descricao": lanc.descricao, "valor": float(lanc.valor),
            "credito": sug["credito"] if sug["origem_sugestao"] == "lembrado" else lanc.credito,
            "vinculo_id": sug["vinculo_id"], "emissao_id": sug["emissao_id"], "nota_exata": bool(sug["nota"] and sug["nota"]["exata"]),
            "categoria": sug["categoria"], "tipo_despesa": sug["tipo_despesa"], "origem_sugestao": sug["origem_sugestao"],
            "despesa_id": conta_id,
        })
    cats = classificar_extrato.categorias(db)
    return {
        "lancamentos": lancamentos,
        "ignorados": db.query(LancamentoBancario.id).filter(LancamentoBancario.status == "ignorado").count(),
        "notas_abertas": notas,
        "contas_a_pagar": contas,
        "categorias": cats["despesas"],
        "categorias_retirada": cats["retiradas"],
    }


def _lancamento(db: Session, lancamento_id: uuid.UUID) -> LancamentoBancario:
    lanc = db.get(LancamentoBancario, lancamento_id)
    if lanc is None:
        raise ConciliacaoError("Lançamento não encontrado.")
    return lanc


def _mes(lanc: LancamentoBancario, competencia: str | None, hoje: date) -> str:
    if competencia:
        return competencia
    ref = lanc.data or hoje
    return f"{ref.year:04d}-{ref.month:02d}"


def como_receita(
    db: Session, lancamento_id: uuid.UUID, vinculo: PrestadorTomador, *, hoje: date,
    emissao_id: uuid.UUID | None = None, competencia: str | None = None,
) -> PagamentoRecebido:
    """A entrada vira um recebimento do tomador — ligado à nota escolhida
    (baixa) ou sem nota (dinheiro que caiu antes da nota)."""
    lanc = _lancamento(db, lancamento_id)
    if lanc.status == "conciliado" and (lanc.pagamento_id or lanc.despesa_id):
        raise ConciliacaoError("Esse lançamento já foi conciliado.")
    try:
        pagamento = registrar_pagamento(
            db, vinculo, competencia=_mes(lanc, competencia, hoje), valor=float(lanc.valor), data_recebimento=lanc.data,
            emissao_id=emissao_id, origem="extrato",
        )
    except ValueError as exc:
        raise ConciliacaoError(str(exc)) from exc
    marcar(lanc, pagamento_id=pagamento.id)
    classificar_extrato.lembrar(db, vinculo.prestador_id, lanc.descricao, credito=True, vinculo_id=vinculo.id)
    db.flush()
    return pagamento


def como_despesa(
    db: Session, lancamento_id: uuid.UUID, prestador_id: uuid.UUID, *, hoje: date,
    despesa_id: uuid.UUID | None = None, categoria: str | None = None, tipo: str = "despesa", competencia: str | None = None,
) -> Despesa:
    """A saída paga uma conta que estava em aberto (`despesa_id`) ou vira uma
    despesa nova da categoria escolhida."""
    lanc = _lancamento(db, lancamento_id)
    if lanc.status == "conciliado" and (lanc.pagamento_id or lanc.despesa_id):
        raise ConciliacaoError("Esse lançamento já foi conciliado.")
    if despesa_id is not None:
        despesa = db.get(Despesa, despesa_id)
        if despesa is None:
            raise ConciliacaoError("Conta não encontrada.")
        if despesa.pago:
            raise ConciliacaoError("Essa conta já está paga.")
        despesa.pago, despesa.pago_em, despesa.valor = True, lanc.data or hoje, lanc.valor
    else:
        if not (categoria or "").strip():
            raise ConciliacaoError("Escolha a categoria da despesa.")
        despesa = classificar_extrato.registrar_saida(
            db, prestador_id, categoria=categoria, competencia=_mes(lanc, competencia, hoje), valor=float(lanc.valor),
            descricao=lanc.descricao, data=lanc.data, tipo=tipo,
        )
    marcar(lanc, despesa_id=despesa.id)
    classificar_extrato.lembrar(db, prestador_id, lanc.descricao, credito=False, categoria=despesa.categoria, tipo=despesa.tipo)
    db.flush()
    return despesa


def ignorar(db: Session, lancamento_id: uuid.UUID, ignorar_: bool = True) -> None:
    """Movimentação que não é receita nem despesa do negócio (transferência
    entre contas próprias, aplicação, estorno): sai da lista."""
    lanc = _lancamento(db, lancamento_id)
    if lanc.status == "conciliado" and (lanc.pagamento_id or lanc.despesa_id):
        raise ConciliacaoError("Esse lançamento já foi conciliado.")
    lanc.status = "ignorado" if ignorar_ else "pendente"
    db.flush()


def trocar_tipo(db: Session, lancamento_id: uuid.UUID, credito: bool) -> None:
    lanc = _lancamento(db, lancamento_id)
    lanc.credito = credito
    db.flush()


def automatico(db: Session, prestador_id: uuid.UUID, hoje: date) -> int:
    """Concilia de uma vez as entradas que têm nota em aberto do mesmo valor."""
    vinculos = {v.id: v for v in db.query(PrestadorTomador)}
    feitos = 0
    for item in painel(db)["lancamentos"]:
        if item["credito"] and item["nota_exata"] and item["emissao_id"] and item["vinculo_id"] in vinculos:
            como_receita(db, item["id"], vinculos[item["vinculo_id"]], hoje=hoje, emissao_id=item["emissao_id"])
            feitos += 1
    return feitos


def listar_ignorados(db: Session) -> list[dict]:
    linhas = (
        db.query(LancamentoBancario).filter(LancamentoBancario.status == "ignorado")
        .order_by(LancamentoBancario.data.desc().nulls_last()).all()
    )
    return [{"id": l.id, "data": l.data, "descricao": l.descricao, "valor": float(l.valor), "credito": l.credito} for l in linhas]
