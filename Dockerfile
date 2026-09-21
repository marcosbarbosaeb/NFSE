# Estágio 1: build do frontend novo (React/Vite, Marco 12/13). Só gera
# arquivos estáticos (HTML/JS/CSS) — não sobe servidor Node nenhum em
# produção, o resultado é copiado pro estágio final e servido pelo próprio
# FastAPI (ver o catch-all no fim de backend/app/main.py).
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Estágio 2: imagem de produção do backend (painel + API). Builda a partir
# da raiz do repositório (não de backend/) porque também precisa do código
# de app/services/importacao_csv.py etc. que importa integracao/ em alguns
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
COPY --from=frontend-build /app/frontend/dist frontend/dist

WORKDIR /app/backend

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
