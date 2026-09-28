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
from calendar import monthrange
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AjusteEvento, Certificado, Emissao, Envio, PagamentoRecebido, Prestador
from app.services import a_receber as notas_abertas
from app.services.envios import listar_envios
from app.services.vinculos import listar_vinculos_ativos
from app.tempo import hoje as hoje_br

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
    hoje = hoje_br()
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


def _avisos_dia_de_gerar(db: Session, vinculos: list, hoje: datetime.date | None = None) -> list[dict]:
    """Pedido do Marcos (28/09/2026): "no dia anterior da data de emissão e
    no dia escolhido para o tomador, coloque o aviso em Precisa da sua
    atenção". Olha o mês REAL (hoje), não o navegado; respeita a data movida
    no calendário (AjusteEvento) e some assim que a nota do mês é gerada.
    Depois do dia, continua avisando que ficou pra trás."""
    hoje = hoje or hoje_br()
    competencia = f"{hoje.year:04d}-{hoje.month:02d}"
    ajustes = {a.chave: a for a in db.query(AjusteEvento).filter(AjusteEvento.tipo == "prazo_emissao").all()}
    avisos = []
    for v in vinculos:
        if v.dia_limite_emissao is None:
            continue
        dia = datetime.date(hoje.year, hoje.month, min(v.dia_limite_emissao, monthrange(hoje.year, hoje.month)[1]))
        ajuste = ajustes.get(f"{v.id}:{competencia}")
        if ajuste is not None:
            if ajuste.oculto:
                continue
            dia = ajuste.nova_data or dia
        faltam = (dia - hoje).days
        if faltam > 1:
            continue
        ja_gerou = (
            db.query(Emissao.id)
            .filter(Emissao.prestador_tomador_id == v.id, Emissao.competencia == competencia, Emissao.estado != "cancelada")
            .first()
            is not None
        )
        if ja_gerou:
            continue
        if faltam == 1:
            mensagem, tipo = f"Amanhã ({dia:%d/%m}) é o dia de gerar a nota de {v.apelido}.", "gerar_amanha"
        elif faltam == 0:
            mensagem, tipo = f"Hoje é o dia de gerar a nota de {v.apelido}.", "gerar_hoje"
        else:
            mensagem, tipo = f"O dia de gerar a nota de {v.apelido} era {dia:%d/%m} e ela ainda não foi gerada.", "gerar_atrasada"
        avisos.append({
            "tipo": tipo,
            "titulo": v.apelido,
            "mensagem": mensagem,
            "link": f"/app/nfse?gerar={v.id}&competencia={competencia}",
            "link_label": "Gerar agora",
        })
    ordem = {"gerar_atrasada": 0, "gerar_hoje": 1, "gerar_amanha": 2}
    return sorted(avisos, key=lambda a: ordem[a["tipo"]])


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

    # Tudo do mês em poucas consultas (antes eram ~4 por tomador): notas,
    # competências pagas e o último envio de cada nota.
    ids_vinculos = [v.id for v in vinculos]
    notas_por_vinculo: dict[uuid.UUID, list[Emissao]] = {}
    if ids_vinculos:
        for e in (
            db.query(Emissao)
            .filter(
                Emissao.prestador_tomador_id.in_(ids_vinculos),
                Emissao.competencia == competencia,
                Emissao.estado != "cancelada",
            )
            .order_by(Emissao.criado_em)
        ):
            notas_por_vinculo.setdefault(e.prestador_tomador_id, []).append(e)
    pagos = {
        v for (v,) in db.query(PagamentoRecebido.prestador_tomador_id).filter(PagamentoRecebido.competencia == competencia).distinct()
    }
    primeiras = [notas[0].id for notas in notas_por_vinculo.values()]
    ultimo_envio: dict[uuid.UUID, str] = {}
    if primeiras:
        for emissao_id, status in (
            db.query(Envio.emissao_id, Envio.status).filter(Envio.emissao_id.in_(primeiras)).order_by(Envio.criado_em)
        ):
            ultimo_envio[emissao_id] = status

    for vinculo in vinculos:
        # Shopee: várias notas no mês (uma por vendedor) — vira uma linha só,
        # somando os valores.
        do_mes = notas_por_vinculo.get(vinculo.id, [])
        emissao = do_mes[0] if do_mes else None
        valor_mes = sum((e.valor for e in do_mes if e.estado in notas_abertas.ESTADOS_COBRAVEIS), Decimal(0))
        if emissao is None:
            aguardando += 1
            continue

        emitidas += 1
        recebido = vinculo.id in pagos
        if not recebido and valor_mes:
            a_receber += valor_mes
            pagamentos_pendentes += 1

        emissoes.append({
            "emissao_id": emissao.id,
            "vinculo_id": vinculo.id,
            "quantidade": len(do_mes),
            "apelido": vinculo.apelido if len(do_mes) == 1 else f"{vinculo.apelido} ({len(do_mes)} notas)",
            "tomador_razao_social": vinculo.tomador.razao_social if len(do_mes) == 1 else "vários vendedores",
            "competencia": emissao.competencia,
            "valor": float(sum((e.valor for e in do_mes), Decimal(0))),
            "estado": emissao.estado,
            "estado_label": ESTADO_NFSE_LABEL.get(emissao.estado, emissao.estado),
            "envio_status": ultimo_envio.get(emissao.id),
            "pagamento_recebido": recebido,
            "tem_pdf": emissao.estado == "confirmado",
            "tem_email": bool(vinculo.email_para or vinculo.email_contato) if len(do_mes) == 1 else False,
            "homologacao": (emissao.tomador_snapshot or {}).get("tpAmb") == "2",
        })

    recebido_no_mes = _soma_pagamentos(db, prestador_id, competencia)
    recebido_mes_anterior = _soma_pagamentos(db, prestador_id, anterior)
    delta_recebimentos_pct = None
    if recebido_mes_anterior:
        delta_recebimentos_pct = float((recebido_no_mes - recebido_mes_anterior) / recebido_mes_anterior * 100)

    atencao: list[dict] = _avisos_dia_de_gerar(db, vinculos)
    base_abertas = notas_abertas.calcular(db)
    atencao += notas_abertas.avisos_abertas_ha_muito(db, base=base_abertas)
    cert = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if cert is not None and cert.validade is not None:
        dias = (cert.validade - hoje_br()).days
        if dias <= DIAS_ALERTA_CERTIFICADO:
            atencao.append({
                "tipo": "certificado_vencido" if dias < 0 else "certificado_vencendo",
                "titulo": "Certificado digital",
                "mensagem": (f"Venceu há {-dias} dia(s)." if dias < 0 else f"Vence em {dias} dia(s)."),
                "link": "/app/configuracoes#certificado",
                "link_label": "Enviar novo certificado",
            })

    # Marco 16, item 5 — alíquota de referência do Simples Nacional ainda
    # não foi confirmada NESTE mês (ver PATCH /api/prestador/aliquota e
    # docstring de Prestador.aliquota_atualizada_em). Só avisa — nunca
    # bloqueia emissão, mesma filosofia do resto desta lista.
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    hoje = hoje_br()
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
            "link": "/app/configuracoes#aliquota",
            "link_label": "Revisar alíquota" if prestador.aliquota_atual is not None else "Definir alíquota",
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
        **notas_abertas.totais(db, base_abertas),
        "emissoes": emissoes,
        "atencao": atencao,
    }


def proximos(db: Session, prestador_id: uuid.UUID, hoje: datetime.date | None = None) -> dict:
    """Card "Próximos eventos" da Visão geral (28/09/2026: "não está
    aparecendo, pode aparecer além de somente eventos"): o que tem pra fazer
    agora (assinar, mandar pra prefeitura, mandar pro tomador, gerar a nota
    do mês, cobrar) + a agenda dos próximos 30 dias."""
    from app.services.calendario import eventos_calendario

    hoje = hoje or hoje_br()
    competencia = f"{hoje.year:04d}-{hoje.month:02d}"
    pendencias: list[dict] = []

    # Filtra no banco (antes pegava as 200 mais recentes e filtrava aqui —
    # depois de um lote grande da Shopee, notas antigas com erro sumiam) e
    # checa "já enviada" com um NOT EXISTS em vez de uma consulta por nota.
    ja_enviada = (
        db.query(Envio.id).filter(Envio.emissao_id == Emissao.id, Envio.status == "enviado").exists()
    )
    ativas = (
        db.query(Emissao)
        .filter(
            (Emissao.estado.in_(("montado", "assinado", "erro")))
            | ((Emissao.estado == "confirmado") & ~ja_enviada)
        )
        .order_by(Emissao.criado_em.desc())
        .limit(500)
        .all()
    )
    for e in ativas:
        snap = e.tomador_snapshot or {}
        nome = snap.get("razao_social") if e.tomador_documento else snap.get("apelido")
        base = {"emissao_id": e.id, "valor": float(e.valor), "competencia": e.competencia, "link": f"/app/nfse/{e.id}"}
        if e.estado == "montado":
            pendencias.append({**base, "tipo": "assinar", "titulo": f"Assinar a nota de {nome}", "acao": "Assinar"})
        elif e.estado == "assinado":
            pendencias.append({**base, "tipo": "prefeitura", "titulo": f"Enviar à prefeitura a nota de {nome}", "acao": "Enviar"})
        elif e.estado == "erro":
            pendencias.append({**base, "tipo": "erro", "titulo": f"A prefeitura recusou a nota de {nome}", "acao": "Ver erro"})
        elif e.estado == "confirmado":
            pendencias.append({**base, "tipo": "enviar_tomador", "titulo": f"Mandar a nota pra {nome}", "acao": "Enviar"})

    competencia_tem_nota = {
        v for (v,) in db.query(Emissao.prestador_tomador_id).filter(Emissao.competencia == competencia, Emissao.estado != "cancelada")
    }
    for v in listar_vinculos_ativos(db):
        if v.id not in competencia_tem_nota:
            quando = f" (dia {v.dia_limite_emissao})" if v.dia_limite_emissao else ""
            pendencias.append({
                "tipo": "gerar", "titulo": f"Gerar a nota de {v.apelido}{quando}", "acao": "Gerar",
                "competencia": competencia, "link": f"/app/nfse?gerar={v.id}&competencia={competencia}",
            })

    for g in notas_abertas.notas_em_aberto(db, hoje)[:5]:
        pendencias.append({
            "tipo": "receber", "titulo": f"Receber de {g['apelido']}", "acao": "Dar baixa",
            "valor": g["valor"], "competencia": g["competencia"], "vinculo_id": g["vinculo_id"],
            "link": "/app/financeiro#a-receber",
        })

    eventos = eventos_calendario(db, prestador_id, hoje, hoje + datetime.timedelta(days=30))
    agenda = [
        {"data": ev["data"], "tipo": ev.get("categoria") or ev["tipo"], "titulo": ev.get("apelido") or ev["titulo"],
         "detalhe": ev["titulo"], "valor": ev.get("valor")}
        for ev in eventos
    ][:8]
    # Muitas notas na mesma etapa viram uma linha só ("Assinar 8 notas").
    agrupaveis = {
        "erro": ("{n} notas recusadas pela prefeitura", "Ver"),
        "prefeitura": ("Enviar {n} notas à prefeitura", "Enviar"),
        "assinar": ("Assinar {n} notas", "Assinar"),
        "enviar_tomador": ("Mandar {n} notas pros tomadores", "Enviar"),
    }
    agrupadas: list[dict] = []
    for tipo, (titulo, acao) in agrupaveis.items():
        do_tipo = [p for p in pendencias if p["tipo"] == tipo]
        if len(do_tipo) > 2:
            agrupadas.append({
                "tipo": tipo, "titulo": titulo.format(n=len(do_tipo)), "acao": acao, "link": "/app/nfse",
                "valor": round(sum(p.get("valor") or 0 for p in do_tipo), 2),
            })
        else:
            agrupadas += do_tipo
    agrupadas += [p for p in pendencias if p["tipo"] not in agrupaveis]
    ordem = {"erro": 0, "prefeitura": 1, "assinar": 2, "enviar_tomador": 3, "gerar": 4, "receber": 5}
    agrupadas.sort(key=lambda p: ordem.get(p["tipo"], 9))
    return {"pendencias": agrupadas[:10], "total_pendencias": len(agrupadas), "agenda": agenda}
