"""Versão 2026.10.5 (08/10/2026) — três dúvidas que apareceram num concorrente
e o que a Ana faz com cada uma:

1. PDF da nota com nome de tomador em chinês/japonês/coreano/cirílico saía com
   quadradinhos (app/services/danfse.py).
2. Nota do mês passado saindo com a competência deste mês: é o normal, a Ana
   não avisa nada (decisão do Marcos — data antiga é que gera multa).
3. Empresa de fora do Brasil que não tem número fiscal (cNaoNIF na DPS).

Dados sintéticos, Postgres real com rollback."""
import datetime
import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Certificado, Emissao, PrestadorTomador
from app.services import danfse
from app.services.conferencia import conferir_emissao, conferir_nota, conferir_vinculo
from app.services.motor_emissao import criar_rascunho, montar
from app.services.nota_visual import montar_nota_visual
from app.tempo import hoje as hoje_br

NS = "http://www.sped.fazenda.gov.br/nfse"
XSD = Path(__file__).resolve().parents[2] / "integracao" / "schemas" / "DPS_v1.00.xsd"
NOME_CHINES = "深圳市样本信息科技有限公司"


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


def _t(raiz, caminho):
    return raiz.find(".//" + "/".join(f"{{{NS}}}{p}" for p in caminho.split("/")))


def _competencia(meses_atras: int = 0) -> str:
    hoje = hoje_br()
    total = hoje.year * 12 + hoje.month - 1 - meses_atras
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _nota(db, vinculo, competencia, valor, estado="confirmado"):
    e = Emissao(
        id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=vinculo.prestador_id, competencia=competencia,
        valor=valor, serie="9", n_dps=int(uuid.uuid4().int % 10**9), estado=estado, tomador_snapshot={},
    )
    db.add(e)
    db.flush()
    return e


# --- 1. PDF com outros alfabetos ---------------------------------------------------


def test_texto_latino_continua_na_helvetica():
    texto = "Rua São João, 100 — ação, coração & Cia. Ltda."
    assert danfse._so_latino(texto)
    assert danfse._trechos(texto, "Helvetica") == [("Helvetica", texto)]
    # a quebra de linha é a mesma de antes
    from reportlab.lib.utils import simpleSplit

    longo = "Serviço de veiculação de anúncios " * 12
    assert danfse._quebrar(longo, "Helvetica", 8.5, 200) == simpleSplit(longo, "Helvetica", 8.5, 200)


def test_chines_sai_com_outra_fonte_e_nao_vira_quadrado():
    trechos = danfse._trechos(f"{NOME_CHINES} Shenzhen Co., Ltd.", "Helvetica")
    assert [t for f, t in trechos if f == "Helvetica"] == [" Shenzhen Co., Ltd."]
    assert "".join(t for f, t in trechos if f != "Helvetica") == NOME_CHINES
    assert "?" not in "".join(t for _, t in trechos)
    assert danfse._largura_do_texto(NOME_CHINES, "Helvetica", 8.5) > 0


def test_chines_quebra_de_linha_sem_espaco_e_cabe_na_coluna():
    largura = 150
    linhas = danfse._quebrar(NOME_CHINES * 6 + " Shenzhen Sample Information Technology Co., Ltd.", "Helvetica", 8.5, largura)
    assert len(linhas) > 2 and "".join(linhas).replace(" ", "").startswith(NOME_CHINES * 6)
    assert all(danfse._largura_do_texto(linha, "Helvetica", 8.5) <= largura for linha in linhas)
    # palavra em alfabeto com espaço (cirílico) não é partida no meio
    assert danfse._quebrar("Общество Ромашка", "Helvetica", 8.5, 60) == ["Общество", "Ромашка"]


def test_pdf_com_tomador_em_chines_e_gerado_com_a_fonte_embutida():
    saida = io.BytesIO()
    c = canvas.Canvas(saida, pagesize=A4)
    pagina = danfse._Pagina(c)
    pagina.titulo("Tomador do serviço")
    pagina.campos([("NIF", "91440300MA5F"), ("Nome / Nome empresarial", f"{NOME_CHINES} 株式会社サンプル"), ("País", "China")], colunas=3)
    pagina.texto(f"Serviços de marketing 营销服务 prestados para {NOME_CHINES}")
    c.save()
    pdf = saida.getvalue()
    assert pdf.startswith(b"%PDF")
    nomes = [nome for nome, _ in danfse._fontes_amplas()]
    assert nomes, "sempre sobra pelo menos a fonte do leitor de PDF"
    # a fonte escolhida está dentro do arquivo (nome da instalada ou a do leitor)
    assert any(marca in pdf for marca in (b"DroidSansFallback", b"NanumGothic", b"DejaVuSans", b"STSong-Light"))


def test_caractere_que_nenhuma_fonte_desenha_vira_interrogacao(monkeypatch):
    monkeypatch.setattr(danfse, "_amplas", [("Helvetica", {ord("深")})])
    assert danfse._trechos("a深圳", "Helvetica") == [("Helvetica", "a深?")]


# --- 2. competência no mês corrente é o normal -------------------------------------
# A primeira ideia era avisar "mês pulado" (tomador com nota de dois meses atrás, sem
# a do mês passado, e a nova saindo neste mês). O Marcos corrigiu: mesmo quando o
# relatório é de meses atrás, a nota sai com a competência deste mês — data antiga é
# que gera multa. Então NÃO há aviso, e este teste segura isso.


def test_nota_no_mes_corrente_sem_a_do_mes_passado_nao_gera_aviso(db, vinculo_teste, prestador_teste):
    db.add(Certificado(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, pfx_criptografado=b"x", senha_criptografada=b"x",
        validade=hoje_br() + datetime.timedelta(days=200),
    ))
    _nota(db, vinculo_teste, _competencia(2), 500)
    _nota(db, vinculo_teste, _competencia(3), 620)
    assert conferir_nota(db, vinculo_teste, 550, hoje_br(), None, None) == []


# --- 3. empresa de fora sem número fiscal ---------------------------------------


def _de_fora(client, vinculo_id, **mudancas):
    corpo = {"tipo": "exterior", "razao_social": NOME_CHINES, "pais": "CN", "nif": "", "motivo_sem_nif": "2"}
    corpo.update(mudancas)
    return client.post(f"/api/vinculos/{vinculo_id}/identificar", json=corpo)


def _cliente_de_controle(client) -> str:
    r = client.post("/api/financeiro/clientes", json={"nome": "Cliente Sintético de Fora"})
    assert r.status_code == 200
    return r.json()["id"]


def test_cadastro_de_fora_sem_nif_pede_o_motivo(client, db):
    vinculo_id = _cliente_de_controle(client)
    r = _de_fora(client, vinculo_id, motivo_sem_nif=None)
    assert r.status_code == 422 and "não tem número fiscal" in r.json()["detail"]
    assert _de_fora(client, vinculo_id, motivo_sem_nif="9").status_code == 422

    r = _de_fora(client, vinculo_id)
    assert r.status_code == 200, r.text
    tomador = r.json()["vinculo"]["tomador"]
    assert tomador["pais"] == "CN" and tomador["nif"] is None and tomador["motivo_sem_nif"] == "2"
    item = next(v for v in client.get("/api/vinculos?todos=true").json() if v["id"] == vinculo_id)
    assert item["tomador_pais"] == "CN" and item["tomador_nif"] is None and item["tomador_motivo_sem_nif"] == "2"

    # informou o número depois: o motivo deixa de valer
    r = _de_fora(client, vinculo_id, nif="91440300MA5F")
    assert r.json()["vinculo"]["tomador"]["nif"] == "91440300MA5F" and r.json()["vinculo"]["tomador"]["motivo_sem_nif"] is None


def test_nota_pra_empresa_de_fora_sem_nif_sai_com_o_motivo_e_vale_no_xsd(client, db, prestador_teste):
    prestador_teste.inscricao_municipal = "123456"
    prestador_teste.op_simples_nacional, prestador_teste.regime_apuracao_sn, prestador_teste.regime_especial_trib = "3", "1", "0"
    vinculo_id = _cliente_de_controle(client)
    assert _de_fora(client, vinculo_id, motivo_sem_nif="1").status_code == 200
    db.expire_all()
    vinculo = db.get(PrestadorTomador, uuid.UUID(vinculo_id))
    vinculo.sem_nota, vinculo.cod_trib_nacional = False, "170601"
    vinculo.template_descricao, vinculo.envio_formas = "Serviços de marketing - {mes_nome_upper}/{ano}", ["download"]
    db.flush()
    assert vinculo.tomador.estrangeiro and vinculo.tomador.sem_nif == "1"
    assert conferir_vinculo(db, vinculo) == []

    emissao = criar_rascunho(db, vinculo, competencia="2026-09", valor=1500, aliq_sn=6.0)
    snap = emissao.tomador_snapshot
    assert snap["tipo_documento"] == "NIF" and snap["cnpj"] is None and snap["motivo_sem_nif"] == "1" and snap["pais"] == "CN"

    montar(db, emissao)
    assert emissao.estado == "montado"
    dps = etree.fromstring(emissao.xml_dps.encode("utf-8"))
    etree.XMLSchema(etree.parse(str(XSD))).assertValid(etree.ElementTree(dps))
    assert _t(dps, "toma/cNaoNIF").text == "1" and _t(dps, "toma/NIF") is None and _t(dps, "toma/CNPJ") is None
    assert _t(dps, "toma/xNome").text == NOME_CHINES  # o nome vai inteiro no XML
    assert _t(dps, "toma/end/endExt/cPais").text == "CN"
    assert _t(dps, "serv/comExt/vServMoeda").text == "1500.00"

    pontos = {p["codigo"] for p in conferir_emissao(db, emissao)}
    assert not {"documento_vazio", "documento_invalido", "cadastro_mudou"} & pontos
    assert montar_nota_visual(emissao)["tomador"]["cnpj"] == "Sem número fiscal (NIF)"
    # depois de autorizada: o PDF mostra o motivo no lugar do número
    emissao.estado, emissao.chave_acesso = "confirmado", "3" * 50
    db.flush()
    dados = dict(danfse.dados_do_danfse(emissao)["tomador"])
    assert dados["CNPJ / CPF / NIF"] == "Sem NIF (dispensado)" and "China" in dados["Município"]
    assert danfse.gerar_danfse(emissao).startswith(b"%PDF")

    # mudou o motivo no cadastro depois: a nota pronta avisa
    vinculo.tomador.motivo_sem_nif = "2"
    assert "cadastro_mudou" in {p["codigo"] for p in conferir_emissao(db, emissao)}
