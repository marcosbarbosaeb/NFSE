"""
Resumo do mês atual pro dashboard (tela "Visão geral") do novo frontend —
diferente de app/services/painel_status.py, que agrega um ANO inteiro, mês
a mês, pro fieldset antigo "Painel de status" (usado pelo painel embutido
em app/main.py). Aqui é UM mês só, com o detalhe por emissão que a tela de
dashboard pede (uma linha por nota, com status de NFS-e/envio/pagamento
lado a lado) — ver mockup do NotaFácil compartilhado por Marcos (imagens
"Visão geral" e o fluxo de 12 telas, 21/09/2026): isso é o "estado final"
combinado, adaptado ao que o modelo de dados atual sustenta sem inventar
conceito novo (ver Marco 12 no histórico do projeto).

Duas decisões de mapeamento que vale registrar — a tela mockada tem
conceitos que não existem 1:1 no motor de emissão hoje:

1. "Notas deste mês" / "Emitidas" / "Aguardando emissão": neste sistema,
   criar uma emissão já MONTA ela na hora (rascunho->montado é uma
   transição só dentro do mesmo POST /api/dps, ver api_criar_dps em
   app/main.py) — não existe hoje um fluxo onde uma nota fica "esperando
   ser emitida" depois de criada. O que existe e bate com a intenção da
   tela: quantos vínculos ATIVOS (= quantos fornecedores a Raiana fatura)
   já têm uma emissão ativa nesta competência vs. quantos ainda não têm
   nenhuma. "Emitida" aqui = já foi gerada pro vínculo+competência;
   "Aguardando emissão" = vínculo ativo sem emissão ainda nesta
   competência (o caso comum é ela ainda não ter rodado a importação de
   CSV/gerado manualmente esse fornecedor no mês). Se um dia existir um
   estado de rascunho de verdade exposto na UI, essa definição precisa ser
   revisitada.
2. "A receber" / "pagamentos pendentes": não existe um vínculo formal
   emissão<->pagamento — `pagamento_recebido` é por vínculo+competência,
   não por emissão (ver PagamentoRecebido em app/models.py), porque o
   registro de recebimento é manual e pode nem sempre corresponder 1:1 a
   uma nota (adiantamento, pagamento agrupado, etc.). Aproximação usada
   aqui: uma emissão ativa é considerada "recebida" se existe AO MENOS UM
   PagamentoRecebido pro mesmo vínculo+competência — não confere se o
   valor bate exatamente, então um pagamento parcial já conta como
   'recebido' nesta v1. "A receber" soma o valor das emissões ativas do
   mês sem nenhum pagamento associado.
"""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Certificado, Emissao, PagamentoRecebido, Prestador
from app.services.envios import listar_envios
from app.services.vinculos import listar_vinculos_ativos

ESTADO_NFSE_LABEL = {
    "rascunho": "Rascunho",
    "montado": "Emitida",
    "assinado": "Assinada",
    "submetido": "Submetida",
    "confirmado": "Confirmada",
    "cancelada": "Cancelada",
    "substituida": "Substituída",
    "erro": "Erro",
}

# Certificado com validade dentro desta janela (ou já vencido) vira alerta
# em "Precisa da sua atenção" — mesmo limiar não existia antes; escolhido
# por ser um prazo confortável pra renovar um A1 sem virar emergência.
DIAS_ALERTA_CERTIFICADO = 30


def _competencia_atual() -> str:
    hoje = datetime.date.today()
    return f"{hoje.year:04d}-{hoje.month:02d}"


def _somar_competencia(competencia: str, delta_meses: int) -> str:
    """delta_meses negativo anda pro passado (usado pra 'mês anterior' e
    pra série dos últimos N meses)."""
    ano, mes = (int(p) for p in competencia.split("-"))
    indice = (ano * 12 + (mes - 1)) + delta_meses
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _status_envio(db: Session, emissao: Emissao) -> str | None:
    """Status do envio mais recente (ver Envio em app/models.py — pode
    haver mais de uma tentativa/canal por emissão); None = nenhum envio
    registrado ainda ('Não enviado' na tela, não é um estado do banco)."""
    envios = listar_envios(db, emissao)
    return envios[0].status if envios else None


def _tem_pagamento(db: Session, prestador_tomador_id: uuid.UUID, competencia: str) -> bool:
    return (
        db.query(PagamentoRecebido)
        .filter_by(prestador_tomador_id=prestador_tomador_id, competencia=competencia)
        .first()
        is not None
    )


def _soma_pagamentos(db: Session, prestador_id: uuid.UUID, competencia: str) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(PagamentoRecebido.valor), 0))
        .filter_by(prestador_id=prestador_id, competencia=competencia)
        .scalar()
    )
    return Decimal(total)


def _serie_recebimentos(db: Session, prestador_id: uuid.UUID, competencia_final: str, meses: int = 6) -> list[dict]:
    """Últimos `meses` (incluindo o atual), pro gráfico de barras de
    'Recebimentos' do dashboard — soma bruta por competência, sem
    diferenciar por vínculo (a tela mostra um total só)."""
    serie = []
    for delta in range(-(meses - 1), 1):
        mes = _somar_competencia(competencia_final, delta)
        serie.append({"competencia": mes, "valor": float(_soma_pagamentos(db, prestador_id, mes))})
    return serie


def resumo_mes(db: Session, prestador_id: uuid.UUID, competencia: str | None = None) -> dict:
    """Monta o payload completo da tela Visão geral pra uma competência
    (padrão: mês corrente). Só leitura — não muda estado de nada."""
    competencia = competencia or _competencia_atual()
    anterior = _somar_competencia(competencia, -1)

    vinculos = listar_vinculos_ativos(db)
    emissoes: list[dict] = []
    emitidas = 0
    aguardando = 0
    a_receber = Decimal(0)
    pagamentos_pendentes = 0

    for vinculo in vinculos:
        emissao = (
            db.query(Emissao)
            .filter(
                Emissao.prestador_tomador_id == vinculo.id,
                Emissao.competencia == competencia,
                Emissao.estado != "cancelada",
            )
            .one_or_none()
        )
        if emissao is None:
            aguardando += 1
            continue

        emitidas += 1
        recebido = _tem_pagamento(db, vinculo.id, competencia)
        if not recebido:
            a_receber += emissao.valor
            pagamentos_pendentes += 1

        emissoes.append({
            "emissao_id": emissao.id,
            "apelido": vinculo.apelido,
            "tomador_razao_social": vinculo.tomador.razao_social,
            "competencia": emissao.competencia,
            "valor": float(emissao.valor),
            "estado": emissao.estado,
            "estado_label": ESTADO_NFSE_LABEL.get(emissao.estado, emissao.estado),
            "envio_status": _status_envio(db, emissao),
            "pagamento_recebido": recebido,
        })

    recebido_no_mes = _soma_pagamentos(db, prestador_id, competencia)
    recebido_mes_anterior = _soma_pagamentos(db, prestador_id, anterior)
    delta_recebimentos_pct = None
    if recebido_mes_anterior:
        delta_recebimentos_pct = float((recebido_no_mes - recebido_mes_anterior) / recebido_mes_anterior * 100)

    atencao: list[dict] = []
    cert = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if cert is not None and cert.validade is not None:
        dias = (cert.validade - datetime.date.today()).days
        if dias <= DIAS_ALERTA_CERTIFICADO:
            atencao.append({
                "tipo": "certificado_vencido" if dias < 0 else "certificado_vencendo",
                "titulo": "Certificado digital",
                "mensagem": (f"Venceu há {-dias} dia(s)." if dias < 0 else f"Vence em {dias} dia(s)."),
            })

    # Marco 16, item 5 — alíquota de referência do Simples Nacional ainda
    # não foi confirmada NESTE mês (ver PATCH /api/prestador/aliquota e
    # docstring de Prestador.aliquota_atualizada_em). Só avisa — nunca
    # bloqueia emissão, mesma filosofia do resto desta lista.
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    hoje = datetime.date.today()
    if prestador is not None and (
        prestador.aliquota_atualizada_em is None
        or (prestador.aliquota_atualizada_em.year, prestador.aliquota_atualizada_em.month) != (hoje.year, hoje.month)
    ):
        atencao.append({
            "tipo": "aliquota_pendente",
            "titulo": "Alíquota do Simples Nacional",
            "mensagem": (
                "Ainda não confirmada este mês — revise em Configurações antes de emitir notas."
                if prestador.aliquota_atual is not None
                else "Nenhuma alíquota de referência definida ainda — configure em Configurações."
            ),
        })

    return {
        "competencia": competencia,
        "total_vinculos": len(vinculos),
        "emitidas": emitidas,
        "aguardando": aguardando,
        "a_receber": float(a_receber),
        "pagamentos_pendentes": pagamentos_pendentes,
        "recebido_no_mes": float(recebido_no_mes),
        "recebido_mes_anterior": float(recebido_mes_anterior),
        "delta_recebimentos_pct": delta_recebimentos_pct,
        "serie_recebimentos": _serie_recebimentos(db, prestador_id, competencia),
        "emissoes": emissoes,
        "atencao": atencao,
    }
