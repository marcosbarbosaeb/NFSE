"""Conciliação NOTAS x RECEBIMENTOS (05/10/2026) — pedido do Marcos: "existem
duas conciliações que devem ser feitas. Uma é na importação do extrato. E a
segunda, mais importante, é se as notas geradas foram pagas. Isso é
importante de aparecer de forma bem clara nesse ambiente de conciliação."

A do extrato (linha do banco x lançamento) mora em `conciliacao.py`. Esta
aqui responde, nota por nota: foi paga? quando? por quanto? está atrasada?

Como cada nota é julgada (ver `_julgar_nota` / `_julgar_lote`):

- **paga**: os recebimentos ligados a ela somam o valor da nota (diferença
  de até `TOLERANCIA`); guarda a data e por onde veio a baixa (extrato,
  baixa à mão, planilha);
- **paga a menor / a maior**: há recebimento ligado, mas a soma não bate —
  a diferença aparece. A pessoa pode dizer "está certo assim" (imposto
  retido, por exemplo): fica marcada como conferida e sai das pendências;
- **em aberto**: sem recebimento, dentro do prazo do tomador ("dias para
  recebimento"); sem prazo cadastrado, vale `DIAS_SEM_PRAZO` dias;
- **atrasada**: sem recebimento e o prazo já passou;
- **sem como saber o valor**: paga pelo histórico do mês (planilha antiga:
  o recebimento vale pro mês inteiro do tomador), considerada recebida sem
  valor (era controlada em outra plataforma) ou, nas notas de vendedores,
  paga junto com a nota do marketplace no mesmo mês. Contam como pagas, mas
  a tela avisa que o valor não dá pra conferir.

Notas de vendedores da Shopee (`tomador_documento` preenchido) são centenas
de notas pequenas pagas num depósito só: entram como UMA linha por tomador +
mês, e o que paga essa linha são os recebimentos do tomador naquele mês que
não estão ligados a uma nota comum. A baixa feita pela tela fica ligada a
uma das notas do mês (`emissao_id` da linha), que é como o calendário já
entendia "mês pago" (`Baixas.mes_pago`).

O módulo só LÊ as notas, e sempre por `a_receber.py` (o ponto de leitura
que o financeiro já usa pro "a receber") — nada do emissor é importado aqui.
Nada é gravado: confirmar uma sugestão usa as rotas de baixa/conciliação
que já existiam.
"""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session, joinedload

from app.deps import modulos_da_empresa
from app.financeiro import a_receber, classificar_extrato, conciliacao
from app.models import AjusteEvento, LancamentoBancario, PagamentoRecebido, PrestadorTomador, RegraExtrato
from app.tempo import data_local, hoje as hoje_br

# Diferença de centavos (arredondamento) ainda é "pago certo".
TOLERANCIA = Decimal("0.05")
# Sem prazo cadastrado no tomador: mesma régua do aviso "nota em aberto há
# mais de dois meses" (a_receber.DIAS_ABERTA_ALERTA).
DIAS_SEM_PRAZO = a_receber.DIAS_ABERTA_ALERTA
# Valor "parecido" pra sugerir uma linha do extrato: R$ 1,00 ou 0,5% da nota.
_PARECIDO_MINIMO = Decimal("1.00")
_PARECIDO_FRACAO = Decimal("0.005")
# Dinheiro que caiu ANTES da nota (quem paga adiantado) só é sugerido se o
# valor for o mesmo e o nome bater — e até este tanto de dias antes.
_DIAS_ANTES_DA_NOTA = 62
_MAX_CANDIDATOS = 6

_ABERTOS = ("em_aberto", "atrasada")
_COM_DIFERENCA = ("paga_a_menor", "paga_a_maior")


def _competencia(dia: datetime.date, meses_atras: int = 0) -> str:
    indice = dia.year * 12 + (dia.month - 1) - meses_atras
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _f(valor) -> float:
    return float(valor) if valor is not None else None


def _tolerancia_do_lote(quantidade: int) -> Decimal:
    """Centenas de notas somadas: um centavo de folga por nota."""
    return max(TOLERANCIA, Decimal("0.01") * quantidade)


class _Base:
    """Tudo que a conciliação lê do banco, de uma vez (sem consulta por
    nota): notas comuns, notas de vendedores já somadas por mês,
    recebimentos, clientes e os ajustes de data/avisos."""

    def __init__(self, db: Session):
        self.notas = a_receber._notas(db)
        self.lotes = a_receber.notas_em_lote(db)
        self.pagamentos = db.query(
            PagamentoRecebido.id, PagamentoRecebido.prestador_tomador_id, PagamentoRecebido.competencia,
            PagamentoRecebido.valor, PagamentoRecebido.data_recebimento, PagamentoRecebido.emissao_id,
            PagamentoRecebido.mes_inteiro, PagamentoRecebido.origem, PagamentoRecebido.criado_em,
        ).order_by(PagamentoRecebido.data_recebimento.nulls_last(), PagamentoRecebido.criado_em).all()
        self.vinculos = {
            v.id: v for v in db.query(
                PrestadorTomador.id, PrestadorTomador.apelido, PrestadorTomador.dias_para_recebimento,
                PrestadorTomador.sem_nota, PrestadorTomador.tomador_id,
            )
        }
        self.datas_ajustadas: dict[str, datetime.date] = {}
        self.ignoradas: set[str] = set()
        ajustes = db.query(AjusteEvento.tipo, AjusteEvento.chave, AjusteEvento.nova_data, AjusteEvento.oculto).filter(
            AjusteEvento.tipo.in_(("recebimento_previsto", "pendencia"))
        )
        for tipo, chave, nova_data, oculto in ajustes:
            if tipo == "pendencia" and oculto:
                self.ignoradas.add(chave)
            elif tipo == "recebimento_previsto" and nova_data is not None and not oculto:
                # A pessoa moveu a previsão dessa nota no calendário.
                self.datas_ajustadas[chave] = nova_data

        ids_comuns = {n["emissao_id"] for n in self.notas}
        pares_com_lote = {(g["vinculo_id"], g["competencia"]) for g in self.lotes}
        self.por_nota: dict[uuid.UUID, list] = {}
        self.do_mes: dict[tuple, list] = {}       # histórico: vale pro mês inteiro do tomador
        self.do_lote: dict[tuple, list] = {}      # pagam as notas de vendedores daquele mês
        self.soltos: list = []                    # recebimento novo, sem nota
        for p in self.pagamentos:
            par = (p.prestador_tomador_id, p.competencia)
            if p.emissao_id is not None and p.emissao_id in ids_comuns:
                self.por_nota.setdefault(p.emissao_id, []).append(p)
            elif par in pares_com_lote:
                # sem nota, ou ligado a uma das notas de vendedores do mês
                self.do_lote.setdefault(par, []).append(p)
                if p.emissao_id is None and p.mes_inteiro:
                    self.do_mes.setdefault(par, []).append(p)
            elif p.emissao_id is None and p.mes_inteiro:
                self.do_mes.setdefault(par, []).append(p)
            elif p.emissao_id is None:
                self.soltos.append(p)
            # (ligado a uma nota que não é mais cobrável — cancelada: não paga nada)


def _linha_pagamento(p) -> dict:
    return {"id": p.id, "valor": _f(p.valor), "data": p.data_recebimento, "origem": p.origem}


def _prazo(base: _Base, vinculo_id, emitida: datetime.date, chave_ajuste: str | None) -> tuple[datetime.date | None, bool]:
    """(vencimento, sem_prazo). Sem "dias para recebimento" no tomador, o
    limite é `DIAS_SEM_PRAZO` dias depois da nota."""
    if chave_ajuste and chave_ajuste in base.datas_ajustadas:
        return base.datas_ajustadas[chave_ajuste], False
    vinculo = base.vinculos.get(vinculo_id)
    dias = vinculo.dias_para_recebimento if vinculo is not None else None
    if dias is None:
        return emitida + datetime.timedelta(days=DIAS_SEM_PRAZO), True
    return emitida + datetime.timedelta(days=dias), False


def _em_aberto(item: dict, base: _Base, hoje: datetime.date, chave_ajuste: str | None) -> None:
    vencimento, sem_prazo = _prazo(base, item["vinculo_id"], item["emitida_em"], chave_ajuste)
    atraso = (hoje - vencimento).days
    item.update(
        status="atrasada" if atraso > 0 else "em_aberto", vencimento=vencimento, sem_prazo=sem_prazo,
        dias_atraso=max(atraso, 0), em_aberto=item["valor"],
    )


def _com_recebimento(item: dict, pagamentos: list, tolerancia: Decimal) -> None:
    recebido = sum((p.valor for p in pagamentos), Decimal(0))
    datas = [p.data_recebimento for p in pagamentos if p.data_recebimento]
    item["pagamentos"] = [_linha_pagamento(p) for p in pagamentos]
    item["pago_em"] = max(datas) if datas else None
    if recebido == 0:
        # "Considerar recebida": baixa sem valor (controlada em outra plataforma).
        item.update(status="paga", como="sem_valor", recebido=None, valor_incerto=True)
        return
    com_valor = [p for p in pagamentos if p.valor]
    diferenca = recebido - item["valor"]
    status = "paga" if abs(diferenca) <= tolerancia else ("paga_a_menor" if diferenca < 0 else "paga_a_maior")
    item.update(
        status=status, como=com_valor[-1].origem, recebido=recebido,
        diferenca=diferenca if status != "paga" else Decimal(0),
    )


def _item(tipo: str, chave: str, vinculo_id, competencia: str, valor: Decimal, emitida_em, hoje: datetime.date) -> dict:
    emitida = data_local(emitida_em) or hoje
    return {
        "chave": chave, "tipo": tipo, "vinculo_id": vinculo_id, "competencia": competencia, "valor": valor,
        "emissao_id": None, "n_dps": None, "estado": None, "quantidade": 1,
        "emitida_em": emitida, "dias_em_aberto": (hoje - emitida).days,
        "status": "em_aberto", "como": None, "recebido": Decimal(0), "diferenca": None, "em_aberto": Decimal(0),
        "pago_em": None, "vencimento": None, "dias_atraso": 0, "sem_prazo": False,
        "valor_incerto": False, "recebido_mes": None, "conferida": False, "antiga": False,
        "pagamentos": [], "sugestao": None, "candidatos": [],
        # nota do marketplace cujo depósito pagou também as notas de vendedores do mês
        "cobre_lote": None,
    }


def _julgar_nota(nota: dict, base: _Base, hoje: datetime.date) -> dict:
    item = _item("nota", f"nota:{nota['emissao_id']}", nota["vinculo_id"], nota["competencia"], nota["valor"], nota["emitida_em"], hoje)
    item.update(emissao_id=nota["emissao_id"], n_dps=nota["n_dps"], estado=nota["estado"])
    par = (nota["vinculo_id"], nota["competencia"])
    ligados = base.por_nota.get(nota["emissao_id"])
    if ligados:
        _com_recebimento(item, ligados, TOLERANCIA)
        item["conferida"] = f"diferenca:{nota['emissao_id']}" in base.ignoradas
    elif par in base.do_mes:
        # Histórico (planilha, baixas antigas): o recebimento é do mês inteiro
        # do tomador — a nota está paga, mas não dá pra conferir o valor dela.
        do_mes = base.do_mes[par]
        datas = [p.data_recebimento for p in do_mes if p.data_recebimento]
        item.update(
            status="paga", como="historico", recebido=None, valor_incerto=True,
            recebido_mes=sum((p.valor for p in do_mes), Decimal(0)), pago_em=max(datas) if datas else None,
        )
    else:
        _em_aberto(item, base, hoje, str(nota["emissao_id"]))
    return item


def _julgar_lote(lote: dict, base: _Base, hoje: datetime.date, pares_com_nota_paga: set) -> dict:
    par = (lote["vinculo_id"], lote["competencia"])
    item = _item("lote", f"lote:{par[0]}:{par[1]}", par[0], par[1], lote["valor"], lote["emitida_em"], hoje)
    # uma das notas do mês: é nela que a tela liga a baixa do depósito
    item.update(quantidade=lote["quantidade"], emissao_id=lote["emissao_id"])
    pagamentos = base.do_lote.get(par)
    if pagamentos:
        _com_recebimento(item, pagamentos, _tolerancia_do_lote(lote["quantidade"]))
        item["conferida"] = f"diferenca:{par[0]}:{par[1]}" in base.ignoradas
    elif par in pares_com_nota_paga:
        # Regra que já valia no calendário (`Baixas.mes_pago`): a nota do
        # próprio marketplace naquele mês foi paga — o depósito veio junto.
        item.update(status="paga", como="junto", recebido=None, valor_incerto=True)
    else:
        _em_aberto(item, base, hoje, None)
    return item


def _julgar_tudo(base: _Base, hoje: datetime.date) -> list[dict]:
    itens = [_julgar_nota(n, base, hoje) for n in base.notas]
    pares_com_nota_paga = {(i["vinculo_id"], i["competencia"]) for i in itens if i["status"] not in _ABERTOS and i["pagamentos"]}
    lotes = [_julgar_lote(g, base, hoje, pares_com_nota_paga) for g in base.lotes]
    for lote in lotes:
        if lote["como"] == "junto":
            _dividir_deposito_com_o_lote(lote, itens)
    return itens + lotes


def _dividir_deposito_com_o_lote(lote: dict, notas: list[dict]) -> None:
    """A Shopee deposita tudo de uma vez na nota dela: o que "sobra" nessa
    nota é o pagamento das notas de vendedores do mesmo mês. Então a conta
    é feita com as duas juntas (06/10/2026: "essa conta deveria fechar") —
    recebido x (nota + vendedores). Fechou: as duas ficam pagas, sem
    diferença. Não fechou: a diferença que aparece é só a que sobra de verdade."""
    par = (lote["vinculo_id"], lote["competencia"])
    candidatas = [
        n for n in notas
        if (n["vinculo_id"], n["competencia"]) == par and n["status"] == "paga_a_maior" and n["recebido"]
    ]
    if not candidatas:
        return
    nota = max(candidatas, key=lambda n: n["diferenca"])
    diferenca = nota["recebido"] - nota["valor"] - lote["valor"]
    tolerancia = TOLERANCIA + _tolerancia_do_lote(lote["quantidade"])
    nota["cobre_lote"] = {"quantidade": lote["quantidade"], "valor": _f(lote["valor"])}
    lote["valor_incerto"] = False
    if abs(diferenca) <= tolerancia:
        nota.update(status="paga", diferenca=Decimal(0))
    else:
        nota.update(status="paga_a_menor" if diferenca < 0 else "paga_a_maior", diferenca=diferenca)


def _pendente(item: dict) -> bool:
    return item["status"] == "atrasada" or (item["status"] in _COM_DIFERENCA and not item["conferida"]) or item["sugestao"] is not None


# --- Sugestões: linha do extrato que parece pagar uma nota em aberto ---

def _parecido(valor: Decimal) -> Decimal:
    return max(_PARECIDO_MINIMO, (valor * _PARECIDO_FRACAO).quantize(Decimal("0.01")))


def _sugerir(db: Session, base: _Base, abertos: list[dict]) -> list[dict]:
    """Liga cada entrada pendente do extrato à nota em aberto que ela parece
    pagar — só SUGERE (a pessoa confirma com um clique). Devolve as entradas
    pendentes, pra tela oferecer "ligar a um lançamento do extrato"."""
    linhas = (
        db.query(LancamentoBancario).filter(conciliacao._pendente(), LancamentoBancario.credito.is_(True))
        .order_by(LancamentoBancario.data.desc().nulls_last(), LancamentoBancario.criado_em.desc()).all()
    )
    saida = [{"id": l.id, "data": l.data, "descricao": l.descricao, "valor": _f(l.valor)} for l in linhas]
    if not linhas or not abertos:
        return saida
    vinculos = (
        db.query(PrestadorTomador).options(joinedload(PrestadorTomador.tomador))
        .filter(PrestadorTomador.excluido_em.is_(None)).all()
    )
    irmaos: dict[uuid.UUID, set] = {}
    for v in vinculos:
        # mesmo pagador com dois programas (AWIN e AWIN Rchlo): o nome no
        # extrato serve pros dois
        irmaos.setdefault(v.tomador_id, set()).add(v.id)
    regras = {r.chave: r.prestador_tomador_id for r in db.query(RegraExtrato).filter(RegraExtrato.credito.is_(True))}

    quem: dict[uuid.UUID, tuple[set, str | None]] = {}
    for l in linhas:
        lembrado = regras.get(l.chave or classificar_extrato.chave_da_descricao(l.descricao))
        por_nome = {v.id for v in classificar_extrato._candidatos_por_nome(l.descricao, vinculos)}
        ids = set(por_nome)
        if lembrado is not None:
            ids.add(lembrado)
        for v in vinculos:
            if v.id in ids:
                ids |= irmaos.get(v.tomador_id, set())
        quem[l.id] = (ids, "lembrado" if lembrado is not None else ("nome" if por_nome else None))

    por_valor_linhas: dict[Decimal, int] = {}
    for l in linhas:
        por_valor_linhas[l.valor] = por_valor_linhas.get(l.valor, 0) + 1
    por_valor_itens: dict[Decimal, int] = {}
    for i in abertos:
        por_valor_itens[i["valor"]] = por_valor_itens.get(i["valor"], 0) + 1

    pares = []
    for item in abertos:
        tolerancia = _tolerancia_do_lote(item["quantidade"])
        candidatos = []
        for l in linhas:
            ids, origem = quem[l.id]
            diferenca = l.valor - item["valor"]
            exato, parecido = abs(diferenca) <= tolerancia, abs(diferenca) <= _parecido(item["valor"])
            do_tomador = item["vinculo_id"] in ids
            dias = (l.data - item["emitida_em"]).days if l.data else None
            depois = dias is None or dias >= 0
            motivos, pontos, confianca = [], 0, None
            if exato:
                motivos.append("mesmo valor")
                pontos += 50
            elif parecido:
                motivos.append("valor quase igual")
                pontos += 25
            if do_tomador:
                motivos.append("como da última vez" if origem == "lembrado" else "nome do cliente no extrato")
                pontos += 30
            if not depois:
                motivos.append("caiu antes da nota")
                pontos -= 10
            elif dias is not None and dias <= 120:
                pontos += 5
            if exato and do_tomador and (depois or dias >= -_DIAS_ANTES_DA_NOTA):
                confianca = "alta"
            elif parecido and do_tomador and depois:
                confianca = "media"
            elif (
                exato and depois and not ids
                and por_valor_linhas[l.valor] == 1 and por_valor_itens[item["valor"]] == 1
            ):
                # sem nome nenhum na linha: só se for a única nota e a única
                # entrada com esse valor
                motivos.append("única nota em aberto desse valor")
                confianca = "media"
            if ids and not do_tomador:
                # a linha diz que é de outro cliente
                continue
            if confianca and f"sugestao:{l.id}:{item['chave']}" in base.ignoradas:
                # a pessoa já disse "não é esse": segue na lista pra ligar à mão
                confianca = None
            if pontos <= 0 or not (exato or parecido or do_tomador):
                continue
            candidato = {"lancamento_id": l.id, "motivos": motivos, "diferenca": _f(diferenca) if not exato else 0.0, "_pontos": pontos}
            candidatos.append(candidato)
            if confianca:
                pares.append((pontos, item, l, {**candidato, "confianca": confianca}))
        candidatos.sort(key=lambda c: -c["_pontos"])
        item["candidatos"] = [{k: v for k, v in c.items() if k != "_pontos"} for c in candidatos[:_MAX_CANDIDATOS]]

    # Cada linha sugere UMA nota e cada nota recebe UMA linha: a melhor primeiro.
    usadas: set = set()
    for _, item, l, sugestao in sorted(pares, key=lambda p: (-p[0], p[1]["emitida_em"])):
        if l.id in usadas or item["sugestao"] is not None:
            continue
        usadas.add(l.id)
        item["sugestao"] = {k: v for k, v in sugestao.items() if k != "_pontos"}
    return saida


# --- O painel da parte "As notas foram pagas?" ---

def _sem_nota(db: Session, base: _Base, desde: str | None) -> list[dict]:
    return [
        r for r in a_receber.recebimentos_sem_nota(db, desde)
        if r["chave"] not in base.ignoradas and f"semnota:{r['vinculo_id']}:{r['competencia']}" not in base.ignoradas
    ]


def _conta(item: dict) -> int:
    """Quanto um item pesa nas contagens. As notas de vendedores de um mês
    (Shopee) contam como UMA — "Shopee + vendedores" — e não como centenas
    (05/10/2026: "aí a pessoa perde o controle")."""
    return 1 if item["tipo"] == "lote" else item["quantidade"]


def _somar(itens: list[dict], base: _Base) -> dict:
    """Totais de um conjunto de notas. O recebido do histórico (pagamento do
    mês inteiro) entra uma vez por tomador + mês."""
    zero = Decimal(0)
    t = {
        "notas": 0, "pagas": 0, "faturado": zero, "recebido": zero, "em_aberto": zero, "notas_em_aberto": 0,
        "atrasado": zero, "notas_atrasadas": 0, "no_prazo": zero, "notas_no_prazo": 0,
        "diferenca": zero, "notas_com_diferenca": 0, "diferencas_a_conferir": 0, "notas_sem_valor": 0,
    }
    pares_do_historico: set = set()
    for i in itens:
        n = _conta(i)
        t["notas"] += n
        t["faturado"] += i["valor"]
        if i["status"] in _ABERTOS:
            t["em_aberto"] += i["valor"]
            t["notas_em_aberto"] += n
            chave = ("atrasado", "notas_atrasadas") if i["status"] == "atrasada" else ("no_prazo", "notas_no_prazo")
            t[chave[0]] += i["valor"]
            t[chave[1]] += n
            continue
        t["pagas"] += n
        if i["recebido"] is not None:
            t["recebido"] += i["recebido"]
        elif i["como"] == "historico":
            pares_do_historico.add((i["vinculo_id"], i["competencia"]))
        if i["valor_incerto"]:
            t["notas_sem_valor"] += n
        if i["status"] in _COM_DIFERENCA:
            t["notas_com_diferenca"] += n
            # Marcada como resolvida: não entra mais na diferença do período.
            if not i["conferida"]:
                t["diferenca"] += i["diferenca"]
                t["diferencas_a_conferir"] += 1
    for par in pares_do_historico:
        if par not in base.do_lote:
            t["recebido"] += sum((p.valor for p in base.do_mes.get(par, [])), Decimal(0))
    return {k: (_f(v) if isinstance(v, Decimal) else v) for k, v in t.items()}


def _saida_item(item: dict) -> dict:
    return {
        **item,
        "valor": _f(item["valor"]), "recebido": _f(item["recebido"]), "diferenca": _f(item["diferenca"]),
        "em_aberto": _f(item["em_aberto"]), "recebido_mes": _f(item["recebido_mes"]),
    }


def _ordem_do_grupo(grupo: dict) -> tuple:
    r = grupo["resumo"]
    return (
        0 if r["notas_atrasadas"] else 1 if grupo["pendencias"] else 2 if r["notas_em_aberto"] else 3,
        -r["em_aberto"], -r["faturado"], grupo["apelido"].lower(),
    )


def _clientes_que_pagaram(base: _Base, desde: str | None, ate: str | None) -> list[dict]:
    """Empresa só com o Financeiro: não há nota pra conferir. O que dá pra
    mostrar é de quem o dinheiro entrou no período."""
    grupos: dict[uuid.UUID, dict] = {}
    for p in base.pagamentos:
        if p.origem == "conciliacao" or (desde and p.competencia < desde) or (ate and p.competencia > ate):
            continue
        vinculo = base.vinculos.get(p.prestador_tomador_id)
        g = grupos.setdefault(p.prestador_tomador_id, {
            "vinculo_id": p.prestador_tomador_id, "nome": vinculo.apelido if vinculo is not None else "(cliente)",
            "recebido": Decimal(0), "recebimentos": 0, "ultimo": None,
        })
        g["recebido"] += p.valor
        g["recebimentos"] += 1
        if p.data_recebimento and (g["ultimo"] is None or p.data_recebimento > g["ultimo"]):
            g["ultimo"] = p.data_recebimento
    return sorted(({**g, "recebido": _f(g["recebido"])} for g in grupos.values()), key=lambda g: -g["recebido"])


def painel(
    db: Session, prestador_id: uuid.UUID, *, desde: str | None = None, ate: str | None = None, tudo: bool = False,
    hoje: datetime.date | None = None,
) -> dict:
    """A parte "As notas foram pagas?" inteira. Período pela competência da
    nota: de `desde` (padrão: três meses atrás) até `ate` — mais as notas
    mais antigas que continuam em aberto (ou com diferença por conferir).
    `tudo`: sem data de início. Só leitura."""
    hoje = hoje or hoje_br()
    desde = None if tudo else (desde or _competencia(hoje, 3))
    emissor = "emissor" in modulos_da_empresa(db, prestador_id)
    base = _Base(db)
    periodo = {"desde": desde, "ate": ate, "antigas": 0}
    if not emissor and not base.notas and not base.lotes:
        # Só o Financeiro e nenhuma nota guardada: não há o que conferir aqui.
        return {
            "modo": "recebimentos", "emissor": False, "periodo": periodo, "tolerancia": _f(TOLERANCIA),
            "resumo": _somar([], base), "estado": _estado([], []), "tomadores": [], "lancamentos": [],
            "recebimentos_sem_nota": [], "clientes": _clientes_que_pagaram(base, desde, ate),
        }

    todos = _julgar_tudo(base, hoje)
    _lancamentos = _sugerir(db, base, [i for i in todos if i["status"] in _ABERTOS])

    def no_periodo(i: dict) -> bool:
        return (desde is None or i["competencia"] >= desde) and (ate is None or i["competencia"] <= ate)

    itens = []
    for i in todos:
        if no_periodo(i):
            itens.append(i)
        elif desde is not None and i["competencia"] < desde and (i["status"] in _ABERTOS or _pendente(i)):
            # mais antiga que o período, mas ainda sem resolver: nunca some
            i["antiga"] = True
            periodo["antigas"] += i["quantidade"]
            itens.append(i)

    grupos: dict[uuid.UUID, dict] = {}
    for i in itens:
        vinculo = base.vinculos.get(i["vinculo_id"])
        g = grupos.setdefault(i["vinculo_id"], {
            "vinculo_id": i["vinculo_id"], "apelido": vinculo.apelido if vinculo is not None else "(cliente)",
            "prazo_dias": vinculo.dias_para_recebimento if vinculo is not None else None, "itens": [],
        })
        g["itens"].append(i)
    tomadores = []
    for g in grupos.values():
        g["itens"].sort(key=lambda i: (i["competencia"], i["emitida_em"], i["n_dps"] or 0), reverse=True)
        g["resumo"] = _somar(g["itens"], base)
        g["pendencias"] = sum(1 for i in g["itens"] if _pendente(i))
        g["itens"] = [_saida_item(i) for i in g["itens"]]
        tomadores.append(g)
    tomadores.sort(key=_ordem_do_grupo)

    sem_nota = _sem_nota(db, base, _competencia(hoje, 12)) if emissor else []
    return {
        "modo": "notas", "emissor": emissor, "periodo": periodo, "tolerancia": _f(TOLERANCIA),
        "resumo": _somar(itens, base), "estado": _estado(itens, sem_nota), "tomadores": tomadores,
        "lancamentos": _lancamentos, "recebimentos_sem_nota": sem_nota, "clientes": [],
    }


def _estado(itens: list[dict], sem_nota: list[dict]) -> dict:
    atrasadas = sum(1 for i in itens if i["status"] == "atrasada")
    diferencas = sum(1 for i in itens if i["status"] in _COM_DIFERENCA and not i["conferida"])
    # sugestão em nota atrasada já está contada em "atrasadas"
    sugestoes = sum(1 for i in itens if i["sugestao"] is not None)
    pendencias = sum(1 for i in itens if _pendente(i)) + len(sem_nota)
    return {
        "ok": pendencias == 0, "pendencias": pendencias, "atrasadas": atrasadas, "diferencas": diferencas,
        "sugestoes": sugestoes, "sem_nota": len(sem_nota),
        "no_prazo": sum(1 for i in itens if i["status"] == "em_aberto"),
    }


# --- A parte do extrato, em números, e o fechamento do mês ---

def resumo_extrato(db: Session) -> dict:
    """Números da conciliação do extrato: quantas linhas vieram do banco,
    quantas viraram recebimento/despesa, quantas faltam e quantas a pessoa
    mandou ignorar; o período coberto e o último arquivo importado."""
    pendente = conciliacao._pendente()
    total, pendentes, entradas, ignoradas, primeira, ultima = db.query(
        func.count(LancamentoBancario.id),
        func.coalesce(func.sum(case((pendente, 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(pendente, LancamentoBancario.credito.is_(True)), 1), else_=0)), 0),
        func.coalesce(func.sum(case((LancamentoBancario.status == "ignorado", 1), else_=0)), 0),
        func.min(LancamentoBancario.data), func.max(LancamentoBancario.data),
    ).one()
    ultimo = (
        db.query(LancamentoBancario.arquivo, LancamentoBancario.criado_em)
        .order_by(LancamentoBancario.criado_em.desc()).first()
    )
    pendentes, entradas, ignoradas = int(pendentes), int(entradas), int(ignoradas)
    return {
        "linhas": total, "classificadas": total - pendentes - ignoradas, "pendentes": pendentes,
        "pendentes_entradas": entradas, "pendentes_saidas": pendentes - entradas, "ignoradas": ignoradas,
        "de": primeira, "ate": ultima,
        "ultimo_arquivo": ultimo.arquivo if ultimo is not None else None,
        "ultimo_importado_em": data_local(ultimo.criado_em) if ultimo is not None else None,
        "ok": pendentes == 0,
    }


def _extrato_por_mes(db: Session, desde: datetime.date) -> dict[str, dict]:
    mes = func.to_char(LancamentoBancario.data, "YYYY-MM")
    linhas = (
        db.query(mes, func.count(LancamentoBancario.id), func.coalesce(func.sum(case((conciliacao._pendente(), 1), else_=0)), 0))
        .filter(LancamentoBancario.data >= desde).group_by(mes).all()
    )
    return {m: {"linhas": n, "pendentes": int(p)} for m, n, p in linhas}


def _fechamentos(db: Session, itens: list[dict], hoje: datetime.date, meses: int = 3) -> list[dict]:
    """O mês está fechado? Junta as duas conciliações, mês a mês (o atual e
    os anteriores): notas daquele mês pagas + linhas do extrato daquele mês
    classificadas.

    - "pendente": nota atrasada, diferença por conferir ou linha do extrato
      sem classificar;
    - "aguardando": só falta cair o que ainda está dentro do prazo;
    - "fechado": tudo pago e classificado;
    - "vazio": nada naquele mês (sem nota e sem extrato)."""
    competencias = [_competencia(hoje, n) for n in range(meses)]
    ano, mes = map(int, competencias[-1].split("-"))
    extrato = _extrato_por_mes(db, datetime.date(ano, mes, 1))
    saida = []
    for competencia in competencias:
        do_mes = [i for i in itens if i["competencia"] == competencia]
        notas = sum(_conta(i) for i in do_mes)
        atrasadas = sum(_conta(i) for i in do_mes if i["status"] == "atrasada")
        no_prazo = sum(_conta(i) for i in do_mes if i["status"] == "em_aberto")
        diferencas = sum(1 for i in do_mes if i["status"] in _COM_DIFERENCA and not i["conferida"])
        linhas = extrato.get(competencia, {"linhas": 0, "pendentes": 0})
        if atrasadas or diferencas or linhas["pendentes"]:
            estado = "pendente"
        elif no_prazo:
            estado = "aguardando"
        elif notas or linhas["linhas"]:
            estado = "fechado"
        else:
            estado = "vazio"
        saida.append({
            "competencia": competencia, "estado": estado, "em_andamento": competencia == competencias[0],
            "notas": notas, "notas_pagas": notas - atrasadas - no_prazo, "notas_atrasadas": atrasadas,
            "notas_no_prazo": no_prazo, "diferencas": diferencas,
            "extrato_linhas": linhas["linhas"], "extrato_pendentes": linhas["pendentes"],
            # quantas notas de vendedores estão dentro do(s) grupo(s) "em lote" do mês
            "notas_em_lote": sum(i["quantidade"] for i in do_mes if i["tipo"] == "lote"),
        })
    # Do mais antigo pro atual: a tela lê da esquerda pra direita.
    saida.reverse()
    return saida


def resumo(db: Session, prestador_id: uuid.UUID, hoje: datetime.date | None = None) -> dict:
    """O estado das DUAS conciliações num relance — pro cabeçalho da tela,
    pro menu e pro Financeiro: quantas pendências em cada uma e se os
    últimos meses estão fechados. Só leitura."""
    hoje = hoje or hoje_br()
    emissor = "emissor" in modulos_da_empresa(db, prestador_id)
    base = _Base(db)
    tem_notas = emissor or bool(base.notas) or bool(base.lotes)
    itens: list[dict] = []
    sem_nota: list[dict] = []
    if tem_notas:
        itens = _julgar_tudo(base, hoje)
        _sugerir(db, base, [i for i in itens if i["status"] in _ABERTOS])
        desde = _competencia(hoje, 3)
        # mesma régua da tela: o período padrão + o que ficou pra trás sem resolver
        visiveis = [i for i in itens if i["competencia"] >= desde or i["status"] in _ABERTOS or _pendente(i)]
        sem_nota = _sem_nota(db, base, _competencia(hoje, 12)) if emissor else []
        notas = {"aplica": True, **_estado(visiveis, sem_nota), **{
            k: v for k, v in _somar(visiveis, base).items() if k in ("notas", "pagas", "em_aberto", "atrasado")
        }}
    else:
        notas = {"aplica": False, **_estado([], [])}
    extrato = resumo_extrato(db)
    return {
        "notas": notas, "extrato": extrato,
        "pendencias": notas["pendencias"] + extrato["pendentes"],
        "fechamentos": _fechamentos(db, itens, hoje),
    }
