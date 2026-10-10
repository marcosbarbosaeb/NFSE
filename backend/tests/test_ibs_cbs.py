"""IBS e CBS na nota — tela e memória (2026.10.7, ideias/ibs-cbs-na-nota.md).

O XML ainda não leva o grupo IBS/CBS (esquema da NT 009 não publicado — raio-x
seção 15). Aqui: escolha da ME/EPP (MEI não escolhe), memória da classificação
no tomador, aviso da conferência a partir de 2027, aviso de confirmação antes
da virada do semestre e o PDF mostrando os valores quando a nota trouxer.
Só dados sintéticos."""
import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.services import danfse, ibs_cbs
from app.services.conferencia import conferir_nota
from app.services.motor_emissao import criar_rascunho, montar
from app.tempo import hoje as hoje_br


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_so_a_me_epp_do_simples_escolhe_e_o_padrao_e_tudo_pelo_simples(prestador_teste):
    assert ibs_cbs.regime(prestador_teste) == "1"
    prestador_teste.op_simples_nacional = "2"  # MEI
    assert ibs_cbs.regime(prestador_teste) is None and not ibs_cbs.escolhe(prestador_teste)
    prestador_teste.op_simples_nacional = "1"  # não optante
    assert ibs_cbs.regime(prestador_teste) is None


def test_salvar_na_empresa_guarda_e_confirma_e_mei_limpa(client, db, prestador_teste):
    r = client.patch("/api/prestador", json={"regime_ibs_cbs": "2", "regime_ibs_cbs_desde": "2027-01"})
    assert r.status_code == 200, r.text
    assert r.json()["regime_ibs_cbs"] == "2" and r.json()["regime_ibs_cbs_desde"] == "2027-01"
    assert prestador_teste.ibs_cbs_confirmado_em == hoje_br()
    assert client.patch("/api/prestador", json={"regime_ibs_cbs": "4"}).status_code == 422
    assert client.patch("/api/prestador", json={"regime_ibs_cbs_desde": "2027-03"}).status_code == 422
    r = client.patch("/api/prestador", json={"op_simples_nacional": "2"})
    assert r.json()["regime_ibs_cbs"] is None and r.json()["regime_ibs_cbs_desde"] is None


def test_classificacao_fica_no_tomador(client, vinculo_teste):
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cclass_trib": "000.001", "cind_op": "100301"})
    assert r.status_code == 200, r.text
    assert r.json()["cclass_trib"] == "000001" and r.json()["cind_op"] == "100301"
    assert client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cclass_trib": "123"}).status_code == 422
    r = client.patch(f"/api/vinculos/{vinculo_teste.id}", json={"cclass_trib": ""})
    assert r.json()["cclass_trib"] is None


def test_conferencia_avisa_a_partir_de_2027(db, vinculo_teste, prestador_teste):
    def codigos(data):
        return {p["codigo"] for p in conferir_nota(db, vinculo_teste, 1000, data, None, 6.0)}

    assert "classificacao_ibs_cbs" not in codigos(datetime.date(2026, 12, 1))
    assert "classificacao_ibs_cbs" in codigos(datetime.date(2027, 1, 5))
    aviso = next(p for p in conferir_nota(db, vinculo_teste, 1000, datetime.date(2027, 1, 5), None, 6.0) if p["codigo"] == "classificacao_ibs_cbs")
    assert aviso["nivel"] == "aviso"  # nunca trava
    vinculo_teste.cclass_trib = "000001"
    assert "classificacao_ibs_cbs" not in codigos(datetime.date(2027, 1, 5))
    vinculo_teste.cclass_trib = None
    prestador_teste.op_simples_nacional, prestador_teste.regime_apuracao_sn = "2", None  # MEI: não avisa
    assert "classificacao_ibs_cbs" not in codigos(datetime.date(2027, 1, 5))


def test_confirmacao_antes_da_virada_do_semestre(prestador_teste):
    nov = datetime.date(2026, 11, 3)
    assert ibs_cbs.precisa_confirmar(prestador_teste, nov)
    aviso = ibs_cbs.aviso_de_atencao(prestador_teste, nov)
    assert "janeiro de 2027" in aviso["mensagem"] and "pelo simples nacional" in aviso["mensagem"]
    assert not ibs_cbs.precisa_confirmar(prestador_teste, datetime.date(2026, 10, 10))  # fora da janela
    prestador_teste.ibs_cbs_confirmado_em = datetime.date(2026, 11, 2)
    assert not ibs_cbs.precisa_confirmar(prestador_teste, datetime.date(2026, 12, 20))
    # confirmação antiga não vale pro semestre seguinte
    assert ibs_cbs.precisa_confirmar(prestador_teste, datetime.date(2027, 5, 10))
    assert "julho de 2027" in ibs_cbs.aviso_de_atencao(prestador_teste, datetime.date(2027, 5, 10))["mensagem"]
    prestador_teste.op_simples_nacional = "2"
    assert ibs_cbs.aviso_de_atencao(prestador_teste, nov) is None


IBSCBS_NFSE = (
    "<IBSCBS><cLocalidadeIncid>3106200</cLocalidadeIncid><valores><vBC>1000.00</vBC></valores>"
    "<totCIBS><vTotNF>1000.00</vTotNF><gTribSN><pIBSSN>0.50</pIBSSN><vIBSSN>5.00</vIBSSN>"
    "<pCBSSN>1.20</pCBSSN><vCBSSN>12.00</vCBSSN></gTribSN></totCIBS></IBSCBS>"
)


def test_pdf_mostra_ibs_e_cbs_quando_a_nota_traz(db, vinculo_teste, prestador_teste):
    prestador_teste.inscricao_municipal = "123456"
    emissao = criar_rascunho(db, vinculo_teste, competencia="2026-10", valor=1000, aliq_sn=6.0)
    montar(db, emissao)
    dps = emissao.xml_dps.split("?>", 1)[-1]
    emissao.estado, emissao.chave_acesso = "confirmado", "3" * 50
    ns = 'xmlns="http://www.sped.fazenda.gov.br/nfse"'
    # sem o grupo: o PDF não ganha a seção
    emissao.xml_resposta = f'<NFSe {ns}><infNFSe Id="NFS1"><nNFSe>1</nNFSe><valores><vLiq>1000.00</vLiq></valores>{dps}</infNFSe></NFSe>'
    assert danfse.dados_do_danfse(emissao)["ibs_cbs"] is None
    # com o grupo (o que a Sefin devolve para a ME/EPP do Simples)
    emissao.xml_resposta = (f'<NFSe {ns}><infNFSe Id="NFS1"><nNFSe>1</nNFSe><valores><vLiq>1000.00</vLiq></valores>'
                            f'{IBSCBS_NFSE}{dps}</infNFSe></NFSe>')
    db.flush()
    linhas = dict(danfse.dados_do_danfse(emissao)["ibs_cbs"])
    assert linhas["IBS no Simples"] == "R$ 5,00" and linhas["CBS no Simples"] == "R$ 12,00"
    assert "IBS" not in linhas  # vIBSTot não vem para quem apura pelo Simples
    assert danfse.gerar_danfse(emissao).startswith(b"%PDF")
