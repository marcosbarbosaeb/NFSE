"""Prepara o banco de um ambiente NOVO (ex.: o ambiente "teste" no Railway).

Roda no start do container, antes das migrações, SÓ quando existe a variável
DATABASE_ADMIN_URL (a URL do administrador do Postgres daquele ambiente —
no Railway, a referência ${{Postgres.DATABASE_URL}}). Em produção essa
variável não existe e este script não faz nada.

O que faz (o mesmo que scripts/provisionar_banco.sql, sem ninguém precisar
rodar SQL na mão nem copiar senha): cria, se ainda não existir, o usuário
sem superpoderes que está na DATABASE_URL da aplicação — é ele que mantém a
proteção por empresa (RLS) valendo — e o banco dele. Pode rodar quantas
vezes for: se já está pronto, não muda nada.
"""
import os
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def provisionar(admin_url: str, app_url: str) -> str:
    app = make_url(app_url)
    admin = make_url(admin_url)
    usuario, senha, banco = app.username, app.password, app.database
    if not usuario or not senha or not banco:
        return "DATABASE_URL sem usuário, senha ou banco: nada a fazer."
    if usuario == admin.username:
        return "A aplicação usa o próprio administrador do banco: nada a criar."
    conexao = psycopg.connect(
        host=admin.host, port=admin.port or 5432, user=admin.username, password=admin.password,
        dbname=admin.database or "postgres", autocommit=True,
    )
    feito = []
    try:
        with conexao.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (usuario,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(usuario), sql.Literal(senha)))
                feito.append(f"usuário {usuario} criado")
            else:
                # mesmo usuário, senha da DATABASE_URL deste ambiente
                cur.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(usuario), sql.Literal(senha)))
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (banco,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(banco), sql.Identifier(usuario)))
                feito.append(f"banco {banco} criado")
            else:
                cur.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(banco), sql.Identifier(usuario)))
            cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(sql.Identifier(banco), sql.Identifier(usuario)))
    finally:
        conexao.close()
    return "; ".join(feito) or "banco já estava pronto"


if __name__ == "__main__":
    admin_url = os.environ.get("DATABASE_ADMIN_URL", "").strip()
    if not admin_url:
        sys.exit(0)
    # Lê direto do ambiente: rodando como `python3 scripts/...` o pacote `app`
    # não está no caminho de importação.
    app_url = os.environ.get("DATABASE_URL", "").strip()
    if not app_url:
        sys.exit("[provisionar] DATABASE_URL não definida.")
    print("[provisionar] " + provisionar(admin_url, app_url))
