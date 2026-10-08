# Registro técnico de versões — Agente Ana

O que mudou em cada versão, pra quem mexe no sistema. O texto pro usuário (tela **Novidades**) fica em
`backend/app/novidades.py`; um teste confere que toda versão de lá está aqui.

## Rotina de publicação

1. Tudo entra primeiro na branch `teste` → ambiente de teste (app-teste.up.railway.app).
2. O Marcos confere lá. O rodapé do menu mostra a versão e o ambiente; `GET /api/versao` responde o mesmo.
3. Com o "pode subir", a `main` recebe exatamente o que está na `teste` (fast-forward; nada vai direto pra `main`).
4. Push pelo GitHub Desktop. O Railway nem sempre publica sozinho: disparar com a variável `DEPLOY_REF=<commit>` no serviço `app` do ambiente.
5. Conferir no real: `GET /api/versao`, as telas alteradas e o item "Conferir depois de publicar" da versão.

Numeração: `ano.mês.sequência`. Versão nova = bloco novo no topo de `novidades.VERSOES` + seção aqui.

Antes de publicar no real, sempre: testes passando (`pytest`), `tsc` e build do frontend, telas conferidas no teste,
migração e variáveis novas anotadas abaixo.

## 2026.10.3 — 08/10/2026

**Situação:** no ambiente de teste. Ainda não está no real.

Pro usuário (ver Novidades): painel do contador refeito (Hoje, Fechamento do mês, Empresas e a ficha de cada empresa), símbolo
"A" no lugar da ilustração, WhatsApp obrigatório no cadastro, pedido de liberação depois do teste, marca do menu leva ao começo.

Gestão (só administração):
- **Autorização depois do teste (fase sem cobrança):** enquanto `STRIPE_SECRET_KEY` não existe, a empresa com teste vencido vê
  "peça a liberação" em vez de "assine". `POST /api/assinatura/pedir-liberacao` anota `assinatura.liberacao_pedida_em` e manda
  e-mail pra `ADMIN_EMAILS` (uma vez). Filtros novos em Contas: "Aguardando sua autorização" e "Pediram liberação". Liberar ou
  bloquear limpa o pedido.
- **Isso só trava no real quando `BLOQUEIO_ATIVO=true` for ligado lá** (decisão do Marcos; antes, liberar na Gestão quem deve continuar).
- Sem cobrança no ar o limite de notas dos planos não vale nem avisa (`billing.cobranca_ativa`, `planos.uso`).
- Telefone da lista de contas = WhatsApp do cadastro (`usuario.telefone`); sem ele, o da empresa, marcado "da empresa".

Técnico:
- Migração `a7d9f1b3c5e6` (`usuario.telefone`, `assinatura.liberacao_pedida_em`).
- `POST /api/cadastro` e `/api/cadastro/contador` exigem `whatsapp` (10–11 dígitos com DDD; aceita +55). `PATCH /api/conta` aceita `telefone`.
- `raio_x.da_empresa`: `serie` (13 meses), `municipio`, `inscricao_municipal`, `aliquota`, `fechamentos` (3 meses, do financeiro);
  `acesso.do_contador` devolve `dono` (nome, e-mail, WhatsApp de quem cuida da empresa).
- Frontend: `components/contador/PainelContador.tsx` (fila, quadro, carteira) e `FichaDaEmpresa.tsx`; aba e empresa ficam na URL
  (`/app/atendimentos?aba=fechamento`, `?empresa=<id>`).
- `frontend/public/ana.webp` removido; `ana-email.png` redesenhado (o "A"). `AnaAvatar` agora desenha o símbolo.
- Variáveis novas: nenhuma.

Conferir depois de publicar: `/api/versao` = 2026.10.3; criar uma conta de teste (pede WhatsApp); painel do contador com uma
empresa convidada; e-mail de exemplo da Gestão com o logo novo.

## 2026.10.2 — 08/10/2026

**Situação:** no ambiente de teste. Ainda não está no real.

Pro usuário (ver Novidades): painel do contador, importação com busca/ordem/marcar, guardar arquivos opcional no lote,
só o regime é obrigatório nos primeiros passos, próximos passos com o dia mais próximo aberto.

Gestão (só administração):
- Gestão manual de contas: **bloquear/desbloquear** (`assinatura.bloqueada_em/bloqueada_obs`; vale mesmo com
  `BLOQUEIO_ATIVO` desligado e passa por cima de teste/liberação) e **excluir** (pede o CNPJ; usa `contas.apagar_empresa`).
  A administradora não bloqueia nem exclui a própria conta. "Aceitar" = o "Liberar" que já existia.
- Telefone da empresa na lista de contas (link pro WhatsApp), na busca e no .csv.
- **Correção:** a contagem de e-mails somava os envios de TODAS as contas em cada conta (`envio` não tem RLS própria);
  agora passa pela nota. O total da Gestão saía multiplicado pelo número de contas.

Correções:
- Visão geral › Emissões do mês: a linha "vendedores" mostrava sempre "Não enviado"; agora conta as entregues.

Técnico:
- Migração `f6c8e0a2b4d5` (duas colunas em `assinatura`).
- Versão e novidades: `app/novidades.py`, `GET /api/versao` (pública), `GET /api/novidades`, `POST /api/conta/novidades-vistas`
  (guarda em `usuario.preferencias["novidades"]`).
- Cadastro: completa a empresa pela Receita (regime, telefone, e-mail, nome fantasia), sem derrubar o cadastro se falhar.
- `prontidao._dados_que_faltam` devolve `obrigatorio` e `por_que`; `pronta` só olha o obrigatório.
- Painel do contador: `app/services/raio_x.py`, evento `resumo_pro_contador`, `GET /api/contador/atendimentos/{id}/pacote`.
- Variáveis novas: nenhuma.

Conferir depois de publicar: `/api/versao` = 2026.10.2; Gestão › E-mails com o total certo; bloquear e desbloquear uma conta de teste.

## 2026.10.1 — 07/10/2026

**Situação:** no real desde 07/10/2026 (publicada antes de existir a numeração).

- Contador: convite com permissões, conta só de contador, pendências de cada empresa, bonificação de 10%.
- Bloqueio depois do teste (`BLOQUEIO_ATIVO`, desligado no real) e liberação pela Gestão.
- Planos por limite de notas e nota excedente (só travam com `BLOQUEIO_ATIVO`; Stripe ainda não configurado).
- E-mails da plataforma com a moldura nova; cadastro só com o CNPJ.
- Convite do contador no menu do usuário, dados da empresa pelo CNPJ, desfazer importação, tela Empresa com cinco abas,
  e-mails de exemplo na Gestão.
- Migrações: `b2e4a6c8d091`, `c3f5b7d9e1a2`, `d4a6c8e0f2b3`, `e5b7d9f1a3c4`.
