"""Primeiros passos e a trava "sem certificado não gera nota" (06/10/2026)."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, exigir_certificado, prestador_atual_id
from app.models import Certificado
from app.services import prontidao


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    app.dependency_overrides.pop(exigir_certificado, None)  # aqui a trava vale de verdade
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _certificado(db, prestador, validade):
    db.add(Certificado(id=uuid.uuid4(), prestador_id=prestador.id, pfx_criptografado=b"x", senha_criptografada=b"y", validade=validade))
    db.flush()


def test_conta_nova_e_guiada_e_nao_gera_nota_sem_certificado(client, db, prestador_teste, vinculo_teste):
    p = client.get("/api/empresa/prontidao").json()
    assert (p["certificado"], p["pode_emitir"], p["pronta"], p["tomadores"]) == ("falta", False, False, 1)
    assert {f["campo"] for f in p["dados_faltando"]} == {"endereco", "regime"}
    assert "certificado digital A1" in p["motivo"] and "Empresa › Certificado" in p["motivo"]

    corpo = {"vinculo_id": str(vinculo_teste.id), "competencia": "2026-10", "data_competencia": "2026-10-05", "valor": 100}
    r = client.post("/api/dps", json=corpo)
    assert r.status_code == 409 and "certificado digital A1" in r.json()["detail"]

    # certificado vencido também trava
    hoje = datetime.date.today()
    _certificado(db, prestador_teste, hoje - datetime.timedelta(days=40))
    assert client.get("/api/empresa/prontidao").json()["certificado"] == "vencido"
    assert client.post("/api/dps", json=corpo).status_code == 409


def test_com_certificado_e_dados_a_empresa_fica_pronta(client, db, prestador_teste, vinculo_teste):
    _certificado(db, prestador_teste, datetime.date.today() + datetime.timedelta(days=200))
    prestador_teste.cep, prestador_teste.logradouro, prestador_teste.numero, prestador_teste.bairro = "30130000", "Rua A", "10", "Centro"
    prestador_teste.op_simples_nacional = "3"
    db.flush()
    p = client.get("/api/empresa/prontidao").json()
    assert p["pode_emitir"] is True and [f["campo"] for f in p["dados_faltando"]] == ["aliquota"] and p["pronta"] is False
    prestador_teste.aliquota_atual = 6
    db.flush()
    assert client.get("/api/empresa/prontidao").json()["pronta"] is True
    assert prontidao.motivo_que_trava(db, prestador_teste.id) is None


def test_simulacao_nao_precisa_de_certificado(db, prestador_teste):
    prestador_teste.demo = True
    db.flush()
    assert prontidao.motivo_que_trava(db, prestador_teste.id) is None
    assert prontidao.prontidao(db, prestador_teste.id)["aplica"] is False


def test_ambiente_de_teste_da_plataforma_nunca_emite_de_verdade(db, prestador_teste, vinculo_teste, monkeypatch):
    """AMBIENTE_TESTE=true (o serviço de teste no Railway): só homologação e
    e-mail de nota só pro login de quem testa."""
    from app.config import get_settings
    from app.main import _tp_amb_da_conta, _tp_amb_da_nota
    from app.services import envio_direto, motor_emissao

    assert _tp_amb_da_conta(db, prestador_teste.id) == "1"
    assert envio_direto.email_da_conta_teste(db, prestador_teste) is None
    monkeypatch.setattr(get_settings(), "ambiente_teste", True)
    assert _tp_amb_da_conta(db, prestador_teste.id) == "2" and _tp_amb_da_nota(db, prestador_teste.id, "1") == "2"
    # uma nota de produção que já existisse não passa do envio
    nota = motor_emissao.criar_rascunho(db, vinculo_teste, competencia="2026-10", valor=10, tpAmb="1")
    nota.estado = "assinado"
    db.flush()
    with pytest.raises(motor_emissao.TransicaoInvalidaError, match="ambiente de teste"):
        motor_emissao.submeter(db, nota, cliente=None)
    assert nota.estado == "assinado"
