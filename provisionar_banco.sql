-- Rode isto UMA VEZ contra um Postgres NOVO (ex.: o addon do Railway),
-- conectado como o usuário administrador que o provedor te deu — ANTES de
-- rodar as migrações do Alembic. Troque a senha abaixo antes de rodar.
--
-- Por quê isto existe: as tabelas de negócio (emissao, certificado, ...)
-- usam FORCE ROW LEVEL SECURITY (ver alembic/versions/*_rls.py) — isso
-- ainda restringe o DONO da tabela, MAS NÃO um superusuário do Postgres,
-- que sempre ignora RLS (é assim que o Postgres funciona, não dá pra
-- forçar contra superusuário). Rodar a aplicação com o usuário
-- administrador do provedor (que normalmente É superusuário) desligaria a
-- proteção de RLS inteira, silenciosamente. Este script cria um role
-- separado, SEM privilégio de superusuário, que passa a ser o dono do
-- banco — é ele que vai na DATABASE_URL da aplicação no dia a dia. O
-- usuário administrador do provedor fica reservado só pra tarefas manuais
-- (scripts/migrar_fornecedores.py, scripts/criar_usuario.py), exatamente
-- como já funciona em desenvolvimento local (role `postgres` vs
-- `nfse_dev` — ver docstring desses scripts).
--
-- Uso:
--   1. Troque 'troque-a-senha' abaixo por uma senha forte de verdade.
--   2. Troque 'nfse_saas' pelo nome do banco que o provedor criou, se for
--      diferente.
--   3. Rode este arquivo conectado como o admin do provedor, ex.:
--        psql "$DATABASE_URL_DO_PROVEDOR" -f scripts/provisionar_banco.sql
--   4. Monte a DATABASE_URL da aplicação com esse novo role+senha e use
--      ela (não a do admin) nas variáveis de ambiente do deploy.

CREATE ROLE nfse_app WITH LOGIN PASSWORD 'troque-a-senha';
ALTER DATABASE nfse_saas OWNER TO nfse_app;
GRANT ALL PRIVILEGES ON DATABASE nfse_saas TO nfse_app;
