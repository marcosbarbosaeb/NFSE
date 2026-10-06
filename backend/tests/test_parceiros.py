"""Parceiras de indicação com comissão (06/10/2026). Só dados sintéticos."""
import datetime
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import Assinatura, ComissaoParceiro, IndicacaoParceiro, Prestador
from app.services import billing, indicacao, parceiros


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


def _admin(db, prestador):
    db.add(Assinatura(id=uuid.uuid4(), prestador_id=prestador.id, status="cortesia"))
    db.flush()


def test_so_a_administracao_cadastra_parceira(client, db, prestador_teste):
    assert client.get("/api/parceiros/acesso").json() == {"admin": False}
    assert client.get("/api/parceiros").status_code == 403
    assert client.post("/api/parceiros", json={"nome": "Contadora Teste", "comissao_pct": 20}).status_code == 403
    _admin(db, prestador_teste)
    assert client.get("/api/parceiros/acesso").json() == {"admin": True}
    r = client.post("/api/parceiros", json={"nome": "Contadora Teste", "email": "C@Teste.com", "comissao_pct": 20, "desconto_1_mes_pct": 50})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["nome"], p["email"], p["comissao_pct"], p["desconto_1_mes_pct"], p["indicados_total"]) == ("Contadora Teste", "c@teste.com", 20.0, 50, 0)
    assert p["link"].endswith(f"/cadastro?ref={p['codigo']}") and "/parceira/" in p["painel"]
    assert client.post("/api/parceiros", json={"nome": "X", "comissao_pct": 150}).status_code == 422

    # o painel abre só com o link secreto; trocar o link derruba o antigo
    token = p["painel"].rsplit("/", 1)[1]
    assert client.get(f"/api/publico/parceira/{token}").json()["nome"] == "Contadora Teste"
    assert client.get("/api/publico/parceira/" + "x" * 40).status_code == 404
    novo = client.post(f"/api/parceiros/{p['id']}/novo-link").json()
    assert novo["painel"] != p["painel"] and client.get(f"/api/publico/parceira/{token}").status_code == 404
    r = client.patch(f"/api/parceiros/{p['id']}", json={"comissao_pct": 25, "ativo": False})
    assert (r.json()["comissao_pct"], r.json()["ativo"]) == (25.0, False)


def test_indicado_da_parceira_gera_comissao_a_cada_mensalidade_paga(client, db, prestador_teste):
    _admin(db, prestador_teste)
    parceira = parceiros.criar(db, "Economista Teste", None, 20, 50)
    indicado = Prestador(id=uuid.uuid4(), cpf_cnpj="00000000000272", razao_social="CLIENTE INDICADO LTDA", cod_municipio="3106200", modulos=["emissor"])
    definir_prestador_atual(db, indicado.id)  # RLS: a empresa nova entra no contexto dela
    db.add(indicado)
    db.flush()
    # cadastro pelo link da parceira (o mesmo ?ref= do "Indique e ganhe")
    assert indicacao.registrar_indicacao(db, parceira.codigo.lower(), indicado.id, indicado.razao_social) is True
    assert indicacao.registrar_indicacao(db, parceira.codigo, indicado.id, indicado.razao_social) is False  # não duplica
    assert indicacao.registrar_indicacao(db, "NAOEXISTE", uuid.uuid4(), "x") is False
    assert db.get(IndicacaoParceiro, indicado.id).status == "trial"

    # assinou: status vira ativa; cada fatura paga vira uma comissão (uma por fatura)
    parceiros.atualizar_status_indicado(db, indicado.id, "ativa")
    fatura = {"id": "in_teste_1", "amount_paid": 4990, "subscription_details": {"metadata": {"prestador_id": str(indicado.id)}}}
    assert billing._comissao_da_fatura(db, fatura) == "invoice.paid"
    billing._comissao_da_fatura(db, fatura)  # evento repetido do Stripe
    # formato novo da API: metadata dentro de parent.subscription_details
    billing._comissao_da_fatura(db, {"id": "in_teste_2", "amount_paid": 4990, "parent": {"subscription_details": {"metadata": {"prestador_id": str(indicado.id)}}}})
    # fatura de quem não veio por parceira, e fatura zerada: nada
    billing._comissao_da_fatura(db, {"id": "in_outro", "amount_paid": 4990, "subscription_details": {"metadata": {"prestador_id": str(prestador_teste.id)}}})
    billing._comissao_da_fatura(db, {"id": "in_zero", "amount_paid": 0, "subscription_details": {"metadata": {"prestador_id": str(indicado.id)}}})
    comissoes = db.query(ComissaoParceiro).filter_by(parceiro_id=parceira.id).all()
    assert sorted(c.stripe_invoice_id for c in comissoes) == ["in_teste_1", "in_teste_2"]
    assert all((c.valor_pago, c.valor, c.comissao_pct) == (Decimal("49.90"), Decimal("9.98"), Decimal("20.00")) for c in comissoes)

    # painel da parceira: só o primeiro nome do indicado, e o que tem a receber
    painel = parceiros.painel_publico(db, parceira.token_painel)
    assert painel["indicados"] == [{"nome": "Cliente I.", "status": "ativa", "desde": db.get(IndicacaoParceiro, indicado.id).criado_em.date()}]
    assert (painel["indicados_ativos"], painel["total_comissao"], painel["a_receber"]) == (1, 19.96, 19.96)
    mes = painel["meses"][0]["competencia"]

    # a administração vê o nome inteiro e marca o mês como pago
    lista = client.get("/api/parceiros").json()
    assert lista[0]["indicados"][0]["nome"] == "CLIENTE INDICADO LTDA"
    r = client.post(f"/api/parceiros/{parceira.id}/pagar", json={"competencia": mes})
    assert r.status_code == 200 and r.json()["marcadas"] == 2 and r.json()["parceiro"]["a_receber"] == 0
    assert parceiros.painel_publico(db, parceira.token_painel)["meses"][0]["pago_em"] is not None
    assert client.post(f"/api/parceiros/{parceira.id}/pagar", json={"competencia": mes, "pago": False}).json()["marcadas"] == 2

    # parceira desativada: o código para de valer pra cadastros novos, mas quem
    # ela já trouxe continua rendendo; comissão em 0% é que encerra
    parceiros.atualizar(db, parceira, {"ativo": False})
    assert indicacao.registrar_indicacao(db, parceira.codigo, uuid.uuid4(), "Outra") is False
    billing._comissao_da_fatura(db, {"id": "in_teste_3", "amount_paid": 4990, "subscription_details": {"metadata": {"prestador_id": str(indicado.id)}}})
    assert db.query(ComissaoParceiro).filter_by(parceiro_id=parceira.id).count() == 3
    parceiros.atualizar(db, parceira, {"comissao_pct": 0})
    billing._comissao_da_fatura(db, {"id": "in_teste_4", "amount_paid": 4990, "subscription_details": {"metadata": {"prestador_id": str(indicado.id)}}})
    assert db.query(ComissaoParceiro).filter_by(parceiro_id=parceira.id).count() == 3


def test_desconto_so_na_primeira_mensalidade(db, prestador_teste, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_x")
    criados = []
    monkeypatch.setattr(parceiros.stripe.Coupon, "retrieve", lambda *a, **k: (_ for _ in ()).throw(parceiros.stripe.InvalidRequestError("nao existe", "id")))
    monkeypatch.setattr(parceiros.stripe.Coupon, "create", lambda **k: criados.append(k))
    parceira = parceiros.criar(db, "Parceira Desconto", None, 20, 50)
    assert parceiros.desconto_no_checkout(db, prestador_teste.id) is None  # não veio por parceira
    parceiros.registrar_indicacao(db, parceira.codigo, prestador_teste.id, "Empresa")
    assert parceiros.desconto_no_checkout(db, prestador_teste.id) == [{"coupon": "parceira-1mes-50"}]
    assert (criados[0]["percent_off"], criados[0]["duration"]) == (50, "once")
    # depois da primeira mensalidade paga, não tem mais desconto
    parceiros.registrar_pagamento(db, prestador_teste.id, "in_primeira", Decimal("24.95"))
    assert parceiros.desconto_no_checkout(db, prestador_teste.id) is None
