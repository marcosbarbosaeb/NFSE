"""Cliente que nasceu "só controle" (sem CNPJ) vira tomador de verdade
(05/10/2026): "lancei um recebimento de controle do GOOGLE ADSENSE e agora na
aba de tomador não tem a opção de eu inserir ele como tomador para poder
gerar notas". Ver app/services/identificar_tomador.py.

Dados sintéticos, Postgres real com rollback (mesmo padrão das outras
suítes). A consulta à Receita (`_dados_oficiais_cnpj`) já vem desligada pelo
conftest."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from app.database import definir_prestador_atual, get_db
from app.main import app, prestador_atual_id
from app.models import PagamentoRecebido, Prestador, PrestadorTomador, Tomador
from app.services import importar_adn
from app.services.conferencia import conferir_emissao, conferir_vinculo
from app.services.danfse import _local_no_exterior
from app.services.motor_emissao import criar_rascunho, montar
from app.services.nota_visual import montar_nota_visual
from app.services.vinculos import criar_tomador_interno

NS = "http://www.sped.fazenda.gov.br/nfse"
XSD = Path(__file__).resolve().parents[2] / "integracao" / "schemas" / "DPS_v1.00.xsd"
CNPJ_NOVO = "55443322000105"  # dígitos verificadores certos, empresa inventada
CNPJ_DO_CATALOGO = "11222333000181"  # o tomador do fixture `vinculo_teste`


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


def _cliente_de_controle(client, nome="Anúncios Sintéticos") -> str:
    """Do jeito que o financeiro cria: só o nome, sem nota."""
    r = client.post("/api/financeiro/clientes", json={"nome": nome})
    assert r.status_code == 200 and r.json()["so_controle"] is True
    return r.json()["id"]


def _t(raiz, caminho):
    return raiz.find(".//" + "/".join(f"{{{NS}}}{p}" for p in caminho.split("/")))


def _codigos(pontos, nivel="erro"):
    return {p["codigo"] for p in pontos if p["nivel"] == nivel}


# --- empresa do Brasil (CNPJ) ---------------------------------------------------


def test_identificar_com_cnpj_novo_mantem_o_vinculo_e_o_historico(client, db):
    vinculo_id = _cliente_de_controle(client)
    interno_id = db.get(PrestadorTomador, uuid.UUID(vinculo_id)).tomador_id
    r = client.post("/api/pagamentos", json={"vinculo_id": vinculo_id, "competencia": "2026-09", "valor": 321.5})
    assert r.status_code == 200
    pagamento_id = uuid.UUID(r.json()["id"])

    # a Receita não respondeu (desligada nos testes): sem nome não dá pra cadastrar
    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={"tipo": "cnpj", "cnpj": CNPJ_NOVO})
    assert r.status_code == 422 and "nome" in r.json()["detail"]

    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={
        "tipo": "cnpj", "cnpj": "55.443.322/0001-05", "razao_social": "  REDE SINTETICA  LTDA ", "cod_municipio": "3550308",
        "cep": "01311-000", "logradouro": "Av Teste", "numero": "10", "bairro": "Centro",
    })
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["aviso"] is None
    assert corpo["vinculo"]["id"] == vinculo_id  # o MESMO cliente
    assert corpo["vinculo"]["tomador"]["cnpj"] == CNPJ_NOVO and corpo["vinculo"]["tomador"]["status"] == "aprovado"
    assert corpo["vinculo"]["tomador"]["razao_social"] == "REDE SINTETICA LTDA" and corpo["vinculo"]["tomador"]["cep"] == "01311000"
    # identificar não liga a emissão: isso é quando a pessoa confere e salva o cadastro
    assert corpo["vinculo"]["sem_nota"] is True

    db.expire_all()
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))
    assert vinculo.tomador.cnpj == CNPJ_NOVO
    # o recebimento continua no mesmo cliente
    assert db.get(PagamentoRecebido, pagamento_id).prestador_tomador_id == vinculo.id
    cliente = next(c for c in client.get("/api/financeiro/clientes?ano=2026").json() if c["id"] == vinculo_id)
    assert cliente["recebimentos"] == 1 and cliente["recebido"] == 321.5
    # o tomador interno que ficou sem dono sumiu
    assert db.get(Tomador, interno_id) is None
    # e a lista passa a mostrar o CNPJ (é o que leva a "Falta configurar a nota")
    item = next(v for v in client.get("/api/vinculos?todos=true").json() if v["id"] == vinculo_id)
    assert item["tomador_cnpj"] == CNPJ_NOVO and item["tomador_nif"] is None and item["sem_nota"] is True


def test_identificar_com_cnpj_que_ja_esta_no_catalogo_reaproveita_e_avisa(client, db, vinculo_teste):
    vinculo_id = _cliente_de_controle(client)
    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={
        "tipo": "cnpj", "cnpj": CNPJ_DO_CATALOGO, "razao_social": "NOME QUE NAO DEVE ENTRAR", "cod_municipio": "3106200",
    })
    assert r.status_code == 200, r.text
    corpo = r.json()
    # usa o cadastro que já existe, sem mexer nele
    assert corpo["vinculo"]["tomador"]["id"] == str(vinculo_teste.tomador_id)
    assert corpo["vinculo"]["tomador"]["razao_social"] == "TOMADOR DE TESTE LTDA"
    # dois clientes com o mesmo CNPJ é permitido (AWIN e AWIN Rchlo) — só avisa
    assert "Fornecedor Teste" in corpo["aviso"]
    assert db.query(Tomador).filter_by(cnpj=CNPJ_DO_CATALOGO).count() == 1


def test_cnpj_com_digito_errado_ou_incompleto_e_recusado_com_frase_clara(client, db):
    vinculo_id = _cliente_de_controle(client)
    interno_id = db.get(PrestadorTomador, uuid.UUID(vinculo_id)).tomador_id
    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={
        "tipo": "cnpj", "cnpj": "55443322000106", "razao_social": "X LTDA", "cod_municipio": "3550308",
    })
    assert r.status_code == 422 and "não existe" in r.json()["detail"]
    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={"tipo": "cnpj", "cnpj": "5544332200"})
    assert r.status_code == 422 and "14 números" in r.json()["detail"]
    # nada mudou
    db.expire_all()
    assert db.get(PrestadorTomador, uuid.UUID(vinculo_id)).tomador_id == interno_id
    assert db.query(Tomador).filter_by(cnpj="55443322000106").count() == 0


def test_tomador_que_ja_tem_cnpj_nao_troca_de_identidade(client, vinculo_teste):
    for corpo in ({"tipo": "cnpj", "cnpj": CNPJ_NOVO, "razao_social": "X LTDA", "cod_municipio": "3550308"},
                  {"tipo": "exterior", "razao_social": "Foreign Co", "pais": "IE", "nif": "IE1234567X"}):
        r = client.post(f"/api/vinculos/{vinculo_teste.id}/identificar", json=corpo)
        assert r.status_code == 409 and "não pode ser trocado" in r.json()["detail"]


def test_tomador_interno_usado_por_outro_cliente_nao_e_apagado(client, db, prestador_teste):
    interno = criar_tomador_interno(db, "Parcerias Sintéticas", "3106200")
    dois = []
    for apelido in ("Parceria A", "Parceria B"):
        v = PrestadorTomador(
            id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=interno.id, apelido=apelido,
            cod_local_prestacao="3106200", cod_trib_nacional="000000", template_descricao=apelido, ativo=True, sem_nota=True,
        )
        db.add(v)
        dois.append(v)
    db.flush()
    r = client.post(f"/api/vinculos/{dois[0].id}/identificar", json={
        "tipo": "cnpj", "cnpj": CNPJ_NOVO, "razao_social": "REDE SINTETICA LTDA", "cod_municipio": "3550308",
    })
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Tomador, interno.id) is not None  # a Parceria B ainda aponta pra ele
    assert db.get(PrestadorTomador, dois[1].id).tomador_id == interno.id


def test_outra_empresa_nao_identifica_o_meu_cliente(client, db, prestador_teste):
    """RLS: o vínculo é de quem criou — pra outra empresa ele nem existe."""
    vinculo_id = _cliente_de_controle(client)
    interno_id = db.get(PrestadorTomador, uuid.UUID(vinculo_id)).tomador_id

    outra = Prestador(
        id=uuid.uuid4(), cpf_cnpj="00000000000272", razao_social="OUTRA EMPRESA DE TESTE", cod_municipio="3106200",
        modulos=["emissor", "financeiro"],
    )
    definir_prestador_atual(db, outra.id)
    db.add(outra)
    db.flush()
    app.dependency_overrides[prestador_atual_id] = lambda: outra.id
    for corpo in ({"tipo": "cnpj", "cnpj": CNPJ_NOVO, "razao_social": "X LTDA", "cod_municipio": "3550308"},
                  {"tipo": "exterior", "razao_social": "Foreign Co", "pais": "IE", "nif": "IE1234567X"}):
        assert client.post(f"/api/vinculos/{vinculo_id}/identificar", json=corpo).status_code == 404

    definir_prestador_atual(db, prestador_teste.id)
    db.expire_all()
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))
    assert vinculo.tomador_id == interno_id and vinculo.tomador.nif is None and vinculo.tomador.status == "interno"


# --- empresa de fora do Brasil ---------------------------------------------------


def _identificar_de_fora(client, vinculo_id, **mudancas):
    corpo = {
        "tipo": "exterior", "razao_social": "Anuncios Sinteticos Ireland Limited", "pais": "ie", "nif": " IE 1234567X ",
        "endereco_exterior": "Dublin, 1 Example Street",
    }
    corpo.update(mudancas)
    return client.post(f"/api/vinculos/{vinculo_id}/identificar", json=corpo)


def test_identificar_empresa_de_fora_guarda_pais_e_nif_no_mesmo_tomador(client, db):
    vinculo_id = _cliente_de_controle(client)
    interno_id = db.get(PrestadorTomador, uuid.UUID(vinculo_id)).tomador_id

    assert _identificar_de_fora(client, vinculo_id, nif="  ").status_code == 422
    assert _identificar_de_fora(client, vinculo_id, pais="").status_code == 422
    assert _identificar_de_fora(client, vinculo_id, pais="ZZ").status_code == 422
    r = _identificar_de_fora(client, vinculo_id, pais="BR")
    assert r.status_code == 422 and "CNPJ" in r.json()["detail"]
    assert _identificar_de_fora(client, vinculo_id, razao_social=" ").status_code == 422

    r = _identificar_de_fora(client, vinculo_id)
    assert r.status_code == 200, r.text
    tomador = r.json()["vinculo"]["tomador"]
    assert tomador["id"] == str(interno_id) and tomador["status"] == "interno"
    assert tomador["pais"] == "IE" and tomador["nif"] == "IE 1234567X" and tomador["cnpj"] == ""  # o código interno não aparece
    assert tomador["razao_social"] == "Anuncios Sinteticos Ireland Limited" and tomador["logradouro"] == "Dublin, 1 Example Street"
    assert tomador["cep"] is None
    assert r.json()["vinculo"]["sem_nota"] is True and r.json()["vinculo"]["id"] == vinculo_id

    item = next(v for v in client.get("/api/vinculos?todos=true").json() if v["id"] == vinculo_id)
    assert item["tomador_cnpj"] == "" and item["tomador_pais"] == "IE" and item["tomador_nif"] == "IE 1234567X"

    # dá pra corrigir depois (mesma rota) e pra virar empresa do Brasil se foi engano
    assert _identificar_de_fora(client, vinculo_id, pais="US", nif="98-7654321").json()["vinculo"]["tomador"]["pais"] == "US"
    r = client.post(f"/api/vinculos/{vinculo_id}/identificar", json={
        "tipo": "cnpj", "cnpj": CNPJ_NOVO, "razao_social": "REDE SINTETICA LTDA", "cod_municipio": "3550308",
    })
    assert r.status_code == 200 and r.json()["vinculo"]["tomador"]["pais"] is None
    assert db.get(Tomador, interno_id) is None


def test_conferencia_do_tomador_de_fora(client, db):
    vinculo_id = _cliente_de_controle(client)
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))

    # só controle: nada em vermelho, com ou sem identificação
    assert conferir_vinculo(db, vinculo) == []
    # quis emitir sem dizer quem é: o erro manda pro passo certo
    vinculo.sem_nota = False
    pontos = conferir_vinculo(db, vinculo)
    assert "documento_vazio" in _codigos(pontos)
    assert any("Quer emitir nota pra este cliente?" in (p["como_corrigir"] or "") for p in pontos)

    assert _identificar_de_fora(client, vinculo_id).status_code == 200
    db.expire_all()
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))
    vinculo.sem_nota, vinculo.cod_trib_nacional = False, "170601"
    vinculo.template_descricao, vinculo.envio_formas = "Veiculação de anúncios - {mes_nome_upper}/{ano}", ["download"]
    db.flush()
    # com país + NIF: nada de "sem CNPJ", "documento inválido" nem endereço/CEP
    assert conferir_vinculo(db, vinculo) == []
    r = client.get(f"/api/vinculos/{vinculo_id}/conferencia")
    assert r.status_code == 200 and r.json()["pontos"] == []

    # faltando um dos dois, trava
    vinculo.tomador.nif = None
    assert _codigos(conferir_vinculo(db, vinculo)) == {"documento_vazio"}
    vinculo.tomador.nif, vinculo.tomador.pais = "IE1234567X", None
    assert _codigos(conferir_vinculo(db, vinculo)) == {"pais_vazio"}
    vinculo.tomador.pais = "ZZ"
    assert _codigos(conferir_vinculo(db, vinculo)) == {"pais_invalido"}


def test_nota_pra_tomador_de_fora_sai_com_nif_pais_e_comercio_exterior_valida_no_xsd(client, db, prestador_teste):
    """`criar_rascunho` + `montar` pelo vínculo: o mesmo XML das notas pra
    vendedores estrangeiros já autorizadas (NIF, endExt só com o país,
    comExt, ISS tributável aqui) — e é uma nota normal do tomador, não avulsa."""
    prestador_teste.inscricao_municipal = "123456"
    prestador_teste.op_simples_nacional, prestador_teste.regime_apuracao_sn, prestador_teste.regime_especial_trib = "3", "1", "0"
    vinculo_id = _cliente_de_controle(client)
    assert _identificar_de_fora(client, vinculo_id).status_code == 200
    db.expire_all()
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))
    vinculo.sem_nota, vinculo.cod_trib_nacional, vinculo.incluir_intermediario = False, "170601", True
    vinculo.template_descricao = "Veiculação de anúncios - {mes_nome_upper}/{ano}"
    db.flush()

    emissao = criar_rascunho(db, vinculo, competencia="2026-09", valor=1234.56, aliq_sn=6.0)
    snap = emissao.tomador_snapshot
    assert emissao.tomador_documento is None and "avulso" not in snap and "intermediario" not in snap
    assert snap["tipo_documento"] == "NIF" and snap["cnpj"] == "IE 1234567X" and snap["pais"] == "IE"
    assert not any(snap["endereco"].values())
    assert snap["razao_social"] == "Anuncios Sinteticos Ireland Limited" and snap["descricao_renderizada"].endswith("SETEMBRO/2026")

    montar(db, emissao)
    assert emissao.estado == "montado"
    dps = etree.fromstring(emissao.xml_dps.encode("utf-8"))
    etree.XMLSchema(etree.parse(str(XSD))).assertValid(etree.ElementTree(dps))
    assert _t(dps, "toma/NIF").text == "IE 1234567X" and _t(dps, "toma/CNPJ") is None
    assert _t(dps, "toma/xNome").text == "Anuncios Sinteticos Ireland Limited"
    assert _t(dps, "toma/end/endExt/cPais").text == "IE" and _t(dps, "toma/end/endExt/xCidade").text == "-"
    assert _t(dps, "toma/end/endNac") is None and _t(dps, "interm") is None
    assert _t(dps, "serv/comExt/vServMoeda").text == "1234.56" and _t(dps, "serv/comExt/tpMoeda").text == "986"
    assert _t(dps, "valores/trib/tribMun/tribISSQN").text == "1"

    # a conferência da nota gerada não reclama de documento nem de endereço,
    # e não acha que "o cadastro mudou" (o retrato usa o NIF, não o código interno)
    pontos = conferir_emissao(db, emissao)
    assert not {"documento_vazio", "documento_invalido", "cidade_invalida", "endereco_incompleto", "cadastro_mudou"} & {p["codigo"] for p in pontos}
    # na tela da nota: NIF e país, nunca o código interno "X..."
    visual = montar_nota_visual(emissao)["tomador"]
    assert visual["cnpj"] == "NIF IE 1234567X" and visual["endereco"] == "Fora do Brasil — Irlanda"
    # se o NIF mudar no cadastro depois, aí sim avisa
    vinculo.tomador.nif = "IE7654321Z"
    assert "cadastro_mudou" in {p["codigo"] for p in conferir_emissao(db, emissao)}


def test_tomador_com_cnpj_continua_saindo_como_sempre(db, prestador_teste, vinculo_teste):
    prestador_teste.inscricao_municipal = "123456"
    prestador_teste.op_simples_nacional, prestador_teste.regime_apuracao_sn, prestador_teste.regime_especial_trib = "3", "1", "0"
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=100, aliq_sn=6.0)
    snap = emissao.tomador_snapshot
    assert snap["cnpj"] == CNPJ_DO_CATALOGO and "tipo_documento" not in snap and "pais" not in snap
    assert snap["endereco"]["cMun"] == "3550308" and snap["endereco"]["CEP"] == "01311000"
    montar(db, emissao)
    dps = etree.fromstring(emissao.xml_dps.encode("utf-8"))
    etree.XMLSchema(etree.parse(str(XSD))).assertValid(etree.ElementTree(dps))
    assert _t(dps, "toma/CNPJ").text == CNPJ_DO_CATALOGO and _t(dps, "toma/NIF") is None
    assert _t(dps, "toma/end/endNac/cMun").text == "3550308" and _t(dps, "toma/end/endExt") is None
    assert _t(dps, "serv/comExt") is None
    assert montar_nota_visual(emissao)["tomador"]["cnpj"] == "11.222.333/0001-81"


def test_tomador_de_fora_pela_metade_nao_vira_nota_de_estrangeiro(db, prestador_teste):
    """Só o país (sem NIF) não muda o retrato da nota — quem trava a geração
    é a conferência (POST /api/dps), não um XML montado pela metade."""
    interno = criar_tomador_interno(db, "Meio Cadastro Inc", "3106200")
    interno.pais = "US"
    v = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=interno.id, apelido="Meio Cadastro",
        cod_local_prestacao="3106200", cod_trib_nacional="170601", template_descricao="Serviço", ativo=True, sem_nota=False,
    )
    db.add(v)
    db.flush()
    assert interno.de_fora and not interno.estrangeiro
    assert "tipo_documento" not in criar_rascunho(db, v, competencia="2026-09", valor=10).tomador_snapshot
    assert _codigos(conferir_vinculo(db, v)) == {"documento_vazio"}


def test_nota_importada_com_nif_reconhece_o_tomador_de_fora(client, db):
    vinculo_id = _cliente_de_controle(client)
    assert _identificar_de_fora(client, vinculo_id, nif="IE1234567X").status_code == 200
    db.expire_all()
    por_doc = importar_adn._vinculos_por_documento(db)
    assert [str(v.id) for v in por_doc["IE1234567X"]] == [vinculo_id]


def test_local_no_exterior_do_danfse():
    assert _local_no_exterior("-", "IE") == "Irlanda"
    assert _local_no_exterior("Dublin", "ie") == "Dublin — Irlanda"
    assert _local_no_exterior(None, None) == "-"


def test_caminho_inteiro_pela_api_controle_vira_tomador_de_fora_e_gera_nota(client, db, prestador_teste):
    """O que a tela faz: identifica, salva o cadastro com a emissão ligada
    (código e descrição conferidos) e gera a nota."""
    prestador_teste.inscricao_municipal = "123456"
    vinculo_id = _cliente_de_controle(client, "Google Sintético")
    # ainda é só controle: a Ana não gera nota
    assert client.post("/api/dps", json={"vinculo_id": vinculo_id, "competencia": "2026-09", "valor": 50}).status_code == 422
    assert _identificar_de_fora(client, vinculo_id).status_code == 200
    r = client.patch(f"/api/vinculos/{vinculo_id}", json={
        "sem_nota": False, "cod_trib_nacional": "170601", "template_descricao": "Veiculação de anúncios - {mes_nome_upper}/{ano}",
        "envio_formas": ["download"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["sem_nota"] is False and r.json()["tomador"]["nif"] == "IE 1234567X"
    r = client.post("/api/dps", json={"vinculo_id": vinculo_id, "competencia": "2026-09", "data_competencia": "2026-09-30", "valor": 50})
    assert r.status_code == 200, r.text
    from app.models import Emissao

    emissao = db.get(Emissao, uuid.UUID(r.json()["id"]))
    assert emissao.tomador_documento is None and emissao.tomador_snapshot["tipo_documento"] == "NIF"
    nota = client.get(f"/api/dps/{emissao.id}/nota").json()
    assert nota["tomador"]["cnpj"] == "NIF IE 1234567X" and "Irlanda" in nota["tomador"]["endereco"]
