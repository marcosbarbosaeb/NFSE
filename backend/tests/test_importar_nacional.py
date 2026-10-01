"""Importar do Emissor Nacional (28/09/2026) — XMLs sintéticos no padrão
nacional, página do ADN simulada."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Emissao, Envio, PrestadorTomador
from app.services import importar_adn

NS = "http://www.sped.fazenda.gov.br/nfse"
PREST = "00000000000191"


def nfse(n, toma_doc, nome, competencia, valor, desc="Comissão", tipo="CNPJ", interm=None, prest=PREST, serie="900"):
    chave = f"3106200{n:043d}"
    interm_xml = f"<interm><CNPJ>{interm}</CNPJ><xNome>Marketplace</xNome></interm>" if interm else ""
    return f"""<NFSe xmlns="{NS}" versao="1.00"><infNFSe Id="NFS{chave}"><nNFSe>{n}</nNFSe>
<dhProc>{competencia}-05T10:00:00-03:00</dhProc><emit><CNPJ>{prest}</CNPJ></emit>
<DPS versao="1.00"><infDPS Id="DPSX"><tpAmb>1</tpAmb><dhEmi>{competencia}-05T10:00:00-03:00</dhEmi>
<serie>{serie}</serie><nDPS>{n}</nDPS><dCompet>{competencia}-05</dCompet><prest><CNPJ>{prest}</CNPJ></prest>
<toma><{tipo}>{toma_doc}</{tipo}><xNome>{nome}</xNome><end><endNac><cMun>3550308</cMun><CEP>01311000</CEP></endNac>
<xLgr>Av X</xLgr><nro>1</nro><xBairro>Centro</xBairro></end></toma>{interm_xml}
<serv><locPrest><cLocPrestacao>3106200</cLocPrestacao></locPrest><cServ><cTribNac>100101</cTribNac>
<xDescServ>{desc}</xDescServ></cServ></serv><valores><vServPrest><vServ>{valor}</vServ></vServPrest></valores>
</infDPS></DPS></infNFSe></NFSe>""".encode(), chave


def cancelamento(chave):
    return f"""<evento xmlns="{NS}"><infEvento><pedRegEvento><infPedReg><chNFSe>{chave}</chNFSe>
<e101101><xDesc>Cancelamento</xDesc></e101101></infPedReg></pedRegEvento></infEvento></evento>""".encode()


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


def test_ler_nfse_e_evento():
    xml, chave = nfse(7, "11222333000181", "Loja", "2026-02", "123.45", desc="Comissão fev")
    nota = importar_adn.ler_nfse(xml)
    assert nota["chave"] == chave and nota["n_dps"] == 7 and nota["serie"] == "900"
    assert nota["toma"]["documento"] == "11222333000181" and nota["valor"] == "123.45"
    assert nota["dcompet"] == "2026-02-05" and nota["cTribNac"] == "100101"
    assert importar_adn.ler_cancelamento(cancelamento(chave)) == chave
    assert importar_adn.ler_nfse(b"<nada/>") is None


def test_busca_previa_e_importacao(client, db, prestador_teste, vinculo_teste, monkeypatch):
    monkeypatch.setattr(importar_adn, "PAUSA_S", 0)
    # outro vínculo do MESMO tomador (tipo AWIN e AWIN Rchlo)
    irmao = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido="Programa B",
        cod_local_prestacao="3106200", cod_trib_nacional="100101", template_descricao="Programa B comissão", ativo=True,
    )
    db.add(irmao)
    db.flush()
    docs = []
    a1, _ = nfse(1, "11222333000181", "TOMADOR", "2026-01", "100.00", desc="Comissão de teste - 01/2026")
    a2, _ = nfse(2, "11222333000181", "TOMADOR", "2026-01", "50.00", desc="Programa B comissão jan")
    a3, _ = nfse(8, "11222333000181", "TOMADOR", "2026-01", "70.00", desc="Comissão de teste - complementar")
    novo, chave_novo = nfse(3, "44555666000199", "Empresa Nova SA", "2026-02", "300.00")
    velho, _ = nfse(4, "77888999000111", "Cliente Antigo", "2025-06", "80.00")
    loja, _ = nfse(2200000000031, "12345678909", "Vendedor PF", "2026-02", "10.00", tipo="CPF", interm="11222333000181")
    recebida, _ = nfse(6, PREST, "Eu", "2026-02", "999.00", prest="99999999000199")
    for i, x in enumerate([a1, a2, a3, novo, velho, loja, recebida], start=1):
        docs.append({"nsu": i, "tipo": "NFSE", "xml": x})
    docs.append({"nsu": 8, "tipo": "EVENTO", "xml": cancelamento(chave_novo)})
    paginas = [docs[:4], docs[4:], []]

    def pagina_falsa(cliente, cnpj, nsu):
        pagina = paginas.pop(0)
        return pagina, (max(d["nsu"] for d in pagina) if pagina else None)

    monkeypatch.setattr(importar_adn, "ler_pagina", pagina_falsa)
    monkeypatch.setattr("app.main._cliente_producao", lambda db, p: object())
    importar_adn._buscas.pop(prestador_teste.id, None)

    r = client.post("/api/importar/nacional/buscar", json={"desde": "2025-01"})
    assert r.status_code == 200, r.text
    previa = r.json()
    assert previa["terminou"] and previa["recebidas"] == 1 and previa["total_notas"] == 6
    grupos = {g["documento"]: g for g in previa["grupos"]}
    assert grupos["11222333000181"]["sugestao"] == "vinculo" and grupos["11222333000181"]["quantidade"] == 3
    assert grupos["12345678909"]["sugestao"] == "avulsa"
    assert grupos["44555666000199"]["sugestao"] == "novo" and grupos["44555666000199"]["canceladas"] == 1

    mapa = [
        {"documento": "11222333000181", "acao": "vinculo", "vinculo_id": str(vinculo_teste.id)},
        {"documento": "12345678909", "acao": "avulsa", "vinculo_id": str(vinculo_teste.id)},
        {"documento": "44555666000199", "acao": "novo"},
        {"documento": "77888999000111", "acao": "novo"},
    ]
    r = client.post("/api/importar/nacional", json={"mapeamento": mapa})
    assert r.status_code == 200, r.text
    res = r.json()
    # três notas do mesmo CNPJ em jan: uma por vínculo e a terceira (histórico
    # com duas no mês) vai pro mais parecido em vez de ser pulada
    assert res["importadas"] == 6 and res["vinculos_criados"] == 2 and res["puladas"] == []

    notas = {e.n_dps: e for e in db.query(Emissao).filter(Emissao.origem == "importada")}
    assert notas[1].prestador_tomador_id == vinculo_teste.id and notas[2].prestador_tomador_id == irmao.id
    assert notas[2200000000031].tomador_documento == "12345678909" and notas[2200000000031].estado == "confirmado"
    assert notas[3].estado == "cancelada"
    assert db.query(Envio).filter(Envio.emissao_id == notas[1].id, Envio.status == "enviado").count() == 1
    antigo = db.get(PrestadorTomador, notas[4].prestador_tomador_id)
    assert antigo.ativo is False  # não recebe nota há meses
    assert notas[8].prestador_tomador_id == vinculo_teste.id
    assert prestador_teste.adn_ultimo_nsu == 8

    # limpar o histórico antes de 2026: some a nota de 2025 e o tomador dela
    r = client.post("/api/importar/nacional/limpar", json={"antes": "2026-01"})
    assert r.status_code == 200 and r.json() == {"notas": 1, "tomadores": 1}
    assert db.get(PrestadorTomador, antigo.id) is None

    # repetir não duplica
    # (a de 2025 volta, porque saiu na limpeza; as outras não duplicam)
    assert client.post("/api/importar/nacional", json={"mapeamento": mapa}).json()["importadas"] == 1
    # o vínculo novo aparece sem o CNPJ interno? (CNPJ real aqui)
    lista = client.get("/api/vinculos?todos=true").json()
    assert any(v["apelido"] == "Empresa Nova SA" for v in lista)


def test_tomador_so_controle_nao_gera_nota(client, db, prestador_teste):
    t = importar_adn.criar_tomador_interno(db, "Parcerias", "3106200")
    v = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=t.id, apelido="Parcerias",
        cod_local_prestacao="3106200", cod_trib_nacional="100101", template_descricao="-", ativo=True, sem_nota=True,
    )
    db.add(v)
    db.flush()
    r = client.post("/api/dps", json={"vinculo_id": str(v.id), "competencia": "2026-05", "valor": 10})
    assert r.status_code == 422 and "controle" in r.json()["detail"]
    item = next(x for x in client.get("/api/vinculos").json() if x["id"] == str(v.id))
    assert item["tomador_cnpj"] == "" and item["sem_nota"] is True
