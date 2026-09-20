# Imagem de produção do backend (painel + API). Builda a partir da raiz do
# repositório (não de backend/) porque também precisa do código de
# app/services/importacao_csv.py etc. que importa integracao/ em alguns
# scripts administrativos (scripts/migrar_fornecedores.py) — ver
# docstring desses scripts pro racional completo.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY integracao/ integracao/

WORKDIR /app/backend

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
