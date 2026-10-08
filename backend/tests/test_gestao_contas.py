"""Gestão manual das contas (08/10/2026): bloquear, desbloquear e excluir,
telefone na lista e a contagem de e-mails por conta. Dados sintéticos."""
import uuid
from decimal import Decimal

from app.config import get_settings
from app.database import definir_prestador_atual
from app.models import AcessoContador, Emissao, Envio, Prestador, PrestadorTomador, Tomador, Usuario

from tests.test_contador import _conta, _convidar_e_aceitar, _entrar, api, cenario  # noqa: F401 (fixtures)

GESTOR = "gestor@plataforma.example"


def _gestor(db, api, monkeypatch):
    _conta(db, "00000000000434", GESTOR, nome="PLATAFORMA")
    monkeypatch.setattr(get_settings(), "admin_emails", GESTOR)
    return _entrar(api, GESTOR)


def _da_gestao(gestor, prestador_id):
    return next(c for c in gestor.get("/api/gestao").json()["contas"] if c["id"] == str(prestador_id))


def test_bloqueio_manual_vale_mesmo_com_o_bloqueio_geral_desligado(db, api, monkeypatch):
    alvo, _ = _conta(db, "00000000000272", "dona@cliente.example", nome="CLIENTE")  # teste em dia
    gestor = _gestor(db, api, monkeypatch)
    cliente = _entrar(api, "dona@cliente.example")
    anotar = lambda: cliente.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"})  # noqa: E731
    assert get_settings().bloqueio_ativo is False and anotar().status_code in (200, 201)

    # quem não é da administração não bloqueia ninguém
    assert cliente.post(f"/api/gestao/contas/{alvo.id}/bloquear", json={}).status_code == 403
    r = gestor.post(f"/api/gestao/contas/{alvo.id}/bloquear", json={"obs": "não pagou o combinado"})
    assert r.status_code == 200 and r.json()["acesso"]["motivo"] == "bloqueada" and r.json()["acesso"]["bloqueado"] is True

    r = anotar()
    assert r.status_code == 402 and "bloqueada" in r.json()["detail"]
    eu = cliente.get("/api/auth/me").json()["acesso"]
    assert (eu["bloqueado"], eu["motivo"]) == (True, "bloqueada")
    assert cliente.get("/api/dps").status_code == 200  # continua consultando
    conta = _da_gestao(gestor, alvo.id)
    assert conta["acesso"]["motivo"] == "bloqueada" and conta["bloqueada_obs"] == "não pagou o combinado"
    # liberar não passa por cima do bloqueio: tem que desbloquear
    gestor.post(f"/api/gestao/contas/{alvo.id}/liberar", json={"sempre": True})
    assert anotar().status_code == 402

    r = gestor.delete(f"/api/gestao/contas/{alvo.id}/bloquear")
    assert r.status_code == 200 and r.json()["acesso"]["motivo"] == "liberacao"
    assert anotar().status_code in (200, 201)


def test_gestora_nao_bloqueia_nem_exclui_a_propria_conta(db, api, monkeypatch):
    gestor = _gestor(db, api, monkeypatch)
    minha = db.query(Usuario).filter_by(email=GESTOR).one().prestador_id
    assert gestor.post(f"/api/gestao/contas/{minha}/bloquear", json={}).status_code == 400
    assert gestor.request("DELETE", f"/api/gestao/contas/{minha}", json={"confirmacao": "00000000000434"}).status_code == 400


def test_excluir_conta_pede_o_cnpj_e_leva_o_login_junto(db, api, cenario, monkeypatch):
    _convidar_e_aceitar(db, api, cenario, ["emitir"])
    gestor = _gestor(db, api, monkeypatch)
    alvo = cenario["cliente"].id
    assert _entrar(api, "dona@cliente.example").request("DELETE", f"/api/gestao/contas/{alvo}", json={"confirmacao": "00000000000272"}).status_code == 403
    assert gestor.request("DELETE", f"/api/gestao/contas/{alvo}", json={"confirmacao": "111"}).status_code == 422
    r = gestor.request("DELETE", f"/api/gestao/contas/{alvo}", json={"confirmacao": "00.000.000/0002-72"})
    assert r.status_code == 200 and r.json()["excluida"] == "CLIENTE LTDA"
    db.expire_all()
    assert db.query(Usuario).filter_by(email="dona@cliente.example").one_or_none() is None
    definir_prestador_atual(db, alvo)
    assert db.get(Prestador, alvo) is None
    assert db.query(AcessoContador).filter_by(prestador_id=alvo).count() == 0
    # a contadora continua com a conta dela, e a Gestão continua funcionando
    assert db.query(Usuario).filter_by(email="contadora@escritorio.example").one_or_none() is not None
    assert all(c["id"] != str(alvo) for c in gestor.get("/api/gestao").json()["contas"])
    assert gestor.request("DELETE", f"/api/gestao/contas/{alvo}", json={"confirmacao": "00000000000272"}).status_code == 404


def test_lista_mostra_telefone_e_conta_os_emails_de_cada_conta_separado(db, api, monkeypatch):
    """`envio` não tem RLS: sem passar pela nota, cada conta mostrava os
    e-mails de todas (a soma saía multiplicada)."""
    a, _ = _conta(db, "00000000000272", "a@cliente.example", nome="A")
    b, _ = _conta(db, "00000000000353", "b@cliente.example", nome="B")
    gestor = _gestor(db, api, monkeypatch)
    definir_prestador_atual(db, a.id)
    a.telefone = "92999990000"
    tomador = Tomador(id=uuid.uuid4(), cnpj="00000000000515", razao_social="TOMADOR SINTETICO LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=a.id, tomador_id=tomador.id, apelido="T", cod_local_prestacao="3106200",
        cod_trib_nacional="170601", template_descricao="x", serie="1", ativo=True,
    )
    db.add(vinculo)
    db.flush()
    nota = Emissao(
        id=uuid.uuid4(), prestador_id=a.id, prestador_tomador_id=vinculo.id, competencia="2026-10", serie="1", n_dps=1,
        estado="confirmado", valor=Decimal("10"), origem="ana", tomador_snapshot={},
    )
    db.add(nota)
    db.flush()
    db.add_all([
        Envio(id=uuid.uuid4(), emissao_id=nota.id, canal="email", status="enviado", tentativas=1),
        Envio(id=uuid.uuid4(), emissao_id=nota.id, canal="email", status="enviado", tentativas=1),
        Envio(id=uuid.uuid4(), emissao_id=nota.id, canal="email", status="falha", tentativas=1),
    ])
    db.flush()

    painel = gestor.get("/api/gestao").json()
    por_id = {c["id"]: c for c in painel["contas"]}
    assert (por_id[str(a.id)]["emails_mes"], por_id[str(a.id)]["emails_falha_mes"], por_id[str(a.id)]["telefone"]) == (2, 1, "92999990000")
    assert (por_id[str(b.id)]["emails_mes"], por_id[str(b.id)]["emails_falha_mes"], por_id[str(b.id)]["telefone"]) == (0, 0, None)
    assert painel["resumo"]["emails_mes"] == 2 and painel["resumo"]["emails_falha_mes"] == 1


# --- versão e novidades por perfil (08/10/2026) --------------------------------


def test_novidades_por_perfil_e_bolinha_do_sino(db, api, cenario):
    from app import novidades

    da_dona = _entrar(api, "dona@cliente.example")
    assert api().get("/api/versao").json() == {"versao": novidades.VERSAO, "ambiente": "producao"}
    assert api().get("/api/novidades").status_code == 401
    d = da_dona.get("/api/novidades").json()
    perfis = {i["perfil"] for v in d["versoes"] for i in v["itens"]}
    assert d["versao"] == novidades.VERSAO and perfis == {"todos", "empresa"} and d["novas"] == 1
    assert da_dona.post("/api/conta/novidades-vistas").json() == {"vista": novidades.VERSAO}
    assert da_dona.get("/api/novidades").json()["novas"] == 0

    # quem atende uma empresa também vê as de contador
    _, da_contadora = _convidar_e_aceitar(db, api, cenario, [])
    perfis = {i["perfil"] for v in da_contadora.get("/api/novidades").json()["versoes"] for i in v["itens"]}
    assert perfis == {"todos", "empresa", "contador"}


def test_versoes_em_ordem_e_com_perfil_valido():
    from app import novidades

    numeros = [novidades._numero(v["versao"]) for v in novidades.VERSOES]
    assert numeros == sorted(numeros, reverse=True) and len(set(numeros)) == len(numeros)
    assert all(i["perfil"] in novidades.PERFIS for v in novidades.VERSOES for i in v["itens"])
    # o registro técnico acompanha: toda versão está no CHANGELOG.md
    from pathlib import Path

    registro = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text(encoding="utf-8")
    assert all(f"## {v['versao']}" in registro for v in novidades.VERSOES)


# --- 08/10/2026 (tarde): WhatsApp no cadastro e autorização depois do teste ------


def test_cadastro_pede_o_whatsapp_e_a_gestao_mostra(db, api, monkeypatch):
    cliente = api()
    base = {"email": "nova@cliente.example", "senha": "SenhaDeTeste123!", "razao_social": "NOVA LTDA", "cpf_cnpj": "00000000000787", "cod_municipio": "3106200"}
    assert cliente.post("/api/cadastro", json=base).status_code == 422  # sem WhatsApp
    r = cliente.post("/api/cadastro", json={**base, "whatsapp": "12345678"})
    assert r.status_code == 422 and "WhatsApp com DDD" in r.json()["detail"]
    assert cliente.post("/api/cadastro", json={**base, "whatsapp": "+55 (92) 99999-0000"}).status_code == 200
    novo = db.query(Usuario).filter_by(email="nova@cliente.example").one()
    assert novo.telefone == "92999990000"
    novo.email_confirmado = True
    db.flush()

    gestor = _gestor(db, api, monkeypatch)
    conta = _da_gestao(gestor, novo.prestador_id)
    assert (conta["telefone"], conta["telefone_origem"]) == ("92999990000", "cadastro")
    # e a pessoa corrige o número no perfil
    dela = _entrar(api, "nova@cliente.example")
    assert dela.patch("/api/conta", json={"telefone": "11 3333-4444"}).json()["telefone"] == "1133334444"
    assert dela.patch("/api/conta", json={"telefone": "9"}).status_code == 422


def test_depois_do_teste_a_pessoa_pede_e_a_gestao_autoriza(db, api, monkeypatch):
    """"Podem começar direto no teste e, depois desse período, me permita
    autorizar o uso" — sem cobrança no ar, o caminho é pedir a liberação."""
    from app.services.email import get_email_sender

    alvo, dona = _conta(db, "00000000000272", "dona@cliente.example", trial_dias=-1, nome="CLIENTE")
    dona.telefone = "92988887777"
    db.flush()
    gestor = _gestor(db, api, monkeypatch)
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    enviados = []
    monkeypatch.setattr(type(get_email_sender()), "enviar", lambda self, **k: enviados.append(k))

    cliente = _entrar(api, "dona@cliente.example")
    r = cliente.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"})
    assert r.status_code == 402 and "peça a liberação" in r.json()["detail"]
    eu = cliente.get("/api/auth/me").json()["acesso"]
    assert (eu["bloqueado"], eu["cobranca_ativa"], eu["liberacao_pedida_em"]) == (True, False, None)

    # pedir é permitido mesmo bloqueada, e avisa a administração (uma vez só)
    assert cliente.post("/api/assinatura/pedir-liberacao").status_code == 200
    assert cliente.post("/api/assinatura/pedir-liberacao").status_code == 200
    assert len(enviados) == 1 and enviados[0]["destinatario"] == [GESTOR] and "CLIENTE LTDA" in enviados[0]["assunto"]
    assert "92988887777" in enviados[0]["corpo_texto"]
    assert cliente.get("/api/auth/me").json()["acesso"]["liberacao_pedida_em"] is not None
    assert _da_gestao(gestor, alvo.id)["liberacao_pedida_em"] is not None

    # a Gestão autoriza: volta a funcionar e o pedido sai da fila
    assert gestor.post(f"/api/gestao/contas/{alvo.id}/liberar", json={"dias": 30}).status_code == 200
    assert cliente.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"}).status_code in (200, 201)
    assert _da_gestao(gestor, alvo.id)["liberacao_pedida_em"] is None


def test_sem_cobranca_o_limite_de_notas_dos_planos_nao_vale(db, api, monkeypatch):
    from app.services import planos

    alvo, _ = _conta(db, "00000000000272", "dona@cliente.example", nome="CLIENTE")
    definir_prestador_atual(db, alvo.id)
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    u = planos.uso(db, alvo.id)
    assert (u["limite"], u["aviso"], u["travado"]) == (None, None, False)
    planos.conferir(db, alvo.id, 9999)  # não levanta
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_sintetica")
    assert planos.uso(db, alvo.id)["limite"] == get_settings().trial_limite_notas
