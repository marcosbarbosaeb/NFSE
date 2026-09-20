#!/bin/sh
# Roda a cada start do container: aplica migrações pendentes ANTES de subir
# o servidor (assim um deploy nunca serve com o schema desatualizado), e
# respeita $PORT (Railway/Render definem essa env var dinamicamente — não
# dá pra fixar 8000 sozinho).
set -e

echo "[entrypoint] Rodando migrações (alembic upgrade head)..."
python3 -m alembic upgrade head

echo "[entrypoint] Subindo o servidor na porta ${PORT:-8000}..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
