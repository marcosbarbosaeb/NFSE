"""Rotas do módulo FINANCEIRO (05/10/2026).

O financeiro é um produto à parte do emissor: recebimentos, despesas,
contas do mês, rotina de fechamento, extrato bancário e conciliação. Tudo
aqui só responde pra empresa que tem o módulo ligado (`exige_modulo`).

Depende só do cadastro geral (app/deps.py: quem está logado, de qual
empresa) e do cadastro de clientes (app/services/vinculos.py). Do emissor
ele lê as notas pra montar o "a receber" (app/financeiro/a_receber.py) —
essa leitura e os eventos de app/financeiro/integracao.py são os pontos de
integração entre os dois produtos.
"""
import json
import re
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import db_sessao, exige_modulo, exigir_conta_real, ler_upload as _ler_upload, prestador_atual_id
from app.financeiro import classificar_extrato, clientes, conciliacao, importar_planilha
from app.financeiro import contas_mes as financeiro
from app.financeiro import mes_a_mes
from app.financeiro.a_receber import notas_em_aberto, recebimentos_sem_nota
from app.financeiro.extrato_pdf import PdfInvalidoError, extrair_extrato
from app.financeiro.importacao_extrato import ItemExtrato, confirmar_importacao_extrato
from app.financeiro.listas import listar_despesas, listar_pagamentos
from app.financeiro.painel_status import painel_status_completo
from app.financeiro.integracao import ligar_pagamento as _ligar_pagamento
from app.financeiro.pagamentos import registrar_pagamento
from app.financeiro.pendencias import pendencias as pendencias_do_financeiro
from app.models import AjusteEvento, Anotacao, Despesa, DespesaRecorrente, Emissao, PagamentoRecebido, Prestador, PrestadorTomador, RotinaMensal
from app.schemas import (
    AtualizarDespesaRequest,
    ConciliarDespesaRequest,
    ConciliarReceitaRequest,
    ConciliarRequest,
    ConfirmarExtratoRequest,
    ConfirmarExtratoResponse,
    ContaFixaAtualizarRequest,
    ContaFixaRequest,
    ContaFixaResponse,
    ContasDoMesResponse,
    DespesaResponse,
    ErroResponse,
    ExtratoExtraidoResponse,
    FonteReceitaRequest,
    ImportarPlanilhaResponse,
    LigarPagamentoRequest,
    NotaAbertaResponse,
    OrdemRequest,
    PagamentoResponse,
    PainelStatusResponse,
    PendenciaItem,
    RecebimentoSemNotaResponse,
    RegistrarDespesaRequest,
    RegistrarPagamentoRequest,
    ResumoFinanceiroResponse,
    RotinaAtualizarRequest,
    RotinaCheckRequest,
    RotinaRequest,
    RotinaResponse,
)
from app.services.vinculos import buscar_vinculo
from app.tempo import hoje as hoje_br

rotas = APIRouter(dependencies=[Depends(exige_modulo("financeiro"))])

_COMPETENCIA_RE = r"^\d{4}-(0[1-9]|1[0-2])$"


@rotas.patch("/api/pagamentos/{pagamento_id}", response_model=PagamentoResponse, responses={404: {"model": ErroResponse}})
def api_ligar_pagamento(pagamento_id: uuid.UUID, req: LigarPagamentoRequest, db: Session = Depends(db_sessao)):
    """Liga um recebimento a uma nota do mesmo tomador (ou solta, com
    `emissao_id: null` — volta a ser um recebimento sem nota)."""
    pagamento = db.get(PagamentoRecebido, pagamento_id)
    if pagamento is None:
        raise HTTPException(status_code=404, detail="Recebimento não encontrado.")
    emissao = None
    if req.emissao_id is not None:
        emissao = db.get(Emissao, req.emissao_id)
        if emissao is None or emissao.prestador_tomador_id != pagamento.prestador_tomador_id:
            raise HTTPException(status_code=404, detail="Essa nota não é do tomador deste recebimento.")
    _ligar_pagamento(pagamento, emissao)
    db.flush()
    vinculo = db.get(PrestadorTomador, pagamento.prestador_tomador_id)
    resposta = PagamentoResponse(
        id=pagamento.id, apelido=vinculo.apelido, competencia=pagamento.competencia, valor=float(pagamento.valor),
        data_recebimento=pagamento.data_recebimento, vinculo_id=vinculo.id, emissao_id=pagamento.emissao_id,
        sem_nota=pagamento.emissao_id is None and not vinculo.sem_nota,
        pode_gerar_nota=pagamento.emissao_id is None and not vinculo.sem_nota,
    )
    db.commit()
    return resposta


@rotas.post("/api/pagamentos", response_model=PagamentoResponse, responses={404: {"model": ErroResponse}})
def api_registrar_pagamento(req: RegistrarPagamentoRequest, db: Session = Depends(db_sessao)):
    """Marco 8 — registro manual de um pagamento recebido (o lado 'recebi'
    do painel de status; o lado 'faturei' já é automático via /api/dps)."""
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    try:
        pagamento = registrar_pagamento(
            db, vinculo, competencia=req.competencia, valor=req.valor, data_recebimento=req.data_recebimento,
            emissao_id=req.emissao_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Antes do commit: depois dele a transação nova não tem o prestador (RLS).
    sem_nota = pagamento.emissao_id is None and not vinculo.sem_nota
    resposta = PagamentoResponse(
        id=pagamento.id, apelido=vinculo.apelido, competencia=pagamento.competencia,
        valor=float(pagamento.valor), data_recebimento=pagamento.data_recebimento,
        sem_nota=sem_nota, vinculo_id=vinculo.id, emissao_id=pagamento.emissao_id, pode_gerar_nota=sem_nota,
    )
    db.commit()
    return resposta


@rotas.delete("/api/pagamentos")
def api_desfazer_pagamento(
    vinculo_id: uuid.UUID | None = None, competencia: str | None = None, emissao_id: uuid.UUID | None = None,
    db: Session = Depends(db_sessao),
):
    """Desfaz a baixa. Com `emissao_id` (03/10/2026, baixa por nota): só
    daquela nota. Sem ele (telas antigas): apaga o(s) recebimento(s) do
    tomador+competência."""
    if emissao_id is not None:
        from app.financeiro import a_receber as ar

        emissao = db.get(Emissao, emissao_id)
        if emissao is None:
            raise HTTPException(status_code=404, detail="Nota não encontrada.")
        removidos = ar.desfazer_baixa(db, emissao)
        db.commit()
        return {"removidos": removidos}
    if vinculo_id is None or competencia is None or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    removidos = (
        db.query(PagamentoRecebido)
        .filter(PagamentoRecebido.prestador_tomador_id == vinculo_id, PagamentoRecebido.competencia == competencia)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"removidos": removidos}


@rotas.get("/api/pagamentos", response_model=list[PagamentoResponse])
def api_listar_pagamentos(
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    por: str | None = None,
    db: Session = Depends(db_sessao),
):
    """Marco 14 — tela 'Recebimentos'. GET puro, sem efeito colateral.
    `por=recebimento`: o ano é o de quando o dinheiro caiu (Financeiro)."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_pagamentos(db, ano=ano, vinculo_id=vinculo_id, por_recebimento=por == "recebimento")


@rotas.post("/api/recebimentos/extrato", response_model=ExtratoExtraidoResponse, responses={400: {"model": ErroResponse}})
def api_extrair_extrato(arquivo: UploadFile = File(...), db: Session = Depends(db_sessao)):
    """Aceita PDF, OFX ou CSV desde 28/09/2026 (ver app/services/extrato_pdf.py)."""
    """Marco 15 (item 5) — extração heurística de transações de um extrato
    bancário em PDF (ver docstring de app/services/extrato_pdf.py). GET
    conceitual apesar do POST (upload exige POST): não grava NADA no banco
    — só devolve candidatos pra tela de revisão. `db_sessao` aqui só serve
    pra manter o padrão de autenticação das outras rotas; o parser em si
    não toca o banco."""
    bruto = _ler_upload(arquivo, 15)
    try:
        resultado = extrair_extrato(bruto, arquivo.filename)
    except PdfInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    transacoes = resultado.transacoes
    sugestoes = classificar_extrato.sugerir(db, transacoes)
    cats = classificar_extrato.categorias(db)
    return ExtratoExtraidoResponse(
        categorias=cats["despesas"], categorias_retirada=cats["retiradas"],
        notas_abertas=classificar_extrato.notas_para_escolher(db),
        formato=resultado.formato,
        linhas_lidas=resultado.linhas_lidas,
        total_transacoes=len(transacoes),
        transacoes=[
            {"linha": t.linha, "data": t.data, "descricao": t.descricao, "valor": float(t.valor), **sug}
            for t, sug in zip(transacoes, sugestoes)
        ],
    )


@rotas.post("/api/recebimentos/extrato/confirmar", response_model=ConfirmarExtratoResponse)
def api_confirmar_extrato(
    req: ConfirmarExtratoRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Segunda metade do fluxo acima — grava um PagamentoRecebido por item
    que a pessoa confirmou na revisão (cada um casado com um vínculo à
    mão). Mesmo padrão de isolamento por item do /api/dps/importar-csv:
    um item ruim não derruba os demais (ver
    app/services/importacao_extrato.py)."""
    itens = [
        ItemExtrato(
            vinculo_id=i.vinculo_id, competencia=i.competencia, valor=i.valor, data_recebimento=i.data_recebimento,
            descricao=i.descricao, emissao_id=i.emissao_id,
        )
        for i in req.itens
    ]
    resultados = confirmar_importacao_extrato(db, itens) if itens else []
    sucesso = sum(1 for r in resultados if r.ok)
    # Toda linha do extrato fica guardada (05/10/2026): as classificadas já
    # conciliadas, as outras pendentes pra tela de conciliação.
    linhas = (
        [{"data": i.data_recebimento, "descricao": i.descricao, "valor": i.valor, "credito": True} for i in req.itens]
        + [{"data": d.data, "descricao": d.descricao, "valor": d.valor, "credito": False} for d in req.despesas]
        + [p.model_dump() for p in req.pendentes]
    )
    lancamentos = conciliacao.guardar(db, prestador_id, linhas, req.arquivo)
    for r in resultados:
        if r.ok and req.itens[r.indice].descricao:
            conciliacao.marcar(lancamentos[r.indice], pagamento_id=r.pagamento_id)
    # Saídas do extrato viram despesas (28/09/2026: "importe as entradas da
    # forma que está e importe as saídas abaixo").
    for n, d in enumerate(req.despesas):
        despesa = classificar_extrato.registrar_saida(
            db, prestador_id, categoria=d.categoria, competencia=d.competencia, valor=d.valor,
            descricao=d.descricao, data=d.data, tipo=d.tipo,
        )
        classificar_extrato.lembrar(db, prestador_id, d.descricao, credito=False, categoria=d.categoria.strip(), tipo=d.tipo)
        if d.descricao:
            conciliacao.marcar(lancamentos[len(req.itens) + n], despesa_id=despesa.id)
    db.flush()
    sem_nota = _sem_nota_dos_pagamentos(db, [r.pagamento_id for r in resultados if r.ok and r.pagamento_id])
    pendentes = conciliacao.contar_pendentes(db)
    db.commit()
    return ConfirmarExtratoResponse(
        total=len(resultados), sucesso=sucesso, erro=len(resultados) - sucesso,
        itens=[{"indice": r.indice, "ok": r.ok, "mensagem": r.mensagem, "pagamento_id": r.pagamento_id} for r in resultados],
        despesas_registradas=len(req.despesas), sem_nota=sem_nota, pendentes=pendentes,
    )


@rotas.get("/api/conciliacao")
def api_conciliacao(db: Session = Depends(db_sessao)):
    return conciliacao.painel(db)


@rotas.get("/api/conciliacao/contagem")
def api_conciliacao_contagem(db: Session = Depends(db_sessao)):
    return {"pendentes": conciliacao.contar_pendentes(db)}


@rotas.get("/api/conciliacao/ignorados")
def api_conciliacao_ignorados(db: Session = Depends(db_sessao)):
    return conciliacao.listar_ignorados(db)


@rotas.post("/api/conciliacao/automatico")
def api_conciliacao_automatico(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    feitos = conciliacao.automatico(db, prestador_id, hoje_br())
    db.commit()
    return {"conciliados": feitos}


@rotas.post("/api/conciliacao/{lancamento_id}/receita")
def api_conciliar_receita(lancamento_id: uuid.UUID, req: ConciliarReceitaRequest, db: Session = Depends(db_sessao)):
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Tomador não encontrado.")
    try:
        pagamento = conciliacao.como_receita(
            db, lancamento_id, vinculo, hoje=hoje_br(), emissao_id=req.emissao_id, competencia=req.competencia,
        )
    except conciliacao.ConciliacaoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    resposta = {
        "pagamento_id": str(pagamento.id), "vinculo_id": str(vinculo.id), "apelido": vinculo.apelido,
        "competencia": pagamento.competencia, "valor": float(pagamento.valor),
        "emissao_id": str(pagamento.emissao_id) if pagamento.emissao_id else None,
        "pode_gerar_nota": pagamento.emissao_id is None and not vinculo.sem_nota,
    }
    db.commit()
    return resposta


@rotas.post("/api/conciliacao/{lancamento_id}/despesa")
def api_conciliar_despesa(
    lancamento_id: uuid.UUID, req: ConciliarDespesaRequest, db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    try:
        despesa = conciliacao.como_despesa(
            db, lancamento_id, prestador_id, hoje=hoje_br(), despesa_id=req.despesa_id, categoria=req.categoria,
            tipo=req.tipo, competencia=req.competencia,
        )
    except conciliacao.ConciliacaoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    resposta = {"despesa_id": str(despesa.id), "categoria": despesa.categoria, "valor": float(despesa.valor)}
    db.commit()
    return resposta


@rotas.post("/api/conciliacao/{lancamento_id}/ignorar")
def api_conciliacao_ignorar(lancamento_id: uuid.UUID, ignorar: bool = True, db: Session = Depends(db_sessao)):
    try:
        conciliacao.ignorar(db, lancamento_id, ignorar)
    except conciliacao.ConciliacaoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"ok": True}


@rotas.post("/api/conciliacao/{lancamento_id}/tipo")
def api_conciliacao_tipo(lancamento_id: uuid.UUID, credito: bool, db: Session = Depends(db_sessao)):
    try:
        conciliacao.trocar_tipo(db, lancamento_id, credito)
    except conciliacao.ConciliacaoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"ok": True}


@rotas.post("/api/vinculos/controle")
def api_criar_fonte_de_receita(
    req: FonteReceitaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Tomador criado direto da revisão do extrato (03/10/2026): só o nome,
    entra como fonte de receita só pra controle (sem nota)."""
    vinculo = classificar_extrato.criar_fonte(db, db.get(Prestador, prestador_id), req.nome)
    resposta = {"id": str(vinculo.id), "apelido": vinculo.apelido, "sem_nota": vinculo.sem_nota}
    db.commit()
    return resposta


def _sem_nota_dos_pagamentos(db: Session, ids: list) -> list[dict]:
    if not ids:
        return []
    alvo = set(ids)
    return [r for r in recebimentos_sem_nota(db) if r["pagamento_id"] in alvo]


@rotas.post("/api/despesas", response_model=DespesaResponse)
def api_registrar_despesa(req: RegistrarDespesaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Lançamento manual — despesa ou retirada (distribuição de lucros), já
    paga ou a pagar."""
    despesa = Despesa(
        id=uuid.uuid4(), prestador_id=prestador_id, categoria=req.categoria.strip(), competencia=req.competencia,
        valor=Decimal(str(req.valor)), descricao=(req.descricao or "").strip() or None, tipo=req.tipo,
        conta=(req.conta or "").strip() or None, vencimento=req.vencimento, pago=req.pago,
        pago_em=req.pago_em or (hoje_br() if req.pago else None),
    )
    db.add(despesa)
    db.commit()
    return financeiro._linha_despesa(despesa)


def _despesa_ou_404(db: Session, despesa_id: uuid.UUID) -> Despesa:
    despesa = db.get(Despesa, despesa_id)
    if despesa is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    return despesa


@rotas.patch("/api/despesas/{despesa_id}", response_model=DespesaResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_despesa(despesa_id: uuid.UUID, req: AtualizarDespesaRequest, db: Session = Depends(db_sessao)):
    """Editar ou ticar ("pagou ✓") um lançamento."""
    despesa = _despesa_ou_404(db, despesa_id)
    campos = req.model_dump(exclude_unset=True)
    for campo, valor in campos.items():
        if campo == "valor" and valor is not None:
            valor = Decimal(str(valor))
        if campo in ("categoria", "descricao", "conta") and isinstance(valor, str):
            valor = valor.strip() or (None if campo != "categoria" else despesa.categoria)
        if campo in ("pago",) and valor is None:
            continue
        setattr(despesa, campo, valor)
    if campos.get("pago") is True and "pago_em" not in campos:
        despesa.pago_em = despesa.pago_em or hoje_br()
    if campos.get("pago") is False:
        despesa.pago_em = None
    db.commit()
    return financeiro._linha_despesa(despesa)


@rotas.delete("/api/despesas/{despesa_id}", responses={404: {"model": ErroResponse}})
def api_apagar_despesa(despesa_id: uuid.UUID, db: Session = Depends(db_sessao)):
    db.delete(_despesa_ou_404(db, despesa_id))
    db.commit()
    return {"ok": True}


@rotas.get("/api/despesas", response_model=list[DespesaResponse])
def api_listar_despesas(ano: str | None = None, db: Session = Depends(db_sessao)):
    """Marco 14 — tela 'Despesas'. GET puro, sem efeito colateral."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_despesas(db, ano=ano)


@rotas.get("/api/painel/status", response_model=PainelStatusResponse)
def api_painel_status(ano: str, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 8 — 'painel de status, seria notas geradas e notas recebidas...
    igual a esta planilha' (item #7 da lista original). `ano` é obrigatório
    e no formato AAAA (o painel mostra um ano de cada vez, como a aba única
    da planilha real hoje mostra 2026)."""
    if len(ano) != 4 or not ano.isdigit():
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return painel_status_completo(db, prestador_id, ano)


@rotas.get("/api/financeiro/resumo", response_model=ResumoFinanceiroResponse)
def api_resumo_financeiro(ano: str = Query(pattern=r"^\d{4}$"), db: Session = Depends(db_sessao)):
    return financeiro.resumo_anual(db, ano)


@rotas.get("/api/financeiro/mes-a-mes")
def api_mes_a_mes(ano: str = Query(pattern=r"^\d{4}$"), db: Session = Depends(db_sessao)):
    """O detalhe do "Mês a mês": cada total do resumo aberto por cliente
    (recebido/faturado) e por categoria → coisa (despesas/retiradas). Só
    leitura; mesmas regras do resumo (ver app/financeiro/mes_a_mes.py)."""
    return mes_a_mes.detalhe_anual(db, ano)


@rotas.get("/api/financeiro/pendencias", response_model=list[PendenciaItem])
def api_pendencias_financeiro(db: Session = Depends(db_sessao)):
    """O que resolver no financeiro: recebimento sem nota, extrato sem
    classificar e notas a receber."""
    return pendencias_do_financeiro(db)


@rotas.get("/api/financeiro/recebimentos-sem-nota", response_model=list[RecebimentoSemNotaResponse])
def api_recebimentos_sem_nota(db: Session = Depends(db_sessao)):
    """Dinheiro que caiu sem nota emitida pro tomador naquele mês (últimos 12
    meses, sem os avisos ignorados)."""
    hoje = hoje_br()
    desde = f"{hoje.year - 1:04d}-{hoje.month:02d}"
    ignoradas = {c for (c,) in db.query(AjusteEvento.chave).filter(AjusteEvento.tipo == "pendencia", AjusteEvento.oculto.is_(True))}
    return [
        r for r in recebimentos_sem_nota(db, desde)
        # (a chave antiga, por tomador + mês, continua valendo pros ignorados de antes)
        if r["chave"] not in ignoradas and f"semnota:{r['vinculo_id']}:{r['competencia']}" not in ignoradas
    ]


@rotas.post("/api/financeiro/conciliar")
def api_conciliar(req: ConciliarRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """"Considerar recebidas" — notas antigas que eram controladas em outra
    plataforma saem do "a receber" sem lançar valor (o recebido não muda)."""
    from app.financeiro import a_receber as ar

    pares = [(i.vinculo_id, i.competencia) for i in req.itens]
    if req.ate:
        pares += [(g["vinculo_id"], g["competencia"]) for g in ar.notas_em_aberto(db) if g["competencia"] <= req.ate]
    feitos = ar.conciliar(db, prestador_id, pares)
    db.commit()
    return {"conciliadas": feitos}


@rotas.get("/api/financeiro/mes", response_model=ContasDoMesResponse)
def api_contas_do_mes(
    competencia: str = Query(pattern=_COMPETENCIA_RE), db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Contas fixas do mês (a pagar / pagas) + rotina de fechamento. Cria os
    lançamentos do mês das contas fixas na primeira vez que é aberto."""
    resultado = financeiro.contas_do_mes(db, prestador_id, competencia)
    db.commit()
    return resultado


@rotas.get("/api/financeiro/contas-fixas", response_model=list[ContaFixaResponse])
def api_listar_contas_fixas(db: Session = Depends(db_sessao)):
    return financeiro.listar_recorrentes(db)


@rotas.post("/api/financeiro/contas-fixas", response_model=ContaFixaResponse)
def api_criar_conta_fixa(req: ContaFixaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    conta = financeiro.criar_recorrente(
        db, prestador_id, nome=req.nome.strip(), categoria=(req.categoria or req.nome).strip()[:100], tipo=req.tipo,
        valor_padrao=Decimal(str(req.valor_padrao)) if req.valor_padrao else None, dia_vencimento=req.dia_vencimento,
        conta=(req.conta or "").strip() or None, agendado_ate=req.agendado_ate or None,
    )
    financeiro.aplicar_agendamento(db, conta, hoje_br())
    db.commit()
    return conta


def _conta_fixa_ou_404(db: Session, conta_id: uuid.UUID) -> DespesaRecorrente:
    conta = db.get(DespesaRecorrente, conta_id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta fixa não encontrada.")
    return conta


@rotas.patch("/api/financeiro/contas-fixas/{conta_id}", response_model=ContaFixaResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_conta_fixa(conta_id: uuid.UUID, req: ContaFixaAtualizarRequest, db: Session = Depends(db_sessao)):
    conta = _conta_fixa_ou_404(db, conta_id)
    for campo, valor in req.model_dump(exclude_unset=True).items():
        if campo == "valor_padrao":
            valor = Decimal(str(valor)) if valor else None
        if campo in ("nome", "categoria") and valor is None:
            continue
        if campo == "agendado_ate":
            valor = valor or None
        setattr(conta, campo, valor)
    db.flush()
    financeiro.aplicar_agendamento(db, conta, hoje_br())
    db.commit()
    return conta


@rotas.delete("/api/financeiro/contas-fixas/{conta_id}", responses={404: {"model": ErroResponse}})
def api_apagar_conta_fixa(conta_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Para de lançar a conta nos próximos meses (o histórico fica). Tira o
    lançamento em aberto e sem valor deste mês em diante."""
    conta = _conta_fixa_ou_404(db, conta_id)
    conta.ativa = False
    hoje = hoje_br()
    db.query(Despesa).filter(
        Despesa.recorrente_id == conta.id, Despesa.pago.is_(False), Despesa.competencia >= f"{hoje.year:04d}-{hoje.month:02d}",
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@rotas.get("/api/financeiro/rotinas", response_model=list[RotinaResponse])
def api_listar_rotinas(db: Session = Depends(db_sessao)):
    return db.query(RotinaMensal).order_by(RotinaMensal.ativa.desc(), RotinaMensal.ordem, RotinaMensal.nome).all()


@rotas.post("/api/financeiro/rotinas", response_model=RotinaResponse)
def api_criar_rotina(req: RotinaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    rotina = financeiro.criar_rotina(db, prestador_id, req.nome)
    db.commit()
    return rotina


def _rotina_ou_404(db: Session, rotina_id: uuid.UUID) -> RotinaMensal:
    rotina = db.get(RotinaMensal, rotina_id)
    if rotina is None:
        raise HTTPException(status_code=404, detail="Item da rotina não encontrado.")
    return rotina


@rotas.put("/api/financeiro/rotinas/ordem")
def api_ordenar_rotinas(req: OrdemRequest, db: Session = Depends(db_sessao)):
    """Nova ordem dos itens da rotina de fechamento (arrastar na tela)."""
    por_id = {r.id: r for r in db.query(RotinaMensal)}
    for posicao, rotina_id in enumerate(req.ids, start=1):
        if rotina_id in por_id:
            por_id[rotina_id].ordem = posicao
    db.commit()
    return {"ok": True}


@rotas.patch("/api/financeiro/rotinas/{rotina_id}", response_model=RotinaResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_rotina(rotina_id: uuid.UUID, req: RotinaAtualizarRequest, db: Session = Depends(db_sessao)):
    rotina = _rotina_ou_404(db, rotina_id)
    if req.nome is not None:
        rotina.nome = req.nome.strip()
    if req.ativa is not None:
        rotina.ativa = req.ativa
    db.commit()
    return rotina


@rotas.post("/api/financeiro/rotinas/{rotina_id}/check", responses={404: {"model": ErroResponse}})
def api_check_rotina(
    rotina_id: uuid.UUID, req: RotinaCheckRequest, db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    financeiro.marcar_rotina(db, prestador_id, _rotina_ou_404(db, rotina_id), req.competencia, req.feita)
    db.commit()
    return {"ok": True}


def _ano_planilha(ano: int | None) -> int:
    if ano is None:
        return hoje_br().year
    if not 2000 <= ano <= 2100:
        raise HTTPException(status_code=422, detail="Ano inválido.")
    return ano


@rotas.post("/api/importar/planilha/previa", responses={400: {"model": ErroResponse}})
def api_previa_planilha(arquivo: UploadFile = File(...), ano: int | None = Form(default=None), db: Session = Depends(db_sessao)):
    """Lê a planilha e devolve o que seria importado — não grava nada."""
    try:
        return importar_planilha.previa(db, _ler_upload(arquivo, 10), _ano_planilha(ano), hoje_br())
    except importar_planilha.PlanilhaInvalidaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@rotas.post("/api/importar/planilha", response_model=ImportarPlanilhaResponse, responses={400: {"model": ErroResponse}}, dependencies=[Depends(exigir_conta_real)])
def api_importar_planilha(
    arquivo: UploadFile = File(...), ano: int | None = Form(default=None), escolhas: str = Form(default="{}"),
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    try:
        opcoes = json.loads(escolhas)
        if not isinstance(opcoes, dict):
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Escolhas inválidas.") from exc
    try:
        resultado = importar_planilha.importar(
            db, db.get(Prestador, prestador_id), _ler_upload(arquivo, 10), _ano_planilha(ano), opcoes, hoje_br(),
        )
    except importar_planilha.PlanilhaInvalidaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return resultado


@rotas.get("/api/notas-a-receber", response_model=list[NotaAbertaResponse])
def api_notas_a_receber(db: Session = Depends(db_sessao)):
    """Notas sem pagamento registrado, de todos os meses (Financeiro)."""
    return notas_em_aberto(db)


# --- Clientes do financeiro (de quem o dinheiro entra) ---

class _ClienteAtualizarRequest(BaseModel):
    nome: str | None = Field(default=None, max_length=60)
    ativo: bool | None = None


@rotas.get("/api/financeiro/clientes")
def api_clientes_do_financeiro(ano: str | None = Query(default=None, pattern=r"^\d{4}$"), db: Session = Depends(db_sessao)):
    return clientes.listar(db, ano=ano or str(hoje_br().year))


@rotas.post("/api/financeiro/clientes")
def api_criar_cliente_do_financeiro(
    req: FonteReceitaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Cliente novo só com o nome (o cadastro fiscal, pra emitir nota, é do
    módulo de notas)."""
    vinculo = classificar_extrato.criar_fonte(db, db.get(Prestador, prestador_id), req.nome)
    resposta = {"id": str(vinculo.id), "nome": vinculo.apelido, "ativo": bool(vinculo.ativo), "so_controle": bool(vinculo.sem_nota)}
    db.commit()
    return resposta


@rotas.patch("/api/financeiro/clientes/{vinculo_id}")
def api_atualizar_cliente_do_financeiro(vinculo_id: uuid.UUID, req: _ClienteAtualizarRequest, db: Session = Depends(db_sessao)):
    try:
        resposta = clientes.atualizar(db, vinculo_id, nome=req.nome, ativo=req.ativo)
    except clientes.ClienteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return resposta


# --- Anotações: abas/notas livres que a pessoa cria (05/10/2026) ---

# Cada anotação tem um formato: "texto" (livre, na coluna `texto`), "lista"
# (itens com tique) ou "tabela" (controle com colunas e total). O conteúdo
# da lista e da tabela fica em `dados` (JSONB), sempre conferido aqui.
_ANOTACAO_FORMATOS = ("texto", "lista", "tabela")
_ANOTACAO_TIPOS_COLUNA = ("texto", "valor", "data")
_ANOTACAO_MAX_ITENS = 200
_ANOTACAO_MAX_COLUNAS = 8
_ANOTACAO_MAX_LINHAS = 300
_ANOTACAO_MAX_TEXTO_ITEM = 500
_ANOTACAO_MAX_NOME_COLUNA = 40
_ANOTACAO_MAX_VALOR = Decimal("99999999999.99")
_ANOTACAO_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


class _AnotacaoRequest(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=80)
    texto: str | None = Field(default=None, max_length=20000)
    formato: str | None = Field(default=None, max_length=20)
    dados: dict | None = None


def _anotacao_invalida(mensagem: str = "Não deu pra entender o conteúdo da anotação.") -> HTTPException:
    return HTTPException(status_code=422, detail=mensagem)


def _anotacao_celula(tipo: str, valor):
    """Uma célula da tabela, já no jeito de guardar: texto → str; valor →
    número (ou None se vazio); data → "AAAA-MM-DD" (ou "" se vazia)."""
    if isinstance(valor, bool) or isinstance(valor, (list, dict)):
        raise _anotacao_invalida()
    if tipo == "texto":
        return "" if valor is None else str(valor)[:_ANOTACAO_MAX_TEXTO_ITEM]
    if tipo == "valor":
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        try:
            numero = Decimal(str(valor).strip())
        except ArithmeticError:
            raise _anotacao_invalida("Tem um valor em dinheiro que não deu pra entender.") from None
        if not numero.is_finite() or abs(numero) > _ANOTACAO_MAX_VALOR:
            raise _anotacao_invalida("Tem um valor em dinheiro grande demais.")
        return float(round(numero, 2))
    # data
    if valor is None or valor == "":
        return ""
    if not isinstance(valor, str) or not _ANOTACAO_DATA.fullmatch(valor):
        raise _anotacao_invalida("Tem uma data que não deu pra entender.")
    try:
        date.fromisoformat(valor)
    except ValueError:
        raise _anotacao_invalida("Tem uma data que não existe.") from None
    return valor


def _anotacao_dados(formato: str, dados: dict | None) -> dict | None:
    """Confere e arruma o conteúdo de uma lista ou tabela (limites de
    tamanho, tipos). Formato "texto" não tem `dados`."""
    if formato == "texto":
        return None
    dados = dados or {}
    if formato == "lista":
        itens = dados.get("itens", [])
        if not isinstance(itens, list):
            raise _anotacao_invalida()
        if len(itens) > _ANOTACAO_MAX_ITENS:
            raise _anotacao_invalida(f"A lista pode ter até {_ANOTACAO_MAX_ITENS} itens. Apague algum pra colocar outro.")
        saida = []
        for item in itens:
            if not isinstance(item, dict) or not isinstance(item.get("texto", ""), str):
                raise _anotacao_invalida()
            saida.append({"texto": item.get("texto", "")[:_ANOTACAO_MAX_TEXTO_ITEM], "feito": item.get("feito") is True})
        return {"itens": saida}

    colunas = dados.get("colunas")
    if colunas is None:
        colunas = [{"nome": "Anotação", "tipo": "texto"}]
    linhas = dados.get("linhas", [])
    if not isinstance(colunas, list) or not isinstance(linhas, list):
        raise _anotacao_invalida()
    if not colunas:
        raise _anotacao_invalida("A tabela precisa de pelo menos uma coluna.")
    if len(colunas) > _ANOTACAO_MAX_COLUNAS:
        raise _anotacao_invalida(f"A tabela pode ter até {_ANOTACAO_MAX_COLUNAS} colunas.")
    if len(linhas) > _ANOTACAO_MAX_LINHAS:
        raise _anotacao_invalida(f"A tabela pode ter até {_ANOTACAO_MAX_LINHAS} linhas. Apague alguma pra colocar outra.")
    colunas_ok = []
    for coluna in colunas:
        if not isinstance(coluna, dict) or not isinstance(coluna.get("nome", ""), str):
            raise _anotacao_invalida()
        if coluna.get("tipo") not in _ANOTACAO_TIPOS_COLUNA:
            raise _anotacao_invalida("Tipo de coluna desconhecido. Use texto, valor ou data.")
        colunas_ok.append({"nome": coluna.get("nome", "").strip()[:_ANOTACAO_MAX_NOME_COLUNA], "tipo": coluna["tipo"]})
    linhas_ok = []
    for linha in linhas:
        if not isinstance(linha, list):
            raise _anotacao_invalida()
        # Linha mais curta que o cabeçalho ganha células vazias; sobra é cortada.
        linhas_ok.append([
            _anotacao_celula(coluna["tipo"], linha[i] if i < len(linha) else None)
            for i, coluna in enumerate(colunas_ok)
        ])
    return {"colunas": colunas_ok, "linhas": linhas_ok}


def _anotacao_formato(formato: str | None) -> str | None:
    if formato is not None and formato not in _ANOTACAO_FORMATOS:
        raise _anotacao_invalida("Formato de anotação desconhecido. Use texto, lista ou tabela.")
    return formato


def _anotacao_dict(a: Anotacao) -> dict:
    return {
        "id": str(a.id), "titulo": a.titulo, "texto": a.texto,
        "formato": a.formato or "texto", "dados": a.dados, "atualizado_em": a.atualizado_em,
    }


@rotas.get("/api/financeiro/anotacoes")
def api_listar_anotacoes(db: Session = Depends(db_sessao)):
    return [_anotacao_dict(a) for a in db.query(Anotacao).order_by(Anotacao.ordem, Anotacao.criado_em)]


@rotas.post("/api/financeiro/anotacoes")
def api_criar_anotacao(req: _AnotacaoRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    if db.query(Anotacao).count() >= 30:
        raise HTTPException(status_code=422, detail="Dá pra ter até 30 anotações. Apague alguma pra criar outra.")
    formato = _anotacao_formato(req.formato) or "texto"
    dados = _anotacao_dados(formato, req.dados)
    ordem = (db.query(func.max(Anotacao.ordem)).scalar() or 0) + 1
    nota = Anotacao(
        id=uuid.uuid4(), prestador_id=prestador_id, titulo=(req.titulo or "Nova anotação").strip()[:80],
        texto=req.texto or "", formato=formato, dados=dados, ordem=ordem,
    )
    db.add(nota)
    db.flush()
    resposta = _anotacao_dict(nota)
    db.commit()
    return resposta


@rotas.patch("/api/financeiro/anotacoes/{anotacao_id}")
def api_atualizar_anotacao(anotacao_id: uuid.UUID, req: _AnotacaoRequest, db: Session = Depends(db_sessao)):
    nota = db.get(Anotacao, anotacao_id)
    if nota is None:
        raise HTTPException(status_code=404, detail="Anotação não encontrada.")
    if req.titulo is not None:
        nota.titulo = req.titulo.strip()[:80] or nota.titulo
    if req.texto is not None:
        nota.texto = req.texto
    formato_novo = _anotacao_formato(req.formato)
    if formato_novo is not None or req.dados is not None:
        formato = formato_novo or nota.formato or "texto"
        # Sem `dados` no pedido: mantém o que já tinha se o formato é o mesmo;
        # se mudou, começa vazio (a tela manda o conteúdo já convertido).
        bruto = req.dados if req.dados is not None else (nota.dados if formato == nota.formato else None)
        nota.dados = _anotacao_dados(formato, bruto)
        nota.formato = formato
    db.flush()
    resposta = _anotacao_dict(nota)
    db.commit()
    return resposta


@rotas.delete("/api/financeiro/anotacoes/{anotacao_id}")
def api_apagar_anotacao(anotacao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    nota = db.get(Anotacao, anotacao_id)
    if nota is None:
        raise HTTPException(status_code=404, detail="Anotação não encontrada.")
    db.delete(nota)
    db.commit()
    return {"ok": True}
