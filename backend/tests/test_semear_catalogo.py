"""Catálogo pré-cadastrado num banco novo (08/10/2026: ambiente de teste com
o catálogo vazio)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import semear_catalogo  # noqa: E402

from app.models import Tomador  # noqa: E402


def test_arquivo_do_catalogo_so_tem_dado_publico_e_valido():
    lista = semear_catalogo.carregar()
    for t in lista:
        assert len(t["cnpj"]) == 14 and t["cnpj"].isdigit()
        assert t["razao_social"] and len(t["cod_municipio"]) == 7
    assert len({t["cnpj"] for t in lista}) == len(lista)
    bruto = json.loads(semear_catalogo.ARQUIVO.read_text(encoding="utf-8")) if semear_catalogo.ARQUIVO.exists() else []
    for t in bruto:
        assert set(t) <= set(semear_catalogo.CAMPOS), "só campos do catálogo (nada de vínculo, valor ou destinatário)"


def test_cria_so_o_que_falta_e_pode_rodar_de_novo(db, tmp_path, monkeypatch):
    arq = tmp_path / "catalogo.json"
    arq.write_text(json.dumps([
        {"cnpj": "99000000000191", "razao_social": "CATALOGO TESTE A LTDA", "cod_municipio": "3550308", "sug_cod_trib_nacional": "170601"},
        {"cnpj": "99000000000272", "razao_social": "CATALOGO TESTE B LTDA", "cod_municipio": "3106200"},
    ]), encoding="utf-8")
    monkeypatch.setattr(semear_catalogo, "ARQUIVO", arq)
    db.add(Tomador(cnpj="99000000000272", razao_social="JÁ EXISTIA", cod_municipio="3106200", status="aprovado"))
    db.flush()
    monkeypatch.setattr(db, "commit", db.flush)

    assert semear_catalogo.semear(db) == 1
    a = db.query(Tomador).filter_by(cnpj="99000000000191").one()
    assert a.status == "aprovado" and a.sug_cod_trib_nacional == "170601"
    assert db.query(Tomador).filter_by(cnpj="99000000000272").one().razao_social == "JÁ EXISTIA"
    assert semear_catalogo.semear(db) == 0
