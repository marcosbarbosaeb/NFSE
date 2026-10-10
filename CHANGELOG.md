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

## 2026.10.7 — 10/10/2026

Atualização grande da etapa 1 do roteiro de lançamento (itens A a G) + IA. Construída na noite de 09 para 10/10 a partir de
`ideias/roteiro-de-lancamento.md`, `ideias/ia-na-ana.md`, `ideias/proxima-versao.md` e dos três levantamentos novos.
Dúvidas que dependem do Marcos: `claude/duvidas-para-o-marcos.md` (projeto).

- **Leiaute IBS/CBS lido primeiro** (raio-x, seção 15). Esquemas 1.01 guardados em `integracao/schemas/` (sem
  `xs:annotation`; LEIA-ME lá). Achado: o 1.01 publicado é anterior à NT 009 (sem `regApIBSCBSSN`, `cAtvSN`,
  `opSimpNac=4`) → nesta versão IBS/CBS fica só na tela e no cadastro; o XML continua 1.00.
- **IA** (`services/ia.py`, `ajuda.py`): "Pergunte à Ana" (Ajuda) responde só com trechos do guia
  (`data/guia-agente-ana.md`, busca por seção `###`), marcadores `[NAO_SEI]`/`[CONTADOR]`; limite por empresa por dia
  (horário de Brasília). Explicação de recusa (`POST /api/dps/{id}/explicar-recusa`, guarda em `emissao.erro_explicacao`;
  recusas de regra fixa E0008/E0240 não chamam a IA). Nada de nome/documento do tomador vai pra IA. Custo por chamada em
  `ia_chamada` + `evento_uso` tipo `ia`; Gestão › Uso mostra perguntas e custo. Conta de simulação: IA desligada.
  **Variáveis:** `IA_ATIVA` (padrão false — sem ela nada chama a API), `ANTHROPIC_API_KEY`, `IA_MODELO`
  (`claude-haiku-5-5`), `IA_LIMITE_DIARIO` (20), `IA_PRECO_ENTRADA`/`IA_PRECO_SAIDA` (US$ por milhão de tokens).
  Política de Privacidade e Termos atualizados (10/10/2026).
- **MEI** (`fiscal/dps.py`): `regras_do_regime`; MEI sem `regApTribSN`, `regEspTrib=0`, sem `pAliq`, `indTotTrib=0`;
  regime vazio = `RegimeNaoInformadoError` (a conferência mostra onde preencher). IM opcional. Teste valida a DPS do MEI no 1.01.
- **Certificado** (`services/certificados.py`, `services/avisos_certificado.py`): vencido não entra nem assina
  (`CertificadoVencidoError`), CNPJ raiz tem que bater (filial ok); e-mail 30 dias antes, uma vez por validade
  (`certificado.aviso_vencimento_para`, thread a cada 6 h). Orientação "não tem certificado?" com
  `CERTIFICADO_ORIENTACAO` e `CERTIFICADO_ORIENTACAO_WHATSAPP` (sem esta, usa o WhatsApp do suporte).
- **Verificação no CNPJ** (`services/atendimento.py`, `services/lista_espera.py`): `GET /api/atendimento?cnpj=` no
  cadastro; MEI atende em qualquer cidade, ME/EPP só nas cidades da lista; não optante e CNPJ inativo ficam de fora;
  consulta fora do ar deixa seguir e a Gestão marca "fora do atendimento". `POST /api/lista-espera` (tabela
  `lista_espera`), aviso por e-mail quando a cidade entra na lista; Gestão › Lista de espera.
- **ISS retido** (`services/conferencia.py`): `prestador_tomador.iss_retido` (memória), `prestador.aliquota_iss_retido`;
  na nota `iss_retido`/`aliq_iss` (snapshot); `tpRetISSQN=2` e `pAliq` (1,8–5%) só pra ME/EPP que apura ISS pelo Simples;
  MEI nunca. Dicas de recusa E0655, E0621, E0628, E0583, E0160. Aviso de NBS faltando (obrigatório no 1.01).
- **Gestores** (`services/gestores.py`): tabela `gestor` (semeada com o e-mail do Marcos + `ADMIN_EMAILS`); Gestão ›
  Gestores adiciona/remove (não remove a si nem o último). `ADMIN_EMAILS` continua valendo (pode ser esvaziada depois).
- **Perfis** (`services/perfis.py`, `data/perfis.json`): cadastro pergunta como emite (pula), `prestador.perfis`;
  pergunta uma vez a quem já tem conta; atalho na Visão geral; buscas sem resultado em `perfil_busca`; Gestão › Perfis.
- **Documentos da empresa** (`services/documentos_empresa.py`, `documentos_rotas.py`, tela `/app/documentos`): tabelas
  `documento_empresa` e `documento_acesso` (RLS). Permissão nova do contador `documentos` (começa desligada para todos);
  só o dono apaga e vê os acessos; Gestão nunca abre (só quantidade/espaço). 15 MB por arquivo, 100 MB por empresa.
  Validade → "Precisa da sua atenção" (sem o nome do documento).
- **IBS e CBS na tela** (`services/ibs_cbs.py`): `prestador.regime_ibs_cbs` (1/2/3, padrão 1), `regime_ibs_cbs_desde`,
  `ibs_cbs_confirmado_em`; `prestador_tomador.cclass_trib`/`cind_op`. Conferência avisa (2027+) sem classificação;
  "Precisa da sua atenção" pede confirmação em mai–jun e nov–dez; DANFSe mostra o grupo `IBSCBS` quando a nota trouxer.

Migrações (em ordem): `f2a4c6e8b0d1` (ia_chamada, emissao.erro_explicacao), `a3b5c7d9e1f3` (aviso do certificado),
`b4c6d8e0f2a4` (lista_espera), `c5d7e9f1a3b5` (ISS retido), `d6e8f0a2b4c6` (gestor), `e7f9a1b3c5d7` (perfis),
`f8a0b2c4d6e8` (documentos), `a9b1c3d5e7f9` (IBS/CBS).

**Conferir depois de publicar:** `GET /api/versao` = 2026.10.7; migração até `a9b1c3d5e7f9` no log; `GET /api/ajuda`
com `ia_ativa` (false enquanto `IA_ATIVA` não for ligada); `GET /api/atendimento?cnpj=` respondendo; Gestão com as abas
Lista de espera, Gestores e Perfis; `/app/documentos` abrindo; Empresa mostrando "IBS e CBS" para ME/EPP do Simples.
Cobrança e `BLOQUEIO_ATIVO` continuam desligados.

## 2026.10.6 — 08/10/2026

Modo demonstração (pra gravar vídeos de anúncio) em cima da simulação, sem ambiente novo, e as falhas achadas no teste.

- **Caminho feliz simulado** (`services/demo_emissao.py`): na conta de simulação, assinar, enviar à prefeitura e
  entregar ao tomador dão certo de mentira (sem certificado, Receita nem e-mail). Chave de 50 dígitos e número inventados,
  `xml_resposta` mínimo em volta da DPS pro DANFSe; envio gravado como `enviado`. As rotas `/dps/{id}/assinar`,
  `/submeter` e `/enviar-email` desviam via `_na_simulacao` (main.py). **Trava**: só com as duas marcas — usuário com
  e-mail do domínio da simulação E `Prestador.demo`; e-mail de simulação sem a marca da empresa continua 403
  (`exigir_conta_real`). Notas da simulação são sempre homologação (`_tp_amb_da_nota`).
- **Cenários** (`app/data/cenarios/*.json`, LEIA-ME lá): empresa, tomadores, valores, meses, recebidos, despesas e
  eventos. `POST /api/demo?cenario=<nome>` (404 se não existe; nome só `[a-z0-9_-]`); tela `/simulacao?cenario=beleza`.
  Cenários: `afiliados` (o de antes, padrão) e `beleza` (tomador "Bella Beauty"). CNPJs de tomador sempre com
  verificador inválido (teste confere). Notas passadas nascem autorizadas e entregues.
- **Tela limpa** (`lib/gravacao.ts`): `?gravacao=1` (em `/simulacao` ou qualquer tela; `?gravacao=0` desliga; guardado
  na aba) esconde a faixa "Modo simulação", o aviso amarelo de homologação, o "· teste" da lista e as dicas do tutorial.
  Só vale com `usuario.demo`. Na simulação, "Ao gerar" vem com os três passos marcados.
  Também tira o "(ambiente de teste)" do selo e a coluna Ambiente da página da nota.
- **/simulacao logado numa conta de verdade**: pergunta "Sair e abrir a simulação" (antes voltava pro painel sem
  avisar). Cada abertura cria uma simulação nova, com os dados do cenário do zero.
- **Cenário sem atraso**: `dia` aceita `"hoje"` e `"hoje+N"` (`demo._dia`, nunca passa do fim do mês); na beleza a
  Bella Beauty vence hoje. Endereço inventado por tomador no cenário (atualiza o tomador de simulação já existente).
- **Página da nota**: homologação confirmada diz "Confirmada pela prefeitura (ambiente de teste)", nunca "nota fiscal
  válida" (`nota_visual`).
- **Visão geral, "Precisa da sua atenção"**: fundo escuro no tema escuro (o título ficava branco sobre amarelo claro).
- **Um clique em "Gerar e fazer tudo"** (`NfsePage` › `NovaEmissaoModal`): o botão não fica mais desabilitado enquanto
  confere; o clique confere de novo se os dados mudaram e só para em erro. Avisos amarelos não pedem mais a caixinha.
- **Visão geral**: "Emitidas" e "Faturado no mês" só com nota `confirmado` (`dashboard.ESTADOS_FATURADOS`); recusada ou a
  assinar fica em "Aguardando emissão".
- **Consulta de CNPJ** (`services/cnpj_lookup.py`): BrasilAPI → CNPJ.ws (publica.cnpj.ws) → ReceitaWS, só quando a
  anterior está fora (404 encerra). O motivo de cada falha vai pro log. No teste a BrasilAPI recusava a saída do servidor.
- **Formulários de CNPJ** (tomador, cadastro, nova empresa, importar do Emissor, identificar cliente): trocar de CNPJ
  limpa o que veio da consulta anterior, mesmo quando a nova consulta falha.
- **Catálogo pré-cadastrado em banco novo**: `scripts/semear_catalogo.py` roda no start (entrypoint) e cria, só se
  faltar, os tomadores de `app/data/catalogo_inicial.json` (11 do catálogo de produção, só dado público + modelo de
  nota; sem textos de e-mail). Em produção não muda nada.
- **Busca pela marca** (`lib/marcas.ts`): no catálogo a Shopee é "SHPS..."; a lista de Tomadores e a busca do
  cadastro mostram e acham pela marca (Shopee, Mercado Livre, Amazon, Magalu...), que também vira o apelido sugerido.
- **Catálogo sem nome de pessoa**: a limpeza (`services/sugestoes.py`) tira a assinatura depois de
  "Atenciosamente/Att/Cordialmente/Abraços", pedaços do nome da empresa e dos usuários (duplas de palavras; primeiro
  nome em razão social de pessoa) e cupons de desconto. Migração `e1c3d5f7a9b2` limpa o que já estava gravado.

- **Conserto 1 — leitura depois do commit (erro 500 "invalid input syntax for type uuid: ''")**: em 05/10 a produção
  teve 6 desses (POST /api/dps às 02:00 UTC e /dps/{id}/submeter às 12:17–12:46 UTC), todos em código antigo — o
  /api/dps já tinha sido corrigido em e9e1022 e o /submeter em 9ed781d; nenhum desde então. Conserto da família inteira:
  `definir_prestador_atual` guarda a empresa em `session.info` e um `after_begin` do `SessionLocal`
  (`database._reaplicar_prestador_atual`) reaplica a variável da RLS em toda transação nova da mesma sessão — qualquer
  leitura pós-commit, em qualquer rota, volta a funcionar. Revisão: rodei a suíte inteira com um vigia de leitura
  pós-commit; das rotas, só o cancelamento (`/dps/{id}/cancelar`) ainda montava a resposta depois do commit (e o
  `/assinar` também, sem gatilho hoje): os dois passaram a montar antes. Teste novo
  `tests/test_rls_depois_do_commit.py`: commit DE VERDADE (fora da transação compartilhada da suíte), prova que sem o
  conserto a armadilha aparece, passeia pelas rotas que gravam com commits reais e trava a variável da RLS a um só lugar.
- **Conserto 2 — e-mail com formato inválido**: `services/emails.py` (regra única, a que o Resend aceita). Entrada:
  validadores nos pedidos (tomador: contato/Para/Cópia/extras; e-mails gerais; envio avulso; pacote; emitente;
  cadastro; convite do contador; suporte; parceira) com a frase pra pessoa (`formatarErro` mostra só a frase).
  Relatório da Shopee: e-mail inválido do vendedor vira `email_invalido` no retrato da nota e aviso no lote. Envio:
  `email.preparar_destinos` tira o inválido e, sem nenhum válido, levanta `EmailDestinoInvalidoError` (frase clara)
  antes de chamar o provedor. Aviso de fim de lote com e-mail da conta inválido: não chama o provedor, grava
  `opcoes.aviso_conta` e a tela do relatório mostra com link pra Minha conta.
- **Conserto 3 — níveis no Railway** (`app/registro.py`): no Railway (variável `RAILWAY_ENVIRONMENT*` ou `LOG_JSON`),
  uma linha JSON por registro no stdout com `level` (info/warn/error); traceback inteiro dentro do registro do erro;
  uvicorn usa o mesmo formato. Alembic escreve no stdout (`alembic.ini`). "Gestão: conta ... excluída" virou `info`.
- **Conserto 4 — endereços desconhecidos**: conferido em produção — /.env, /.git/config, /wp-json/..., /test/phpinfo.php,
  /robots.txt e /sitemap.xml devolviam 200 com a página do app (index.html, 1.801 bytes), nenhum arquivo de verdade.
  Agora o catch-all só devolve o app pras telas de `App.tsx` (/, /app/*, /entrar, /cadastro, /simulacao,
  /confirmar-email, /privacidade, /termos, /parceira/<token>) e pros arquivos do build; pedaço que começa com "."
  é 404 sem olhar o disco; o resto é 404 com página simples (noindex). Endereço antigo do painel sem /app → 301.

Migração: `e1c3d5f7a9b2` (só dados do catálogo). Variáveis novas: nenhuma (o formato de registro liga sozinho no Railway).

Conferir depois de publicar: `/api/versao` = 2026.10.6; `/simulacao?cenario=beleza&gravacao=1` sem faixa, aviso e dicas,
e Nova emissão pra Bella Beauty em um clique até "Enviada"; Tomadores › Adicionar com "Shopee" no catálogo e um CNPJ
novo consultado; Visão geral sem nota recusada em "Emitidas".

## 2026.10.5 — 08/10/2026

Lista de ajustes do Marcos + três dúvidas que apareceram num concorrente.

- **Calendário** (`pages/CalendarioPage.tsx`): clicar no dia abre `DiaModal` com todos os eventos do dia — editar (manual),
  "Mudar data ou regra" (calculados, o mesmo `AjusteModal`; o ajuste de `prazo_emissao` já valia nos Próximos passos) e um
  link pra tela onde o evento se resolve. Ícone por tipo (legenda, grade e painel); no celular a grade mostra só os ícones.
- **Gráficos com tipo escolhível** (`components/graficos/Fatias.tsx`): "Para onde vai o dinheiro" e "Recebido por cliente"
  em barras, rosca ou faixa (no máximo 6 fatias, o resto vira Outros). Escolha guardada no navegador
  (`agenteana:grafico:<id>`). Cores: 6 primeiras da paleta categórica de referência, validadas para vizinhas (claro/escuro).
- **Conciliação**: o cartão do Fechamento do mês leva pra `?parte=notas&mes=AAAA-MM&filtro=...` (atrasadas, diferença ou
  abertas); `ConciliacaoNotas` ganhou `mesInicial`.
- **NFS-e / Notas em lote**: 10 notas por vez + "Carregar mais"/"Mostrar todas" (`NfsePage.POR_PAGINA`); seleção e ações
  continuam valendo pro filtro inteiro.
- **Visão geral**: a linha dos vendedores ganhou `total_grupo`, `assinadas`, `autorizadas`, `recusadas`
  (`dashboard.resumo_mes`) e mostra Assinadas / Autorizadas / Enviadas como as outras linhas.
- **Pasta do mês** (`app/services/pasta.py`, `app/pasta_rotas.py`, `components/pasta/PastaDoMes.tsx`): pedidos recorrentes do
  contador, arquivos por mês (no banco nesta fase: 15 MB por arquivo, 300 MB por empresa), marcas "não teve"/"conferido" e
  uma conversa por empresa. As mesmas rotas em `/api/pasta/...` (empresa aberta) e `/api/contador/atendimentos/{id}/pasta/...`
  (painel do contador, sem entrar). Pedido tipo "extrato" conta sozinho pelo evento `extrato_do_mes` (financeiro).
  Tela `/app/pasta` com selo no menu; ficha da empresa no painel do contador; tarefas em "Hoje".
  **Migração `d0b2c4e6f8a1`** (tabelas `pasta_*` com RLS e `assinatura_agenda` sem RLS).
- **Link de assinatura da agenda** (`app/services/agenda_ics.py`): `GET /api/agenda/<token>.ics` sem login (um mês pra trás,
  seis pra frente), `GET /api/calendario/assinatura`, `POST /api/calendario/assinatura/novo`. Em Empresa › Integrações e no
  Calendário. O endereço usa `APP_BASE_URL`.
- **Integrações** (Empresa › Integrações): Drive (Google; OneDrive/Dropbox "em breve"), agenda e WhatsApp ("em breve").
  "Enviar para o Drive" no lugar de "Google Drive" nas opções de envio, na nota e no lote; conectar só nas Integrações.
  Conectar o Drive manda `login_hint` com o e-mail do login (a conta do Google já vem escolhida).
- Política de Privacidade: Pasta do mês e link da agenda.
- Correção (no ar em 08/10/2026): os campos novos da linha dos vendedores não estavam no `response_model` do resumo do mês
  (`EmissaoResumoLinha` em `schemas.py`) e sumiam no caminho; teste novo passa pela API.
- **Google Drive no real** (configuração, sem código): "Erro 400: redirect_uri_mismatch" = o endereço
  `https://notas.agenteana.com.br/api/drive/callback` (o que o app manda, conferido em 08/10/2026) não está na lista de
  URIs de redirecionamento autorizados do cliente OAuth no Google Cloud. Pro ambiente de teste vale o mesmo com o domínio dele.
- **PDF da nota (DANFSe) com outros alfabetos** (`app/services/danfse.py`): a Helvetica só escreve o alfabeto latino e o
  nome do tomador em chinês/japonês/coreano/cirílico saía como quadrados. O que ela não escreve vai com DejaVu Sans, Droid
  Sans Fallback ou NanumGothic (`_FONTES_AMPLAS`), embutidas no PDF só com os caracteres usados; a quebra de linha entende
  texto sem espaço. Texto latino segue exatamente como antes.
  - **Dockerfile**: instala `fonts-dejavu-core fonts-droid-fallback fonts-nanum`. Sem as fontes (máquina de desenvolvimento)
    cai na fonte chinesa do leitor de PDF.
  - Não cobre árabe/hebraico (escrita da direita pra esquerda).
- **Competência no mês corrente**: chegou a ser feito um aviso `mes_pulado` (nota neste mês sem a do mês passado) e foi
  retirado antes de publicar — a prática é emitir com a competência do mês corrente mesmo quando o relatório é de meses
  atrás (data antiga gera multa). Segue valendo só o aviso `competencia_antiga`. Há um teste segurando a ausência do aviso.
- **Empresa de fora sem NIF**: `tomador.motivo_sem_nif` ("1" dispensada, "2" o país não exige) — **migração `c9f1b3d5e7a8`**.
  A DPS sai com `<cNaoNIF>` no lugar de `<NIF>` (o XSD já previa), com `endExt` e `comExt` como nas outras notas pro exterior.
  Cadastro: “Esta empresa não tem número fiscal” em Dados do tomador. Relatório da Shopee continua pulando vendedor sem documento.
  - **Conferir antes de publicar no real**: o XML passa no XSD, mas nenhuma nota com `cNaoNIF` foi enviada à Sefin ainda —
    emitir uma em homologação pelo ambiente de teste.

## 2026.10.4 — 08/10/2026

**Situação:** no ambiente de teste. Ainda não está no real.

Pro usuário (ver Novidades): passeio "o que mudou desde a sua última visita" com o assistente do tutorial.

Gestão (só administração):
- **Uso da plataforma** (aba nova "Uso"): telas abertas, ações feitas e erros dos últimos 30 dias (vezes e pessoas), o caminho da
  conta nova até a primeira nota (onde param) e "Onde olhar primeiro" (regras simples em cima dos números).
- O que é anotado: só o NOME da tela/rota e quem fez (`evento_uso`: usuario_id, prestador_id, tipo, nome, detalhe = código do
  erro). Nunca conteúdo nem ids de nota/tomador. Contas de simulação ficam de fora. Guarda 180 dias. A Política de Privacidade
  ganhou o parágrafo correspondente.

Técnico:
- Migração `b8e0a2c4d6f7` (tabela `evento_uso`, sem RLS e sem FK).
- `app/services/uso.py`; middleware `_anotar_uso` em `app/main.py` — declarado ANTES do `SessionMiddleware` de propósito (roda por
  dentro dele e enxerga a sessão). `POST /api/uso/tela` (o painel avisa a tela), `GET /api/gestao/uso`.
- Novidades: item pode ter `alvo` (um `data-tour` da tela) pro passeio; conta nova nasce com `preferencias.novidades.vista` = versão
  atual (`novidades.marcar_em_dia`); quem nunca viu é tratado como quem viu até a penúltima.
- Frontend: `components/tour/PasseioNovidades.tsx` (pergunta "Ver o que mudou / Agora não" e percorre os itens),
  `lib/uso.ts` (avisa a tela a cada navegação).
- Variáveis novas: nenhuma.

Conferir depois de publicar: `/api/versao` = 2026.10.4; entrar com uma conta antiga (aparece o convite do passeio) e com uma conta
nova (só o tutorial normal); Gestão › Uso mostrando as telas depois de navegar um pouco.

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
