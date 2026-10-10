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
  Depois de `db.commit()` o contexto some: **monte a resposta ANTES do commit**. Rede de proteção (09/10/2026):
  `definir_prestador_atual` guarda a empresa na sessão e o `after_begin` de `SessionLocal` reaplica em toda transação nova —
  por isso a variável da RLS só se define por `definir_prestador_atual` (teste trava). A suíte troca commit por flush e não
  pega esse erro: `tests/test_rls_depois_do_commit.py` faz commit de verdade. UPDATE de dados em migração não enxerga linhas.
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
  Conta só de contador (`/cadastro?tipo=contador`): sem CNPJ, teste ou assinatura. Como todo login precisa de uma
  empresa "de casa", ela ganha um `prestador` de fachada com `so_contador=true` (cpf_cnpj = código "CT...", não é CNPJ);
  nele nada é criado (403) e ele fica fora dos números da Gestão.
  Bonificação: ao aceitar o convite o contador vira `parceiro` (`usuario_id`, `CONTADOR_BONIFICACAO_PCT`, padrão 10%) e a
  empresa entra como `indicacao_parceiro.por_contador`; some quando o acesso acaba. Empresa de outra parceira não muda de dono.
  "Empresas que atendo" mostra as pendências de cada cliente (`acesso._pendencias_da_empresa`: só títulos e quantidades).
  Painel da carteira (07/10/2026, `app/services/raio_x.py`): cartões, alertas e raio-x de cada empresa. Faturamento = notas
  AUTORIZADAS por competência (homologação só conta no ambiente de teste); não é o RBT12 oficial e a tela diz isso. O
  financeiro entra pelo evento `resumo_pro_contador`. Pacote do mês: `GET /api/contador/atendimentos/{id}/pacote` (registra no histórico).
- E-mails da plataforma (confirmação, código, convite) usam a moldura de `app/services/email_modelo.py` (logo em
  `frontend/public/ana-email.png`). E-mail de nota pro tomador NÃO passa por ela.
- Planos (`billing.PLANOS`, `app/services/planos.py`): por limite de notas AUTORIZADAS no mês, por CNPJ (cancelada, recusada,
  homologação e importada não contam). Aviso aos 80%; no limite, sobe de plano ou aceita R$ 0,80 por nota (item pendente
  na Stripe, cai na próxima fatura). Teste grátis: 150 notas. Cortesia e liberação da Gestão: sem limite. O limite só
  TRAVA com `BLOQUEIO_ATIVO` (a trava mora em `motor_emissao.submeter` e no início do lote). Um preço da Stripe por
  plano: `STRIPE_PRICE_ID_BASICO/EMPREENDEDOR/EMPRESA/AVANCADO/ILIMITADO/FINANCEIRO`.
- Bloqueio sem assinatura: `BLOQUEIO_ATIVO=true` deixa a empresa com teste vencido/cancelada só pra consulta (402 em
  tudo que muda, menos assinar/apagar). Desligado em produção até o Stripe estar recebendo. A Gestão libera na mão
  (`assinatura.liberado_ate/liberado_sempre`); a regra única é `billing.situacao_do_acesso`.
- Desfazer importação (07/10/2026): não há tabela de "importações". Extrato e planilha são reconhecidos pelo `criado_em`
  (tudo que uma importação grava nasce na mesma transação → mesmo `now()`): `app/financeiro/desfazer.py`. Nota do Emissor
  Nacional leva a marca em `tomador_snapshot["importacao"]` (`importar_adn.importacoes/desfazer`); as de antes disso aparecem
  juntas como "anteriores". Desfazer nunca toca no que foi lançado à mão nem em nota gerada pela Ana.
- Completar a empresa pelo CNPJ (`app/services/completar_empresa.py`): só preenche campo em branco, nunca troca o que a pessoa escreveu.
- Tela Empresa tem cinco abas (`emitente`, `notas`, `certificado`, `contador`, `mais`); os ids antigos (`aliquotas`, `emails`,
  `modulos`, `dados`) são redirecionados em `EmpresaPage.ABA_ANTIGA` — não quebre links antigos.
- **Fluxo de publicação (rotina combinada em 08/10/2026):** tudo vai primeiro pra branch `teste` (ambiente `teste` do
  Railway, app-teste.up.railway.app); só com o "pode subir" do Marcos a `main` recebe exatamente a `teste`. NADA vai direto
  pra `main`. Cada leva tem número (`ano.mês.sequência`): bloco novo no topo de `backend/app/novidades.py` (texto pro
  usuário, por perfil: todos/empresa/contador) + seção no `CHANGELOG.md` (técnico) — um teste cobra as duas. O rodapé do
  menu e `GET /api/versao` mostram versão e ambiente. O Railway não publica sozinho: `DEPLOY_REF=<commit>` no serviço.
- Gestão manual de contas: liberar ("aceitar"), bloquear (`assinatura.bloqueada_em`, vale mesmo com `BLOQUEIO_ATIVO`
  desligado; a trava leve fica em `acesso.conferir`) e excluir (pede o CNPJ). Nunca na própria conta de quem administra.
- `envio` NÃO tem RLS (não carrega `prestador_id`): toda consulta nela tem que passar por `emissao` — a Gestão já contou os
  e-mails de todas as contas em cada conta por causa disso.
- Fase sem cobrança (`billing.cobranca_ativa()` = existe `STRIPE_SECRET_KEY`): depois do teste a pessoa PEDE a liberação
  (`POST /api/assinatura/pedir-liberacao`) e a Gestão autoriza; mensagens falam em "pedir", não em "assinar"; limite de
  notas dos planos não vale. Tudo isso só trava com `BLOQUEIO_ATIVO=true`.
- Cadastro exige WhatsApp (`usuario.telefone`, só dígitos com DDD). A identidade visual é o símbolo "A" (`SimboloAna`);
  não existe mais ilustração/mascote (`AnaAvatar` desenha o símbolo).
- Painel do contador (`/app/atendimentos`): Hoje / Fechamento do mês / Empresas + ficha da empresa (`?empresa=<id do acesso>`).
  Tudo sai de `GET /api/contador/atendimentos` (sem entrar na empresa); `raio_x.py` faz as contas.
- Uso da plataforma (`app/services/uso.py`, tabela `evento_uso` sem RLS/FK): só NOME de tela/rota + quem; nunca conteúdo nem
  ids. Ações e erros são anotados pelo middleware `_anotar_uso`, que fica declarado ANTES do `SessionMiddleware` (precisa da
  sessão — não mude a ordem); telas vêm de `POST /api/uso/tela`. Simulação não é anotada; guarda 180 dias. Mudou o que é
  coletado → atualizar a Política de Privacidade (`LegalPage.tsx`). Nos testes `uso.gravar` é desligado no conftest.
- Passeio "o que mudou" (`components/tour/PasseioNovidades.tsx`): convida quando há versão nova pro perfil; item de
  `novidades.VERSOES` pode ter `link` (tela) e `alvo` (um `data-tour`). Conta nova nasce em dia (`novidades.marcar_em_dia`).
  Enquanto o passeio está aberto, as dicas de primeira visita esperam (`tutorial.passeioEmAndamento`).
  **Item de novidade nunca leva para fora de `/app`** (sair do painel no meio do passeio deu looping; teste trava).
  Dicas vistas: por login no navegador e na conta (`PUT /api/conta/tutorial`). "Pergunte à Ana" mora no `SuporteModal`
  (busca → Ana → equipe); `inicio="equipe"` pula direto pra equipe (contratar, certificado).
- Competência: a prática é emitir com a data do mês corrente mesmo quando o relatório/serviço é de meses atrás (data antiga
  gera multa — a Ana só avisa `competencia_antiga`). Não crie aviso sugerindo voltar a data pro mês passado.
- DANFSe e alfabetos (08/10/2026): a Helvetica só escreve latino; o resto vai pelas fontes de `danfse._FONTES_AMPLAS`, que o
  `Dockerfile` instala (tirar o `apt-get` de lá = voltar a sair quadradinho). Texto novo no PDF vindo de cadastro passa por
  `_escrever`/`_quebrar`, nunca `drawString` direto.
- Tomador de fora do Brasil: país + NIF, ou país + `motivo_sem_nif` (vira `<cNaoNIF>` na DPS). `Tomador.estrangeiro` cobre os
  dois; no frontend use `identificadaDeFora()` em vez de testar `pais && nif`.
- Pasta do mês (`app/services/pasta.py`): arquivos ficam no banco (`pasta_arquivo.conteudo`, deferred) nesta fase — se crescer,
  trocar por bucket mantendo as rotas. Rotas registradas duas vezes em `app/pasta_rotas.py` (empresa aberta e painel do contador);
  o papel (empresa/contador) é decidido no servidor. Nas rotas de leitura não use `db.rollback()` (os testes compartilham a transação).
- Link da agenda (`app/services/agenda_ics.py`): token em `assinatura_agenda` (sem RLS); a rota .ics é pública.
- Drive: conecta só em Empresa › Integrações (`components/integracoes/Integracoes.tsx`, `LINK_INTEGRACOES`); no resto do painel o
  rótulo é "Enviar para o Drive" (vale pra qualquer nuvem que entrar depois).
- Dados da empresa: obrigatório é só o regime tributário (`prontidao._dados_que_faltam`, `obrigatorio`). Endereço e alíquota
  são opcionais — não use pra travar nada.
- Simulação / modo demonstração: o caminho feliz de mentira (`app/services/demo_emissao.py`) só vale com as DUAS marcas
  (e-mail do domínio da simulação + `Prestador.demo`) — rota nova que fala com o mundo de fora usa `_na_simulacao` ou
  `exigir_conta_real`, nunca só uma das marcas. Dados de exemplo ficam nos cenários `app/data/cenarios/*.json` (CNPJ de
  tomador sempre com verificador inválido). `?gravacao=1` só esconde avisos com `usuario.demo` (`lib/gravacao.ts`).
- Catálogo de tomadores: tudo que vai pra `tomador.sug_*` passa por `sugestoes.limpar_texto` (com os nomes da empresa e dos
  usuários). `app/data/catalogo_inicial.json` = só dado público + modelo de nota (nunca texto de e-mail); o
  `scripts/semear_catalogo.py` cria o que faltar no start.
- Consulta de CNPJ: várias fontes em `cnpj_lookup._FONTES` (só passa pra próxima se a anterior está fora; 404 encerra).
  Formulário com consulta de CNPJ: trocar de CNPJ limpa o que veio da consulta anterior.
- E-mail: formato só por `app/services/emails.py` (entrada nos schemas e `email.preparar_destinos` antes de enviar).
  Inválido vira frase pra pessoa ou aviso no lote — nunca recusa crua do provedor.
- Registros: no Railway saem em JSON no stdout com `level` (`app/registro.py`). Ação de rotina é `logger.info`; `warning`
  pra algo que alguém deveria olhar; `error`/`exception` só pra defeito de verdade.
- Endereços: o catch-all do frontend só devolve o app pras telas de `App.tsx` (lista `_ROTAS_DO_PAINEL` em main.py) — tela
  nova fora de /app tem que entrar lá, senão dá 404.
- IA (2026.10.7, `app/services/ia.py`): só chama a API com `IA_ATIVA=true` + `ANTHROPIC_API_KEY`. "Pergunte à Ana" responde só
  com trechos do guia; explicação de recusa guarda em `emissao.erro_explicacao` e nunca leva nome/documento do tomador. Toda
  chamada vira `ia_chamada` (custo) e `evento_uso` tipo `ia`. Conta de simulação: IA desligada. Nos testes `_gravar_chamada` é no-op.
- Regime (2026.10.7): `fiscal/dps.regras_do_regime` decide o que vai em `regTrib`. MEI (`opSimpNac=2`): sem `regApTribSN`,
  `regEspTrib=0`, sem `pAliq`, `indTotTrib=0`, sem retenção. Regime vazio = `RegimeNaoInformadoError` (o conftest preenche o
  regime do `prestador_teste`). Leiaute 1.01 / NT 009 / IBS-CBS: raio-x seção 15 e `integracao/schemas/LEIA-ME.md`.
- Certificado (2026.10.7): vencido não carrega (`CertificadoVencidoError`, filha de NaoEncontrado) e CNPJ raiz tem que bater
  (`certificados.conferir_para_empresa`). Aviso de vencimento por e-mail: `services/avisos_certificado.py` (thread, uma vez por validade).
- Atendimento no cadastro (2026.10.7, `services/atendimento.py`): MEI qualquer cidade; ME/EPP só cidade da lista; não optante e
  inativo fora → lista de espera (`lista_espera`). Consulta fora do ar deixa seguir (Gestão marca). No conftest a consulta é "fora".
- ISS retido (2026.10.7): memória em `prestador_tomador.iss_retido`, alíquota em `prestador.aliquota_iss_retido`, retrato na nota
  (`conferencia.retencao_da_nota`). `pAliq` só pra ME/EPP que apura ISS pelo Simples, e vem ANTES de `tpRetISSQN` (ordem do 1.00).
- Quem é da Gestão (2026.10.7): tabela `gestor` + `ADMIN_EMAILS` (`services/gestores.py`). Use `gestores.eh_gestor`/`emails`,
  nunca leia `ADMIN_EMAILS` direto. No conftest a tabela vem vazia (`_da_tabela`).
- Documentos da empresa (2026.10.7): exceção ao "contador sempre vê" — só com a permissão `documentos`; `documentos_rotas._ctx`
  confere dono ou acesso de contador de novo (o gestor nunca abre). DELETE é `NUNCA` pro contador. Gestão vê só quantidade/espaço.
- IBS/CBS (2026.10.7, `services/ibs_cbs.py`): só tela e memória; NÃO monte o grupo IBSCBS no XML até a Sefin publicar o esquema
  da NT 009. Valores de IBS/CBS são da Sefin (só lemos da NFS-e autorizada pro PDF).
- Gestão num endereço próprio (2026.10.7, `services/area_gestao.py`): com `GESTAO_HOST` as rotas da Gestão/parceiras só
  respondem nesse host e o app das notas não mostra a Gestão. Rota nova da Gestão usa `exigir_gestor` (que já faz a trava
  do host). No frontend, `ehDominioGestao()` só muda a aparência.
- Carteira do contador (2026.10.7, `services/carteira.py`): "ativo no mês" (base da cobrança por cliente, ainda desligada)
  mora em `carteira.ativo_no_mes`. Empresa cadastrada pelo contador: `acesso_contador.criado_pelo_contador` + `convite_dono`
  (sem RLS, lido pelo token). Rota do contador que lê `prestador` define o contexto da RLS antes (num pedido real ele começa vazio).
- Financeiro sozinho (2026.10.7): fora da venda para conta nova (`billing.PLANOS["financeiro"]["a_venda"] = False`).
- Nunca commitar: `backend/.db_url_tmp`, `backend/producao.env.txt`, relatórios/planilhas/PDFs reais. Testes só com dados sintéticos.
- Segredos (Stripe, Resend, Google) só nas variáveis do Railway — nunca no código nem em conversa.

## Checagem antes de publicar (combinada em 08/10/2026 — "antes de subir uma atualização faça sempre um check")
1. `pytest` inteiro — inclui `tests/test_contrato_respostas.py`, que falha se uma rota com `response_model` descartar campo
   que o serviço montou (foi o que escondeu "Assinadas/Autorizadas" no real). Rota nova de leitura com `response_model` →
   acrescentar nela.
2. `npx tsc -b && npm run build`.
3. Tela nova ou alterada: abrir no navegador local (Playwright) com dados e conferir que os números aparecem — pela API, não
   só pelo serviço. Limpar depois as linhas de teste (`evento_uso`, `registro_contador`, pasta) do banco local.
4. Depois do deploy no teste: deploy SUCCESS no commit certo, logs de build/migração, `GET /api/versao`, as rotas novas
   respondendo e os campos novos chegando na resposta. Só então pedir o push da `main`.
5. Depois do deploy no real: a mesma conferência, com os dados de verdade da conta do Marcos.

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
