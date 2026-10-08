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
2. Nada de pagamento aqui (05/10/2026): o emissor e o financeiro são
   produtos separados. A Visão geral mostra o que é da nota — emitida,
   assinada, enviada — e quanto foi FATURADO (valor das notas); o que foi
   recebido é assunto do módulo financeiro.
"""
import datetime
from calendar import monthrange
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AjusteEvento, Certificado, Emissao, Envio, Prestador
from app.services.envios import listar_envios
from app.services.motor_emissao import motivo_da_recusa, recusa_corrigivel
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


# O que já saiu como nota (montado = gerada, ainda sem assinar). Rascunho,
# erro, cancelada e substituída não contam como faturamento.
ESTADOS_FATURADOS = ("montado", "assinado", "submetido", "confirmado")


def _faturado(db: Session, competencia: str) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(Emissao.valor), 0))
        .filter(Emissao.competencia == competencia, Emissao.estado.in_(ESTADOS_FATURADOS))
        .scalar()
    )
    return Decimal(total)


def _serie_faturamento(db: Session, competencia_final: str, meses: int = 6) -> list[dict]:
    """Últimos `meses` (incluindo o atual), pro gráfico de barras da Visão
    geral: valor das notas de cada mês."""
    pontos = []
    for delta in range(meses - 1, -1, -1):
        comp = _somar_competencia(competencia_final, -delta)
        pontos.append({"competencia": comp, "valor": float(_faturado(db, comp))})
    return pontos


def _avisos_dia_de_gerar(
    db: Session, vinculos: list, hoje: datetime.date | None = None, *, incluir_vespera: bool = True,
) -> list[dict]:
    """Pedido do Marcos (28/09/2026): "no dia anterior da data de emissão e
    no dia escolhido para o tomador, coloque o aviso em Precisa da sua
    atenção". Olha o mês REAL (hoje), não o navegado; respeita a data movida
    no calendário (AjusteEvento) e some assim que a nota do mês é gerada.
    Depois do dia, continua avisando que ficou pra trás.

    05/10/2026: o aviso da véspera continua na Visão geral ("não é
    pendência, mas é um ponto de atenção sim para a pessoa").
    Quem clicou em "ignorar este aviso" nos Próximos passos (atraso
    consciente) também não é cobrado aqui."""
    hoje = hoje or hoje_br()
    competencia = f"{hoje.year:04d}-{hoje.month:02d}"
    ajustes = {a.chave: a for a in db.query(AjusteEvento).filter(AjusteEvento.tipo == "prazo_emissao").all()}
    ignoradas = {
        c for (c,) in db.query(AjusteEvento.chave).filter(AjusteEvento.tipo == "pendencia", AjusteEvento.oculto.is_(True))
    }
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
        if faltam > (1 if incluir_vespera else 0):
            continue
        if f"gerar:{v.id}:{competencia}" in ignoradas:
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


def _data_lembrete_aliquota(db: Session, prestador: Prestador, hoje: datetime.date) -> datetime.date | None:
    """Dia em que a revisão da alíquota DESTE mês está marcada — a mesma
    conta do evento 'revisar_aliquota' do calendário (app/services/
    calendario.py): dia da regra do prestador (padrão 1), e o ajuste daquela
    ocorrência (AjusteEvento) manda — movida vale a nova data, ocultada não
    tem data (None)."""
    dia = prestador.dia_lembrete_aliquota or 1
    data = datetime.date(hoje.year, hoje.month, min(dia, monthrange(hoje.year, hoje.month)[1]))
    ajuste = (
        db.query(AjusteEvento)
        .filter_by(tipo="revisar_aliquota", chave=f"{hoje.year:04d}-{hoje.month:02d}")
        .one_or_none()
    )
    if ajuste is not None:
        if ajuste.oculto:
            return None
        data = ajuste.nova_data or data
    return data


def resumo_mes(
    db: Session, prestador_id: uuid.UUID, competencia: str | None = None, hoje: datetime.date | None = None,
) -> dict:
    """Monta o payload completo da tela Visão geral pra uma competência
    (padrão: mês corrente). Só leitura — não muda estado de nada.

    "Precisa da sua atenção" (`atencao`) é só o que está pendente AGORA
    (05/10/2026): o que está marcado pra um dia que ainda não chegou fica na
    agenda / nos Próximos passos, não aqui."""
    hoje = hoje or hoje_br()
    competencia = competencia or f"{hoje.year:04d}-{hoje.month:02d}"
    anterior = _somar_competencia(competencia, -1)

    # Clientes "só controle" (fontes de receita do financeiro) não são do emissor.
    vinculos = [v for v in listar_vinculos_ativos(db) if not v.sem_nota]
    emissoes: list[dict] = []
    emitidas = 0
    aguardando = 0

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
    # Notas de vendedores da Shopee (avulsas) ficam numa linha própria e
    # fora do controle de pagamento: a Shopee paga tudo junto na nota dela.
    vendedores_por_vinculo: dict[uuid.UUID, list[Emissao]] = {}
    for vid, notas in list(notas_por_vinculo.items()):
        avulsas = [e for e in notas if e.tomador_documento]
        if avulsas:
            vendedores_por_vinculo[vid] = avulsas
            notas_por_vinculo[vid] = [e for e in notas if not e.tomador_documento]
    do_mes_ids = [e.id for notas in notas_por_vinculo.values() for e in notas]
    ultimo_envio: dict[uuid.UUID, str] = {}
    if do_mes_ids:
        for emissao_id, status in (
            db.query(Envio.emissao_id, Envio.status)
            .filter(Envio.emissao_id.in_(do_mes_ids), Envio.canal.in_(("email", "whatsapp", "direto_fornecedor")))
            .order_by(Envio.criado_em)
        ):
            ultimo_envio[emissao_id] = status

    for vinculo in vinculos:
        # Shopee: várias notas no mês (uma por vendedor) — vira uma linha só,
        # somando os valores.
        do_mes = notas_por_vinculo.get(vinculo.id, [])
        vendedores = vendedores_por_vinculo.get(vinculo.id, [])
        if vendedores:
            # "A Shopee vendedores está como não enviado, no entanto foram
            # disparados os e-mails" (08/10/2026): a linha junta centenas de
            # notas, então o envio é a conta de quantas já foram entregues.
            autorizadas = [e.id for e in vendedores if e.estado == "confirmado"]
            entregues = 0
            if autorizadas:
                entregues = (
                    db.query(func.count(func.distinct(Envio.emissao_id)))
                    .join(Emissao, Emissao.id == Envio.emissao_id)
                    .filter(
                        Emissao.prestador_tomador_id == vinculo.id, Emissao.competencia == competencia,
                        Emissao.tomador_documento.isnot(None), Emissao.estado == "confirmado",
                        Envio.status == "enviado", Envio.canal.in_(("email", "whatsapp", "direto_fornecedor")),
                    ).scalar() or 0
                )
            envio_do_grupo = None if not entregues else "enviado" if entregues >= len(autorizadas) else "parcial"
            # "Deixe ela com Assinada, Autorizada e o Enviada (x)" (08/10/2026): a
            # linha mostra as mesmas três colunas das outras, com a conta do grupo.
            ativas = [e for e in vendedores if e.estado != "substituida"]
            assinadas = sum(1 for e in ativas if e.estado in ("assinado", "submetido", "confirmado", "erro"))
            recusadas = sum(1 for e in ativas if e.estado == "erro")
            emissoes.append({
                "emissao_id": vendedores[0].id, "vinculo_id": vinculo.id, "quantidade": len(vendedores),
                "apelido": f"{vinculo.apelido} — vendedores ({len(vendedores)} notas)", "tomador_razao_social": "vários vendedores",
                "competencia": competencia, "valor": float(sum((e.valor for e in vendedores), Decimal(0))),
                "estado": vendedores[0].estado, "estado_label": ESTADO_NFSE_LABEL.get(vendedores[0].estado, vendedores[0].estado),
                "envio_status": envio_do_grupo, "enviadas": int(entregues), "a_enviar": len(autorizadas),
                "total_grupo": len(ativas), "assinadas": assinadas, "autorizadas": len(autorizadas), "recusadas": recusadas,
                "tem_pdf": False, "tem_email": False,
                "homologacao": (vendedores[0].tomador_snapshot or {}).get("tpAmb") == "2", "envio_forma": "email",
                "vendedores": True,
            })
        if not do_mes:
            aguardando += 1
            continue

        emitidas += 1
        # Uma linha por nota.
        for emissao in do_mes:
            emissoes.append({
                "emissao_id": emissao.id,
                "vinculo_id": vinculo.id,
                "quantidade": 1,
                "apelido": vinculo.apelido,
                "tomador_razao_social": vinculo.tomador.razao_social,
                "competencia": emissao.competencia,
                "valor": float(emissao.valor),
                "estado": emissao.estado,
                "estado_label": ESTADO_NFSE_LABEL.get(emissao.estado, emissao.estado),
                "envio_status": ultimo_envio.get(emissao.id),
                "tem_pdf": emissao.estado == "confirmado" and bool(emissao.chave_acesso),
                "tem_email": bool(vinculo.email_para or vinculo.email_contato),
                "homologacao": (emissao.tomador_snapshot or {}).get("tpAmb") == "2",
                "envio_forma": vinculo.envio_canal,
                "erro_detalhe": motivo_da_recusa(emissao.erro_detalhe) if emissao.estado == "erro" else None,
                "erro_corrigivel": emissao.estado == "erro" and recusa_corrigivel(emissao.erro_detalhe),
            })

    faturado_no_mes = _faturado(db, competencia)
    faturado_mes_anterior = _faturado(db, anterior)
    delta_faturamento_pct = None
    if faturado_mes_anterior:
        delta_faturamento_pct = float((faturado_no_mes - faturado_mes_anterior) / faturado_mes_anterior * 100)

    atencao: list[dict] = _avisos_dia_de_gerar(db, vinculos, hoje)  # com a véspera: é um ponto de atenção pedido pelo Marcos
    cert = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if cert is not None and cert.validade is not None:
        # Fica mesmo antes de vencer: renovar um A1 leva dias e, vencido,
        # trava a emissão — não existe "dia marcado" na agenda pra isso.
        dias = (cert.validade - hoje).days
        if dias <= DIAS_ALERTA_CERTIFICADO:
            atencao.append({
                "tipo": "certificado_vencido" if dias < 0 else "certificado_vencendo",
                "titulo": "Certificado digital",
                "mensagem": (f"Venceu há {-dias} dia(s)." if dias < 0 else f"Vence em {dias} dia(s)."),
                "link": "/app/empresa?aba=certificado",
                "link_label": "Enviar novo certificado",
            })

    # Marco 16, item 5 — alíquota de referência do Simples Nacional ainda
    # não foi confirmada NESTE mês (ver PATCH /api/prestador/aliquota e
    # docstring de Prestador.aliquota_atualizada_em). Só avisa — nunca
    # bloqueia emissão, mesma filosofia do resto desta lista.
    # 05/10/2026 ("joguei a revisão de alíquota — está na agenda no dia 15 —,
    # assim ela não deveria aparecer"): só entra quando o dia marcado no
    # calendário já chegou; antes disso é agenda, não pendência.
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    nao_confirmada = prestador is not None and (
        prestador.aliquota_atualizada_em is None
        or (prestador.aliquota_atualizada_em.year, prestador.aliquota_atualizada_em.month) != (hoje.year, hoje.month)
    )
    data_lembrete = _data_lembrete_aliquota(db, prestador, hoje) if nao_confirmada else None
    if data_lembrete is not None and data_lembrete <= hoje:
        atencao.append({
            "tipo": "aliquota_pendente",
            "titulo": "Alíquota do Simples Nacional",
            "mensagem": (
                "Ainda não confirmada este mês — revise em Empresa › Dados da empresa (Alíquota) antes de emitir notas."
                if prestador.aliquota_atual is not None
                else "Nenhuma alíquota de referência definida ainda — configure em Configurações."
            ),
            "link": "/app/empresa?aba=aliquotas",
            "link_label": "Revisar alíquota" if prestador.aliquota_atual is not None else "Definir alíquota",
        })

    return {
        "competencia": competencia,
        "total_vinculos": len(vinculos),
        "emitidas": emitidas,
        "aguardando": aguardando,
        "faturado_no_mes": float(faturado_no_mes),
        "faturado_mes_anterior": float(faturado_mes_anterior),
        "delta_faturamento_pct": delta_faturamento_pct,
        "serie_faturamento": _serie_faturamento(db, competencia),
        "emissoes": emissoes,
        "atencao": atencao,
    }


def _da_pra_enviar(e: Emissao) -> bool:
    """A nota autorizada ainda tem envio a fazer? Vendedor de relatório sem
    e-mail não tem como receber — não vira pendência (05/10/2026); tomador
    marcado como "não precisa enviar", também não."""
    if e.tomador_documento:
        return bool(((e.tomador_snapshot or {}).get("email") or "").strip())
    return bool(e.vinculo and e.vinculo.envio_canal != "nenhum")


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
        db.query(Envio.id).filter(
            Envio.emissao_id == Emissao.id, Envio.status == "enviado", Envio.canal.in_(("email", "whatsapp", "direto_fornecedor"))
        ).exists()
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
        nome = (snap.get("razao_social") or "vendedor") if e.tomador_documento else snap.get("apelido")
        base = {"emissao_id": e.id, "valor": float(e.valor), "competencia": e.competencia, "link": f"/app/nfse/{e.id}"}
        if e.estado == "montado":
            pendencias.append({**base, "tipo": "assinar", "titulo": f"Assinar a nota de {nome}", "acao": "Assinar"})
        elif e.estado == "assinado":
            pendencias.append({**base, "tipo": "prefeitura", "titulo": f"Enviar à prefeitura a nota de {nome}", "acao": "Enviar"})
        elif e.estado == "erro":
            pendencias.append({**base, "tipo": "erro", "titulo": f"A prefeitura recusou a nota de {nome}", "acao": "Ver erro"})
        elif e.estado == "confirmado" and (_da_pra_enviar(e)):
            pendencias.append({**base, "tipo": "enviar_tomador", "titulo": f"Mandar a nota pra {nome}", "acao": "Enviar"})

    competencia_tem_nota = {
        v for (v,) in db.query(Emissao.prestador_tomador_id).filter(
            Emissao.competencia == competencia, Emissao.estado != "cancelada", Emissao.tomador_documento.is_(None)
        )
    }
    ignoradas = {c for (c,) in db.query(AjusteEvento.chave).filter(AjusteEvento.tipo == "pendencia", AjusteEvento.oculto.is_(True))}
    for v in listar_vinculos_ativos(db):
        if v.id in competencia_tem_nota or v.sem_nota:
            continue
        chave = f"gerar:{v.id}:{competencia}"
        if chave in ignoradas:
            continue
        # Dia combinado pra gerar (o último dia do mês quando o mês é mais curto).
        data = (
            datetime.date(hoje.year, hoje.month, min(v.dia_limite_emissao, monthrange(hoje.year, hoje.month)[1]))
            if v.dia_limite_emissao else None
        )
        pendencias.append({
            "tipo": "gerar", "titulo": f"Gerar a nota de {v.apelido}", "acao": "Gerar", "vinculo_id": v.id,
            "competencia": competencia, "link": f"/app/nfse?gerar={v.id}&competencia={competencia}", "chave": chave,
            "data": data, "atrasada": bool(data and data < hoje),
        })

    eventos = eventos_calendario(db, prestador_id, hoje, hoje + datetime.timedelta(days=30))
    # A agenda é só o que AINDA vai acontecer e não está na lista de cima:
    # "dia de gerar a nota" deste mês já é uma pendência (aparecia duas
    # vezes) e "recebido" já aconteceu — não é próximo passo (05/10/2026).
    a_gerar = {str(p["vinculo_id"]) for p in pendencias if p["tipo"] == "gerar"}
    da_agenda = [
        ev for ev in eventos
        if ev["tipo"] != "recebimento_confirmado"
        and not (
            ev["tipo"] == "prazo_emissao" and str(ev.get("vinculo_id")) in a_gerar
            and (ev["data"].year, ev["data"].month) == (hoje.year, hoje.month)
        )
    ]
    # Vários avisos iguais no mesmo dia viram uma linha só ("Dia de gerar 8
    # notas") — o card ficava comprido demais (05/10/2026); o detalhe de cada
    # um está no Calendário.
    juntaveis = {
        "prazo_emissao": "Dia de gerar {n} notas",
        "recebimento_previsto": "Previsão de {n} recebimentos",
    }
    por_dia: dict[tuple, list[dict]] = {}
    for ev in da_agenda:
        if ev["tipo"] in juntaveis:
            por_dia.setdefault((ev["data"], ev["tipo"]), []).append(ev)
    agenda: list[dict] = []
    for ev in da_agenda:
        grupo = por_dia.get((ev["data"], ev["tipo"])) if ev["tipo"] in juntaveis else None
        if grupo is not None and len(grupo) > 2:
            if ev is not grupo[0]:
                continue
            titulo = juntaveis[ev["tipo"]].format(n=len(grupo))
            valores = [g["valor"] for g in grupo if g.get("valor") is not None]
            agenda.append({
                "data": ev["data"], "tipo": ev["tipo"], "titulo": titulo, "detalhe": titulo,
                "valor": round(sum(valores), 2) if valores else None, "quantidade": len(grupo),
            })
        else:
            agenda.append({
                "data": ev["data"], "tipo": ev.get("categoria") or ev["tipo"], "titulo": ev.get("apelido") or ev["titulo"],
                "detalhe": ev["titulo"], "valor": ev.get("valor"),
            })
    agenda.sort(key=lambda ev: ev["data"])
    total_agenda = len(agenda)
    agenda = agenda[:8]
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
    # Notas a gerar: mais de duas pro MESMO dia viram "Gerar 8 notas" (o dia
    # vai em `data`, a tela escreve "até 15/10"); cada uma continua em
    # `itens`, com o seu link e o seu "ignorar".
    gerar_por_dia: dict[datetime.date | None, list[dict]] = {}
    for p in pendencias:
        if p["tipo"] == "gerar":
            gerar_por_dia.setdefault(p.get("data"), []).append(p)
    # 08/10/2026: "a data mais próxima estendida e a data mais longa
    # recolhida" — o dia que vence primeiro já vem aberto, nota por nota; os
    # dias seguintes ficam numa linha só cada, pra abrir se quiser.
    dias = sorted(gerar_por_dia, key=lambda d: d or datetime.date.max)
    for n, data in enumerate(dias):
        do_dia = sorted(gerar_por_dia[data], key=lambda p: p["titulo"].lower())
        mais_proximo = n == 0
        if len(do_dia) > 2 or (len(do_dia) == 2 and not mais_proximo):
            agrupadas.append({
                "tipo": "gerar", "titulo": f"Gerar {len(do_dia)} notas", "acao": "Ver", "link": "/app/tomadores",
                "competencia": competencia, "data": data, "atrasada": bool(data and data < hoje), "itens": do_dia,
                "aberto": mais_proximo,
            })
        else:
            agrupadas += do_dia
    agrupadas += [p for p in pendencias if p["tipo"] not in agrupaveis and p["tipo"] != "gerar"]
    ordem = {"erro": 0, "prefeitura": 1, "assinar": 2, "enviar_tomador": 3, "gerar": 4}
    # Primeiro o que já dá pra resolver agora; depois as notas a gerar, na
    # ordem do dia combinado (as sem dia por último).
    agrupadas.sort(key=lambda p: (ordem.get(p["tipo"], 9), p.get("data") or datetime.date.max, p["titulo"].lower()))
    return {"pendencias": agrupadas[:10], "total_pendencias": len(agrupadas), "agenda": agenda, "total_agenda": total_agenda}


def proxima_nota(db: Session, atual: Emissao) -> dict:
    """Depois de terminar uma nota, qual é a próxima que ainda tem passo
    pendente (05/10/2026: "um botão ali embaixo pra pessoa já ir pro
    próximo passo, pra não ter que voltar na tela inicial"). Fica no mesmo
    grupo da nota aberta: as de vendedores (lote) ou as dos tomadores."""
    ja_enviada = (
        db.query(Envio.id).filter(
            Envio.emissao_id == Emissao.id, Envio.status == "enviado", Envio.canal.in_(("email", "whatsapp", "direto_fornecedor"))
        ).exists()
    )
    grupo = Emissao.tomador_documento.isnot(None) if atual.tomador_documento else Emissao.tomador_documento.is_(None)
    candidatas = (
        db.query(Emissao)
        .filter(
            grupo, Emissao.id != atual.id,
            # Nota importada do Emissor Nacional já foi entregue por fora: não entra na fila.
            (Emissao.estado.in_(("montado", "assinado", "erro")))
            | ((Emissao.estado == "confirmado") & ~ja_enviada & (Emissao.origem != "importada")),
        )
        .order_by(Emissao.criado_em, Emissao.n_dps)
        .limit(300)
        .all()
    )
    passos = {"montado": "Assinar", "assinado": "Enviar à prefeitura", "erro": "Ver a recusa", "confirmado": "Enviar ao tomador"}
    fila = [
        e for e in candidatas
        if e.estado != "confirmado" or _da_pra_enviar(e)
    ]
    if not fila:
        return {"proxima": None, "restantes": 0}
    e = fila[0]
    snap = e.tomador_snapshot or {}
    nome = (snap.get("razao_social") or "vendedor") if e.tomador_documento else (snap.get("apelido") or snap.get("razao_social") or "")
    return {
        "proxima": {"id": e.id, "nome": nome, "competencia": e.competencia, "valor": float(e.valor), "passo": passos[e.estado]},
        "restantes": len(fila),
    }


def _mes_anterior(competencia: str) -> str:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    return f"{ano - 1:04d}-12" if mes == 1 else f"{ano:04d}-{mes - 1:02d}"
