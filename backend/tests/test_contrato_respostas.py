"""Contrato das respostas (08/10/2026): "antes de subir uma atualização faça
sempre um check para evitar isso".

O que aconteceu: o resumo do mês ganhou campos novos (assinadas, autorizadas...)
mas a rota filtra a resposta por um schema (`response_model`) que não tinha
esses campos — o FastAPI descartou em silêncio, os testes do serviço passaram e
a tela no real ficou sem os números.

Este teste chama as rotas de leitura que passam por `response_model` com uma
empresa de dados sintéticos e falha se QUALQUER campo que o serviço montou for
descartado pelo schema. Campo novo no serviço = campo novo no schema (ou entra
em DESCARTE_INTENCIONAL, com o motivo).
"""
import datetime
import json
import uuid
from decimal import Decimal

import fastapi.routing
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Emissao, EventoManual

# Campos que o serviço monta mas a resposta não deve levar, de propósito: (rota, campo) -> motivo.
DESCARTE_INTENCIONAL: dict[tuple[str, str], str] = {}


def _chaves(valor, caminho=""):
    """Todos os caminhos de chave de dicts aninhados (listas viram [])."""
    saida = set()
    if isinstance(valor, dict):
        for k, v in valor.items():
            atual = f"{caminho}.{k}" if caminho else str(k)
            saida.add(atual)
            saida |= _chaves(v, atual)
    elif isinstance(valor, (list, tuple)):
        for item in valor:
            saida |= _chaves(item, f"{caminho}[]")
    return saida


@pytest.fixture
def descartados(monkeypatch):
    achados: list[tuple[str, str]] = []
    original = fastapi.routing.serialize_response

    async def espiao(*args, **kwargs):
        resultado = await original(*args, **kwargs)
        conteudo = kwargs.get("response_content")
        espiao.chamadas += 1
        # o FastAPI pode devolver o JSON já em bytes (caminho rápido)
        saida = json.loads(resultado) if isinstance(resultado, (bytes, bytearray)) else resultado
        if kwargs.get("field") is not None and isinstance(conteudo, (dict, list)) and isinstance(saida, (dict, list)):
            for chave in sorted(_chaves(conteudo) - _chaves(saida)):
                achados.append((espiao.rota, chave))
        return resultado

    espiao.rota = ""
    espiao.chamadas = 0
    monkeypatch.setattr(fastapi.routing, "serialize_response", espiao)
    return achados, espiao


def test_nenhum_campo_do_servico_some_na_resposta(db, prestador_teste, vinculo_teste, descartados):
    achados, espiao = descartados
    hoje = datetime.date.today()
    comp = f"{hoje.year:04d}-{hoje.month:02d}"
    # Uma empresa com um pouco de tudo: nota do tomador, notas de vendedores, evento na agenda.
    nota = Emissao(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, prestador_tomador_id=vinculo_teste.id, competencia=comp,
        serie="5", n_dps=501, estado="montado", valor=Decimal("150.00"), origem="ana",
        tomador_snapshot={"razao_social": "TOMADOR DE TESTE LTDA", "cnpj": "11222333000181", "codigo_servico_usado": {}},
    )
    db.add(nota)
    for n, estado in enumerate(["confirmado", "assinado", "erro"]):
        db.add(Emissao(
            id=uuid.uuid4(), prestador_id=prestador_teste.id, prestador_tomador_id=vinculo_teste.id, competencia=comp,
            serie="5", n_dps=600 + n, estado=estado, valor=Decimal("10.00"), origem="ana",
            tomador_documento=f"0000000000{n}", tomador_snapshot={"razao_social": f"Vendedor {n}"},
        ))
    db.add(EventoManual(id=uuid.uuid4(), prestador_id=prestador_teste.id, data=hoje, titulo="Lembrete sintético", categoria="lembrete"))
    db.flush()

    db.commit = db.flush
    app.dependency_overrides[get_db] = lambda: (yield db)
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    rotas = [
        f"/api/painel/resumo-mes?competencia={comp}",
        "/api/painel/proximos",
        "/api/vinculos?todos=true",
        f"/api/vinculos/{vinculo_teste.id}",
        f"/api/calendario?inicio={hoje.replace(day=1)}&fim={hoje.replace(day=28)}",
        "/api/prestador",
        f"/api/dps?ano={hoje.year}",
        f"/api/dps/{nota.id}",
        f"/api/dps/{nota.id}/nota",
        "/api/lotes",
        f"/api/envios/resumo?ano={hoje.year}",
    ]
    cliente = TestClient(app)
    try:
        for rota in rotas:
            espiao.rota = rota.split("?")[0]
            r = cliente.get(rota)
            assert r.status_code == 200, (rota, r.text[:300])
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(prestador_atual_id, None)

    assert espiao.chamadas > 0, "o espião não viu nenhuma resposta: o FastAPI mudou a forma de serializar"
    perdidos = [(rota, campo) for rota, campo in achados if (rota, campo.split(".")[-1].rstrip("[]")) not in DESCARTE_INTENCIONAL]
    assert not perdidos, (
        "Campos que o serviço monta e a resposta descarta (falta no schema de resposta em app/schemas.py): "
        + "; ".join(f"{r} → {c}" for r, c in perdidos)
    )
