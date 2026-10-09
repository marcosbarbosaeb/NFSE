"""Contador com permissões, bloqueio de quem não tem assinatura e liberação
pela Gestão (06/10/2026). Só dados sintéticos. Aqui o login é de verdade
(sem trocar `prestador_atual_id`): é nele que as travas moram."""
import datetime
from decimal import Decimal
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_senha
from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.main import app
from app.models import AcessoContador, Assinatura, Prestador, RegistroContador, Usuario, UsuarioPrestador
from app.services import acesso, billing, contas

SENHA = "SenhaDeTeste123!"
_HASH = hash_senha(SENHA)


@pytest.fixture
def api(db):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    yield lambda: TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _conta(db, cnpj: str, email: str, *, trial_dias: int = 14, nome: str = "EMPRESA") -> tuple[Prestador, Usuario]:
    prestador = Prestador(id=uuid.uuid4(), cpf_cnpj=cnpj, razao_social=f"{nome} LTDA", cod_municipio="3106200", modulos=["emissor", "financeiro"])
    definir_prestador_atual(db, prestador.id)
    db.add(prestador)
    db.flush()
    db.add(Assinatura(
        id=uuid.uuid4(), prestador_id=prestador.id, status="trial",
        trial_termina_em=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=trial_dias),
    ))
    usuario = Usuario(id=uuid.uuid4(), prestador_id=prestador.id, email=email, senha_hash=_HASH, email_confirmado=True, nome=email.split("@")[0])
    db.add(usuario)
    db.flush()
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador.id))
    db.flush()
    return prestador, usuario


def _entrar(api, email: str) -> TestClient:
    cliente = api()
    resposta = cliente.post("/api/auth/login", json={"email": email, "senha": SENHA})
    assert resposta.status_code == 200, resposta.text
    return cliente


@pytest.fixture
def cenario(db, api):
    """Uma empresa cliente e um escritório de contabilidade, cada um com o seu login."""
    cliente, dona = _conta(db, "00000000000272", "dona@cliente.example", nome="CLIENTE")
    escritorio, contadora = _conta(db, "00000000000353", "contadora@escritorio.example", nome="ESCRITORIO")
    return {"cliente": cliente, "dona": dona, "escritorio": escritorio, "contadora": contadora}


def _convidar_e_aceitar(db, api, cenario, permissoes: list[str]) -> tuple[TestClient, TestClient]:
    da_dona = _entrar(api, "dona@cliente.example")
    r = da_dona.post("/api/contador/acessos", json={"email": "Contadora@Escritorio.example", "permissoes": permissoes})
    assert r.status_code == 200, r.text
    da_contadora = _entrar(api, "contadora@escritorio.example")
    convites = da_contadora.get("/api/contador/atendimentos").json()["convites"]
    assert [c["empresa"] for c in convites] == ["CLIENTE LTDA"]
    assert da_contadora.post(f"/api/contador/convites/{convites[0]['id']}/aceitar").status_code == 200
    assert da_contadora.post(f"/api/empresas/{cenario['cliente'].id}/ativar").json()["papel"] == "contador"
    return da_dona, da_contadora


# --- o mapa de permissões cobre todas as rotas --------------------------------

# Rotas que mudam algo mas não são "da empresa ativa" (login, conta, etc.).
_FORA_DA_EMPRESA = (
    "/api/auth/", "/api/cadastro", "/api/conta", "/api/empresas", "/api/webhooks/", "/api/suporte", "/api/demo",
    "/api/certificado/ler", "/api/contador/convites/", "/api/contador/atendimentos/",
)


def test_toda_rota_que_muda_algo_tem_dono_no_mapa_de_permissoes():
    """Rota nova tem que entrar em acesso.REGRAS (com a permissão que o
    contador precisa, LIVRE ou NUNCA) — senão ela cai no "só o dono" sem
    ninguém ter decidido isso."""
    sem_regra = []
    for caminho, metodos in app.openapi()["paths"].items():
        if not caminho.startswith("/api/") or caminho.startswith(_FORA_DA_EMPRESA):
            continue
        exemplo = caminho.replace("{", "").replace("}", "")
        for metodo in metodos:
            if metodo.upper() in ("GET", "HEAD", "OPTIONS"):
                continue
            if not any(metodo.upper() in ms and padrao.fullmatch(exemplo) for ms, padrao, _, _ in acesso.REGRAS):
                sem_regra.append(f"{metodo.upper()} {caminho}")
    assert sem_regra == []


def test_classificar():
    assert acesso.classificar("POST", "/api/dps") == ("emitir", "Criou uma nota")
    assert acesso.classificar("POST", "/api/dps/abc/enviar-email")[0] == "enviar"
    assert acesso.classificar("POST", "/api/vinculos/publicar-sugestoes")[0] == acesso.NUNCA
    assert acesso.classificar("DELETE", "/api/empresa")[0] == acesso.NUNCA
    assert acesso.classificar("POST", "/api/lotes/previa")[0] == acesso.LIVRE
    assert acesso.classificar("GET", "/api/dps")[0] == acesso.LIVRE
    assert acesso.classificar("GET", "/api/contador/acessos")[0] == acesso.NUNCA
    # rota desconhecida que muda algo: só o dono
    assert acesso.classificar("POST", "/api/alguma-coisa-nova")[0] == acesso.NUNCA


# --- convite ------------------------------------------------------------------


def test_convite_aceite_e_o_que_o_contador_enxerga(db, api, cenario):
    da_dona, da_contadora = _convidar_e_aceitar(db, api, cenario, ["financeiro"])
    eu = da_contadora.get("/api/auth/me").json()
    assert eu["prestador_id"] == str(cenario["cliente"].id)
    assert (eu["papel"], eu["permissoes"], eu["atende_empresas"]) == ("contador", ["financeiro"], True)
    # a empresa do cliente aparece no seletor dela, marcada como de contador
    papeis = {e["razao_social"]: e["papel"] for e in da_contadora.get("/api/empresas").json()}
    assert papeis == {"ESCRITORIO LTDA": "dono", "CLIENTE LTDA": "contador"}
    # ...mas a empresa "de casa" do login continua sendo a dela
    assert db.get(Usuario, cenario["contadora"].id).prestador_id == cenario["escritorio"].id
    # a dona vê quem tem acesso
    lista = da_dona.get("/api/contador/acessos").json()["acessos"]
    assert [(a["email"], a["status"], a["permissoes"]) for a in lista] == [("contadora@escritorio.example", "ativo", ["financeiro"])]
    assert da_dona.get("/api/auth/me").json()["papel"] == "dono"


def test_regras_do_convite(db, api, cenario):
    da_dona = _entrar(api, "dona@cliente.example")
    assert da_dona.post("/api/contador/acessos", json={"email": "dona@cliente.example", "permissoes": []}).status_code == 409
    # 09/10/2026: formato de e-mail conferido na entrada, com a frase pra pessoa
    ruim = da_dona.post("/api/contador/acessos", json={"email": "sem-arroba", "permissoes": []})
    assert ruim.status_code == 422 and "não é um e-mail válido" in ruim.text
    assert da_dona.post("/api/contador/acessos", json={"email": "contadora@escritorio.example", "permissoes": ["emitir", "inventada"]}).status_code == 200
    assert da_dona.post("/api/contador/acessos", json={"email": "contadora@escritorio.example", "permissoes": []}).status_code == 409
    convite = db.query(AcessoContador).one()
    assert convite.permissoes == ["emitir"] and convite.status == "pendente"
    # convite pendente não dá acesso nenhum, e outra pessoa não aceita no lugar
    da_contadora = _entrar(api, "contadora@escritorio.example")
    assert da_contadora.post(f"/api/empresas/{cenario['cliente'].id}/ativar").status_code == 404
    _conta(db, "00000000000434", "curioso@outro.example", nome="OUTRA")
    do_curioso = _entrar(api, "curioso@outro.example")
    assert do_curioso.post(f"/api/contador/convites/{convite.id}/aceitar").status_code == 404
    assert do_curioso.get("/api/contador/atendimentos").json()["convites"] == []
    # recusar apaga o convite
    assert da_contadora.post(f"/api/contador/convites/{convite.id}/recusar").status_code == 200
    assert db.query(AcessoContador).count() == 0


# --- permissões ---------------------------------------------------------------


def test_contador_so_faz_o_que_foi_liberado_e_fica_registrado(db, api, cenario):
    da_dona, da_contadora = _convidar_e_aceitar(db, api, cenario, ["financeiro"])
    # ver: sempre
    assert da_contadora.get("/api/vinculos").status_code == 200
    assert da_contadora.get("/api/financeiro/anotacoes").status_code == 200
    # liberado: financeiro
    r = da_contadora.post("/api/financeiro/anotacoes", json={"titulo": "Fechamento", "texto": "ok"})
    assert r.status_code in (200, 201), r.text
    # não liberado: gerar nota e dados da empresa
    r = da_contadora.post("/api/dps", json={})
    assert r.status_code == 403 and "Gerar e cancelar notas" in r.json()["detail"]
    assert da_contadora.patch("/api/prestador/preferencias", json={}).status_code == 403
    # nunca, com qualquer permissão
    assert da_contadora.get("/api/contador/acessos").status_code == 403
    assert da_contadora.post("/api/assinatura/checkout", json={"plano": "emissor"}).status_code == 403
    assert da_contadora.request("DELETE", "/api/empresa", json={"confirmacao": "00000000000272"}).status_code == 403
    assert da_contadora.post("/api/dados/limpar", json={}).status_code == 403
    # só o que deu certo entra no registro, e a dona vê
    assert [(r.email, r.acao) for r in db.query(RegistroContador).all()] == [("contadora@escritorio.example", "Alterou uma anotação")]
    historico = da_dona.get("/api/contador/acessos").json()["historico"]
    assert [h["acao"] for h in historico] == ["Alterou uma anotação"]
    # na empresa DELA a contadora continua dona de tudo
    assert da_contadora.post(f"/api/empresas/{cenario['escritorio'].id}/ativar").json()["papel"] == "dono"
    assert da_contadora.get("/api/contador/acessos").status_code == 200


def test_dona_muda_as_permissoes_e_tira_o_acesso(db, api, cenario):
    da_dona, da_contadora = _convidar_e_aceitar(db, api, cenario, [])
    assert da_contadora.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"}).status_code == 403
    acesso_id = db.query(AcessoContador).one().id
    assert da_dona.patch(f"/api/contador/acessos/{acesso_id}", json={"permissoes": ["financeiro"]}).json()["permissoes"] == ["financeiro"]
    assert da_contadora.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"}).status_code in (200, 201)
    # tirou o acesso: na hora o login dela volta pra empresa dela
    assert da_dona.delete(f"/api/contador/acessos/{acesso_id}").status_code == 200
    eu = da_contadora.get("/api/auth/me").json()
    assert (eu["prestador_id"], eu["papel"]) == (str(cenario["escritorio"].id), "dono")
    assert [e["razao_social"] for e in da_contadora.get("/api/empresas").json()] == ["ESCRITORIO LTDA"]
    # acesso de outra empresa não se mexe daqui
    assert da_contadora.delete(f"/api/contador/acessos/{acesso_id}").status_code == 404


def test_contador_deixa_de_atender(db, api, cenario):
    _, da_contadora = _convidar_e_aceitar(db, api, cenario, ["emitir"])
    atendimento = da_contadora.get("/api/contador/atendimentos").json()["clientes"][0]
    assert (atendimento["empresa"], atendimento["permissoes"]) == ("CLIENTE LTDA", ["emitir"])
    assert da_contadora.delete(f"/api/contador/atendimentos/{atendimento['id']}").status_code == 200
    assert da_contadora.get("/api/auth/me").json()["prestador_id"] == str(cenario["escritorio"].id)
    assert db.query(AcessoContador).count() == 0


def test_apagar_a_conta_da_dona_leva_a_empresa_mesmo_com_contador(db, api, cenario):
    """O contador não é "outro dono": a empresa não fica órfã na mão dele."""
    _convidar_e_aceitar(db, api, cenario, ["emitir"])
    cliente_id = cenario["cliente"].id
    contas.apagar_conta(db, cenario["dona"])
    db.expire_all()
    definir_prestador_atual(db, cliente_id)
    assert db.get(Prestador, cliente_id) is None
    assert db.query(AcessoContador).count() == 0


# --- bloqueio de quem não tem assinatura ---------------------------------------


def test_situacao_do_acesso():
    agora = datetime.datetime(2026, 10, 6, tzinfo=datetime.timezone.utc)
    dia = datetime.timedelta(days=1)

    def a(**campos):
        base = dict(status="trial", trial_termina_em=agora - dia, liberado_ate=None, liberado_sempre=False)
        return type("A", (), {**base, **campos})()

    s = billing.situacao_do_acesso
    assert s(None, agora)["motivo"] == "sem_assinatura"
    assert s(a(trial_termina_em=agora + 3 * dia), agora) == {"liberado": True, "motivo": "teste", "ate": agora + 3 * dia, "dias_restantes": 3}
    assert s(a(), agora)["motivo"] == "teste_acabou" and not s(a(), agora)["liberado"]
    assert s(a(status="cancelada"), agora)["motivo"] == "cancelada"
    assert s(a(status="ativa"), agora)["motivo"] == "assinatura"
    assert s(a(status="cortesia"), agora)["motivo"] == "cortesia"
    assert s(a(liberado_sempre=True), agora) == {"liberado": True, "motivo": "liberacao", "ate": None, "dias_restantes": None}
    assert s(a(status="cancelada", liberado_ate=agora + 30 * dia), agora)["dias_restantes"] == 30
    assert s(a(liberado_ate=agora - dia), agora)["motivo"] == "teste_acabou"


def test_teste_vencido_fica_so_pra_consulta_quando_o_bloqueio_esta_ligado(db, api, monkeypatch):
    empresa, _ = _conta(db, "00000000000272", "dona@cliente.example", trial_dias=-1)
    cliente = _entrar(api, "dona@cliente.example")
    anotar = lambda: cliente.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"})  # noqa: E731
    # bloqueio desligado (padrão): nada muda
    assert anotar().status_code in (200, 201)
    assert cliente.get("/api/auth/me").json()["acesso"]["bloqueado"] is False

    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    r = anotar()
    assert r.status_code == 402 and "teste grátis" in r.json()["detail"]
    eu = cliente.get("/api/auth/me").json()["acesso"]
    assert (eu["bloqueado"], eu["motivo"]) == (True, "teste_acabou")
    # continua vendo o que é dela e consegue chegar na assinatura
    assert cliente.get("/api/dps").status_code == 200
    assert cliente.get("/api/assinatura").json()["situacao"] == "teste_acabou"
    assert cliente.post("/api/assinatura/checkout", json={"plano": "emissor"}).status_code != 402

    # a Gestão liberou por 30 dias: volta a funcionar
    definir_prestador_atual(db, empresa.id)
    billing.liberar_acesso(db.query(Assinatura).filter_by(prestador_id=empresa.id).one(), dias=30, sempre=False, obs="amiga testando")
    db.flush()
    assert anotar().status_code in (200, 201)
    assert cliente.get("/api/auth/me").json()["acesso"]["motivo"] == "liberacao"


def test_empresa_bloqueada_tambem_trava_o_contador(db, api, cenario, monkeypatch):
    _, da_contadora = _convidar_e_aceitar(db, api, cenario, ["financeiro"])
    definir_prestador_atual(db, cenario["cliente"].id)
    db.query(Assinatura).filter_by(prestador_id=cenario["cliente"].id).one().trial_termina_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
    db.flush()
    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    assert da_contadora.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"}).status_code == 402
    assert da_contadora.get("/api/contador/atendimentos").json()["clientes"][0]["situacao"]["bloqueado"] is True


def test_gestao_libera_e_tira_a_liberacao(db, api, monkeypatch):
    _conta(db, "00000000000353", "gestor@plataforma.example", nome="PLATAFORMA")
    alvo, _ = _conta(db, "00000000000272", "dona@cliente.example", trial_dias=-5, nome="CLIENTE")
    comum = _entrar(api, "dona@cliente.example")
    monkeypatch.setattr(get_settings(), "admin_emails", "gestor@plataforma.example")
    assert comum.post(f"/api/gestao/contas/{alvo.id}/liberar", json={"sempre": True}).status_code == 403

    gestor = _entrar(api, "gestor@plataforma.example")
    conta = next(c for c in gestor.get("/api/gestao").json()["contas"] if c["id"] == str(alvo.id))
    assert (conta["acesso"]["liberado"], conta["acesso"]["motivo"]) == (False, "teste_acabou")
    assert gestor.post(f"/api/gestao/contas/{alvo.id}/liberar", json={}).status_code == 422
    r = gestor.post(f"/api/gestao/contas/{alvo.id}/liberar", json={"dias": 90, "obs": "parceira"})
    assert r.status_code == 200 and r.json()["acesso"]["motivo"] == "liberacao" and r.json()["acesso"]["dias_restantes"] in (89, 90)
    conta = next(c for c in gestor.get("/api/gestao").json()["contas"] if c["id"] == str(alvo.id))
    assert conta["acesso"]["liberado"] and conta["liberado_obs"] == "parceira"
    assert gestor.post(f"/api/gestao/contas/{alvo.id}/liberar", json={"sempre": True}).json()["acesso"]["ate"] is None
    assert gestor.delete(f"/api/gestao/contas/{alvo.id}/liberar").json()["acesso"]["motivo"] == "teste_acabou"
    assert gestor.post(f"/api/gestao/contas/{uuid.uuid4()}/liberar", json={"sempre": True}).status_code == 404


# --- conta só de contador (07/10/2026) ----------------------------------------


def test_conta_so_de_contador_sem_cnpj_sem_teste_e_so_trabalha_no_cliente(db, api, monkeypatch):
    from app.services.cadastro import criar_cadastro_contador

    monkeypatch.setattr(get_settings(), "bloqueio_ativo", True)
    cliente, _ = _conta(db, "00000000000272", "dona@cliente.example", nome="CLIENTE")
    contadora = criar_cadastro_contador(db, email="Ana@Escritorio.example", senha=SENHA, nome="Ana Contadora", escritorio="Escritório Ana")
    contadora.email_confirmado = True
    db.flush()
    casa = contadora.prestador_id
    definir_prestador_atual(db, casa)
    assert db.query(Assinatura).filter_by(prestador_id=casa).count() == 0  # sem teste, sem assinatura
    assert db.get(Prestador, casa).so_contador is True

    dela = _entrar(api, "ana@escritorio.example")
    eu = dela.get("/api/auth/me").json()
    assert (eu["so_contador"], eu["modulos"], eu["papel"]) == (True, [], "dono")
    assert (eu["acesso"]["liberado"], eu["acesso"]["bloqueado"], eu["acesso"]["motivo"]) == (True, False, "contador")
    # na "casa" dela não se cria nada
    r = dela.post("/api/financeiro/anotacoes", json={"titulo": "x", "texto": "y"})
    assert r.status_code == 403
    assert dela.post("/api/dps", json={}).status_code == 403
    assert dela.get("/api/empresas").json()[0]["so_contador"] is True

    # convidada, aceita e trabalha na empresa do cliente
    da_dona = _entrar(api, "dona@cliente.example")
    assert da_dona.post("/api/contador/acessos", json={"email": "ana@escritorio.example", "permissoes": ["financeiro"]}).status_code == 200
    convite = dela.get("/api/contador/atendimentos").json()["convites"][0]
    assert dela.post(f"/api/contador/convites/{convite['id']}/aceitar").status_code == 200
    assert dela.post(f"/api/empresas/{cliente.id}/ativar").json()["papel"] == "contador"
    eu = dela.get("/api/auth/me").json()
    assert (eu["so_contador"], eu["papel"], eu["permissoes"]) == (False, "contador", ["financeiro"])
    assert dela.post("/api/financeiro/anotacoes", json={"titulo": "Fechamento", "texto": "ok"}).status_code in (200, 201)


def test_cadastro_de_contador_pela_api(db, api):
    cliente = api()
    r = cliente.post("/api/cadastro/contador", json={"whatsapp": "(92) 99999-0000", "email": "novo@escritorio.example", "senha": SENHA, "nome": "Novo Contador"})
    assert r.status_code == 200 and r.json()["email"] == "novo@escritorio.example"
    assert cliente.post("/api/cadastro/contador", json={"whatsapp": "(92) 99999-0000", "email": "novo@escritorio.example", "senha": SENHA, "nome": "De novo"}).status_code == 409
    usuario = db.query(Usuario).filter_by(email="novo@escritorio.example").one()
    assert usuario.email_confirmado is False and usuario.nome == "Novo Contador"


# --- bonificação do contador e pendências das empresas (07/10/2026) -----------


def test_contador_vira_parceiro_com_10_por_cento_enquanto_atende(db, api, cenario):
    from app.models import IndicacaoParceiro, Parceiro
    from app.services import parceiros

    da_dona, da_contadora = _convidar_e_aceitar(db, api, cenario, ["financeiro"])
    parceiro = db.query(Parceiro).filter_by(usuario_id=cenario["contadora"].id).one()
    assert (float(parceiro.comissao_pct), parceiro.desconto_1_mes_pct, parceiro.email) == (10.0, 0, "contadora@escritorio.example")
    indicacao = db.get(IndicacaoParceiro, cenario["cliente"].id)
    assert (indicacao.parceiro_id, indicacao.por_contador, indicacao.status) == (parceiro.id, True, "trial")
    bonus = da_contadora.get("/api/contador/atendimentos").json()["bonificacao"]
    assert (bonus["pct"], bonus["clientes"], bonus["a_receber"]) == (10.0, 1, 0)
    assert bonus["painel"] == f"/parceira/{parceiro.token_painel}"

    # a mensalidade do cliente gera 10% pra ela
    parceiros.registrar_pagamento(db, cenario["cliente"].id, "in_teste_1", Decimal("129.90"), datetime.date(2026, 10, 7))
    assert da_contadora.get("/api/contador/atendimentos").json()["bonificacao"]["a_receber"] == 12.99

    # o cliente tirou o acesso: a bonificação daquela empresa para, o que já rendeu fica
    acesso_id = db.query(AcessoContador).one().id
    assert da_dona.delete(f"/api/contador/acessos/{acesso_id}").status_code == 200
    assert db.get(IndicacaoParceiro, cenario["cliente"].id) is None
    assert parceiros.resumo_do_contador(db, cenario["contadora"].id)["total"] == 12.99


def test_empresa_que_veio_por_outra_parceira_continua_dela(db, api, cenario):
    from app.models import IndicacaoParceiro
    from app.services import parceiros

    outra = parceiros.criar(db, "Parceira Antiga", None, 20, 0)
    parceiros.registrar_indicacao(db, outra.codigo, cenario["cliente"].id, "CLIENTE LTDA")
    da_dona, _ = _convidar_e_aceitar(db, api, cenario, [])
    assert db.get(IndicacaoParceiro, cenario["cliente"].id).parceiro_id == outra.id
    acesso_id = db.query(AcessoContador).one().id
    assert da_dona.delete(f"/api/contador/acessos/{acesso_id}").status_code == 200
    assert db.get(IndicacaoParceiro, cenario["cliente"].id).parceiro_id == outra.id  # não mexe na indicação alheia


def test_contador_ve_as_pendencias_de_cada_empresa_sem_entrar_nela(db, api, cenario):
    from app.models import PrestadorTomador, Tomador
    from app.services.motor_emissao import criar_rascunho

    _, da_contadora = _convidar_e_aceitar(db, api, cenario, ["emitir"])
    assert da_contadora.post(f"/api/empresas/{cenario['escritorio'].id}/ativar").status_code == 200  # fora do cliente
    cliente = cenario["cliente"]
    definir_prestador_atual(db, cliente.id)
    tomador = Tomador(id=uuid.uuid4(), cnpj="00000000000515", razao_social="TOMADOR SINTETICO LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=cliente.id, tomador_id=tomador.id, apelido="Tomador Sintético",
        cod_local_prestacao=cliente.cod_municipio, cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="Serviço - {competencia_mm_aaaa}", serie="1", requer_revisao=True, ativo=True,
    )
    db.add(vinculo)
    db.flush()
    nota = criar_rascunho(db, vinculo, competencia="2026-10", valor=100)
    nota.estado = "montado"  # pronta pra assinar
    db.flush()

    atendido = da_contadora.get("/api/contador/atendimentos").json()["clientes"][0]
    assert atendido["total_pendencias"] >= 1, atendido["pendencias"]
    assert any(p["tipo"] == "assinar" and "Tomador Sintético" in p["titulo"] for p in atendido["pendencias"])
    # só título e quantidade — e ela continua na empresa dela
    assert set(atendido["pendencias"][0]) == {"tipo", "titulo", "link", "quantidade", "atrasada"}
    assert da_contadora.get("/api/auth/me").json()["prestador_id"] == str(cenario["escritorio"].id)
