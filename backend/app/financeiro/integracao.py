"""O que o financeiro ouve dos outros módulos (05/10/2026, ver
app/eventos.py). É o ÚNICO lugar em que o financeiro reage ao emissor — e o
emissor não sabe que este arquivo existe.

Hoje a ligação é uma só: recebimento x nota.

- o financeiro pede a nota de um recebimento (a tela manda o emissor gerar
  com ``origem="fin:pagamento:<id>"``): quando a nota nasce, o recebimento
  passa a ser dela;
- uma nota não enviada é trocada por outra: o recebimento que estava ligado
  à antiga passa pra nova;
- o emissor quer apagar um tomador criado por notas importadas: o financeiro
  avisa se há recebimento dele;
- o calendário pergunta o que há pra agenda: o financeiro traz a previsão de
  recebimento e o que já caiu (app/financeiro/agenda.py).
"""
import uuid

from sqlalchemy.orm import Session

from app import eventos
from app.financeiro.agenda import eventos_da_agenda
from app.models import Emissao, PagamentoRecebido

PREFIXO = "fin:pagamento:"


def ligar_pagamento(pagamento: PagamentoRecebido, emissao: Emissao | None) -> None:
    """Esse recebimento paga ESTA nota — e conta no mês dela."""
    pagamento.emissao_id = emissao.id if emissao is not None else None
    pagamento.mes_inteiro = False
    if emissao is not None:
        pagamento.competencia = emissao.competencia


def _nota_criada(db: Session, emissao: Emissao, origem: str | None = None) -> None:
    if not origem or not origem.startswith(PREFIXO):
        return
    try:
        pagamento = db.get(PagamentoRecebido, uuid.UUID(origem[len(PREFIXO):]))
    except ValueError:
        pagamento = None
    if pagamento is None or pagamento.prestador_tomador_id != emissao.prestador_tomador_id:
        raise eventos.RecusaDeIntegracao("Recebimento não encontrado pra este tomador.")
    if pagamento.emissao_id is None or pagamento.emissao_id == emissao.id:
        ligar_pagamento(pagamento, emissao)


def _antes_de_trocar_nota(db: Session, emissao: Emissao):
    pagamentos = db.query(PagamentoRecebido).filter(PagamentoRecebido.emissao_id == emissao.id).all()
    if not pagamentos:
        return None

    def passar_pra_nova(nova: Emissao) -> None:
        for p in pagamentos:
            ligar_pagamento(p, nova)

    return passar_pra_nova


def _tomador_em_uso(db: Session, vinculo_id: uuid.UUID) -> bool:
    return db.query(PagamentoRecebido.id).filter(PagamentoRecebido.prestador_tomador_id == vinculo_id).first() is not None


def _resumo_pro_contador(db: Session, prestador_id: uuid.UUID) -> dict:
    """Pro painel do contador (app/services/acesso.py e raio_x.py): o que
    falta conferir na conciliação desta empresa, como ficou o fechamento do
    mês passado e quanto dinheiro entrou sem nota — só quantidades."""
    from app.financeiro import conciliacao_notas

    r = conciliacao_notas.resumo(db, prestador_id)
    # fechamentos vêm do mais antigo pro atual: o penúltimo é o mês passado
    anterior = r["fechamentos"][-2] if len(r["fechamentos"]) >= 2 else None
    return {
        "pendencias": _pendencias_da_empresa(r),
        "fechamento": {"competencia": anterior["competencia"], "estado": anterior["estado"]} if anterior else None,
        # os três últimos meses (do mais antigo pro atual), pro quadro de fechamento
        "fechamentos": [
            {"competencia": f["competencia"], "estado": f["estado"], "notas_atrasadas": f["notas_atrasadas"], "extrato_pendentes": f["extrato_pendentes"]}
            for f in r["fechamentos"]
        ],
        "sem_nota": int(r["notas"].get("sem_nota") or 0) if r["notas"].get("aplica") else 0,
    }


def _pendencias_da_empresa(r: dict) -> list[dict]:
    notas = r["notas"]["pendencias"] if r["notas"].get("aplica") else 0
    extrato = r["extrato"]["pendentes"]
    itens = []
    if notas:
        itens.append({
            "tipo": "conciliar_notas", "titulo": f"{notas} nota{'s' if notas != 1 else ''} pra conferir se {'foram pagas' if notas != 1 else 'foi paga'}",
            "link": "/app/financeiro/conciliacao", "quantidade": notas, "atrasada": False,
        })
    if extrato:
        itens.append({
            "tipo": "conciliar_extrato", "titulo": f"{extrato} linha{'s' if extrato != 1 else ''} do extrato sem classificar",
            "link": "/app/financeiro/conciliacao", "quantidade": extrato, "atrasada": False,
        })
    return itens


def _extrato_do_mes(db: Session, prestador_id: uuid.UUID, competencia: str) -> int:
    """Pasta do mês (app/services/pasta.py): quantas linhas de extrato do mês
    já foram importadas — o pedido "Extrato do banco" conta como entregue."""
    import datetime as _dt

    from app.models import LancamentoBancario

    ano, mes = int(competencia[:4]), int(competencia[5:7])
    inicio = _dt.date(ano, mes, 1)
    fim = _dt.date(ano + (mes == 12), mes % 12 + 1, 1)
    return (
        db.query(LancamentoBancario.id)
        .filter(LancamentoBancario.prestador_id == prestador_id, LancamentoBancario.data >= inicio, LancamentoBancario.data < fim)
        .count()
    )


def registrar() -> None:
    eventos.ouvir("nota_criada", _nota_criada)
    eventos.ouvir("antes_de_trocar_nota", _antes_de_trocar_nota)
    eventos.ouvir("tomador_em_uso", _tomador_em_uso)
    eventos.ouvir("agenda", eventos_da_agenda)
    eventos.ouvir("resumo_pro_contador", _resumo_pro_contador)
    eventos.ouvir("extrato_do_mes", _extrato_do_mes)
