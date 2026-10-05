"""Conciliação NOTAS x RECEBIMENTOS (05/10/2026): cada nota emitida foi paga?
Dados sintéticos."""
import datetime
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.database import get_db
from app.financeiro import a_receber, conciliacao, conciliacao_notas
from app.main import app, prestador_atual_id
from app.models import AjusteEvento, Emissao, LancamentoBancario, PagamentoRecebido, PrestadorTomador, Tomador
from app.tempo import hoje as hoje_br

HOJE = datetime.date(2026, 10, 5)


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


_numero = iter(range(880001, 899999))


def _nota(db, vinculo, competencia, valor, emitida: datetime.date, documento=None, estado="confirmado"):
    e = Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="78", n_dps=next(_numero), estado=estado, valor=Decimal(str(valor)), origem="importada",
        tomador_snapshot={"apelido": vinculo.apelido}, tomador_documento=documento,
        criado_em=datetime.datetime(emitida.year, emitida.month, emitida.day, 15, 0, tzinfo=datetime.timezone.utc),
    )
    db.add(e)
    db.flush()
    return e


def _pago(db, vinculo, competencia, valor, data=None, nota=None, origem="manual", mes_inteiro=False):
    p = PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=vinculo.prestador_id, competencia=competencia,
        valor=Decimal(str(valor)), data_recebimento=data, emissao_id=nota.id if nota is not None else None,
        origem=origem, mes_inteiro=mes_inteiro,
    )
    db.add(p)
    db.flush()
    return p


def _outro_vinculo(db, prestador, apelido, cnpj, razao, prazo=None, sem_nota=False):
    tomador = Tomador(
        id=uuid.uuid4(), cnpj=cnpj, razao_social=razao, cod_municipio="3550308", cep="01311000",
        logradouro="Av Teste", numero="1", bairro="Centro",
    )
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador.id, tomador_id=tomador.id, apelido=apelido,
        cod_local_prestacao=prestador.cod_municipio, cod_trib_nacional="170601", template_descricao="x",
        ativo=True, dias_para_recebimento=prazo, sem_nota=sem_nota,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def _linha(db, prestador, data, descricao, valor, credito=True):
    return conciliacao.guardar(
        db, prestador.id, [{"data": data, "descricao": descricao, "valor": valor, "credito": credito}], "extrato_teste.csv",
    )[0]


def _itens(painel):
    """Nota comum pelo id dela; mês de notas de vendedores pela chave."""
    return {(i["emissao_id"] if i["tipo"] == "nota" else i["chave"]): i for g in painel["tomadores"] for i in g["itens"]}


def test_status_de_cada_nota(db, prestador_teste, vinculo_teste):
    """Paga (com data e por onde veio), paga a menor/a maior com a diferença,
    em aberto no prazo, atrasada — com e sem prazo cadastrado no tomador."""
    vinculo_teste.dias_para_recebimento = 30
    sem_prazo = _outro_vinculo(db, prestador_teste, "Sem Prazo", "22333444000181", "CLIENTE SEM PRAZO LTDA")
    d = datetime.date

    paga = _nota(db, vinculo_teste, "2026-09", 1000, d(2026, 9, 1))
    _pago(db, vinculo_teste, "2026-09", "1000.03", d(2026, 9, 20), paga, origem="extrato")   # centavos: é "paga"
    a_menor = _nota(db, vinculo_teste, "2026-08", 500, d(2026, 8, 3))
    _pago(db, vinculo_teste, "2026-08", 450, d(2026, 8, 30), a_menor)
    a_maior = _nota(db, vinculo_teste, "2026-07", 300, d(2026, 7, 3))
    _pago(db, vinculo_teste, "2026-07", 200, d(2026, 7, 20), a_maior)
    _pago(db, vinculo_teste, "2026-07", 120, d(2026, 7, 28), a_maior)                          # duas parcelas somam
    no_prazo = _nota(db, vinculo_teste, "2026-10", 800, d(2026, 9, 25))                          # vence 25/10
    atrasada = _nota(db, vinculo_teste, "2026-08", 700, d(2026, 8, 20))                          # venceu 19/09
    velha_sem_prazo = _nota(db, sem_prazo, "2026-07", 250, d(2026, 7, 1))                        # 96 dias
    nova_sem_prazo = _nota(db, sem_prazo, "2026-09", 150, d(2026, 9, 20))
    antiga_paga = _nota(db, sem_prazo, "2026-03", 90, d(2026, 3, 5))
    _pago(db, sem_prazo, "2026-03", 90, d(2026, 3, 30), antiga_paga)
    antiga_aberta = _nota(db, sem_prazo, "2026-02", 60, d(2026, 2, 5))
    cancelada = _nota(db, sem_prazo, "2026-09", 999, d(2026, 9, 2), estado="cancelada")

    painel = conciliacao_notas.painel(db, prestador_teste.id, hoje=HOJE)
    assert painel["modo"] == "notas" and painel["periodo"] == {"desde": "2026-07", "ate": None, "antigas": 1}
    itens = _itens(painel)
    assert cancelada.id not in itens and antiga_paga.id not in itens          # fora do período e resolvida
    assert itens[antiga_aberta.id]["antiga"] is True                          # antiga, mas em aberto: aparece

    i = itens[paga.id]
    assert (i["status"], i["como"], i["pago_em"], i["recebido"], i["diferenca"]) == ("paga", "extrato", d(2026, 9, 20), 1000.03, 0.0)
    i = itens[a_menor.id]
    assert (i["status"], i["recebido"], i["diferenca"], i["conferida"]) == ("paga_a_menor", 450.0, -50.0, False)
    i = itens[a_maior.id]
    assert (i["status"], i["recebido"], i["diferenca"]) == ("paga_a_maior", 320.0, 20.0) and len(i["pagamentos"]) == 2
    i = itens[no_prazo.id]
    assert (i["status"], i["vencimento"], i["sem_prazo"], i["em_aberto"]) == ("em_aberto", d(2026, 10, 25), False, 800.0)
    i = itens[atrasada.id]
    assert (i["status"], i["vencimento"], i["dias_atraso"]) == ("atrasada", d(2026, 9, 19), 16)
    i = itens[velha_sem_prazo.id]
    assert (i["status"], i["sem_prazo"], i["dias_em_aberto"]) == ("atrasada", True, 96)
    i = itens[nova_sem_prazo.id]
    assert (i["status"], i["sem_prazo"]) == ("em_aberto", True)

    r = painel["resumo"]
    assert (r["notas"], r["pagas"]) == (8, 3)
    assert r["faturado"] == 1000 + 500 + 300 + 800 + 700 + 250 + 150 + 60
    assert r["recebido"] == pytest.approx(1000.03 + 450 + 320)
    assert (r["em_aberto"], r["notas_em_aberto"]) == (800 + 700 + 250 + 150 + 60, 5)
    assert (r["atrasado"], r["notas_atrasadas"]) == (700 + 250 + 60, 3)
    assert (r["no_prazo"], r["notas_no_prazo"]) == (950, 2)
    assert (r["diferenca"], r["notas_com_diferenca"], r["diferencas_a_conferir"]) == (-30.0, 2, 2)
    estado = painel["estado"]
    assert estado["ok"] is False and (estado["atrasadas"], estado["diferencas"], estado["pendencias"]) == (3, 2, 5)

    # por tomador, com subtotal — quem tem atraso maior em aberto vem primeiro
    grupos = painel["tomadores"]
    assert [g["apelido"] for g in grupos] == ["Fornecedor Teste", "Sem Prazo"]
    assert grupos[0]["prazo_dias"] == 30 and grupos[0]["resumo"]["notas"] == 5 and grupos[0]["resumo"]["em_aberto"] == 1500
    assert grupos[1]["resumo"]["notas_atrasadas"] == 2 and grupos[1]["pendencias"] == 2

    # "está certo assim" (imposto retido): a diferença fica conferida e sai das pendências
    for nota in (a_menor, a_maior):
        db.add(AjusteEvento(id=uuid.uuid4(), prestador_id=prestador_teste.id, tipo="pendencia", chave=f"diferenca:{nota.id}", oculto=True))
    # ...e a previsão que a pessoa moveu no calendário vale como vencimento
    db.add(AjusteEvento(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tipo="recebimento_previsto", chave=str(atrasada.id),
        nova_data=d(2026, 10, 20),
    ))
    db.flush()
    painel = conciliacao_notas.painel(db, prestador_teste.id, hoje=HOJE)
    itens = _itens(painel)
    assert itens[a_menor.id]["conferida"] is True and itens[a_menor.id]["status"] == "paga_a_menor"
    assert (itens[atrasada.id]["status"], itens[atrasada.id]["vencimento"]) == ("em_aberto", d(2026, 10, 20))
    assert (painel["estado"]["diferencas"], painel["estado"]["atrasadas"], painel["estado"]["pendencias"]) == (0, 2, 2)

    # período escolhido: só setembro (mais o que ficou pra trás em aberto); "tudo" traz a antiga paga
    setembro = conciliacao_notas.painel(db, prestador_teste.id, desde="2026-09", ate="2026-09", hoje=HOJE)
    assert paga.id in _itens(setembro) and no_prazo.id not in _itens(setembro) and velha_sem_prazo.id in _itens(setembro)
    assert antiga_paga.id in _itens(conciliacao_notas.painel(db, prestador_teste.id, tudo=True, hoje=HOJE))


def test_pagas_sem_como_saber_o_valor(db, prestador_teste, vinculo_teste):
    """Histórico do mês inteiro (planilha) e "considerar recebida" sem valor:
    contam como pagas, mas marcadas — o valor não dá pra conferir."""
    d = datetime.date
    n1 = _nota(db, vinculo_teste, "2026-08", 1000, d(2026, 8, 3))
    n2 = _nota(db, vinculo_teste, "2026-08", 400, d(2026, 8, 9))
    _pago(db, vinculo_teste, "2026-08", 1380, None, origem="planilha", mes_inteiro=True)
    n3 = _nota(db, vinculo_teste, "2026-09", 700, d(2026, 9, 3))
    assert a_receber.conciliar(db, prestador_teste.id, [(vinculo_teste.id, "2026-09")]) == 1

    painel = conciliacao_notas.painel(db, prestador_teste.id, hoje=HOJE)
    itens = _itens(painel)
    for nota in (n1, n2):
        i = itens[nota.id]
        assert (i["status"], i["como"], i["valor_incerto"], i["recebido"], i["recebido_mes"]) == ("paga", "historico", True, None, 1380.0)
    i = itens[n3.id]
    assert (i["status"], i["como"], i["valor_incerto"], i["recebido"]) == ("paga", "sem_valor", True, None)
    r = painel["resumo"]
    # o recebido do mês entra UMA vez (não uma por nota); a baixa sem valor não soma
    assert (r["notas"], r["pagas"], r["notas_sem_valor"], r["recebido"], r["faturado"]) == (3, 3, 3, 1380.0, 2100.0)
    assert painel["estado"]["ok"] is True


def test_notas_de_vendedores_viram_uma_linha_por_mes(client, db, prestador_teste, vinculo_teste):
    """Shopee: centenas de notas pequenas no mês, pagas num depósito só. Uma
    linha por mês, conciliada no total — e sem uma consulta por nota."""
    shopee = _outro_vinculo(db, prestador_teste, "Shopee", "22333444000181", "MARKETPLACE DE TESTE LTDA", prazo=20)
    hoje = hoje_br()
    recente, velho = hoje - datetime.timedelta(days=5), hoje - datetime.timedelta(days=40)
    mes, mes_velho = f"{recente.year:04d}-{recente.month:02d}", f"{velho.year:04d}-{velho.month:02d}"
    if mes == mes_velho:   # dia 6 em diante de um mês longo: joga o lote velho pro mês anterior
        velho = recente.replace(day=1) - datetime.timedelta(days=25)
        mes_velho = f"{velho.year:04d}-{velho.month:02d}"
    for n in range(366):
        _nota(db, shopee, mes, "12.34", recente, documento=f"{10000000000 + n}")
    for n in range(40):
        _nota(db, shopee, mes_velho, "10.00", velho, documento=f"{20000000000 + n}")
    comum = _nota(db, vinculo_teste, mes, 500, recente)

    consultas = []
    conta = lambda conn, cursor, statement, *a: consultas.append(statement)  # noqa: E731
    event.listen(db.bind, "before_cursor_execute", conta)
    try:
        r = client.get("/api/conciliacao/notas")
    finally:
        event.remove(db.bind, "before_cursor_execute", conta)
    assert r.status_code == 200, r.text
    assert len(consultas) <= 16, len(consultas)                               # nada de N+1 com 400 notas
    painel = r.json()
    grupo = next(g for g in painel["tomadores"] if g["apelido"] == "Shopee")
    assert [(i["tipo"], i["competencia"], i["quantidade"], i["valor"], i["status"]) for i in grupo["itens"]] == [
        ("lote", mes, 366, 4516.44, "em_aberto"), ("lote", mes_velho, 40, 400.0, "atrasada"),
    ]
    # as notas de vendedores de um mês contam como UMA ("Shopee + vendedores")
    assert grupo["resumo"]["notas"] == 2 and painel["resumo"]["notas"] == 3
    # o "a receber" de sempre continua sem as notas dos vendedores
    assert [n["emissao_id"] for n in client.get("/api/notas-a-receber").json()] == [str(comum.id)]

    # o depósito da Shopee é registrado no tomador + mês (sem nota única): paga o mês inteiro
    pag = client.post("/api/pagamentos", json={
        "vinculo_id": str(shopee.id), "competencia": mes, "valor": 4516.44, "data_recebimento": hoje.isoformat(),
    })
    assert pag.status_code == 200 and pag.json()["emissao_id"] is None
    # ...e não vira "recebimento sem nota" (as notas dele são as dos vendedores)
    assert client.get("/api/financeiro/recebimentos-sem-nota").json() == []
    # depósito menor que o total no outro mês: aparece a diferença
    client.post("/api/pagamentos", json={"vinculo_id": str(shopee.id), "competencia": mes_velho, "valor": 380})
    painel = client.get("/api/conciliacao/notas").json()
    grupo = next(g for g in painel["tomadores"] if g["apelido"] == "Shopee")
    atual, anterior = grupo["itens"]
    assert (atual["status"], atual["recebido"], atual["como"], atual["pago_em"]) == ("paga", 4516.44, "manual", hoje.isoformat())
    assert (anterior["status"], anterior["recebido"], anterior["diferenca"]) == ("paga_a_menor", 380.0, -20.0)
    assert painel["recebimentos_sem_nota"] == [] and grupo["resumo"]["pagas"] == 2

    # desfazer: apaga só aquele recebimento e o mês volta a ficar em aberto
    assert client.delete(f"/api/pagamentos/{pag.json()['id']}").json() == {"removidos": 1}
    assert client.delete(f"/api/pagamentos/{uuid.uuid4()}").status_code == 404
    grupo = next(g for g in client.get("/api/conciliacao/notas").json()["tomadores"] if g["apelido"] == "Shopee")
    assert grupo["itens"][0]["status"] == "em_aberto"


def test_sugestao_vinda_do_extrato_nunca_confirma_sozinha(client, db, prestador_teste, vinculo_teste):
    """Entrada pendente do extrato com o valor da nota e o nome do tomador:
    "parece o pagamento da nota X" — a pessoa confirma com um clique."""
    hoje = hoje_br()
    emitida = hoje - datetime.timedelta(days=10)
    mes = f"{emitida.year:04d}-{emitida.month:02d}"
    outro = _outro_vinculo(db, prestador_teste, "Padaria Central", "22333444000181", "PADARIA CENTRAL LTDA")
    nota = _nota(db, vinculo_teste, mes, "1234.56", emitida)
    da_padaria = _nota(db, outro, mes, "1234.56", emitida)        # mesmo valor, outro cliente
    sem_nome = _nota(db, outro, mes, "777.00", emitida)
    quase = _nota(db, outro, mes, "2000.00", emitida)

    certa = _linha(db, prestador_teste, hoje, "Pix recebido TOMADOR DE TESTE LTDA", 1234.56)
    unica = _linha(db, prestador_teste, hoje, "Pix recebido", 777)
    parecida = _linha(db, prestador_teste, hoje, "TED PADARIA CENTRAL", 1999.5)
    _linha(db, prestador_teste, hoje, "Tarifa pacote", 49.9, credito=False)                 # saída: não entra

    painel = client.get("/api/conciliacao/notas").json()
    itens = _itens(painel)
    assert {l["id"] for l in painel["lancamentos"]} == {str(certa.id), str(unica.id), str(parecida.id)}
    sug = itens[str(nota.id)]["sugestao"]
    assert sug["lancamento_id"] == str(certa.id) and sug["confianca"] == "alta"
    assert sug["motivos"][:2] == ["mesmo valor", "nome do cliente no extrato"]
    # a linha diz "TOMADOR DE TESTE": não é sugerida pra nota de mesmo valor da padaria
    assert itens[str(da_padaria.id)]["sugestao"] is None
    assert str(certa.id) not in [c["lancamento_id"] for c in itens[str(da_padaria.id)]["candidatos"]]
    # sem nome na linha: só porque é a única nota e a única entrada desse valor
    sug = itens[str(sem_nome.id)]["sugestao"]
    assert (sug["lancamento_id"], sug["confianca"]) == (str(unica.id), "media") and "única nota em aberto desse valor" in sug["motivos"]
    # nome bate, valor quase igual (dentro de R$ 1,00 ou 0,5%)
    sug = itens[str(quase.id)]["sugestao"]
    assert (sug["lancamento_id"], sug["confianca"], sug["diferenca"]) == (str(parecida.id), "media", -0.5)
    assert painel["estado"]["sugestoes"] == 3 and painel["estado"]["ok"] is False

    # "não é esse": a sugestão some, mas a linha continua oferecida pra ligar à mão
    chave = f"sugestao:{parecida.id}:nota:{quase.id}"
    assert client.post("/api/painel/pendencias/ignorar", json={"chave": chave}).status_code == 200
    i = _itens(client.get("/api/conciliacao/notas").json())[str(quase.id)]
    assert i["sugestao"] is None and i["candidatos"][0]["lancamento_id"] == str(parecida.id)
    assert client.post("/api/painel/pendencias/ignorar", json={"chave": chave, "ignorar": False}).status_code == 200

    # olhar a tela não confirma nada
    assert db.query(PagamentoRecebido).count() == 0
    assert db.get(LancamentoBancario, certa.id).status == "pendente"

    # um clique: a rota de conciliação que já existia
    r = client.post(f"/api/conciliacao/{certa.id}/receita", json={"vinculo_id": str(vinculo_teste.id), "emissao_id": str(nota.id)})
    assert r.status_code == 200, r.text
    painel = client.get("/api/conciliacao/notas").json()
    i = _itens(painel)[str(nota.id)]
    assert (i["status"], i["como"], i["pago_em"], i["sugestao"]) == ("paga", "extrato", hoje.isoformat(), None)
    assert str(certa.id) not in {l["id"] for l in painel["lancamentos"]} and painel["estado"]["sugestoes"] == 2


def test_sugestao_pro_mes_das_notas_de_vendedores_e_regra_lembrada(client, db, prestador_teste, vinculo_teste):
    """O depósito do marketplace bate com a soma das notas dos vendedores do
    mês; e uma descrição já classificada antes (regra_extrato) vale como nome."""
    hoje = hoje_br()
    emitida = hoje - datetime.timedelta(days=8)
    mes = f"{emitida.year:04d}-{emitida.month:02d}"
    shopee = _outro_vinculo(db, prestador_teste, "Shopee", "22333444000181", "MARKETPLACE DE TESTE LTDA", prazo=30)
    for n in range(30):
        _nota(db, shopee, mes, "20.00", emitida, documento=f"{30000000000 + n}")
    nota = _nota(db, vinculo_teste, mes, 900, emitida)
    deposito = _linha(db, prestador_teste, hoje, "TED MARKETPLACE DE TESTE", 600)
    # "EXI IMPORTACAO" não lembra o nome do tomador — mas já foi classificado assim antes
    from app.financeiro.classificar_extrato import lembrar

    lembrar(db, prestador_teste.id, "Pix recebido EXI IMPORTACAO", credito=True, vinculo_id=vinculo_teste.id)
    lembrado = _linha(db, prestador_teste, hoje, "Pix recebido EXI IMPORTACAO", 900)

    itens = _itens(client.get("/api/conciliacao/notas").json())
    lote = itens[f"lote:{shopee.id}:{mes}"]
    assert lote["sugestao"]["lancamento_id"] == str(deposito.id) and lote["sugestao"]["confianca"] == "alta"
    sug = itens[str(nota.id)]["sugestao"]
    assert sug["lancamento_id"] == str(lembrado.id) and "como da última vez" in sug["motivos"]

    # confirmar o do lote: a baixa fica ligada a UMA das notas do mês (a que a linha indica)
    r = client.post(f"/api/conciliacao/{deposito.id}/receita", json={"vinculo_id": str(shopee.id), "emissao_id": lote["emissao_id"]})
    assert r.status_code == 200 and r.json()["emissao_id"] == lote["emissao_id"] and r.json()["competencia"] == mes
    lote = _itens(client.get("/api/conciliacao/notas").json())[f"lote:{shopee.id}:{mes}"]
    assert (lote["status"], lote["recebido"], lote["como"], len(lote["pagamentos"])) == ("paga", 600.0, "extrato", 1)
    # ...que é como o calendário já entendia "mês pago"
    assert a_receber.Baixas(db).mes_pago(shopee.id, mes) is True
    assert client.get("/api/financeiro/recebimentos-sem-nota").json() == []


def test_recebimento_sem_nota_e_o_problema_espelhado(client, db, prestador_teste, vinculo_teste):
    hoje = hoje_br()
    mes = f"{hoje.year:04d}-{hoje.month:02d}"
    pag = client.post("/api/pagamentos", json={"vinculo_id": str(vinculo_teste.id), "competencia": mes, "valor": 321}).json()
    painel = client.get("/api/conciliacao/notas").json()
    assert [(r["pagamento_id"], r["valor"]) for r in painel["recebimentos_sem_nota"]] == [(pag["id"], 321.0)]
    assert painel["estado"]["sem_nota"] == 1 and painel["estado"]["ok"] is False
    resumo = client.get("/api/conciliacao/resumo").json()
    assert resumo["notas"]["sem_nota"] == 1 and resumo["notas"]["pendencias"] == 1
    # aviso ignorado sai da conta (mesma regra do card do Financeiro)
    assert client.post("/api/painel/pendencias/ignorar", json={"chave": f"semnota:{pag['id']}"}).status_code == 200
    assert client.get("/api/conciliacao/notas").json()["estado"]["ok"] is True


def test_resumo_das_duas_conciliacoes_e_fechamento_do_mes(client, db, prestador_teste, vinculo_teste):
    hoje = hoje_br()
    este = f"{hoje.year:04d}-{hoje.month:02d}"
    inicio_passado = (hoje.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    passado = f"{inicio_passado.year:04d}-{inicio_passado.month:02d}"
    vinculo_teste.dias_para_recebimento = 1
    vencida = _nota(db, vinculo_teste, passado, 500, inicio_passado)
    if hoje.day > 2:
        vencida.criado_em = datetime.datetime.combine(hoje - datetime.timedelta(days=3), datetime.time(12), datetime.timezone.utc)
    vazio = client.get("/api/conciliacao/resumo").json()
    assert vazio["extrato"] == {
        "linhas": 0, "classificadas": 0, "pendentes": 0, "pendentes_entradas": 0, "pendentes_saidas": 0, "ignoradas": 0,
        "de": None, "ate": None, "ultimo_arquivo": None, "ultimo_importado_em": None, "ok": True,
    }

    entrada = _linha(db, prestador_teste, inicio_passado, "Pix recebido de alguem", 500)
    saida = _linha(db, prestador_teste, inicio_passado + datetime.timedelta(days=3), "Tarifa pacote de servicos", 49.9, credito=False)
    ignorada = _linha(db, prestador_teste, hoje, "Aplicacao CDB", 1000, credito=False)
    conciliacao.ignorar(db, ignorada.id)
    conciliacao.como_despesa(db, saida.id, prestador_teste.id, hoje=hoje, categoria="Tarifas bancárias")

    resumo = client.get("/api/conciliacao/resumo").json()
    e = resumo["extrato"]
    assert (e["linhas"], e["classificadas"], e["pendentes"], e["pendentes_entradas"], e["ignoradas"], e["ok"]) == (3, 1, 1, 1, 1, False)
    assert (e["de"], e["ate"], e["ultimo_arquivo"]) == (inicio_passado.isoformat(), hoje.isoformat(), "extrato_teste.csv")
    n = resumo["notas"]
    assert (n["aplica"], n["ok"], n["atrasadas"], n["notas"], n["pagas"]) == (True, False, 1, 1, 0)
    assert resumo["pendencias"] == n["pendencias"] + 1
    por_mes = {f["competencia"]: f for f in resumo["fechamentos"]}
    assert len(por_mes) == 3 and por_mes[este]["em_andamento"] is True
    f = por_mes[passado]
    assert (f["estado"], f["notas"], f["notas_atrasadas"], f["extrato_linhas"], f["extrato_pendentes"]) == ("pendente", 1, 1, 2, 1)
    assert por_mes[este]["estado"] == "fechado" and por_mes[este]["extrato_linhas"] == 1   # só a linha ignorada

    # resolve as duas: a entrada do extrato paga a nota -> o mês fecha
    assert client.post(
        f"/api/conciliacao/{entrada.id}/receita", json={"vinculo_id": str(vinculo_teste.id), "emissao_id": str(vencida.id)},
    ).status_code == 200
    resumo = client.get("/api/conciliacao/resumo").json()
    assert resumo["pendencias"] == 0 and resumo["notas"]["ok"] is True and resumo["extrato"]["ok"] is True
    assert {f["competencia"]: f["estado"] for f in resumo["fechamentos"]}[passado] == "fechado"

    # nota nova ainda dentro do prazo: nada a fazer, mas o mês fica "aguardando"
    vinculo_teste.dias_para_recebimento = 45
    _nota(db, vinculo_teste, este, 100, hoje)
    resumo = client.get("/api/conciliacao/resumo").json()
    assert resumo["notas"]["ok"] is True and resumo["notas"]["no_prazo"] == 1
    assert {f["competencia"]: f["estado"] for f in resumo["fechamentos"]}[este] == "aguardando"


def test_empresa_so_com_o_financeiro(client, db, prestador_teste):
    """Sem o módulo de notas não há nota pra conferir: a parte das notas dá
    lugar a "de quem o dinheiro entrou", e só o extrato conta pro fechamento."""
    prestador_teste.modulos = ["financeiro"]
    db.flush()
    hoje = hoje_br()
    mes = f"{hoje.year:04d}-{hoje.month:02d}"
    cliente = client.post("/api/financeiro/clientes", json={"nome": "Padaria Central"}).json()
    outro = client.post("/api/financeiro/clientes", json={"nome": "Oficina"}).json()
    for vinculo, valor in ((cliente, 250), (cliente, 100), (outro, 80)):
        assert client.post("/api/pagamentos", json={
            "vinculo_id": vinculo["id"], "competencia": mes, "valor": valor, "data_recebimento": hoje.isoformat(),
        }).status_code == 200
    _linha(db, prestador_teste, hoje, "Pix recebido PADARIA CENTRAL", 40)

    painel = client.get("/api/conciliacao/notas").json()
    assert painel["modo"] == "recebimentos" and painel["emissor"] is False
    assert painel["tomadores"] == [] and painel["recebimentos_sem_nota"] == [] and painel["estado"]["ok"] is True
    assert [(c["nome"], c["recebido"], c["recebimentos"], c["ultimo"]) for c in painel["clientes"]] == [
        ("Padaria Central", 350.0, 2, hoje.isoformat()), ("Oficina", 80.0, 1, hoje.isoformat()),
    ]
    resumo = client.get("/api/conciliacao/resumo").json()
    assert resumo["notas"]["aplica"] is False and resumo["notas"]["pendencias"] == 0
    assert resumo["extrato"]["pendentes"] == 1 and resumo["pendencias"] == 1
    assert {f["competencia"]: f["estado"] for f in resumo["fechamentos"]}[mes] == "pendente"


def test_rotas_novas_fecham_sem_o_modulo_financeiro(client, db, prestador_teste):
    prestador_teste.modulos = ["emissor"]
    db.flush()
    for metodo, rota in (("get", "/api/conciliacao/notas"), ("get", "/api/conciliacao/resumo"), ("delete", f"/api/pagamentos/{uuid.uuid4()}")):
        r = getattr(client, metodo)(rota)
        assert r.status_code == 403 and "Financeiro" in r.json()["detail"], rota
    prestador_teste.modulos = ["emissor", "financeiro"]
    db.flush()
    assert client.get("/api/conciliacao/notas?desde=2026-13").status_code == 422


def test_deposito_do_marketplace_paga_a_nota_dele_e_as_dos_vendedores(client, db, prestador_teste, vinculo_teste):
    """06/10/2026: a Shopee deposita tudo na nota dela. O que "sobra" nessa
    nota é o pagamento das notas de vendedores do mês — a conta tem que
    fechar com as duas juntas, sem "paga a maior"."""
    shopee = _outro_vinculo(db, prestador_teste, "Shopee", "22333444000181", "MARKETPLACE DE TESTE LTDA", prazo=20)
    hoje = hoje_br()
    dia = hoje - datetime.timedelta(days=5)
    mes = f"{dia.year:04d}-{dia.month:02d}"
    for n in range(40):
        _nota(db, shopee, mes, "10.00", dia, documento=f"{30000000000 + n}")
    dela = _nota(db, shopee, mes, 3000, dia)

    def shopee_do_painel():
        painel = client.get("/api/conciliacao/notas").json()
        grupo = next(g for g in painel["tomadores"] if g["apelido"] == "Shopee")
        nota = next(i for i in grupo["itens"] if i["tipo"] == "nota")
        lote = next(i for i in grupo["itens"] if i["tipo"] == "lote")
        return painel, nota, lote

    # depósito = nota dela + vendedores (com 15 centavos de arredondamento)
    pag = client.post("/api/pagamentos", json={"vinculo_id": str(shopee.id), "competencia": mes, "emissao_id": str(dela.id), "valor": 3399.85, "data_recebimento": hoje.isoformat()})
    assert pag.status_code == 200, pag.text
    painel, nota, lote = shopee_do_painel()
    assert (nota["status"], nota["diferenca"], nota["recebido"]) == ("paga", 0.0, 3399.85)
    assert nota["cobre_lote"] == {"quantidade": 40, "valor": 400.0}
    assert (lote["status"], lote["como"], lote["valor_incerto"]) == ("paga", "junto", False)
    assert painel["resumo"]["diferenca"] == 0 and painel["estado"]["diferencas"] == 0
    # a conta fecha: faturado - recebido não passa da folga
    assert abs(painel["resumo"]["faturado"] - painel["resumo"]["recebido"]) < 1

    # depósito bem maior que as duas juntas: aí sim sobra, e é só o que sobra de verdade
    client.delete(f"/api/pagamentos/{pag.json()['id']}")
    client.post("/api/pagamentos", json={"vinculo_id": str(shopee.id), "competencia": mes, "emissao_id": str(dela.id), "valor": 3900, "data_recebimento": hoje.isoformat()})
    painel, nota, lote = shopee_do_painel()
    assert (nota["status"], nota["diferenca"]) == ("paga_a_maior", 500.0)
    assert painel["resumo"]["diferenca"] == 500.0
    # marcada como resolvida: sai da diferença do período
    client.post("/api/painel/pendencias/ignorar", json={"chave": f"diferenca:{dela.id}", "ignorar": True})
    painel, nota, lote = shopee_do_painel()
    assert nota["conferida"] is True and painel["resumo"]["diferenca"] == 0 and painel["estado"]["diferencas"] == 0
