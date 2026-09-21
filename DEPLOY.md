# Como colocar isso no ar

## Status atual

Já está no ar: projeto `nfse-saas` no Railway, service `app` (build a
partir do `Dockerfile` deste repo, conectado ao GitHub
`marcosbarbosaeb/NFSE`, branch `main`) + service `Postgres`. `DATABASE_URL`,
`CERT_MASTER_KEY` e `SESSION_SECRET_KEY` já estão configurados nas
Variables do service `app`. A partir daqui, **atualizar o que está no ar é
só dar `git push` pra `main`** — o Railway builda e reimplanta sozinho
(deploy a cada push), e o `entrypoint.sh` roda `alembic upgrade head` a
cada start, então o schema do banco de produção fica em dia sozinho
também. O resto deste documento (passos 1–3 abaixo) é o roteiro original
de como esse setup foi feito, útil se precisar refazer do zero num
projeto/conta novos — não precisa repetir pra atualizar o que já existe.

Desde o Marco 12, o `Dockerfile` builda o frontend novo (React/Vite, em
`frontend/`) num estágio separado (Node) e copia o resultado estático pra
dentro da imagem final — o FastAPI serve esse build em `/` (ver o
catch-all no fim de `backend/app/main.py`). Não tem servidor Node nenhum
rodando em produção.

Este projeto até agora só rodou dentro do sandbox onde foi construído — nada
está hospedado em lugar nenhum que dê pra abrir num navegador de fora. Este
documento é o passo a passo pra isso mudar.

## Visão geral

1. Colocar este código num repositório Git de verdade (GitHub), pra não
   depender do sandbox continuar existindo.
2. Hospedar num serviço (Railway, ou equivalente) que builda a partir do
   `Dockerfile` deste repositório e te dá um Postgres gerenciado.
3. Provisionar o banco (schema + role de runtime + os 5 fornecedores da
   Raiana + o primeiro login).

## 1. Repositório Git

O repositório já está inicializado localmente (`git log` mostra o
histórico de commits deste projeto). Falta só um remoto:

```
git remote add origin <url-do-seu-repositorio-no-github>
git push -u origin master
```

Se você ainda não tem o repositório criado no GitHub, crie um vazio (sem
README/gitignore — este projeto já tem os dois) e use a URL que ele te dá.

## 2. Hospedagem (Railway)

O `Dockerfile` na raiz do repositório builda o backend inteiro. Qualquer
serviço que aceite "deploy a partir de um Dockerfile num repositório Git"
funciona — o roteiro abaixo é pro Railway especificamente:

1. **Novo projeto no Railway** → "Deploy from GitHub repo" → aponte pro
   repositório que você acabou de criar.
2. **Adicione um Postgres**: dentro do mesmo projeto, "+ New" → "Database"
   → "PostgreSQL". O Railway te dá uma `DATABASE_URL` de administrador
   automaticamente (fica disponível como variável no serviço do Postgres).
3. **Rode `backend/scripts/provisionar_banco.sql`** contra esse Postgres,
   conectado como o administrador que o Railway deu (o botão "Connect" do
   serviço Postgres no painel do Railway te dá um jeito de abrir um
   `psql` direto, ou copie a `DATABASE_URL` e rode local:
   `psql "$DATABASE_URL_DO_RAILWAY" -f backend/scripts/provisionar_banco.sql`
   — troque a senha no arquivo antes). Isso cria o role `nfse_app`, que é
   quem a aplicação usa no dia a dia (ver o comentário no topo do arquivo
   pro porquê disso importar: sem isso, a proteção de RLS entre
   fornecedores fica sem efeito).
4. **Configure as variáveis de ambiente do serviço do backend** (não do
   Postgres): vá nas "Variables" do serviço web e defina:
   - `DATABASE_URL` = a connection string com o role `nfse_app` (não a do
     administrador) que você acabou de criar no passo 3.
   - `CERT_MASTER_KEY` = gere com
     `python3 -c "from app.crypto import gerar_chave_local; print(gerar_chave_local())"`
   - `SESSION_SECRET_KEY` = gere com
     `python3 -c "import secrets; print(secrets.token_hex(32))"`

   (Essas duas últimas NÃO podem ser os valores default que estão no
   código — aqueles são só pra rodar local nesta sessão de
   desenvolvimento.)
5. **Deploy**. O Railway builda a imagem e sobe o container; o
   `entrypoint.sh` roda as migrações do Alembic automaticamente a cada
   start, então o schema fica sempre em dia sozinho.
6. **Seed inicial** (uma vez só): rode, apontando pra `DATABASE_URL` do
   ADMINISTRADOR do Railway (não a do `nfse_app`):
   ```
   python3 backend/scripts/migrar_fornecedores.py --database-url "<database-url-admin-do-railway>"
   python3 backend/scripts/criar_usuario.py --email <email-da-raiana> --database-url "<database-url-admin-do-railway>"
   ```
   Dá pra rodar isso da sua própria máquina (não precisa ser de dentro do
   Railway) — só precisa da `DATABASE_URL` alcançável de fora, que o
   Railway te dá.

Depois disso, a URL pública que o Railway gerar pro serviço já é o painel
— abrir ela no navegador mostra a tela de login.

### Alternativa: Render

O mesmo `Dockerfile` funciona no Render (ou em qualquer PaaS baseado em
Docker) — a diferença é só na interface: "New Web Service" → conectar o
repositório → ele detecta o Dockerfile sozinho. O Postgres é um "New
PostgreSQL" separado, com a mesma lógica do passo 2 acima.

## 3. Rodando local com Docker (opcional, pra testar antes)

```
cp backend/.env.example backend/.env   # preencha CERT_MASTER_KEY e SESSION_SECRET_KEY
docker compose up --build
```

Na primeira vez, rode o seed (numa segunda janela de terminal):
```
docker compose exec app python3 scripts/migrar_fornecedores.py --database-url postgresql://postgres:postgres_local@db:5432/nfse_saas
docker compose exec app python3 scripts/criar_usuario.py --email voce@exemplo.com --database-url postgresql://postgres:postgres_local@db:5432/nfse_saas
```

O painel fica em `http://localhost:8000`.

## O que ainda não muda com o deploy

- **Submissão real à Sefin** continua não testada por este sistema — o
  sandbox onde ele foi construído nunca teve rede liberada pra gov.br.
  Hospedar em qualquer lugar com internet normal (Railway inclui) É o que
  falta pra validar isso, mas isso ainda vai exigir ligar
  `motor_emissao.submeter`/`cancelar` ao painel (hoje só têm teste com
  mock) — não é automático só por estar no ar.
- **E-mail/WhatsApp automáticos** (Marco 9) continuam manuais — hospedar
  não muda isso sozinho, precisaria integrar com um provedor de verdade
  (SMTP, API do WhatsApp Business).
