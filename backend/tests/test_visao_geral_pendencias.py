"""Visão geral (05/10/2026):

- "Precisa da sua atenção" é só o que está pendente AGORA — o que está
  marcado pra um dia que ainda não chegou (ex.: revisar a alíquota no dia
  15) fica na agenda;
- "Próximos passos" junta as linhas repetidas ("Gerar 8 notas") pra caber
  num card curto, sem perder o caminho pra cada nota.
"""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import AjusteEvento, Certificado, Tomador
from app.services import calendario
from app.services.calendario import ajustar_ocorrencia, eventos_calendario
from app.services.dashboard import proximos, resumo_mes
from app.services.motor_emissao import criar_rascunho
from app.services.vinculos import criar_vinculo

HOJE = datetime.date(2026, 10, 5)


@pytest.fixture(autouse=True)
def _hoje_fixo(monkeypatch):
    """O lembrete de alíquota do calendário olha o relógio — trava no mesmo
    dia que os testes passam pro dashboard."""
    monkeypatch.setattr(calendario, "hoje_br", lambda: HOJE)


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


def _vinculo(db, prestador, apelido, dia=None):
    tomador = Tomador(id=uuid.uuid4(), cnpj=str(uuid.uuid4().int)[:14], razao_social=f"{apelido} LTDA", cod_municipio="3550308")
    db.add(tomador)
    db.flush()
    return criar_vinculo(
        db, prestador_id=prestador.id, tomador_id=tomador.id, apelido=apelido, cod_local_prestacao="3106200",
        cod_trib_nacional="170601", template_descricao="Comissão {competencia_mm_aaaa}", dia_limite_emissao=dia,
    )


def _tipos_atencao(db, prestador, hoje=HOJE):
    return [a["tipo"] for a in resumo_mes(db, prestador.id, hoje=hoje)["atencao"]]


def _aliquota_antiga(db, prestador):
    prestador.aliquota_atual = 6.0
    prestador.aliquota_atualizada_em = datetime.date(2026, 9, 3)
    db.flush()


# --- Alíquota: só depois do dia marcado ---------------------------------------


def test_aliquota_marcada_pra_depois_nao_entra_em_atencao(db, prestador_teste):
    """O caso do Marcos: a revisão está na agenda no dia 15 e hoje é dia 5."""
    _aliquota_antiga(db, prestador_teste)
    prestador_teste.dia_lembrete_aliquota = 15
    db.flush()

    assert _tipos_atencao(db, prestador_teste) == []
    # ...e continua na agenda, no dia 15.
    agenda = proximos(db, prestador_teste.id, HOJE)["agenda"]
    assert [(ev["data"], ev["tipo"]) for ev in agenda] == [(datetime.date(2026, 10, 15), "revisar_aliquota")]


def test_aliquota_entra_em_atencao_no_dia_marcado_e_depois(db, prestador_teste):
    _aliquota_antiga(db, prestador_teste)
    prestador_teste.dia_lembrete_aliquota = 15
    db.flush()

    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 14)) == []
    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 15)) == ["aliquota_pendente"]
    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 28)) == ["aliquota_pendente"]
    # Confirmou no mês: some.
    prestador_teste.aliquota_atualizada_em = datetime.date(2026, 10, 16)
    db.flush()
    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 28)) == []


def test_aliquota_sem_dia_configurado_vale_o_dia_1_do_calendario(db, prestador_teste):
    _aliquota_antiga(db, prestador_teste)
    assert prestador_teste.dia_lembrete_aliquota is None
    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 1)) == ["aliquota_pendente"]


def test_aliquota_movida_no_calendario_so_cobra_na_nova_data(db, prestador_teste):
    """Regra no dia 1, mas ESTA ocorrência foi arrastada pro dia 15."""
    _aliquota_antiga(db, prestador_teste)
    ajustar_ocorrencia(db, prestador_teste.id, tipo="revisar_aliquota", chave="2026-10", nova_data=datetime.date(2026, 10, 15))

    assert _tipos_atencao(db, prestador_teste) == []
    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 15)) == ["aliquota_pendente"]


def test_aliquota_adiantada_no_calendario_cobra_antes_do_dia_da_regra(db, prestador_teste):
    _aliquota_antiga(db, prestador_teste)
    prestador_teste.dia_lembrete_aliquota = 20
    ajustar_ocorrencia(db, prestador_teste.id, tipo="revisar_aliquota", chave="2026-10", nova_data=datetime.date(2026, 10, 3))

    assert _tipos_atencao(db, prestador_teste) == ["aliquota_pendente"]


def test_aliquota_ocultada_no_calendario_nao_cobra(db, prestador_teste):
    _aliquota_antiga(db, prestador_teste)
    ajustar_ocorrencia(db, prestador_teste.id, tipo="revisar_aliquota", chave="2026-10", oculto=True)

    assert _tipos_atencao(db, prestador_teste, datetime.date(2026, 10, 31)) == []


def test_ajuste_de_outro_mes_nao_vale_pra_este(db, prestador_teste):
    _aliquota_antiga(db, prestador_teste)
    ajustar_ocorrencia(db, prestador_teste.id, tipo="revisar_aliquota", chave="2026-09", oculto=True)

    assert _tipos_atencao(db, prestador_teste) == ["aliquota_pendente"]


@pytest.mark.parametrize("dia_regra,ajuste", [
    (None, None),
    (15, None),
    (3, None),
    (1, {"nova_data": datetime.date(2026, 10, 15)}),
    (20, {"nova_data": datetime.date(2026, 10, 2)}),
    (1, {"oculto": True}),
])
def test_atencao_e_calendario_concordam_sobre_a_aliquota(db, prestador_teste, dia_regra, ajuste):
    """A conta do dia é feita em dois lugares (calendário e dashboard):
    "está em atenção" tem que ser o mesmo que "o calendário tem o lembrete
    num dia que já chegou"."""
    _aliquota_antiga(db, prestador_teste)
    prestador_teste.dia_lembrete_aliquota = dia_regra
    db.flush()
    if ajuste:
        ajustar_ocorrencia(db, prestador_teste.id, tipo="revisar_aliquota", chave="2026-10", **ajuste)

    no_calendario = [
        ev for ev in eventos_calendario(db, prestador_teste.id, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31))
        if ev["tipo"] == "revisar_aliquota"
    ]
    ja_chegou = any(ev["data"] <= HOJE for ev in no_calendario)
    assert ("aliquota_pendente" in _tipos_atencao(db, prestador_teste)) is ja_chegou


# --- Os outros avisos do card ---------------------------------------------------


def _so_gerar(db, prestador, hoje):
    return [t for t in _tipos_atencao(db, prestador, hoje) if t.startswith("gerar")]


def test_dia_de_gerar_entra_em_atencao_na_vespera_no_dia_e_depois(db, prestador_teste):
    v = _vinculo(db, prestador_teste, "Aviso", dia=10)

    assert _so_gerar(db, prestador_teste, datetime.date(2026, 10, 8)) == []
    # Véspera: não é pendência, mas é um ponto de atenção que o Marcos pediu (05/10/2026).
    assert _so_gerar(db, prestador_teste, datetime.date(2026, 10, 9)) == ["gerar_amanha"]
    assert _so_gerar(db, prestador_teste, datetime.date(2026, 10, 10)) == ["gerar_hoje"]
    assert _so_gerar(db, prestador_teste, datetime.date(2026, 10, 20)) == ["gerar_atrasada"]
    criar_rascunho(db, v, competencia="2026-10", valor=10)
    assert _so_gerar(db, prestador_teste, datetime.date(2026, 10, 20)) == []


def test_nota_atrasada_ignorada_de_proposito_nao_cobra_em_atencao(db, prestador_teste):
    v = _vinculo(db, prestador_teste, "Atraso consciente", dia=2)
    assert _so_gerar(db, prestador_teste, HOJE) == ["gerar_atrasada"]

    db.add(AjusteEvento(id=uuid.uuid4(), prestador_id=prestador_teste.id, tipo="pendencia", chave=f"gerar:{v.id}:2026-10", oculto=True))
    db.flush()
    assert _so_gerar(db, prestador_teste, HOJE) == []


def test_certificado_vencendo_e_vencido_continuam_em_atencao(db, prestador_teste):
    prestador_teste.aliquota_atualizada_em = HOJE
    cert = Certificado(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, pfx_criptografado=b"x", senha_criptografada=b"y",
        validade=HOJE + datetime.timedelta(days=5),
    )
    db.add(cert)
    db.flush()
    assert _tipos_atencao(db, prestador_teste) == ["certificado_vencendo"]

    cert.validade = HOJE - datetime.timedelta(days=2)
    db.flush()
    assert _tipos_atencao(db, prestador_teste) == ["certificado_vencido"]


# --- Próximos passos: linhas repetidas viram uma só -----------------------------


def test_notas_a_gerar_no_mesmo_dia_viram_uma_linha_com_os_itens(db, prestador_teste):
    prestador_teste.aliquota_atualizada_em = HOJE
    do_dia_15 = [_vinculo(db, prestador_teste, f"Cliente {i}", dia=15) for i in range(8)]
    _vinculo(db, prestador_teste, "Outro dia", dia=20)
    _vinculo(db, prestador_teste, "Sem dia")

    dados = proximos(db, prestador_teste.id, HOJE)
    gerar = [p for p in dados["pendencias"] if p["tipo"] == "gerar"]
    assert [p["titulo"] for p in gerar] == ["Gerar 8 notas", "Gerar a nota de Outro dia", "Gerar a nota de Sem dia"]
    assert dados["total_pendencias"] == 3

    grupo = gerar[0]
    assert grupo["data"] == datetime.date(2026, 10, 15) and grupo["atrasada"] is False
    # Cada nota continua alcançável: link pra gerar e chave pra ignorar.
    assert {p["vinculo_id"] for p in grupo["itens"]} == {v.id for v in do_dia_15}
    assert all(p["link"].startswith("/app/nfse?gerar=") and p["chave"] for p in grupo["itens"])
    assert [p["titulo"] for p in grupo["itens"]] == sorted(p["titulo"] for p in grupo["itens"])


def test_ate_duas_notas_no_mesmo_dia_ficam_em_linhas_separadas(db, prestador_teste):
    for nome in ("A", "B"):
        _vinculo(db, prestador_teste, nome, dia=15)

    gerar = [p for p in proximos(db, prestador_teste.id, HOJE)["pendencias"] if p["tipo"] == "gerar"]
    assert [p["titulo"] for p in gerar] == ["Gerar a nota de A", "Gerar a nota de B"]
    assert all(not p.get("itens") for p in gerar)


def test_grupo_de_notas_atrasadas_vem_marcado_e_respeita_o_ignorar(db, prestador_teste):
    vinculos = [_vinculo(db, prestador_teste, f"Atrasado {i}", dia=2) for i in range(4)]
    db.add(AjusteEvento(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tipo="pendencia", chave=f"gerar:{vinculos[0].id}:2026-10", oculto=True,
    ))
    db.flush()

    gerar = [p for p in proximos(db, prestador_teste.id, HOJE)["pendencias"] if p["tipo"] == "gerar"]
    assert len(gerar) == 1 and gerar[0]["titulo"] == "Gerar 3 notas" and gerar[0]["atrasada"] is True
    assert vinculos[0].id not in {p["vinculo_id"] for p in gerar[0]["itens"]}


def test_agenda_junta_os_dias_de_gerar_do_mes_que_vem(db, prestador_teste):
    """As notas de outubro já saíram; na agenda sobra o dia 2 de novembro de
    cada tomador — quatro avisos iguais viram uma linha."""
    prestador_teste.aliquota_atualizada_em = HOJE
    for i in range(4):
        v = _vinculo(db, prestador_teste, f"Mensal {i}", dia=2)
        criar_rascunho(db, v, competencia="2026-10", valor=10)

    dados = proximos(db, prestador_teste.id, HOJE)
    assert [(ev["data"], ev["titulo"], ev["quantidade"]) for ev in dados["agenda"]] == [
        (datetime.date(2026, 11, 2), "Dia de gerar 4 notas", 4),
    ]
    assert dados["total_agenda"] == 1


def test_endpoint_proximos_devolve_o_grupo_com_os_itens(client, db, prestador_teste):
    for i in range(3):
        _vinculo(db, prestador_teste, f"Api {i}", dia=28)

    resp = client.get("/api/painel/proximos")
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert "total_agenda" in dados
    grupos = [p for p in dados["pendencias"] if p.get("itens")]
    # (no dia 29+ de um mês o teste cai no mesmo grupo, só que atrasado)
    assert len(grupos) == 1 and grupos[0]["titulo"] == "Gerar 3 notas"
    assert len(grupos[0]["itens"]) == 3 and all(i["vinculo_id"] and i["chave"] for i in grupos[0]["itens"])
