"""Detalhe do "Mês a mês" do Financeiro (05/10/2026): quanto cada cliente
pagou e quanto se gastou com cada coisa, mês a mês — e a soma do detalhe
tem que bater com o total do resumo. Dados sintéticos."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, PagamentoRecebido, PrestadorTomador


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


def _outro_cliente(db, vinculo, apelido):
    outro = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, tomador_id=vinculo.tomador_id, apelido=apelido,
        cod_local_prestacao=vinculo.cod_local_prestacao, cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="x", serie="1", requer_revisao=True, ativo=True,
    )
    db.add(outro)
    db.flush()
    return outro


def _recebeu(db, vinculo, competencia, valor, origem="manual"):
    db.add(PagamentoRecebido(
        id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=vinculo.prestador_id,
        competencia=competencia, valor=Decimal(valor), origem=origem,
    ))


def _nota(db, vinculo, competencia, valor, n, estado="confirmado"):
    db.add(Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="78", n_dps=n, estado=estado, valor=Decimal(valor), origem="importada",
        tomador_snapshot={"apelido": vinculo.apelido},
    ))


def _gastou(db, prestador, categoria, competencia, valor, descricao=None, tipo="despesa", pago=True):
    db.add(Despesa(
        id=uuid.uuid4(), prestador_id=prestador.id, categoria=categoria, descricao=descricao, tipo=tipo,
        competencia=competencia, valor=Decimal(valor), pago=pago,
    ))


@pytest.fixture
def cenario(db, prestador_teste, vinculo_teste):
    loja = _outro_cliente(db, vinculo_teste, "Loja Sintética")
    # recebimentos: dois clientes, vários meses, centavos quebrados
    _recebeu(db, vinculo_teste, "2026-01", "1000.10")
    _recebeu(db, vinculo_teste, "2026-01", "0.20")
    _recebeu(db, vinculo_teste, "2026-03", "333.33")
    _recebeu(db, loja, "2026-01", "50.05")
    _recebeu(db, loja, "2026-12", "70.70", origem="extrato")
    _recebeu(db, loja, "2026-03", "0", origem="conciliacao")  # baixa histórica, sem valor
    _recebeu(db, loja, "2025-12", "999")  # outro ano: fora
    # notas: só as confirmadas contam no faturado
    _nota(db, vinculo_teste, "2026-01", "1200", 7801)
    _nota(db, loja, "2026-02", "80.80", 7802)
    _nota(db, loja, "2026-02", "500", 7803, estado="rascunho")
    _nota(db, loja, "2026-02", "600", 7804, estado="cancelada")
    # despesas: categoria → coisa
    _gastou(db, prestador_teste, "Escritório", "2026-01", "99.90", "Internet")
    _gastou(db, prestador_teste, "Escritório", "2026-02", "99.90", " internet ")
    _gastou(db, prestador_teste, "Escritório", "2026-03", "109.90", "Internet")
    _gastou(db, prestador_teste, "Escritório", "2026-01", "250", "Contador")
    _gastou(db, prestador_teste, "Escritório", "2026-03", "250", "Contador", pago=False)  # a pagar também conta no resumo
    _gastou(db, prestador_teste, "Simples Nacional", "2026-01", "800.01")
    _gastou(db, prestador_teste, "Simples Nacional", "2026-03", "0.33")
    _gastou(db, prestador_teste, "Escritório", "2025-12", "5000", "Internet")  # outro ano: fora
    # retiradas: linha separada, nunca dentro das despesas
    _gastou(db, prestador_teste, "Distribuição de lucros", "2026-01", "300", "Inter", tipo="retirada")
    _gastou(db, prestador_teste, "Distribuição de lucros", "2026-03", "150.50", "ML", tipo="retirada")
    db.flush()
    return {"principal": vinculo_teste, "loja": loja}


def _linha(linhas, nome):
    return next(l for l in linhas if l["nome"] == nome)


def test_detalhe_por_cliente(client, cenario):
    r = client.get("/api/financeiro/mes-a-mes?ano=2026")
    assert r.status_code == 200
    d = r.json()
    assert d["ano"] == "2026" and d["meses"] == [f"{m:02d}" for m in range(1, 13)]

    # quanto cada cliente pagou, mês a mês — maior primeiro
    assert [c["nome"] for c in d["recebido"]] == ["Fornecedor Teste", "Loja Sintética"]
    principal = _linha(d["recebido"], "Fornecedor Teste")
    assert principal["id"] == str(cenario["principal"].id)
    assert principal["valores"] == [1000.30, 0, 333.33, 0, 0, 0, 0, 0, 0, 0, 0, 0] and principal["total"] == 1333.63
    loja = _linha(d["recebido"], "Loja Sintética")
    assert loja["valores"][0] == 50.05 and loja["valores"][11] == 70.70 and loja["total"] == 120.75
    assert all(len(c["valores"]) == 12 for c in d["recebido"])

    # faturado: só nota confirmada
    assert _linha(d["faturado"], "Fornecedor Teste")["valores"][0] == 1200
    assert _linha(d["faturado"], "Loja Sintética")["valores"][1] == 80.80
    assert _linha(d["faturado"], "Loja Sintética")["total"] == 80.80


def test_detalhe_por_categoria_e_descricao(client, cenario):
    d = client.get("/api/financeiro/mes-a-mes?ano=2026").json()

    assert [c["nome"] for c in d["despesas"]] == ["Escritório", "Simples Nacional"]
    escritorio = _linha(d["despesas"], "Escritório")
    assert escritorio["valores"][:3] == [349.90, 99.90, 359.90] and escritorio["total"] == 809.70
    # "Internet" e " internet " são a mesma coisa; fica a grafia mais usada
    assert [i["nome"] for i in escritorio["itens"]] == ["Contador", "Internet"]
    internet = _linha(escritorio["itens"], "Internet")
    assert internet["valores"][:4] == [99.90, 99.90, 109.90, 0] and internet["total"] == 309.70
    assert _linha(escritorio["itens"], "Contador")["valores"][:3] == [250, 0, 250]
    # sem descrição: a coisa leva o nome da categoria
    simples = _linha(d["despesas"], "Simples Nacional")
    assert [i["nome"] for i in simples["itens"]] == ["Simples Nacional"] and simples["itens"][0]["total"] == 800.34

    # retirada não entra nas despesas — tem a linha dela
    assert all(c["nome"] != "Distribuição de lucros" for c in d["despesas"])
    retiradas = _linha(d["retiradas"], "Distribuição de lucros")
    assert retiradas["valores"][:3] == [300, 0, 150.50]
    assert {i["nome"]: i["total"] for i in retiradas["itens"]} == {"Inter": 300, "ML": 150.50}

    # cada categoria é a soma das suas coisas, mês a mês
    for grupo in d["despesas"] + d["retiradas"]:
        for m in range(12):
            assert round(sum(i["valores"][m] for i in grupo["itens"]), 2) == grupo["valores"][m]
        assert round(sum(grupo["valores"]), 2) == grupo["total"]


def test_soma_do_detalhe_bate_com_o_resumo(client, cenario):
    resumo = client.get("/api/financeiro/resumo?ano=2026").json()
    d = client.get("/api/financeiro/mes-a-mes?ano=2026").json()
    assert resumo["totais"]["recebido"] > 0 and resumo["totais"]["despesas"] > 0 and resumo["totais"]["retiradas"] > 0

    for linha in ("faturado", "recebido", "despesas", "retiradas"):
        for m in range(12):
            assert round(sum(x["valores"][m] for x in d[linha]), 2) == resumo[linha][m], (linha, m)
        assert round(sum(x["total"] for x in d[linha]), 2) == resumo["totais"][linha], linha
    # e as categorias são as mesmas do "Para onde vai o dinheiro"
    assert {c["nome"]: c["total"] for c in d["despesas"]} == {c["categoria"]: c["total"] for c in resumo["categorias"]}


def test_ano_sem_nada_e_ano_invalido(client, cenario):
    vazio = client.get("/api/financeiro/mes-a-mes?ano=2031").json()
    assert vazio["recebido"] == [] and vazio["despesas"] == [] and vazio["retiradas"] == [] and vazio["faturado"] == []
    assert client.get("/api/financeiro/mes-a-mes?ano=26").status_code == 422


def test_so_com_o_modulo_financeiro(client, db, prestador_teste, cenario):
    prestador_teste.modulos = ["emissor"]
    db.flush()
    assert client.get("/api/financeiro/mes-a-mes?ano=2026").status_code == 403
