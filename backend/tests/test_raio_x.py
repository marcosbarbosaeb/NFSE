"""Painel do contador (07/10/2026): raio-x de cada empresa, alertas e o
pacote de notas do mês. Dados sintéticos; login de verdade."""
import datetime
import io
import uuid
import zipfile
from decimal import Decimal

from app.database import definir_prestador_atual
from app.models import Certificado, Emissao, PrestadorTomador, RegistroContador, Tomador
from app.services import raio_x
from app.tempo import hoje as hoje_br

from tests.test_contador import _convidar_e_aceitar, _entrar, api, cenario  # noqa: F401 (fixtures)


def _mes(atras: int = 0) -> str:
    return raio_x._mes(hoje_br(), atras)


def _vinculo(db, cliente):
    tomador = Tomador(id=uuid.uuid4(), cnpj="00000000000515", razao_social="TOMADOR SINTETICO LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=cliente.id, tomador_id=tomador.id, apelido="Tomador Sintético",
        cod_local_prestacao=cliente.cod_municipio, cod_trib_nacional="170601", template_descricao="Serviço", serie="1", ativo=True,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def _nota(db, vinculo, competencia, valor, n, estado="confirmado", amb="1"):
    e = Emissao(
        id=uuid.uuid4(), prestador_id=vinculo.prestador_id, prestador_tomador_id=vinculo.id, competencia=competencia,
        serie="1", n_dps=n, estado=estado, valor=Decimal(valor), origem="ana",
        tomador_snapshot={"apelido": vinculo.apelido, "tpAmb": amb}, xml_resposta="<NFSe/>",
        tomador_documento=str(n),  # várias no mesmo mês (como notas avulsas)
    )
    db.add(e)
    db.flush()
    return e


def test_raio_x_soma_so_nota_autorizada_de_verdade_e_compara_com_o_limite(db, api, cenario):
    _, da_contadora = _convidar_e_aceitar(db, api, cenario, [])
    assert da_contadora.post(f"/api/empresas/{cenario['escritorio'].id}/ativar").status_code == 200
    cliente = cenario["cliente"]
    definir_prestador_atual(db, cliente.id)
    cliente.op_simples_nacional = "2"  # MEI
    vinculo = _vinculo(db, cliente)
    _nota(db, vinculo, _mes(), "30000.00", 1)
    _nota(db, vinculo, _mes(), "40000.00", 2)
    _nota(db, vinculo, _mes(), "99999.00", 3, estado="cancelada")
    _nota(db, vinculo, _mes(), "99999.00", 4, amb="2")          # homologação não é faturamento
    _nota(db, vinculo, _mes(), "50.00", 5, estado="erro")       # recusada
    _nota(db, vinculo, _mes(14), "88888.00", 6)                 # fora dos 12 meses
    db.add(Certificado(
        id=uuid.uuid4(), prestador_id=cliente.id, pfx_criptografado=b"x", senha_criptografada=b"x",
        validade=hoje_br() + datetime.timedelta(days=10),
    ))
    db.flush()

    dados = da_contadora.get("/api/contador/atendimentos").json()
    c = dados["clientes"][0]
    r = c["raio_x"]
    assert r["regime_nome"] == "MEI" and r["notas_mes"] == 2 and r["faturado_mes"] == 70000.0
    assert r["faturado_ano"] == 70000.0 and r["limite"] == 81000.0 and r["limite_pct"] == 86.4
    assert r["recusadas"] == 1 and r["certificado"]["situacao"] == "vencendo" and r["certificado"]["dias"] == 10
    tipos = {a["tipo"]: a["nivel"] for a in c["alertas"]}
    assert tipos == {"certificado": "critico", "recusadas": "critico", "limite": "atencao"}
    assert c["alertas"][0]["nivel"] == "critico" and "86% do limite do MEI" in next(a["texto"] for a in c["alertas"] if a["tipo"] == "limite")
    assert dados["resumo"]["empresas"] == 1 and dados["resumo"]["notas_mes"] == 2 and dados["resumo"]["faturado_mes"] == 70000.0
    assert dados["resumo"]["alertas_criticos"] == 2
    # ela continua na empresa dela
    assert da_contadora.get("/api/auth/me").json()["prestador_id"] == str(cenario["escritorio"].id)


def test_alertas_de_certificado_e_limite():
    base = {"regime": "3", "faturado_ano": 0, "limite": 4800000.0, "limite_pct": 0.0, "recusadas": 0, "sem_nota": 0}
    cert = lambda situacao, dias=None: {**base, "certificado": {"situacao": situacao, "dias": dias, "validade": None}}  # noqa: E731
    assert raio_x.alertas(cert("ok", 200)) == []
    assert raio_x.alertas(cert("vencendo", 30))[0]["nivel"] == "atencao"
    assert raio_x.alertas(cert("vencendo", 15))[0]["nivel"] == "critico"
    assert "vence hoje" in raio_x.alertas(cert("vencendo", 0))[0]["texto"]
    assert raio_x.alertas(cert("vencido", -3))[0]["nivel"] == "critico"
    assert raio_x.alertas(cert("falta"))[0]["tipo"] == "certificado"
    passou = raio_x.alertas({**base, "certificado": None, "regime": "2", "limite": 81000.0, "limite_pct": 104.0, "faturado_ano": 84240.0})
    assert passou[0]["nivel"] == "critico" and "Passou do limite do MEI" in passou[0]["texto"]
    sem = raio_x.alertas({**base, "certificado": None, "sem_nota": 2}, bloqueada=True)
    assert [a["tipo"] for a in sem] == ["sem_nota", "assinatura"]


def test_pacote_do_mes_so_pra_quem_atende_e_fica_no_historico(db, api, cenario):
    _, da_contadora = _convidar_e_aceitar(db, api, cenario, [])
    assert da_contadora.post(f"/api/empresas/{cenario['escritorio'].id}/ativar").status_code == 200
    cliente = cenario["cliente"]
    definir_prestador_atual(db, cliente.id)
    vinculo = _vinculo(db, cliente)
    _nota(db, vinculo, "2026-09", "100.00", 1)
    _nota(db, vinculo, "2026-09", "100.00", 2, estado="erro")
    definir_prestador_atual(db, cenario["escritorio"].id)
    acesso_id = da_contadora.get("/api/contador/atendimentos").json()["clientes"][0]["id"]

    r = da_contadora.get(f"/api/contador/atendimentos/{acesso_id}/pacote?competencia=2026-09")
    assert r.status_code == 200, r.text
    assert "notas-00000000000272-2026-09.zip" in r.headers["content-disposition"]
    nomes = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert len([n for n in nomes if n.endswith(".xml")]) == 1  # só a autorizada
    assert da_contadora.get(f"/api/contador/atendimentos/{acesso_id}/pacote?competencia=2026-08").status_code == 404
    assert da_contadora.get(f"/api/contador/atendimentos/{acesso_id}/pacote?competencia=setembro").status_code == 422
    registros = [x.acao for x in db.query(RegistroContador).filter_by(prestador_id=cliente.id)]
    assert "Baixou as notas de 09/2026 (1)" in registros

    # quem não atende a empresa não baixa nada (nem a própria dona por esta rota)
    da_dona = _entrar(api, "dona@cliente.example")
    assert da_dona.get(f"/api/contador/atendimentos/{acesso_id}/pacote?competencia=2026-09").status_code == 404
