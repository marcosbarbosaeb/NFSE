"""Planos por limite de notas (07/10/2026). Só dados sintéticos."""
import datetime
import uuid

import pytest

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import Assinatura
from app.services import billing, planos
from app.services.motor_emissao import LimiteDoPlanoError, criar_rascunho, submeter

HOJE = datetime.date(2026, 10, 7)


@pytest.fixture(autouse=True)
def _cobranca_no_ar(monkeypatch):
    """Os limites dos planos só valem com a cobrança no ar (08/10/2026: sem o
    Stripe, quem autoriza o uso é a Gestão e não há limite)."""
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_sintetica")


def _assinatura(db, prestador, **campos) -> Assinatura:
    base = dict(status="ativa", plano="basico", stripe_subscription_id="sub_teste", stripe_customer_id="cus_teste")
    a = Assinatura(id=uuid.uuid4(), prestador_id=prestador.id, **{**base, **campos})
    db.add(a)
    db.flush()
    return a


_SEQ = iter(range(10_000))


def _notas(db, vinculo, quantas: int, *, estado: str = "confirmado", origem: str = "ana", tp_amb: str = "1") -> list:
    """Notas sintéticas. Cada uma numa competência diferente (só pode uma
    nota ativa por tomador e competência); o que conta pro limite é a data
    em que foi criada, não a competência."""
    criadas = []
    for _ in range(quantas):
        n = next(_SEQ)
        nota = criar_rascunho(db, vinculo, competencia=f"{2030 + n // 12:04d}-{n % 12 + 1:02d}", valor=100, tpAmb=tp_amb)
        nota.estado, nota.origem = estado, origem
        criadas.append(nota)
    db.flush()
    return criadas


def test_catalogo_e_escada():
    ids = [p["id"] for p in billing.listar_planos()]
    assert ids == ["basico", "empreendedor", "empresa", "avancado", "ilimitado", "financeiro"]
    por_id = {p["id"]: p for p in billing.listar_planos()}
    assert [por_id[i]["limite_notas"] for i in billing.ESCADA_DE_NOTAS] == [30, 150, 300, 500, None]
    assert [por_id[i]["valor"] for i in ids] == [49.90, 99.90, 129.90, 149.00, 299.00, 39.90]
    assert [por_id[i]["aceita_financeiro"] for i in ids] == [True, True, False, False, False, False]
    assert billing.modulos_do_plano("basico", True) == ["emissor", "financeiro"]
    assert billing.modulos_do_plano("empresa", True) == ["emissor", "financeiro"]
    # plano antigo só aparece pra quem o tem
    assert "ambos" in [p["id"] for p in billing.listar_planos("ambos")]


def test_plano_dos_itens_da_stripe(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "stripe_price_id_basico", "price_b")
    monkeypatch.setattr(s, "stripe_price_id_empresa", "price_e")
    monkeypatch.setattr(s, "stripe_price_id_financeiro", "price_f")
    item = lambda preco: {"price": {"id": preco}}  # noqa: E731
    assert billing.plano_dos_itens([item("price_b")]) == ("basico", False)
    assert billing.plano_dos_itens([item("price_f"), item("price_b")]) == ("basico", True)
    assert billing.plano_dos_itens([item("price_e"), item("price_f")]) == ("empresa", False)  # já inclui
    assert billing.plano_dos_itens([item("price_f")]) == ("financeiro", False)
    assert billing.plano_dos_itens([item("price_desconhecido")]) == (None, False)


def test_limite_por_situacao(db, prestador_teste):
    agora = datetime.datetime.now(datetime.timezone.utc)
    assert planos.limite_da_assinatura(None) == (None, None)
    a = _assinatura(db, prestador_teste, plano="empreendedor")
    assert planos.limite_da_assinatura(a) == (150, "empreendedor")
    a.plano = "ilimitado"
    assert planos.limite_da_assinatura(a) == (None, "ilimitado")
    a.plano = "financeiro"
    assert planos.limite_da_assinatura(a) == (0, "financeiro")
    a.status, a.trial_termina_em = "trial", agora + datetime.timedelta(days=5)
    assert planos.limite_da_assinatura(a) == (150, None)  # teste grátis
    a.liberado_sempre = True  # personalizado: a Gestão liberou
    assert planos.limite_da_assinatura(a) == (None, None)
    a.liberado_sempre, a.status = False, "cortesia"
    assert planos.limite_da_assinatura(a) == (None, None)


def test_so_conta_nota_autorizada_do_mes(db, prestador_teste, vinculo_teste):
    _assinatura(db, prestador_teste)
    autorizadas = _notas(db, vinculo_teste, 3)
    _notas(db, vinculo_teste, 1, estado="cancelada")
    _notas(db, vinculo_teste, 1, estado="erro")
    _notas(db, vinculo_teste, 1, estado="montado")
    _notas(db, vinculo_teste, 1, origem="importada")
    _notas(db, vinculo_teste, 1, tp_amb="2")  # homologação
    hoje = autorizadas[0].criado_em.date()
    assert planos.notas_do_mes(db, prestador_teste.id, hoje) == 3
    mes_que_vem = (hoje.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    assert planos.notas_do_mes(db, prestador_teste.id, mes_que_vem) == 0


def test_aviso_aos_80_e_sugestao_do_plano_de_cima(db, prestador_teste, vinculo_teste):
    _assinatura(db, prestador_teste, plano="basico")
    _notas(db, vinculo_teste, 23)
    u = planos.uso(db, prestador_teste.id)
    assert (u["usadas"], u["limite"], u["aviso"], u["restantes"]) == (23, 30, None, 7)
    _notas(db, vinculo_teste, 1)  # 24 de 30 = 80%
    u = planos.uso(db, prestador_teste.id)
    assert (u["aviso"], u["pct"]) == ("perto", 80)
    assert u["proximo_plano"] == {"id": "empreendedor", "nome": "Empreendedor", "limite_notas": 150, "valor": 99.90}
    _notas(db, vinculo_teste, 6)
    u = planos.uso(db, prestador_teste.id)
    assert (u["aviso"], u["restantes"], u["excedentes"], u["travado"]) == ("limite", 0, 0, False)  # trava desligada


def test_no_limite_trava_ate_subir_de_plano_ou_aceitar_o_excedente(db, prestador_teste, vinculo_teste, monkeypatch):
    a = _assinatura(db, prestador_teste, plano="basico")
    _notas(db, vinculo_teste, 30)
    # com a trava desligada (antes de a cobrança estar no ar) nada é barrado
    planos.conferir(db, prestador_teste.id)
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_sintetica")
    with pytest.raises(planos.LimiteDeNotasError) as erro:
        planos.conferir(db, prestador_teste.id)
    assert "30 de 30" in str(erro.value) and "Empreendedor" in str(erro.value) and "0,80" in str(erro.value)
    assert planos.uso(db, prestador_teste.id)["travado"] is True
    # aceitou pagar por nota a mais: passa
    u = planos.aceitar_excedente(db, prestador_teste.id, True)
    assert (u["excedente_aceito"], u["travado"]) == (True, False)
    planos.conferir(db, prestador_teste.id, 50)
    # desfez: trava de novo; subiu de plano: passa
    planos.aceitar_excedente(db, prestador_teste.id, False)
    with pytest.raises(planos.LimiteDeNotasError):
        planos.conferir(db, prestador_teste.id)
    a.plano = "empreendedor"
    db.flush()
    planos.conferir(db, prestador_teste.id)
    # lote que não cabe
    with pytest.raises(planos.LimiteDeNotasError) as erro:
        planos.conferir(db, prestador_teste.id, 200)
    assert "200 notas" in str(erro.value) and "120" in str(erro.value)


def test_teste_gratis_tem_limite_e_nao_tem_excedente(db, prestador_teste, vinculo_teste, monkeypatch):
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_sintetica")
    monkeypatch.setattr(get_settings(), "trial_limite_notas", 2)
    db.add(Assinatura(id=uuid.uuid4(), prestador_id=prestador_teste.id, status="trial",
                      trial_termina_em=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)))
    db.flush()
    _notas(db, vinculo_teste, 2)
    u = planos.uso(db, prestador_teste.id)
    assert (u["em_teste"], u["limite"], u["excedente_pode"], u["proximo_plano"]["id"]) == (True, 2, False, "basico")
    with pytest.raises(planos.LimiteDeNotasError) as erro:
        planos.conferir(db, prestador_teste.id)
    assert "teste grátis" in str(erro.value) and "0,80" not in str(erro.value)
    with pytest.raises(planos.LimiteDeNotasError):
        planos.aceitar_excedente(db, prestador_teste.id, True)


def test_enviar_a_prefeitura_respeita_o_limite(db, prestador_teste, vinculo_teste, monkeypatch):
    _assinatura(db, prestador_teste, plano="basico")
    _notas(db, vinculo_teste, 30)
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_sintetica")
    nota = _notas(db, vinculo_teste, 1, estado="assinado")[0]
    with pytest.raises(LimiteDoPlanoError):
        submeter(db, nota, cliente=None)
    assert nota.estado == "assinado"  # a nota fica como estava, pronta pra ir depois


def test_excedente_vira_um_item_na_proxima_fatura(db, prestador_teste, vinculo_teste, monkeypatch):
    import stripe

    a = _assinatura(db, prestador_teste, plano="basico", excedente_aceito_em=datetime.datetime.now(datetime.timezone.utc))
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_falsa")
    chamadas = []
    monkeypatch.setattr(stripe.InvoiceItem, "create", lambda **k: chamadas.append(("criar", k["amount"], k["customer"])) or {"id": "ii_1"})

    def _mudar(item, **k):
        chamadas.append(("mudar", item, k["amount"]))

    monkeypatch.setattr(stripe.InvoiceItem, "modify", _mudar)
    _notas(db, vinculo_teste, 30)
    assert planos.cobrar_excedente(db, prestador_teste.id) == 0 and chamadas == []  # dentro do limite
    _notas(db, vinculo_teste, 2)
    assert planos.cobrar_excedente(db, prestador_teste.id) == 2
    assert chamadas == [("criar", 160, "cus_teste")]
    assert planos.cobrar_excedente(db, prestador_teste.id) == 0  # nada novo: não cobra de novo
    _notas(db, vinculo_teste, 1)
    assert planos.cobrar_excedente(db, prestador_teste.id) == 1
    assert chamadas[-1] == ("mudar", "ii_1", 240)  # o mesmo item, agora com 3 notas
    assert list(a.excedente_cobranca.values())[0] == {"item": "ii_1", "item_qtd": 3, "cobradas": 3}
    assert planos.uso(db, prestador_teste.id)["excedente_valor"] == 2.40

    # o item já entrou numa fatura: a Stripe recusa mudar e a Ana abre outro
    def _recusa(item, **k):
        raise RuntimeError("invoice item already invoiced")

    monkeypatch.setattr(stripe.InvoiceItem, "modify", _recusa)
    monkeypatch.setattr(stripe.InvoiceItem, "create", lambda **k: chamadas.append(("criar", k["amount"], k["customer"])) or {"id": "ii_2"})
    _notas(db, vinculo_teste, 1)
    assert planos.cobrar_excedente(db, prestador_teste.id) == 1
    assert chamadas[-1] == ("criar", 80, "cus_teste")
    assert list(a.excedente_cobranca.values())[0] == {"item": "ii_2", "item_qtd": 1, "cobradas": 4}
