"""Lote "completo" em segundo plano (assina, envia à prefeitura e manda o
e-mail numa passada só), conserto de CEP pela recusa E0240, formas de envio
múltiplas, destinatários com e-mail próprio, dados do tomador editáveis e o
mês de referência da descrição (05/10/2026). Só dados sintéticos."""
import uuid

import pytest
from fastapi.testclient import TestClient

import app.services.cep as cep
from app.database import get_db
from app.fiscal.cliente_sefin import RespostaSefin
from app.main import app, prestador_atual_id
from app.models import Envio, LoteAcao, LoteFila
from app.services import lotes
from app.services.motor_emissao import criar_rascunho, mes_anterior, montar


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


class _Email:
    def __init__(self):
        self.enviados = []

    def enviar(self, **kw):
        self.enviados.append(kw)


class _Resp:
    def __init__(self, status, dados):
        self.status_code, self._dados = status, dados

    def json(self):
        return self._dados


def _viacep(tabela):
    """requests.get falso: {trecho da URL: resposta}."""
    def get(url, timeout=None):
        for trecho, dados in tabela.items():
            if trecho in url:
                return _Resp(200, dados)
        return _Resp(200, {"erro": True})
    return get


SP = {"cep": "01311-000", "ibge": "3550308", "logradouro": "Avenida Paulista", "bairro": "Bela Vista", "localidade": "São Paulo", "uf": "SP"}
CAMPINAS = {"cep": "13010-000", "ibge": "3509502", "logradouro": "Rua Qualquer", "bairro": "Centro", "localidade": "Campinas", "uf": "SP"}


def test_cep_achado_pelo_endereco(monkeypatch):
    monkeypatch.setattr(cep.requests, "get", _viacep({"/99999999/": {"erro": True}, "/SP/": [SP]}))
    c = cep.corrigir_endereco({"cMun": "3550308", "CEP": "99999999", "xLgr": "Av Paulista", "nro": "10", "xBairro": "Bela Vista"})
    assert c.endereco["CEP"] == "01311000" and c.endereco["cMun"] == "3550308" and "01311000" in c.explicacao


def test_cep_de_outra_cidade_fica_com_a_cidade_do_cep(monkeypatch):
    monkeypatch.setattr(cep.requests, "get", _viacep({"/13010000/": CAMPINAS, "/SP/": []}))
    c = cep.corrigir_endereco({"cMun": "3550308", "CEP": "13010000", "xLgr": "Rua Qualquer", "nro": "1", "xBairro": "Centro"})
    assert c.endereco["cMun"] == "3509502" and c.endereco["CEP"] == "13010000"


def test_cep_sem_conserto_tira_o_endereco_e_servico_fora_nao_mexe(monkeypatch):
    monkeypatch.setattr(cep.requests, "get", _viacep({}))
    c = cep.corrigir_endereco({"cMun": "3550308", "CEP": "99999999", "xLgr": "Rua Inexistente", "nro": "1", "xBairro": "X"})
    assert c.endereco is None
    # CEP e cidade batem: nada a fazer
    monkeypatch.setattr(cep.requests, "get", _viacep({"/01311000/": SP}))
    assert cep.corrigir_endereco({"cMun": "3550308", "CEP": "01311000", "xLgr": "Av Paulista", "nro": "1", "xBairro": "B"}) is None

    def fora(url, timeout=None):
        raise cep.requests.ConnectionError("sem rede")
    monkeypatch.setattr(cep.requests, "get", fora)
    assert cep.corrigir_endereco({"cMun": "3550308", "CEP": "99999999", "xLgr": "Av Paulista", "nro": "1", "xBairro": "B"}) is None


def _avulsa(db, vinculo, doc, email, cep_="01311000"):
    e = criar_rascunho(db, vinculo, competencia="2026-09", valor=10, tpAmb="2", tomador_avulso={
        "documento": doc, "tipo_documento": "CNPJ", "razao_social": f"Loja {doc[-2:]}", "email": email, "pais": "BR", "lojas": [],
        "endereco": {"cMun": "3550308", "CEP": cep_, "xLgr": "Av Paulista", "nro": "10", "xBairro": "Bela Vista"},
    })
    montar(db, e)
    return e


class _Sefin:
    """Recusa (E0240) toda DPS cujo XML traz o CEP ruim; autoriza o resto."""
    enviadas: list[bytes] = []

    def __init__(self, *a, **k):
        pass

    def submeter_dps(self, xml: bytes):
        _Sefin.enviadas.append(xml)
        if b"99999999" in xml:
            return RespostaSefin(400, {"erros": [{"Codigo": "E0240", "Descricao": "O CEP informado não existe ou não pertence ao município."}]})
        return RespostaSefin(201, {"chaveAcesso": "C" + uuid.uuid4().hex})

    def consultar_dps(self, id_dps):
        return RespostaSefin(404, None)


@pytest.fixture
def pipeline(monkeypatch, certificado_teste):
    import app.services.certificados as certificados
    import app.services.envio_direto as envio_direto

    email = _Email()
    _Sefin.enviadas = []
    monkeypatch.setattr(envio_direto, "get_email_sender", lambda: email)
    monkeypatch.setattr("app.services.email.get_email_sender", lambda: email)
    monkeypatch.setattr(envio_direto, "motivo_email_desabilitado", lambda vinculo, destino=None: None if destino else "sem destino")
    monkeypatch.setattr(certificados, "carregar_certificado", lambda db, pid, chave: (certificado_teste["private_key"], certificado_teste["cert"]))
    monkeypatch.setattr(lotes, "ClienteSefin", _Sefin)
    monkeypatch.setattr(lotes, "PAUSA_EMAIL_S", 0)
    monkeypatch.setattr(lotes, "iniciar", lambda *a, **k: None)  # os testes rodam `processar` na mão
    monkeypatch.setattr(cep.requests, "get", _viacep({"/99999999/": {"erro": True}, "/SP/": [SP]}))
    return email


def test_lote_completo_faz_tudo_conserta_cep_e_gera_relatorio(client, db, prestador_teste, vinculo_teste, pipeline):
    vinculo_teste.email_anexos = "xml"
    boas = [_avulsa(db, vinculo_teste, f"112223330001{i:02d}", f"v{i}@x.com") for i in range(2)]
    cep_ruim = _avulsa(db, vinculo_teste, "11222333000150", "cep@x.com", cep_="99999999")
    sem_email = _avulsa(db, vinculo_teste, "11222333000160", "")

    corpo = {"acao": "completo", "vinculo_id": str(vinculo_teste.id), "competencia": "2026-09"}
    assert client.post("/api/lotes/previa", json=corpo).json()["quantidade"] == 4
    r = client.post("/api/lotes", json=corpo)
    assert r.status_code == 200, r.text
    assert r.json()["passos"] == ["assinar", "submeter", "email"]
    lote = db.get(LoteAcao, uuid.UUID(r.json()["id"]))
    assert db.get(LoteFila, lote.id) is not None  # é por aqui que um reinício retoma

    lotes.processar(db, lote, prestador_teste.id, "https://x")
    assert lote.status == "concluido"
    assert all(e.estado == "confirmado" for e in (*boas, cep_ruim, sem_email))
    # o CEP foi achado pelo endereço e a nota reenviada com o mesmo número
    assert cep_ruim.tomador_snapshot["endereco"]["CEP"] == "01311000"
    assert "endereco_corrigido" in cep_ruim.tomador_snapshot
    assert lote.relatorio == {"assinadas": 4, "autorizadas": 4, "cep_corrigido": 1, "enviadas": 3, "email_falhou": 1}
    assert (lote.feitos, lote.falhas) == (3, 1) and lote.erros[0]["erro"].startswith("E-mail:")
    assert db.get(LoteFila, lote.id) is None
    resumo = client.get(f"/api/lotes/{lote.id}").json()
    assert "4 autorizadas pela prefeitura" in resumo["linhas_relatorio"] and "1 com o CEP corrigido automaticamente" in resumo["linhas_relatorio"]
    # o relatório também foi pro e-mail de quem usa a conta? (sem usuário no teste: só não quebra)
    enviados_tomador = [m for m in pipeline.enviados if "anexos" in m]
    assert len(enviados_tomador) == 3
    # nada mais a fazer: um novo lote completo não pega as que já terminaram
    assert client.post("/api/lotes/previa", json=corpo).json()["quantidade"] == 1  # só a do e-mail que falhou


def test_lote_completo_so_ate_a_prefeitura_e_retoma_nota_que_ficou_no_meio(client, db, prestador_teste, vinculo_teste, pipeline):
    a = _avulsa(db, vinculo_teste, "11222333000101", "a@x.com")
    b = _avulsa(db, vinculo_teste, "11222333000102", "b@x.com")
    r = client.post("/api/lotes", json={"acao": "completo", "emissao_ids": [str(a.id), str(b.id)], "passos": ["assinar", "submeter"]})
    assert r.json()["passos"] == ["assinar", "submeter"]
    lote = db.get(LoteAcao, uuid.UUID(r.json()["id"]))
    # o servidor caiu com a nota "b" no meio do envio
    from app.services.motor_emissao import assinar
    import app.services.certificados as certificados

    chave, cert = certificados.carregar_certificado(db, prestador_teste.id, "x")
    assinar(db, b, chave, cert)
    b.estado = "submetido"
    db.flush()
    lotes.processar(db, lote, prestador_teste.id, "https://x")
    assert a.estado == "confirmado" and b.estado == "confirmado"
    assert not pipeline.enviados  # e-mail não estava nos passos
    assert lotes.normalizar_passos(["email"]) == ("assinar",)  # e-mail sem prefeitura não existe
    assert lotes.normalizar_passos(["assinar", "email"]) == ("assinar",)


def test_shopee_gerar_ja_cria_o_lote_em_segundo_plano(client, db, prestador_teste, vinculo_teste, pipeline):
    vinculo_teste.metodo_captura_valor = "csv"
    cabecalho = "Mês,ID do Vendedor,Nome da Loja,Razão Social,CNPJ/CPF,E-mail,Endereço,Comissão"
    linhas = [
        cabecalho,
    ]
    # Sem depender do formato exato do relatório: usa as notas já geradas do mês.
    nota = _avulsa(db, vinculo_teste, "11222333000177", "s@x.com")
    ids = lotes.selecionar(db, "completo", vinculo_id=vinculo_teste.id, competencia="2026-09", so_avulsas=True)
    assert ids == [nota.id]
    normal = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=50, tpAmb="2")
    montar(db, normal)
    assert lotes.selecionar(db, "completo", vinculo_id=vinculo_teste.id, competencia="2026-09", so_avulsas=True) == [nota.id]
    assert set(lotes.selecionar(db, "completo", vinculo_id=vinculo_teste.id, competencia="2026-09")) == {nota.id, normal.id}
    assert linhas


def test_corrigir_e_reenviar_usa_o_endereco_novo_do_cadastro(client, db, prestador_teste, vinculo_teste, pipeline, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "ClienteSefin", _Sefin)
    monkeypatch.setattr(main_mod, "carregar_certificado", lambda db, pid, chave: lotes_cert(db, pid))
    vinculo_teste.tomador.cep = "99999999"
    e = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100, tpAmb="2")
    montar(db, e)
    e.estado, e.erro_detalhe = "erro", "A Receita recusou a nota: E0240 — O CEP informado não existe."
    db.flush()
    assert client.get(f"/api/dps/{e.id}").json()["erro_corrigivel"] is True

    # 1) a pessoa corrige o CEP no cadastro: a cidade tem que bater com o CEP
    corpo = {"razao_social": "TOMADOR DE TESTE LTDA", "cod_municipio": "3550308", "cep": "13010-000", "logradouro": "Av Paulista", "numero": "10", "bairro": "Bela Vista"}
    monkeypatch.setattr(cep.requests, "get", _viacep({"/13010000/": CAMPINAS, "/01311000/": SP}))
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}/tomador", json=corpo)
    assert r.status_code == 422 and "Campinas" in r.json()["detail"]
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}/tomador", json={**corpo, "cep": "00000000"}).status_code == 422
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}/tomador", json={**corpo, "cep": "01311-000"})
    assert r.status_code == 200 and r.json()["tomador"]["cep"] == "01311000"

    # 2) "Corrigir e reenviar" manda a nota com o endereço novo
    r = client.post(f"/api/dps/{e.id}/corrigir-reenviar")
    assert r.status_code == 200 and r.json()["estado"] == "confirmado", r.text
    assert e.tomador_snapshot["endereco"]["CEP"] == "01311000" and e.tomador_snapshot["endereco"]["xLgr"] == "Av Paulista"
    assert client.get("/api/cep/01311000").json()["cod_municipio"] == "3550308"
    assert client.get("/api/cep/00000000").status_code == 404


def lotes_cert(db, pid):
    import app.services.certificados as certificados

    return certificados.carregar_certificado(db, pid, "x")


def test_endereco_pela_metade_sai_sem_endereco(db, vinculo_teste):
    vinculo_teste.tomador.logradouro = None
    e = criar_rascunho(db, vinculo_teste, competencia="2026-07", valor=10, tpAmb="2")
    montar(db, e)
    toma = e.xml_dps.split("<toma>")[1].split("</toma>")[0]
    assert "<endNac>" not in toma and "None" not in toma and "TOMADOR DE TESTE" in toma


def test_formas_de_envio_e_destinatarios_com_email_proprio(client, db, vinculo_teste, pipeline):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={
        "envio_formas": ["download", "email"], "email_contato": "fin@t.com", "email_anexos": "xml",
        "email_extras": [
            {"email": "contador@c.com", "rotulo": "Contador", "assunto": "Nota {competencia} pra lançar", "mensagem": "Segue a nota de {valor}."},
            {"email": "eu@t.com"},
            {"email": "não é e-mail"},
        ],
    })
    assert r.status_code == 200, r.text
    assert r.json()["envio_formas"] == ["email", "download"] and r.json()["envio_canal"] == "email"
    assert [x["email"] for x in r.json()["email_extras"]] == ["contador@c.com", "eu@t.com"]
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_formas": ["pombo"]}).status_code == 422

    e = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=1234.5, tpAmb="2")
    montar(db, e)
    previa = client.get(f"/api/dps/{e.id}/email-previa").json()
    assert previa["formas"] == ["email", "download"] and previa["canal_preferido"] == "email"
    assert previa["extras"][0]["assunto"] == "Nota 09/2026 pra lançar" and previa["extras"][0]["proprio"] is True
    assert previa["extras"][1]["assunto"] == previa["assunto"] and previa["extras"][1]["proprio"] is False

    r = client.post(f"/api/dps/{e.id}/enviar-email", json={"extras": ["contador@c.com"]})
    assert r.json()["status"] == "enviado"
    assert [m["destinatario"] for m in pipeline.enviados] == [["fin@t.com"], ["contador@c.com"]]
    assert pipeline.enviados[1]["assunto"] == "Nota 09/2026 pra lançar" and "1.234,50" in pipeline.enviados[1]["corpo_texto"]
    canais = [(x.canal, x.destino) for x in db.query(Envio).filter_by(emissao_id=e.id).order_by(Envio.criado_em)]
    assert ("email", "fin@t.com") in canais and ("email_geral", "Contador: contador@c.com") in canais

    # sem escolher: vão todos; lista vazia de formas = não precisa enviar
    pipeline.enviados.clear()
    client.post(f"/api/dps/{e.id}/enviar-email", json={})
    assert len(pipeline.enviados) == 3
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_formas": []})
    assert r.json()["envio_canal"] == "nenhum"
    assert client.get(f"/api/dps/{e.id}/email-previa").json()["canal_preferido"] == "nenhum"
    # só "baixar o PDF": pra lista, é um envio manual (como portal)
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_formas": ["download"]}).json()["envio_canal"] == "portal"
    # tela antiga (só envio_canal) continua valendo
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"envio_canal": "whatsapp"})
    assert r.json()["envio_formas"] is None and client.get(f"/api/dps/{e.id}/email-previa").json()["formas"] == ["whatsapp"]


def test_descricao_com_mes_de_referencia_anterior(client, db, vinculo_teste):
    assert mes_anterior("2026-01", 2) == "2025-11" and mes_anterior("2026-10", 1) == "2026-09"
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"descricao_meses_atras": 1, "template_descricao": "Comissão - {mes_nome_upper}/{ano}"})
    assert r.status_code == 200 and r.json()["descricao_meses_atras"] == 1
    e = criar_rascunho(db, vinculo_teste, competencia="2026-01", valor=10, tpAmb="2")
    assert e.tomador_snapshot["descricao_renderizada"] == "Comissão - DEZEMBRO/2025"
    assert e.competencia == "2026-01"


def test_proxima_nota_pendente(client, db, vinculo_teste):
    a = criar_rascunho(db, vinculo_teste, competencia="2026-05", valor=10, tpAmb="2")
    montar(db, a)
    assert client.get(f"/api/dps/{a.id}/proxima").json() == {"proxima": None, "restantes": 0}
    b = criar_rascunho(db, vinculo_teste, competencia="2026-06", valor=20, tpAmb="2")
    montar(db, b)
    _avulsa(db, vinculo_teste, "11222333000133", "z@x.com")  # nota de lote não entra na fila das normais
    r = client.get(f"/api/dps/{a.id}/proxima").json()
    assert r["restantes"] == 1 and r["proxima"]["id"] == str(b.id) and r["proxima"]["passo"] == "Assinar"


def test_compatibilidade_da_cidade_com_o_emissor_nacional(client):
    sp = client.get("/api/compatibilidade?cod_municipio=3550308").json()
    assert sp["emissor"] == "sim" and "São Paulo/SP" in sp["mensagem"] and sp["financeiro"] == "sim"
    df = client.get("/api/compatibilidade?cod_municipio=5300108").json()
    assert df["emissor"] == "nao" and "sistema próprio" in df["mensagem"]
    assert client.get("/api/compatibilidade?cod_municipio=0000000").json()["emissor"] == "indefinido"


def test_plano_define_os_modulos_da_empresa(client, db, prestador_teste, monkeypatch):
    import app.services.billing as billing
    from app.config import get_settings
    from app.models import Assinatura

    s = get_settings()
    monkeypatch.setattr(s, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(s, "stripe_webhook_secret", "whsec_x")
    monkeypatch.setattr(s, "stripe_price_id_emissor", "price_notas")
    monkeypatch.setattr(s, "stripe_price_id_financeiro", "price_fin")
    monkeypatch.setattr(s, "stripe_price_id_ambos", "price_tudo")
    monkeypatch.setattr(billing.stripe.Price, "retrieve", lambda pid, api_key=None: {"unit_amount": 4900, "currency": "brl", "recurring": {"interval": "month"}})
    billing._precos_cache.clear()
    assinatura = billing.criar_assinatura_trial(db, prestador_teste.id)

    planos = {p["id"]: p for p in client.get("/api/assinatura").json()["planos"]}
    assert planos["emissor"]["disponivel"] and planos["emissor"]["valor"] == 49.0 and planos["ambos"]["modulos"] == ["emissor", "financeiro"]
    # em teste grátis a pessoa liga e desliga módulo à vontade
    assert client.put("/api/empresa/modulos", json={"modulos": ["emissor", "financeiro"]}).status_code == 200

    # a Stripe avisa que a assinatura do plano "financeiro" está ativa
    evento = {"type": "customer.subscription.updated", "data": {"object": {
        "id": "sub_1", "status": "active", "metadata": {"prestador_id": str(prestador_teste.id)},
        "items": {"data": [{"id": "si_1", "price": {"id": "price_fin"}}]},
    }}}
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event", lambda payload, sig, secret: evento)
    billing.processar_webhook(db, b"{}", "sig")
    assert assinatura.plano == "financeiro" and prestador_teste.modulos == ["financeiro"]
    # com plano pago, módulo só muda trocando o plano
    assert client.put("/api/empresa/modulos", json={"modulos": ["emissor"]}).status_code == 409
    resp = client.get("/api/assinatura").json()
    assert resp["plano"] == "financeiro" and resp["modulos_pelo_plano"] is True

    chamadas = {}
    monkeypatch.setattr(billing.stripe.Subscription, "retrieve", lambda sid, api_key=None: {"items": {"data": [{"id": "si_1"}]}})
    monkeypatch.setattr(billing.stripe.Subscription, "modify", lambda sid, **kw: chamadas.update(kw))
    r = client.post("/api/assinatura/plano", json={"plano": "ambos"})
    assert r.status_code == 200 and r.json()["modulos"] == ["emissor", "financeiro"]
    assert chamadas["items"] == [{"id": "si_1", "price": "price_tudo"}] and prestador_teste.modulos == ["emissor", "financeiro"]
    assert db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).one().plano == "ambos"
