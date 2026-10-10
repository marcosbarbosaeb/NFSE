"""Versões e novidades (08/10/2026).

Rotina combinada com o Marcos pra "não dar erros": tudo sobe primeiro pro
ambiente de teste, ganha um número de versão e uma lista do que mudou — "até
para informarmos aos usuários". Duas camadas:

- **Aqui**: o que o USUÁRIO percebe, em linguagem de leigo, por perfil
  ("novidades por perfil"): `todos`, `empresa` (quem emite nota / usa o
  financeiro) ou `contador`. Aparece na tela Novidades e no sino.
- **CHANGELOG.md** (raiz do repositório): o registro técnico, com o que o
  usuário não vê (migração, variável nova, o que conferir ao publicar).

Como numerar: `ano.mês.sequência` (2026.10.1, 2026.10.2...). A versão mais
nova vai SEMPRE no topo da lista; o número que o painel mostra no rodapé é o
dela. Publicar no real sem acrescentar a versão aqui = publicar sem número.
"""
from __future__ import annotations

PERFIS = ("todos", "empresa", "contador")

# A mais nova primeiro.
VERSOES: list[dict] = [
    {
        "versao": "2026.10.7",
        "data": "2026-10-10",
        "resumo": "Pergunte à Ana, nota de MEI certa, ISS retido, documentos da empresa e o começo da reforma tributária (IBS e CBS).",
        "itens": [
            {"perfil": "todos", "titulo": "Pergunte à Ana", "link": "/app/ajuda",
             "texto": "Na Ajuda, escreva a sua dúvida do seu jeito e eu respondo com base no guia da Ana. Quando a pergunta é de "
                      "contabilidade (imposto, regime, alíquota), eu digo que é com o seu contador. Há um número de perguntas por dia."},
            {"perfil": "empresa", "titulo": "Nota recusada explicada em palavras simples",
             "texto": "Quando a prefeitura recusa uma nota, a página dela ganha “Em palavras simples”: o que aconteceu e o que fazer, "
                      "passo a passo, sem o código da recusa."},
            {"perfil": "empresa", "titulo": "Nota de MEI do jeito certo", "link": "/app/empresa?aba=emitente",
             "texto": "Para MEI, a nota sai sem alíquota e sem os campos que o MEI não pode mandar. O regime da empresa (MEI, Simples "
                      "ou não optante) passa a ser obrigatório: sem ele eu não gero a nota e digo onde preencher."},
            {"perfil": "empresa", "titulo": "Certificado: aviso antes de vencer e trava quando venceu", "link": "/app/empresa?aba=certificado",
             "texto": "Eu mando um e-mail 30 dias antes de o certificado vencer. Certificado vencido, ou de outro CNPJ, não entra e não "
                      "assina nota — e a mensagem diz o que fazer. Quem ainda não tem certificado vê como conseguir um."},
            {"perfil": "todos", "titulo": "Confiro a cidade e o regime no cadastro", "link": "/cadastro",
             "texto": "Ao criar a conta, eu consulto o CNPJ e digo se já atendo a sua cidade e o seu regime. Se ainda não, você entra "
                      "na lista de espera e eu aviso por e-mail quando a sua cidade entrar."},
            {"perfil": "empresa", "titulo": "ISS retido pelo tomador", "link": "/app/tomadores",
             "texto": "No cadastro do tomador, marque “Este tomador retém o ISS”: as notas dele saem com a retenção e a alíquota do ISS "
                      "da sua faixa do Simples (que fica guardada em Empresa). Dá pra mudar numa nota só, na hora de gerar. MEI não tem retenção."},
            {"perfil": "empresa", "titulo": "Código NBS: comece a completar", "link": "/app/tomadores",
             "texto": "Com a reforma tributária o código NBS passa a ser obrigatório na nota. A conferência avisa quando o tomador está sem ele."},
            {"perfil": "empresa", "titulo": "Como você emite?", "link": "/app/empresa?aba=emitente",
             "texto": "Uma pergunta rápida (dá pra pular): muitas notas de uma vez, clientes fixos, fechamento do mês ou nota avulsa. "
                      "A Visão geral ganha um atalho para o seu jeito de emitir. Dá pra mudar em Empresa."},
            {"perfil": "empresa", "titulo": "Documentos da empresa", "link": "/app/documentos",
             "texto": "Um lugar fixo para contrato social, cartão CNPJ, documentos dos sócios, certidões e alvará — fora da pasta do mês. "
                      "Coloque a validade e eu aviso 30 dias antes. Só você e o contador que você liberar enxergam (o contador começa "
                      "SEM essa permissão: libere em Empresa › Contador). Só você apaga e vê quem abriu cada documento."},
            {"perfil": "contador", "titulo": "Documentos da empresa do cliente", "link": "/app/documentos",
             "texto": "Com a permissão “Documentos da empresa” (o cliente libera em Empresa › Contador), você vê, envia e substitui "
                      "os documentos fixos da empresa. Apagar é só com o dono."},
            {"perfil": "empresa", "titulo": "IBS e CBS: o começo", "link": "/app/empresa?aba=emitente#ibs-cbs",
             "texto": "Para empresa do Simples: diga em Empresa como recolhe IBS e CBS a partir de 2027 (o padrão é tudo pelo Simples). "
                      "No tomador dá pra guardar a classificação que o seu contador passar. A nota ainda não leva esses campos — "
                      "o governo não publicou o formato final; quando publicar, eu uso o que você já deixou guardado."},
        ],
    },
    {
        "versao": "2026.10.6",
        "data": "2026-10-08",
        "resumo": "Gerar a nota num clique só, Visão geral contando só notas autorizadas, consulta de CNPJ mais firme e e-mail conferido.",
        "itens": [
            {"perfil": "empresa", "titulo": "“Gerar e fazer tudo” num clique só", "link": "/app/nfse",
             "texto": "Antes o primeiro clique só conferia os dados e o botão mudava de lugar. Agora um clique confere, gera, assina, "
                      "envia à prefeitura e entrega ao tomador. Só para se a conferência achar algo em vermelho; os avisos amarelos "
                      "continuam aparecendo, mas não pedem mais a caixinha de “conferi”."},
            {"perfil": "empresa", "titulo": "Visão geral: “Emitida” é nota autorizada", "link": "/app",
             "texto": "Nota recusada pela prefeitura, ou ainda a assinar, não conta mais como emitida: ela fica em “Aguardando emissão” "
                      "até ser autorizada. “Faturado no mês” soma só as notas autorizadas."},
            {"perfil": "todos", "titulo": "Consulta de CNPJ mais firme",
             "texto": "Quando a fonte de sempre dos dados da Receita está fora do ar, eu tento outras duas antes de pedir pra você preencher à mão. "
                      "E, se você trocar o CNPJ e a consulta não der, os dados do CNPJ anterior saem do formulário."},
            {"perfil": "empresa", "titulo": "Ache o tomador pelo nome da marca", "link": "/app/tomadores",
             "texto": "Procure “Shopee”, “Mercado Livre”, “Amazon” ou “Magalu” na lista de tomadores: aparece a empresa certa, "
                      "mesmo com outra razão social no cadastro da Receita."},
            {"perfil": "todos", "titulo": "Simulação mais completa", "link": "/simulacao",
             "texto": "Na simulação, “Gerar e fazer tudo” vai até o fim (de mentira: nada sai pra Receita nem pra ninguém) e as notas de "
                      "exemplo já aparecem autorizadas e entregues, com os números da Visão geral e do financeiro andando juntos."},
            {"perfil": "empresa", "titulo": "Gerar, assinar e cancelar a nota sem erro no meio",
             "texto": "Em alguns casos a nota era gravada, mas a tela mostrava erro na hora de devolver o resultado (gerar, enviar à "
                      "prefeitura, cancelar). Isso foi corrigido de uma vez pra todas as telas, não só pras que deram erro."},
            {"perfil": "todos", "titulo": "E-mail errado vira aviso, não erro",
             "texto": "Eu confiro o formato do e-mail quando você cadastra (tomador, cópias, e-mails gerais, convite do contador) e "
                      "digo qual está errado. No lote, vendedor com e-mail inválido no relatório aparece como aviso, e se o e-mail da "
                      "sua conta estiver errado o relatório do lote te avisa pra corrigir em Minha conta."},
            {"perfil": "todos", "titulo": "Endereço que não existe mostra “Página não encontrada”",
             "texto": "Antes, qualquer endereço digitado errado abria o painel. Agora aparece “Página não encontrada”, com o link "
                      "pro início. Links antigos do painel (sem o /app) levam pro lugar certo."},
        ],
    },
    {
        "versao": "2026.10.5",
        "data": "2026-10-08",
        "resumo": "Pasta do mês com o contador, Integrações, agenda no Google, calendário novo e gráficos que mudam de forma.",
        "itens": [
            {"perfil": "empresa", "titulo": "Pasta do mês (com o seu contador)", "link": "/app/pasta",
             "texto": "Um lugar só pro que o contador precisa todo mês: a lista do que mandar, os arquivos de cada mês e uma conversa "
                      "pra deixar tudo combinado por escrito. O extrato que você importa na Conciliação já conta como enviado."},
            {"perfil": "contador", "titulo": "Pasta do mês de cada cliente", "link": "/app/atendimentos",
             "texto": "Na ficha de cada empresa: monte a lista do que você precisa todo mês, baixe os arquivos, marque como conferido "
                      "e converse com o cliente — sem entrar na empresa. O que chegar de novo aparece em “Hoje”."},
            {"perfil": "empresa", "titulo": "Empresa › Integrações", "link": "/app/empresa?aba=integracoes",
             "texto": "O Drive agora se conecta num lugar só. Nas opções de envio fica só “Enviar para o Drive”, e as notas vão pro Drive "
                      "que você conectou (Google Drive hoje; OneDrive e Dropbox em breve)."},
            {"perfil": "todos", "titulo": "Seu calendário no Google Agenda", "link": "/app/calendario",
             "texto": "Copie o link da sua agenda (no Calendário ou em Empresa › Integrações) e cole no Google Agenda, Outlook ou Apple: "
                      "os dias de gerar nota, as previsões de recebimento e os seus lembretes aparecem lá."},
            {"perfil": "todos", "titulo": "Calendário: tudo do dia num clique", "link": "/app/calendario",
             "texto": "Clique num dia e veja tudo o que está marcado nele: dá pra editar seus eventos, mudar a data de um prazo (vale também "
                      "em Próximos passos) e ir direto pra tela onde ele se resolve. Cada tipo de evento ganhou um ícone, além da cor."},
            {"perfil": "empresa", "titulo": "Escolha o tipo de gráfico", "link": "/app/financeiro",
             "texto": "Em “Para onde vai o dinheiro” e “Recebido por cliente”, escolha entre barras, rosca ou faixa. Eu lembro da sua escolha."},
            {"perfil": "empresa", "titulo": "Conciliação abre onde está a pendência", "link": "/app/financeiro/conciliacao",
             "texto": "Clicar nas notas de um mês, no Fechamento do mês, abre a lista já naquele mês e nas notas que faltam."},
            {"perfil": "empresa", "titulo": "Listas de notas mais curtas", "link": "/app/nfse/lote",
             "texto": "Notas em lote e NFS-e mostram 10 notas por vez, com “Carregar mais” no fim. Selecionar todas continua valendo pra tudo o que o filtro achou."},
            {"perfil": "empresa", "titulo": "Vendedores na Visão geral",
             "texto": "A linha das notas dos vendedores mostra quantas estão assinadas, autorizadas e enviadas, como as outras notas."},
            {"perfil": "empresa", "titulo": "PDF da nota com nome em chinês, japonês, coreano...",
             "texto": "Tomador de fora com o nome escrito em outro alfabeto agora sai certo no PDF da nota (antes apareciam quadradinhos "
                      "no lugar das letras). No XML sempre saiu certo."},
            {"perfil": "empresa", "titulo": "Empresa de fora do Brasil sem número fiscal", "link": "/app/tomadores",
             "texto": "Algumas empresas de fora não têm o número fiscal (NIF). Agora dá pra marcar “Esta empresa não tem número fiscal” "
                      "no cadastro do tomador e dizer o motivo — a nota sai com o tomador identificado pelo nome e pelo país."},
        ],
    },
    {
        "versao": "2026.10.4",
        "data": "2026-10-08",
        "resumo": "Eu te mostro o que mudou desde a sua última visita.",
        "itens": [
            {"perfil": "todos", "titulo": "Passeio pelas novidades", "alvo": "novidades-sino",
             "texto": "Quando sair uma atualização, eu aviso ao entrar e ofereço um passeio rápido pelo que mudou. Não quer agora? É só fechar: "
                      "o sino aqui em cima guarda tudo."},
        ],
    },
    {
        "versao": "2026.10.3",
        "data": "2026-10-08",
        "resumo": "Painel próprio do contador, cara nova da Ana e WhatsApp no cadastro.",
        "itens": [
            {"perfil": "contador", "titulo": "Painel do contador, refeito", "link": "/app/atendimentos", "alvo": "contador-abas",
             "texto": "Três telas em volta da sua rotina: “Hoje” (uma fila só com o que fazer, do mais urgente pro menos), “Fechamento do mês” "
                      "(as empresas em colunas: falta conferir, aguardando pagamento, fechado) e “Empresas” (a carteira com os números)."},
            {"perfil": "contador", "titulo": "Ficha de cada empresa, sem entrar nela", "link": "/app/atendimentos", "alvo": "contador-busca",
             "texto": "Escolha a empresa no topo do painel e veja o que te interessa: notas mês a mês, limite do regime, fechamento, certificado, "
                      "o que tem pra fazer e o contato do responsável. “Entrar na empresa” continua lá pra quando for trabalhar nela."},
            {"perfil": "todos", "titulo": "A Ana de cara nova", "alvo": "marca",
             "texto": "Saiu a ilustração e ficou só o “A” da marca, no painel e nos e-mails. Clicar na marca, no topo do menu, volta pro começo."},
            {"perfil": "todos", "titulo": "WhatsApp no cadastro e no perfil", "link": "/app/conta", "alvo": "conta-whatsapp",
             "texto": "Agora o cadastro pede o seu WhatsApp, pra nossa equipe conseguir falar com você. Quem já tem conta pode informar em Minha conta › Perfil."},
            {"perfil": "empresa", "titulo": "Depois do teste grátis", "link": "/app/conta?aba=assinatura",
             "texto": "Nesta fase não há cobrança pelo painel: quando o teste termina, você pede a liberação em Minha conta › Assinatura "
                      "(um clique) e a nossa equipe autoriza o uso."},
        ],
    },
    {
        "versao": "2026.10.2",
        "data": "2026-10-08",
        "resumo": "Painel do contador, importação mais fácil de escolher e menos coisa obrigatória pra começar.",
        "itens": [
            {"perfil": "todos", "titulo": "Novidades e número da versão",
             "texto": "Esta tela: a cada atualização eu conto aqui o que mudou. O número da versão fica no rodapé do menu."},
            {"perfil": "contador", "titulo": "Painel da carteira", "link": "/app/atendimentos",
             "texto": "Em “Painel do contador”: notas e faturamento do mês de todas as empresas, o que pede atenção (certificado vencendo, "
                      "nota recusada, limite do MEI ou do Simples chegando) e o raio-x de cada uma, sem entrar em nenhuma."},
            {"perfil": "contador", "titulo": "Baixar as notas do mês de cada cliente", "link": "/app/atendimentos",
             "texto": "Um arquivo .zip com os XMLs e PDFs do mês, direto do painel. O dono da empresa vê no histórico que você baixou."},
            {"perfil": "empresa", "titulo": "Menos coisa obrigatória pra começar",
             "texto": "Dos dados da empresa, só o regime tributário é obrigatório — e eu busco na Receita pelo CNPJ. Endereço e alíquota "
                      "ficam opcionais: se deixar em branco, não trava nada."},
            {"perfil": "empresa", "titulo": "Importação: buscar, ordenar e marcar",
             "texto": "Ao trazer notas do Emissor Nacional dá pra buscar pelo nome, ordenar por valor, quantidade ou data e marcar de uma vez o que apareceu na busca."},
            {"perfil": "empresa", "titulo": "Notas em lote: guardar os arquivos é opcional", "link": "/app/nfse/lote",
             "texto": "Não vai baixar nem compartilhar agora? Marque a etapa como concluída e o mês fica fechado."},
            {"perfil": "empresa", "titulo": "Visão geral mais direta", "link": "/app",
             "texto": "Nos próximos passos, as notas do dia que vence primeiro já aparecem abertas; as dos dias seguintes ficam recolhidas. "
                      "E a linha das notas de vendedores mostra quantas já foram enviadas."},
        ],
    },
    {
        "versao": "2026.10.1",
        "data": "2026-10-07",
        "resumo": "Contador com acesso próprio, dados da empresa pelo CNPJ e desfazer importação.",
        "itens": [
            {"perfil": "empresa", "titulo": "Convide o seu contador", "link": "/app/empresa?aba=contador",
             "texto": "No menu do seu nome, “Convidar meu contador”: ele entra com o login dele e você escolhe o que ele pode fazer."},
            {"perfil": "empresa", "titulo": "Dados da empresa pelo CNPJ", "link": "/app/empresa",
             "texto": "O botão “Preencher pelo CNPJ” busca na Receita o endereço e o regime e preenche só o que estiver em branco."},
            {"perfil": "empresa", "titulo": "Desfazer uma importação",
             "texto": "Importou o extrato errado ou notas demais? Em Financeiro › Conciliação e em Empresa › Notas e e-mails tem "
                      "“Importações feitas”, com o botão Desfazer."},
            {"perfil": "empresa", "titulo": "Tela Empresa mais simples", "link": "/app/empresa",
             "texto": "De oito abas pra cinco: Dados da empresa, Notas e e-mails, Certificado, Contador e Mais opções."},
            {"perfil": "contador", "titulo": "Conta de contador, grátis", "link": "/app/atendimentos",
             "texto": "Sem CNPJ e sem mensalidade: você entra nas empresas dos clientes que te convidarem e vê as pendências de cada uma."},
            {"perfil": "contador", "titulo": "Bonificação", "link": "/app/atendimentos",
             "texto": "Você recebe uma parte da mensalidade de cada cliente que atende, enquanto atender."},
        ],
    },
]

VERSAO: str = VERSOES[0]["versao"]


def _numero(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in versao.split(".") if p.isdigit())


def para(perfis: set[str], vista: str | None = None) -> dict:
    """As versões com o que interessa a quem está logado. `vista` = a última
    versão que a pessoa já viu (pra bolinha do sino e pro passeio "o que
    mudou desde a sua última visita"). Quem nunca abriu as novidades (conta de
    antes de existir a tela) é tratado como quem viu até a penúltima: só a
    versão mais nova aparece como nova. Conta nova já nasce em dia
    (`marcar_em_dia`) — pra ela vale o tutorial normal."""
    if vista is None and len(VERSOES) > 1:
        vista = VERSOES[1]["versao"]
    quero = perfis | {"todos"}
    versoes = []
    for v in VERSOES:
        itens = [i for i in v["itens"] if i["perfil"] in quero]
        if itens:
            versoes.append({**v, "itens": itens, "nova": vista is None or _numero(v["versao"]) > _numero(vista)})
    return {"versao": VERSAO, "versoes": versoes, "novas": sum(1 for v in versoes if v["nova"])}


def marcar_em_dia(preferencias: dict | None) -> dict:
    """Preferências de quem acabou de criar a conta: nada é "novidade" pra
    quem está chegando agora."""
    return {**(preferencias or {}), "novidades": {"vista": VERSAO}}
