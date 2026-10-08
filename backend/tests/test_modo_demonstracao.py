"""Modo demonstração (08/10/2026): caminho feliz simulado, cenários e trava."""
import json

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Emissao, Envio, Prestador, PrestadorTomador, Tomador
from app.services import demo
from app.services.demo import _dv_cnpj, carregar_cenario, cenarios, criar_conta_demo
from app.tempo import hoje

_MES = hoje().strftime("%Y-%m")


@pytest.fixture
def cliente(db):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_cenarios_so_tem_cnpj_que_nao_existe():
    assert {"afiliados", "beleza"} <= set(cenarios())
    for nome in cenarios():
        c = carregar_cenario(nome)
        for t in c["tomadores"]:
            assert len(t["cnpj"]) == 14 and t["cnpj"].isdigit()
            assert _dv_cnpj(t["cnpj"][:12]) != t["cnpj"][12:], f"{nome}: {t['apelido']} tem CNPJ válido — use um de mentira"


@pytest.mark.parametrize("nome", ["nao-existe", "../afiliados", "AFILIADOS/../x"])
def test_cenario_inexistente_ou_caminho_estranho(nome):
    with pytest.raises(demo.CenarioInexistenteError):
        carregar_cenario(nome)


def test_cenario_beleza_nasce_com_notas_autorizadas_e_entregues(db):
    usuario = criar_conta_demo(db, "beleza")
    prestador = db.get(Prestador, usuario.prestador_id)
    assert prestador.demo and prestador.razao_social == "Lumi Conteúdo Digital LTDA"
    vinculos = db.query(PrestadorTomador).filter_by(prestador_id=prestador.id).all()
    assert "Bella Beauty" in {v.apelido for v in vinculos}
    assert all(db.get(Tomador, v.tomador_id).status == "pendente" for v in vinculos)
    notas = db.query(Emissao).filter_by(prestador_id=prestador.id).all()
    assert len(notas) == 9 and all(n.estado == "confirmado" and n.chave_acesso for n in notas)
    assert all((n.tomador_snapshot or {}).get("tpAmb") == "2" for n in notas)
    assert db.query(Envio).filter(Envio.emissao_id.in_([n.id for n in notas]), Envio.status == "enviado").count() == 9


def test_gerar_e_fazer_tudo_na_simulacao_da_certo_e_conta_na_visao_geral(cliente, db):
    assert cliente.post("/api/demo?cenario=beleza").status_code == 200
    bella = next(v for v in cliente.get("/api/vinculos?todos=true").json() if v["apelido"] == "Bella Beauty")
    antes = cliente.get("/api/painel/resumo-mes").json()

    nota = cliente.post("/api/dps", json={"vinculo_id": bella["id"], "competencia": _MES, "valor": 3650.0, "aliq_sn": 6.0})
    assert nota.status_code == 200, nota.text
    nota_id = nota.json()["id"]
    assinada = cliente.post(f"/api/dps/{nota_id}/assinar")
    assert assinada.status_code == 200 and assinada.json()["estado"] == "assinado"
    autorizada = cliente.post(f"/api/dps/{nota_id}/submeter")
    assert autorizada.status_code == 200 and autorizada.json()["estado"] == "confirmado"
    assert autorizada.json()["chave_acesso"]
    previa = cliente.get(f"/api/dps/{nota_id}/email-previa").json()
    assert previa["destinos"]
    envio = cliente.post(f"/api/dps/{nota_id}/enviar-email", json={})
    assert envio.status_code == 200 and envio.json()["status"] == "enviado"

    pdf = cliente.get(f"/api/dps/{nota_id}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    depois = cliente.get("/api/painel/resumo-mes").json()
    assert depois["emitidas"] == antes["emitidas"] + 1
    assert depois["faturado_no_mes"] == pytest.approx(antes["faturado_no_mes"] + 3650.0)


def test_trava_conta_real_nunca_simula(cliente, db, vinculo_teste):
    """Conta de verdade sem certificado: assinar dá o erro de sempre, nunca sucesso."""
    from app.deps import prestador_atual_id
    from app.services.motor_emissao import criar_rascunho, montar

    nota = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=100.0, aliq_sn=6.0, tpAmb="2")
    montar(db, nota)
    app.dependency_overrides[prestador_atual_id] = lambda: vinculo_teste.prestador_id
    try:
        resp = cliente.post(f"/api/dps/{nota.id}/assinar")
        envio = cliente.post(f"/api/dps/{nota.id}/submeter")
    finally:
        app.dependency_overrides.pop(prestador_atual_id, None)
    assert resp.status_code == 409 and "certificado" in resp.json()["detail"]
    assert envio.status_code == 409
    db.refresh(nota)
    assert nota.estado == "montado" and nota.chave_acesso is None


def test_trava_usuario_de_simulacao_em_empresa_sem_marca_demo_e_recusado(cliente, db):
    assert cliente.post("/api/demo").status_code == 200
    vinculo = next(v for v in cliente.get("/api/vinculos?todos=true").json() if v["apelido"] == "Loja Modelo")
    nota = cliente.post("/api/dps", json={"vinculo_id": vinculo["id"], "competencia": _MES, "valor": 10.0, "aliq_sn": 6.0})
    assert nota.status_code == 200, nota.text
    nota = nota.json()
    prestador = db.query(Prestador).join(PrestadorTomador, PrestadorTomador.prestador_id == Prestador.id).filter(
        PrestadorTomador.id == vinculo["id"]
    ).one()
    prestador.demo = False
    db.flush()
    resp = cliente.post(f"/api/dps/{nota['id']}/assinar")
    assert resp.status_code == 403


def test_simulacao_com_cenario_inexistente_da_404(cliente):
    resp = cliente.post("/api/demo?cenario=nao-existe")
    assert resp.status_code == 404 and "afiliados" in resp.json()["detail"]


def test_leia_me_cita_os_campos_do_cenario():
    texto = (demo.PASTA_CENARIOS / "LEIA-ME.md").read_text(encoding="utf-8")
    campos = set(json.loads((demo.PASTA_CENARIOS / "beleza.json").read_text(encoding="utf-8")))
    for campo in campos - {"titulo", "meses_passados", "variacao_por_mes"}:
        assert f"`{campo}`" in texto
