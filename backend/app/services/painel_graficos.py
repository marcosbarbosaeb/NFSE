"""Gráficos da Visão geral (05/10/2026): "faltam algumas ferramentas gráficas".

Só leitura, duas consultas agrupadas (nada de trazer nota por nota pra tela):

- `serie`: o valor das notas de cada um dos últimos 12 meses, terminando na
  competência pedida — mesma regra do "Faturado no mês" da Visão geral
  (`ESTADOS_FATURADOS`: gerada, assinada, enviada ou confirmada);
- `por_tomador`: quanto cada tomador somou em notas no ano da competência.
  As notas de vendedores (relatório do marketplace) são do vínculo do
  marketplace, então entram no nome dele — não viram centenas de linhas.
"""
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Emissao, PrestadorTomador
from app.services.dashboard import ESTADOS_FATURADOS, _somar_competencia
from app.tempo import hoje as hoje_br

MESES_DA_SERIE = 12


def graficos(db: Session, competencia: str | None = None) -> dict:
    if competencia is None:
        hoje = hoje_br()
        competencia = f"{hoje.year:04d}-{hoje.month:02d}"
    inicio = _somar_competencia(competencia, -(MESES_DA_SERIE - 1))
    por_mes = dict(
        db.query(Emissao.competencia, func.sum(Emissao.valor))
        .filter(Emissao.competencia >= inicio, Emissao.competencia <= competencia, Emissao.estado.in_(ESTADOS_FATURADOS))
        .group_by(Emissao.competencia)
    )
    serie = [
        {"competencia": c, "valor": float(por_mes.get(c) or 0)}
        for c in (_somar_competencia(inicio, i) for i in range(MESES_DA_SERIE))
    ]
    # Média só dos meses desde a primeira nota: empresa que começou há 3 meses
    # não tem a média puxada pra baixo pelos 9 meses em branco de antes.
    desde = next((i for i, p in enumerate(serie) if p["valor"]), None)
    com_nota = serie[desde:] if desde is not None else []
    media = round(sum(p["valor"] for p in com_nota) / len(com_nota), 2) if com_nota else None

    ano = competencia[:4]
    linhas = (
        db.query(Emissao.prestador_tomador_id, PrestadorTomador.apelido, func.sum(Emissao.valor), func.count(Emissao.id))
        .outerjoin(PrestadorTomador, Emissao.prestador_tomador_id == PrestadorTomador.id)
        .filter(Emissao.competencia.like(f"{ano}-%"), Emissao.estado.in_(ESTADOS_FATURADOS))
        .group_by(Emissao.prestador_tomador_id, PrestadorTomador.apelido)
        .all()
    )
    por_tomador = sorted(
        (
            {"vinculo_id": str(vid), "nome": apelido or "Tomador sem nome", "total": float(total or 0), "notas": notas}
            for vid, apelido, total, notas in linhas
        ),
        key=lambda x: (-x["total"], x["nome"].casefold()),
    )
    return {
        "competencia": competencia,
        "serie": serie,
        "media": media,
        "ano": ano,
        "por_tomador": por_tomador,
        "total_ano": round(float(sum((Decimal(str(t["total"])) for t in por_tomador), Decimal(0))), 2),
    }
