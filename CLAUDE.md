# Agente Ana — guia rápido pra quem (ou qual IA) for mexer aqui

Emissor de NFS-e (Emissor Nacional) + controle financeiro, vendidos como módulos separados.
App: notas.agenteana.com.br · site: agenteana.com.br · deploy: Railway (push na `main` = produção).

## Estrutura
- `backend/` FastAPI + SQLAlchemy + Postgres. Rotas do emissor em `app/main.py`, serviços em `app/services/`,
  XML fiscal em `app/fiscal/`. Financeiro é um módulo à parte em `app/financeiro/` (rotas próprias) e fala com o
  emissor só por `app/eventos.py` / `app/financeiro/integracao.py` — há testes de regra de import em `tests/test_modulos.py`.
- `frontend/` React 19 + Vite + Tailwind v4. Tipos em `src/lib/types.ts`.
- Migrações Alembic em `backend/alembic/versions/` (uma cabeça só; confira com `alembic heads`).

## Regras que já custaram caro
- **RLS**: todas as tabelas de dados têm FORCE ROW LEVEL SECURITY por `app.current_prestador_id` (vale só na transação).
  Depois de `db.commit()` o contexto some: **monte a resposta ANTES do commit**. UPDATE de dados em migração não enxerga linhas.
- Tabelas sem RLS de propósito: `tomador` (catálogo compartilhado), `usuario`, `usuario_prestador`, `sessao`, `lote_fila`.
- A Sefin compara `dhEmi` sem converter fuso: emitir em America/Sao_Paulo menos 2 min.
- O PDF (DANFSe) é gerado aqui (`app/services/danfse.py`); a API do governo foi suspensa.
- Lotes em segundo plano: thread no próprio processo (`app/services/lotes.py`), retomados no startup pela `lote_fila`.
- Nunca commitar: `backend/.db_url_tmp`, `backend/producao.env.txt`, relatórios/planilhas/PDFs reais. Testes só com dados sintéticos.
- Segredos (Stripe, Resend, Google) só nas variáveis do Railway — nunca no código nem em conversa.

## Como rodar
```
service postgresql start            # o banco local às vezes para
cd backend && alembic upgrade head && timeout 300 python3 -m pytest -q tests/
cd frontend && npx tsc -b && npm run build
cd backend && uvicorn app.main:app --port 8765   # serve a API e o frontend buildado
```

## Jeito da casa
- Texto de tela em português simples, pra leigo; a Ana fala em primeira pessoa ("eu preencho...").
- Valor em dinheiro: `components/ui/CampoMoeda`. Select com muitas opções: `components/ui/CaixaBusca`.
- Dark mode (`dark:`) e celular em toda tela nova.
- Lista de municípios que usam o Emissor Nacional: `backend/app/data/emissor_nacional.json`
  (atualize com `backend/scripts/atualizar_emissor_nacional.py` e a planilha da Receita).
