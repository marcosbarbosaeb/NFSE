"""Verificação no CNPJ com bloqueio e lista de espera (2026.10.7 — item B).

A consulta da Receita é trocada por dados de mentira (nada de rede). Cidade
no Emissor Nacional: Belo Horizonte (3106200). Fora: Brasília (5300108), que
tem sistema próprio. Só dados sintéticos."""
import uuid

import pytest
from fastapi.testclient import TestClient

import app.services.atendimento as atendimento
from app.database import get_db
from app.main import app
from app.models import ListaEspera
from app.services import lista_espera
from app.services.cnpj_lookup import ConsultaCnpjIndisponivelError, DadosCnpj

DENTRO, FORA = "3106200", "5300108"


def _dados(regime="3", situacao="ATIVA", cod=DENTRO):
    return DadosCnpj(razao_social="EMPRESA SINTETICA LTDA", logradouro="Rua A", numero="1", complemento=None, bairro="Centro",
                     cep="30100000", municipio="X", uf="MG", cod_municipio_sugerido=cod, situacao_cadastral=situacao, regime=regime)


@pytest.fixture
def receita(monkeypatch):
    estado = {"dados": _dados()}

    def consultar(cnpj):
        if estado["dados"] is None:
            raise ConsultaCnpjIndisponivelError("fora do ar")
        return estado["dados"]

    monkeypatch.setattr(atendimento, "_consultar", consultar)
    return estado


@pytest.mark.parametrize("regime,situacao,cod,codigo,pode,lista", [
    ("3", "ATIVA", DENTRO, "atende", True, False),
    ("2", "ATIVA", DENTRO, "atende", True, False),
    ("2", "ATIVA", FORA, "atende", True, False),  # MEI: a Sefin aceita em qualquer município
    ("3", "ATIVA", FORA, "cidade_fora", False, True),
    ("1", "ATIVA", DENTRO, "regime", False, True),
    ("3", "BAIXADA", DENTRO, "inativo", False, False),
    (None, "ATIVA", DENTRO, "indefinido", True, False),
])
def test_tabela_do_roteiro(receita, regime, situacao, cod, codigo, pode, lista):
    receita["dados"] = _dados(regime, situacao, cod)
    v = atendimento.avaliar_cnpj("00000000000191")
    assert (v["codigo"], v["pode_criar"], v["lista_espera"]) == (codigo, pode, lista)
    if codigo == "atende":
        assert v["titulo"] == "A Ana atende você" and v["regime_rotulo"]


def test_consulta_fora_do_ar_segue(receita):
    receita["dados"] = None
    assert atendimento.avaliar_cnpj("00000000000191")["codigo"] == "sem_consulta"


def test_so_financeiro_passa_menos_inativo(receita):
    receita["dados"] = _dados("1", "ATIVA", FORA)
    assert atendimento.avaliar_cnpj("00000000000191", so_financeiro=True)["pode_criar"] is True
    receita["dados"] = _dados("3", "INAPTA", DENTRO)
    assert atendimento.avaliar_cnpj("00000000000191", so_financeiro=True)["pode_criar"] is False


@pytest.fixture
def publico(db):
    db.commit = db.flush

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


CADASTRO = {"email": "nova@exemplo.com.br", "senha": "senha-boa-123", "whatsapp": "31999990000", "razao_social": "EMPRESA SINTETICA LTDA",
            "cod_municipio": DENTRO}



def test_cadastro_barrado_e_lista_de_espera(publico, receita, db):
    receita["dados"] = _dados("3", "ATIVA", FORA)
    r = publico.get("/api/atendimento", params={"cnpj": "11222333000181"})
    assert r.status_code == 200 and r.json()["codigo"] == "cidade_fora" and r.json()["cidade"] == "Brasília/DF"
    r = publico.post("/api/cadastro", json={**CADASTRO, "cpf_cnpj": "11222333000181"})
    assert r.status_code == 422 and "Emissor Nacional" in r.json()["detail"]

    r = publico.post("/api/lista-espera", json={"cnpj": "11222333000181", "email": " Nova@Exemplo.com.br ", "whatsapp": "(61) 99999-0000"})
    assert r.status_code == 200 and r.json()["motivo"] == "cidade_fora"
    reg = db.query(ListaEspera).filter_by(cnpj="11222333000181").one()
    assert (reg.email, reg.whatsapp, reg.cidade, reg.cod_municipio) == ("nova@exemplo.com.br", "61999990000", "Brasília/DF", FORA)
    # de novo: atualiza, não duplica
    publico.post("/api/lista-espera", json={"cnpj": "11222333000181", "email": "outro@exemplo.com.br"})
    assert db.query(ListaEspera).filter_by(cnpj="11222333000181").count() == 1

    resumo = lista_espera.resumo_gestao(db)
    assert any(c["cidade"] == "Brasília/DF" and c["pessoas"] >= 1 for c in resumo["por_cidade"])


def test_quem_e_atendido_nao_entra_na_lista(publico, receita):
    receita["dados"] = _dados("3", "ATIVA", DENTRO)
    r = publico.post("/api/lista-espera", json={"cnpj": "11222333000181", "email": "a@exemplo.com.br"})
    assert r.status_code == 409


def test_lista_espera_recusa_email_ruim(publico, receita):
    receita["dados"] = _dados("1")
    assert publico.post("/api/lista-espera", json={"cnpj": "11222333000181", "email": "sem-arroba"}).status_code == 422


def test_cadastro_com_regime_nao_atendido_e_barrado(publico, receita):
    receita["dados"] = _dados("1", "ATIVA", DENTRO)
    r = publico.post("/api/cadastro", json={**CADASTRO, "cpf_cnpj": "11222333000181"})
    assert r.status_code == 422 and "Ainda não atendemos" in r.json()["detail"]
    # só o Financeiro: passa
    r = publico.post("/api/cadastro", json={**CADASTRO, "cpf_cnpj": "11222333000181", "produto": "financeiro"})
    assert r.status_code == 200, r.text


def test_aviso_quando_a_cidade_entra(db, monkeypatch):
    enviados = []
    monkeypatch.setattr("app.services.email.get_email_sender", lambda: type("S", (), {"enviar": lambda self, **kw: enviados.append(kw)})())
    monkeypatch.setattr(db, "commit", db.flush)
    cnpj = "9" + uuid.uuid4().hex[:13].translate(str.maketrans("abcdef", "123456"))
    db.add(ListaEspera(id=uuid.uuid4(), email="espera@exemplo.com.br", cnpj=cnpj, cidade="Belo Horizonte/MG", cod_municipio=DENTRO, motivo="cidade_fora"))
    db.add(ListaEspera(id=uuid.uuid4(), email="espera2@exemplo.com.br", cnpj=cnpj, cidade="Brasília/DF", cod_municipio=FORA, motivo="regime"))
    db.flush()
    lista_espera.avisar_cidades_novas(db)
    meus = [e for e in enviados if e["destinatario"] == "espera@exemplo.com.br"]
    assert len(meus) == 1 and "Belo Horizonte/MG" in meus[0]["assunto"]
    assert not [e for e in enviados if e["destinatario"] == "espera2@exemplo.com.br"]
    lista_espera.avisar_cidades_novas(db)
    assert len([e for e in enviados if e["destinatario"] == "espera@exemplo.com.br"]) == 1


def test_gestao_marca_conta_fora_do_atendimento():
    assert atendimento.fora_do_atendimento(regime="1", cod_municipio=DENTRO, modulos=["emissor"]) == "regime"
    assert atendimento.fora_do_atendimento(regime="3", cod_municipio=FORA, modulos=["emissor"]) == "cidade_fora"
    assert atendimento.fora_do_atendimento(regime="2", cod_municipio=FORA, modulos=["emissor"]) is None
    assert atendimento.fora_do_atendimento(regime="1", cod_municipio=FORA, modulos=["financeiro"]) is None
