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
- E-mail (Resend) tem cota: 429 de cota vira `EmailCotaEsgotadaError` — o lote fica "aguardando" e volta sozinho
  (`lotes.iniciar_relogio`), nunca conta como falha. Vendedor sem e-mail também não é falha: vira aviso.
- Lote de e-mail nunca reenvia nota já entregue por QUALQUER canal (`lotes.CANAIS_ENTREGA`) sem `reenviar=True`.
- Google Drive: escopo `drive.file`, callback `/api/drive/callback`, token cifrado no prestador (`app/services/drive.py`).
- Catálogo de tomadores (`tomador.sug_*`) é compartilhado entre contas: texto livre só entra depois de
  `app/services/sugestoes.limpar_texto` (tira conta bancária, CNPJ, pedido, ID de afiliado, @). Nunca destinatários.
- Sem certificado A1 válido não se gera nota: dependência `exigir_certificado` nas rotas de geração
  (`app/services/prontidao.py`). O conftest desliga a trava; `tests/test_prontidao.py` liga de volta.
- Importar do Emissor Nacional é opt-in: só tomador que a pessoa já tem ou pré-cadastrado vem marcado.
- Parceiras de indicação (`app/services/parceiros.py`): comissão = % de cada fatura paga (`invoice.paid` do Stripe),
  sem login (painel por link secreto `/parceira/<token>`), repasse por fora. Administração = `ADMIN_EMAILS`
  (ou, sem a variável, a conta "cortesia").
- Gestão (`/app/gestao`, `app/services/gestao.py`): números de uso de TODAS as contas, só pra quem está em
  `ADMIN_EMAILS` (sem a variável ninguém entra). Passa empresa por empresa trocando o contexto da RLS e devolve o
  contexto no fim. Nunca expor conteúdo de nota/financeiro ali. O guia da ajuda (`app/data/guia-agente-ana.md`)
  não é público: só a Gestão baixa.
- Ambiente de teste da plataforma: `AMBIENTE_TESTE=true` no serviço de teste. Toda conta vira conta de teste,
  só sai nota de homologação (trava final em `motor_emissao.submeter`) e e-mail de nota vai só pro login de quem testa.
- Contador (`app/services/acesso.py`, `app/contador.py`): o dono convida por e-mail e marca permissões; o contador fica em
  `acesso_contador` — NUNCA em `usuario_prestador` (lá é dono: apagar empresa/conta contam com isso). A trava mora em
  `deps.prestador_atual_id` → `acesso.conferir`. **Rota nova que muda algo tem que entrar em `acesso.REGRAS`**
  (permissão, LIVRE ou NUNCA); sem regra ela é recusada pro contador e `tests/test_contador.py` acusa.
  Empresa de cliente nunca vira `usuario.prestador_id` (fica só na sessão).
- Bloqueio sem assinatura: `BLOQUEIO_ATIVO=true` deixa a empresa com teste vencido/cancelada só pra consulta (402 em
  tudo que muda, menos assinar/apagar). Desligado em produção até o Stripe estar recebendo. A Gestão libera na mão
  (`assinatura.liberado_ate/liberado_sempre`); a regra única é `billing.situacao_do_acesso`.
- Fluxo de publicação: tudo vai primeiro pra branch `teste` (ambiente `teste` do Railway, app-teste.up.railway.app);
  só depois de conferido lá entra na `main`.
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
