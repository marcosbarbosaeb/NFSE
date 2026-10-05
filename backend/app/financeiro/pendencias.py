"""O que o financeiro tem pra resolver (05/10/2026): recebimento sem nota,
nota a receber e lançamento do extrato sem classificar. Saiu da Visão geral
do emissor (app/services/dashboard.py) na separação dos módulos — a lista
agora é do financeiro."""
import datetime

from sqlalchemy.orm import Session

from app.financeiro import a_receber, conciliacao
from app.models import AjusteEvento
from app.tempo import hoje as hoje_br


def _tres_meses_atras(hoje: datetime.date) -> str:
    ano, mes = hoje.year, hoje.month - 3
    if mes < 1:
        ano, mes = ano - 1, mes + 12
    return f"{ano:04d}-{mes:02d}"


def pendencias(db: Session, hoje: datetime.date | None = None) -> list[dict]:
    hoje = hoje or hoje_br()
    ignoradas = {c for (c,) in db.query(AjusteEvento.chave).filter(AjusteEvento.tipo == "pendencia", AjusteEvento.oculto.is_(True))}
    lista: list[dict] = []

    # Recebimento sem nota (quem paga antes): oferece gerar a nota daquele
    # valor. Só os últimos meses, pra não virar lista de histórico.
    for r in a_receber.recebimentos_sem_nota(db, _tres_meses_atras(hoje)):
        if r["chave"] in ignoradas or f"semnota:{r['vinculo_id']}:{r['competencia']}" in ignoradas:
            continue
        lista.append({
            "tipo": "nota_recebimento", "titulo": f"Recebimento de {r['apelido']} sem nota", "acao": "Gerar nota",
            "valor": r["valor"], "competencia": r["competencia"], "vinculo_id": r["vinculo_id"], "chave": r["chave"],
            "link": f"/app/nfse?gerar={r['vinculo_id']}&valor={r['valor']}&origem=fin:pagamento:{r['pagamento_id']}",
        })

    sem_classificar = conciliacao.contar_pendentes(db)
    if sem_classificar and "conciliar" not in ignoradas:
        lista.append({
            "tipo": "conciliar", "acao": "Conciliar", "link": "/app/financeiro/conciliacao", "chave": "conciliar",
            "titulo": (
                "1 lançamento do extrato pra classificar" if sem_classificar == 1
                else f"{sem_classificar} lançamentos do extrato pra classificar"
            ),
        })

    a_receber_n = 0
    for g in a_receber.notas_em_aberto(db, hoje):
        chave = f"receber:{g['emissao_id']}"
        # (chave antiga, de quando a baixa era por tomador + mês)
        if chave in ignoradas or f"receber:{g['vinculo_id']}:{g['competencia']}" in ignoradas:
            continue
        lista.append({
            "tipo": "receber", "titulo": f"Receber de {g['apelido']}", "acao": "Dar baixa",
            "valor": g["valor"], "competencia": g["competencia"], "vinculo_id": g["vinculo_id"],
            "link": "/app/financeiro#a-receber", "chave": chave,
        })
        a_receber_n += 1
        if a_receber_n >= 5:
            break
    return lista
