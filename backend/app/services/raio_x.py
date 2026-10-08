"""Raio-X das empresas pro contador (07/10/2026).

O Marcos trouxe uma proposta de painel do contador (métricas gerais, tabela
"raio-x" por empresa, central de alertas, fechamento do mês). Aqui fica a
conta de cada empresa — só leitura, com o que a Ana realmente sabe:

- **Faturamento** = soma das notas AUTORIZADAS (as geradas aqui e as trazidas
  do Emissor Nacional), pela competência. Não é o RBT12 oficial: receita que
  não virou NFS-e por aqui (venda de produto, nota de outro sistema que não
  foi importada) não entra. A tela diz isso.
- **Limite do regime**: MEI R$ 81 mil e Simples R$ 4,8 milhões, os dois por
  ano-calendário (o do MEI é proporcional no ano de abertura — a Ana não
  sabe a data, então compara com o ano cheio).
- **Regime**: o que está no cadastro (`op_simples_nacional`). Quem não é do
  Simples aparece como "Fora do Simples": a Ana não sabe se é Lucro
  Presumido ou Real.

O financeiro (fechamento do mês, dinheiro que entrou sem nota) vem por
`app/eventos.py` — este módulo não importa nada de `app/financeiro`.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Certificado, Emissao, Prestador
from app.services.municipios import municipio_por_codigo

LIMITE_MEI = Decimal("81000")
LIMITE_SIMPLES = Decimal("4800000")
AVISO_PCT = 80          # "margem de segurança" do limite
CERT_ATENCAO_DIAS = 30
CERT_CRITICO_DIAS = 15

REGIMES = {"2": "MEI", "3": "Simples Nacional", "1": "Fora do Simples"}


def _mes(d: datetime.date, atras: int = 0) -> str:
    indice = d.year * 12 + d.month - 1 - atras
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _certificado(db: Session, prestador_id, hoje: datetime.date) -> dict:
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        return {"situacao": "falta", "validade": None, "dias": None}
    if registro.validade is None:
        return {"situacao": "ok", "validade": None, "dias": None}
    dias = (registro.validade - hoje).days
    situacao = "vencido" if dias < 0 else "vencendo" if dias <= CERT_ATENCAO_DIAS else "ok"
    return {"situacao": situacao, "validade": registro.validade, "dias": dias}


def da_empresa(db: Session, prestador: Prestador, hoje: datetime.date, financeiro: dict | None = None) -> dict:
    """Os números de uma empresa. O contexto da RLS já está nela."""
    emissor = "emissor" in (prestador.modulos or ["emissor"])
    atual, inicio_12m = _mes(hoje), _mes(hoje, 12)
    consulta = db.query(Emissao.competencia, func.count(Emissao.id), func.coalesce(func.sum(Emissao.valor), 0)).filter(
        Emissao.prestador_id == prestador.id, Emissao.estado == "confirmado",
        Emissao.competencia >= min(inicio_12m, f"{hoje.year:04d}-01"), Emissao.competencia <= atual,
    )
    if not get_settings().ambiente_teste:
        # nota de homologação não é faturamento (no ambiente de teste da
        # plataforma só existe ela — lá conta, senão não dá pra testar)
        consulta = consulta.filter(func.coalesce(Emissao.tomador_snapshot["tpAmb"].astext, "1") != "2")
    por_mes = {c: (int(n), Decimal(v)) for c, n, v in consulta.group_by(Emissao.competencia)}

    zero = Decimal(0)
    faturado_ano = sum((v for c, (_, v) in por_mes.items() if c[:4] == f"{hoje.year:04d}"), zero)
    # base do RBT12: os 12 meses ANTES do mês corrente
    faturado_12m = sum((v for c, (_, v) in por_mes.items() if inicio_12m <= c < atual), zero)
    limite = LIMITE_MEI if prestador.op_simples_nacional == "2" else LIMITE_SIMPLES if prestador.op_simples_nacional == "3" else None
    recusadas = db.query(func.count(Emissao.id)).filter(Emissao.prestador_id == prestador.id, Emissao.estado == "erro").scalar() if emissor else 0

    financeiro = financeiro or {}
    # Mês a mês (os 12 anteriores + o atual), pro gráfico e pra tabela da ficha.
    serie = [
        {"competencia": c, "notas": por_mes.get(c, (0, zero))[0], "valor": float(por_mes.get(c, (0, zero))[1])}
        for c in (_mes(hoje, n) for n in range(12, -1, -1))
    ]
    cidade = municipio_por_codigo(prestador.cod_municipio)
    return {
        "serie": serie,
        "municipio": f"{cidade['nome']}/{cidade['uf']}" if cidade else None,
        "inscricao_municipal": prestador.inscricao_municipal,
        "aliquota": float(prestador.aliquota_atual) if prestador.aliquota_atual is not None else None,
        "fechamentos": financeiro.get("fechamentos") or [],
        "regime": prestador.op_simples_nacional, "regime_nome": REGIMES.get(prestador.op_simples_nacional or "", "Não informado"),
        "competencia": atual,
        "notas_mes": por_mes.get(atual, (0, zero))[0], "faturado_mes": float(por_mes.get(atual, (0, zero))[1]),
        "faturado_ano": float(faturado_ano), "faturado_12m": float(faturado_12m),
        "limite": float(limite) if limite is not None else None,
        "limite_pct": round(float(faturado_ano / limite * 100), 1) if limite else None,
        "certificado": _certificado(db, prestador.id, hoje) if emissor else None,
        "recusadas": int(recusadas or 0),
        # do financeiro (None = a empresa não usa o módulo)
        "fechamento": financeiro.get("fechamento"),
        "sem_nota": financeiro.get("sem_nota"),
    }


def _brl(valor: float) -> str:
    inteiro = f"{valor:,.0f}".replace(",", ".")
    return f"R$ {inteiro}"


def alertas(raio: dict, *, bloqueada: bool = False) -> list[dict]:
    """O que pede a atenção do contador nesta empresa, do mais grave pro
    menos. `nivel`: "critico" ou "atencao". `link` = a tela onde se resolve."""
    saida: list[dict] = []
    cert = raio.get("certificado")
    if cert:
        if cert["situacao"] == "falta":
            saida.append({"tipo": "certificado", "nivel": "critico", "texto": "Sem certificado digital: a empresa não consegue emitir nota", "link": "/app/empresa?aba=certificado"})
        elif cert["situacao"] == "vencido":
            saida.append({"tipo": "certificado", "nivel": "critico", "texto": "Certificado digital vencido: a emissão está parada", "link": "/app/empresa?aba=certificado"})
        elif cert["situacao"] == "vencendo":
            dias = cert["dias"]
            quando = "hoje" if dias == 0 else "amanhã" if dias == 1 else f"em {dias} dias"
            saida.append({
                "tipo": "certificado", "nivel": "critico" if dias <= CERT_CRITICO_DIAS else "atencao",
                "texto": f"Certificado digital vence {quando}", "link": "/app/empresa?aba=certificado",
            })
    if raio.get("recusadas"):
        n = raio["recusadas"]
        saida.append({
            "tipo": "recusadas", "nivel": "critico",
            "texto": f"{n} nota{'s' if n != 1 else ''} recusada{'s' if n != 1 else ''} na emissão, esperando correção", "link": "/app/nfse",
        })
    pct, limite = raio.get("limite_pct"), raio.get("limite")
    if pct is not None and pct >= AVISO_PCT:
        nome = "do MEI" if raio["regime"] == "2" else "do Simples Nacional"
        if pct >= 100:
            texto = f"Passou do limite {nome}: {_brl(raio['faturado_ano'])} em notas no ano (limite {_brl(limite)})"
        else:
            texto = f"{pct:.0f}% do limite {nome}: {_brl(raio['faturado_ano'])} de {_brl(limite)} no ano"
        saida.append({"tipo": "limite", "nivel": "critico" if pct >= 100 else "atencao", "texto": texto, "link": "/app/nfse"})
    if raio.get("sem_nota"):
        n = raio["sem_nota"]
        saida.append({
            "tipo": "sem_nota", "nivel": "atencao",
            "texto": f"{n} recebimento{'s' if n != 1 else ''} sem nota fiscal correspondente", "link": "/app/financeiro/conciliacao",
        })
    if bloqueada:
        saida.append({"tipo": "assinatura", "nivel": "atencao", "texto": "Empresa sem assinatura: só dá pra consultar", "link": "/app"})
    saida.sort(key=lambda a: a["nivel"] != "critico")
    return saida


def resumo(clientes: list[dict]) -> dict:
    """Os cards do topo: a carteira inteira."""
    raios = [c["raio_x"] for c in clientes if c.get("raio_x")]
    todos = [a for c in clientes for a in c.get("alertas", [])]
    return {
        "empresas": len(clientes),
        "notas_mes": sum(r["notas_mes"] for r in raios),
        "faturado_mes": round(sum(r["faturado_mes"] for r in raios), 2),
        "pendencias": sum(c.get("total_pendencias", 0) for c in clientes),
        "alertas_criticos": sum(1 for a in todos if a["nivel"] == "critico"),
        "alertas": len(todos),
        "competencia": raios[0]["competencia"] if raios else None,
    }
