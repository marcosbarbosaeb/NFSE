#!/bin/sh
# Roda a cada start do container: aplica migrações pendentes ANTES de subir
# o servidor (assim um deploy nunca serve com o schema desatualizado), e
# respeita $PORT (Railway/Render definem essa env var dinamicamente — não
# dá pra fixar 8000 sozinho).
set -e

# Ambiente novo (ex.: "teste"): com DATABASE_ADMIN_URL definida, cria o usuário e
# o banco da aplicação se ainda não existirem. Em produção a variável não existe.
if [ -n "$DATABASE_ADMIN_URL" ]; then
  python3 scripts/provisionar_ambiente.py
fi

echo "[entrypoint] Rodando migrações (alembic upgrade head)..."
python3 -m alembic upgrade head

echo "[entrypoint] Subindo o servidor na porta ${PORT:-8000}..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
