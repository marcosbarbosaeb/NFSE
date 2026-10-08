"""Garante os tomadores pré-cadastrados no catálogo (08/10/2026).

No ambiente de teste o catálogo vinha vazio (busca "Shopee": nada
encontrado), embora a tela inicial diga que os mais comuns já vêm
pré-cadastrados: o banco de teste é separado e o catálogo de produção foi
sendo formado pelo uso. Este script roda no start do container (entrypoint.sh)
e cria, SÓ se o CNPJ ainda não estiver no catálogo, os tomadores de
app/data/catalogo_inicial.json. Em produção eles já existem: não muda nada.

Só dado público de empresa (CNPJ, razão social, endereço) e o modelo de
preenchimento já limpo de dado pessoal (`sug_*`, ver app/services/sugestoes.py).
Nunca vínculos, valores ou destinatários.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ARQUIVO = Path(__file__).resolve().parents[1] / "app" / "data" / "catalogo_inicial.json"
CAMPOS = (
    "cnpj", "razao_social", "cod_municipio", "cep", "logradouro", "numero", "complemento", "bairro",
    "sug_cod_trib_nacional", "sug_template_descricao", "sug_dia_emissao", "sug_dias_recebimento",
    "sug_cod_trib_municipal", "sug_cod_nbs", "sug_meses_atras", "sug_envio_formas", "sug_email_assunto",
    "sug_email_mensagem", "sug_email_anexos",
)


def carregar() -> list[dict]:
    if not ARQUIVO.exists():
        return []
    return [{k: t.get(k) for k in CAMPOS} for t in json.loads(ARQUIVO.read_text(encoding="utf-8"))]


def semear(db) -> int:
    from app.models import Tomador

    lista = [t for t in carregar() if t.get("cnpj") and t.get("razao_social") and t.get("cod_municipio")]
    if not lista:
        return 0
    existentes = {c for (c,) in db.query(Tomador.cnpj).filter(Tomador.cnpj.in_([t["cnpj"] for t in lista]))}
    novos = [Tomador(status="aprovado", **t) for t in lista if t["cnpj"] not in existentes]
    db.add_all(novos)
    db.commit()
    return len(novos)


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL", "").strip():
        sys.exit(0)
    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            n = semear(db)
        print(f"[catalogo] {n} tomador(es) pré-cadastrado(s) incluído(s)" if n else "[catalogo] catálogo já estava completo")
    except Exception as exc:  # nunca impede o servidor de subir
        print(f"[catalogo] não deu pra conferir o catálogo: {exc}")
