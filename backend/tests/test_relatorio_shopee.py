"""Relatório mensal da Shopee (28/09/2026): uma nota por vendedor, sem salvar
os vendedores como tomadores. Dados FICTÍCIOS — o relatório real tem dados
de terceiros e nunca entra no repositório."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from app.database import get_db
from app.fiscal.dps import montar_dps_xml
from app.main import app, prestador_atual_id
from app.models import Despesa, Emissao, Tomador
from app.services.relatorio_shopee import (
    RelatorioShopeeInvalidoError,
    gerar_notas,
    ler_relatorio,
    parsear_competencia,
    parsear_endereco,
)

CABECALHO = (
    "﻿Mês de conclusão,Nome da loja,ID da Loja,Comissão Total do Vendedor,CNPJ do Vendedor,CPF do Vendedor,"
    "Identificação Fiscal Estrangeira,Razão social do vendedor,Endereço do Vendedor,País do Vendedor,Inscrição Estadual,E-mail\n"
)
LINHAS = [
    'Aug 2026,Loja Um,1,"R$7,14",11222333000181,,,LOJA UM LTDA,"R Exemplo, 425, Sala 2 - Centro, Hortolândia - São Paulo, 13186642",BR,1,um@exemplo.com',
    'Aug 2026,Loja Um Filial,2,"R$2,86",11222333000181,,,LOJA UM LTDA,"R Exemplo, 425, Sala 2 - Centro, Hortolândia - São Paulo, 13186642",BR,1,um@exemplo.com',
    'Aug 2026,Pessoa Física,3,"R$1,00",,52998224725,,FULANA DE TAL,"R Dois, 74 - Vila Nova, Jandira - São Paulo, 06636030",BR,,f@exemplo.com',
    'Aug 2026,Loja Fora,4,"R$5,19",,,202602050G,FOREIGN SHOP LIMITED,"Harbour Road, Hong Kong",CN,,x@exemplo.com',
    'Aug 2026,Centavo,5,"R$0,01",22333444000181,,,CENTAVO LTDA,"Av Três, 1,  - Bela Vista, São Paulo - São Paulo, 01311927",BR,,c@exemplo.com',
    'Jul 2026,Loja Um,1,"R$3,00",11222333000181,,,LOJA UM LTDA,"R Exemplo, 425, Sala 2 - Centro, Hortolândia - São Paulo, 13186642",BR,1,um@exemplo.com',
]


def _csv(linhas=LINHAS) -> bytes:
    return (CABECALHO + "\n".join(linhas) + "\n").encode("utf-8")


def test_competencia_e_endereco():
    assert parsear_competencia("Aug 2026") == "2026-08"
    assert parsear_competencia("set 2026") == "2026-09"
    e = parsear_endereco("R Joaquim M Leite, 425, Cond 4 AP 236 - Jardim Interlagos, Hortolândia - São Paulo, 13186642")
    assert (e["xLgr"], e["nro"], e["xCpl"], e["xBairro"], e["CEP"], e["uf"]) == (
        "R Joaquim M Leite", "425", "Cond 4 AP 236", "Jardim Interlagos", "13186642", "SP",
    )
    assert e["cMun"] == "3519071"  # Hortolândia
    assert parsear_endereco("上海市浦东新区") is None


def test_le_agrupa_lojas_do_mesmo_vendedor_e_marca_estrangeiro():
    r = ler_relatorio(_csv())
    agosto = {v.documento: v for v in r.vendedores if v.competencia == "2026-08"}
    assert agosto["11222333000181"].valor == Decimal("10.00")
    assert agosto["11222333000181"].lojas == ["Loja Um", "Loja Um Filial"]
    assert agosto["52998224725"].tipo_documento == "CPF"
    assert agosto["202602050G"].estrangeiro and agosto["202602050G"].tipo_documento == "NIF"
    assert len([v for v in r.vendedores if v.competencia == "2026-07"]) == 1


def test_arquivo_que_nao_e_da_shopee():
    with pytest.raises(RelatorioShopeeInvalidoError):
        ler_relatorio(b"apelido,competencia,valor\nAWIN,2026-08,10\n")


def test_dps_com_cpf_e_sem_endereco():
    prest = {"CNPJ": "00000000000191", "IM": "1", "cMun": "3106200", "opSimpNac": "3", "regApTribSN": "1", "regEspTrib": "0"}
    serv = {"cLocPrestacao": "3106200", "cTribNac": "170601", "cTribMun": "001", "descricao": "x"}
    dps = montar_dps_xml(prest=prest, toma={"CPF": "52998224725", "xNome": "FULANA"}, serv=serv, serie="1", n_dps=1, valor=1.0)
    xml = etree.tostring(dps).decode()
    assert "<CPF>52998224725</CPF>" in xml and "<end>" not in xml.split("<toma>")[1].split("</toma>")[0]


def test_gera_uma_nota_por_vendedor_sem_criar_tomadores(db, vinculo_teste):
    tomadores_antes = db.query(Tomador).count()
    r = ler_relatorio(_csv())
    res = gerar_notas(db, vinculo_teste, r, competencia="2026-08", valor_minimo=Decimal("0.05"))
    assert res.geradas == 2  # CNPJ (2 lojas somadas) + CPF; estrangeiro e centavo pulados
    assert res.puladas == 2 and not res.erros
    assert db.query(Tomador).count() == tomadores_antes
    notas = db.query(Emissao).filter_by(prestador_tomador_id=vinculo_teste.id, competencia="2026-08").all()
    assert sorted(n.tomador_documento for n in notas) == ["11222333000181", "52998224725"]
    cpf = next(n for n in notas if n.tomador_documento == "52998224725")
    assert "<CPF>52998224725</CPF>" in cpf.xml_dps and cpf.tomador_snapshot["email"] == "f@exemplo.com"
    # reenviar o mesmo relatório não duplica
    again = gerar_notas(db, vinculo_teste, r, competencia="2026-08", valor_minimo=Decimal("0.05"))
    assert again.geradas == 0 and again.ja_existiam == 2


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


def test_endpoints_previa_e_gerar(client, vinculo_teste):
    arq = {"arquivo": ("MonthlyReport.csv", _csv(), "text/csv")}
    previa = client.post("/api/shopee/previa", data={"vinculo_id": str(vinculo_teste.id)}, files=arq)
    assert previa.status_code == 200
    meses = {m["competencia"]: m for m in previa.json()["competencias"]}
    assert meses["2026-08"]["vendedores"] == 4 and meses["2026-08"]["estrangeiros"] == 1

    gerar = client.post(
        "/api/shopee/gerar",
        data={"vinculo_id": str(vinculo_teste.id), "competencia": "2026-07", "aliq_sn": "6"},
        files={"arquivo": ("MonthlyReport.csv", _csv(), "text/csv")},
    )
    assert gerar.status_code == 200 and gerar.json()["geradas"] == 1

    linha = next(v for v in client.get("/api/vinculos?todos=true&competencia=2026-07").json() if v["id"] == str(vinculo_teste.id))
    assert linha["emissao_quantidade"] == 1


def test_extrato_confirma_saidas_como_despesas(client, db, prestador_teste):
    resp = client.post(
        "/api/recebimentos/extrato/confirmar",
        json={"itens": [], "despesas": [{"categoria": "Tarifas bancárias", "competencia": "2026-09", "valor": 12.5}]},
    )
    assert resp.status_code == 200 and resp.json()["despesas_registradas"] == 1
    assert db.query(Despesa).filter_by(prestador_id=prestador_teste.id, categoria="Tarifas bancárias").count() == 1
