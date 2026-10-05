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


def registrar() -> None:
    eventos.ouvir("nota_criada", _nota_criada)
    eventos.ouvir("antes_de_trocar_nota", _antes_de_trocar_nota)
    eventos.ouvir("tomador_em_uso", _tomador_em_uso)
    eventos.ouvir("agenda", eventos_da_agenda)
