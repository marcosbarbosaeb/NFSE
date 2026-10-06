// Perguntas frequentes da tela de Ajuda (05/10/2026) — "vamos fazer uma
// sessão de FAQ". Mesmo conteúdo, em formato curto, do guia interno
// (backend/app/data/guia-agente-ana.md, que NÃO é público): mudou um botão ou
// uma tela, acerte nos dois lugares.
//
// Regras da casa: português simples, a Ana fala em primeira pessoa, 2 a 5
// frases por resposta, e todo botão citado entre aspas existe na tela com
// esse nome. `modulo` esconde a pergunta de quem não tem aquele produto;
// `link` só aponta pra tela que a pessoa consegue abrir (tela de um módulo
// => a pergunta leva o mesmo `modulo`).
import type { Modulo } from "./modulos"

export type TemaFaq =
  | "primeiros-passos"
  | "tomadores"
  | "gerar"
  | "recusadas"
  | "lote"
  | "envio"
  | "financeiro"
  | "visao-geral"
  | "assinatura"
  | "conta"

export interface PerguntaFaq {
  id: string
  tema: TemaFaq
  pergunta: string
  resposta: string
  /** Tela onde isso se resolve ("Ir pra essa tela"). */
  link?: string
  /** Só aparece pra quem tem este módulo ligado. */
  modulo?: Modulo
  /** A pergunta só faz sentido com os DOIS módulos (ex.: dar baixa numa nota:
   * a tela é do Financeiro, a nota é do módulo de Notas). */
  tambemModulo?: Modulo
}

/** A pessoa vê esta pergunta? (some a que fala de um módulo que ela não tem) */
export function perguntaVisivel(p: PerguntaFaq, modulos: Record<Modulo, boolean>): boolean {
  return (!p.modulo || modulos[p.modulo]) && (!p.tambemModulo || modulos[p.tambemModulo])
}

/** Os temas, na ordem em que aparecem na tela. */
export const TEMAS_FAQ: { id: TemaFaq; titulo: string }[] = [
  { id: "primeiros-passos", titulo: "Primeiros passos e certificado digital" },
  { id: "tomadores", titulo: "Tomadores" },
  { id: "gerar", titulo: "Gerar, assinar, enviar à prefeitura e ao tomador" },
  { id: "recusadas", titulo: "Notas recusadas e CEP" },
  { id: "lote", titulo: "Notas em lote e relatório da Shopee" },
  { id: "envio", titulo: "Envio da nota: e-mail, download, Google Drive" },
  { id: "financeiro", titulo: "Financeiro, Mês a mês e Conciliação" },
  { id: "visao-geral", titulo: "Anotações e Visão geral" },
  { id: "assinatura", titulo: "Assinatura, planos e módulos" },
  { id: "conta", titulo: "Conta, segurança e suporte" },
]

export const FAQ: PerguntaFaq[] = [
  // --- Primeiros passos e certificado digital ---------------------------------
  {
    id: "o-que-e-a-ana",
    tema: "primeiros-passos",
    pergunta: "O que a Ana faz por mim?",
    resposta:
      "Eu tenho dois produtos, que você pode ter juntos ou separados. No de Notas, eu gero, assino, envio à prefeitura e entrego ao tomador as suas notas fiscais de serviço (NFS-e). No Financeiro, eu controlo o que entrou, o que saiu e o que sobrou, e confiro se cada nota foi paga. No menu aparecem só as telas dos módulos que a sua empresa tem ligados.",
    link: "/app",
  },
  {
    id: "minha-cidade",
    tema: "primeiros-passos",
    pergunta: "A Ana emite nota em qualquer cidade?",
    resposta:
      "Eu emito pelo Emissor Nacional da NFS-e, então depende de a prefeitura da sua cidade usar esse emissor. Eu confiro isso no cadastro, assim que você informa o CNPJ. Se a sua prefeitura ainda usa um sistema próprio de nota, eu ainda não consigo emitir por lá. O Financeiro funciona em qualquer cidade.",
    modulo: "emissor",
  },
  {
    id: "certificado-o-que-e",
    tema: "primeiros-passos",
    pergunta: "O que é o certificado digital A1 e por que eu preciso dele?",
    resposta:
      "É o arquivo com que eu assino as notas em nome da sua empresa — o mesmo que o contador costuma usar. Sem ele eu não consigo assinar nem enviar nota à prefeitura. Ele fica guardado de forma criptografada.",
    link: "/app/empresa?aba=certificado",
    modulo: "emissor",
  },
  {
    id: "certificado-enviar",
    tema: "primeiros-passos",
    pergunta: "Como envio ou troco o certificado digital?",
    resposta:
      "Abra Empresa, aba “Certificado”. Escolha o arquivo (termina em .pfx), digite a senha do certificado e clique em “Enviar certificado”. A tela mostra a validade e avisa quando ele estiver “Vencido”. Pra trocar por um novo é o mesmo caminho: o botão passa a se chamar “Substituir certificado”.",
    link: "/app/empresa?aba=certificado",
    modulo: "emissor",
  },
  {
    id: "importar-nacional",
    tema: "primeiros-passos",
    pergunta: "Já emito pelo Emissor Nacional. Dá pra trazer minhas notas e meus tomadores?",
    resposta:
      "Dá. Primeiro cadastre os seus tomadores (os mais comuns já vêm pré-cadastrados). Depois, em Empresa, aba “Notas”, use “Importar do Emissor Nacional”: com o certificado da empresa eu leio as notas que ela já emitiu e você escolhe de quais tomadores trazer — já vêm marcados só os que você tem e os pré-cadastrados; o resto fica em “Não importar” até você escolher. É só leitura: nada é enviado à prefeitura nem aos tomadores.",
    link: "/app/empresa?aba=notas",
    modulo: "emissor",
  },
  {
    id: "notas-de-teste",
    tema: "primeiros-passos",
    pergunta: "Posso testar sem emitir nota de verdade?",
    resposta:
      "Pode. Em Empresa, aba “Notas”, ligue “Gerar notas de teste (homologação)”. Enquanto estiver ligado, as notas novas vão pro ambiente de teste da Receita e não valem como nota fiscal. Lembre de desligar pra voltar a emitir de verdade — eu aviso na tela de gerar nota quando a conta está em teste.",
    link: "/app/empresa?aba=notas",
    modulo: "emissor",
  },

  // --- Tomadores --------------------------------------------------------------
  {
    id: "tomador-cadastrar",
    tema: "tomadores",
    pergunta: "Como cadastro um tomador?",
    resposta:
      "Em Tomadores, clique em “Adicionar tomador”. O jeito mais fácil é “Enviar uma nota antiga” desse cliente (o PDF ou o XML): eu preencho o cadastro inteiro e você só confere. Sem nota antiga, use “Digitar o CNPJ” que eu busco o nome e o endereço, ou “Escolher do catálogo”. No fim, clique em “Cadastrar tomador”.",
    link: "/app/tomadores/novo",
    modulo: "emissor",
  },
  {
    id: "codigo-do-servico",
    tema: "tomadores",
    pergunta: "Que “Código do serviço” eu coloco?",
    resposta:
      "É o tipo de serviço que você presta, pela lista nacional. No campo, busque por número ou por palavra (por exemplo, “publicidade”) — só vale código da lista oficial. Afiliados costumam usar 17.06.01 (propaganda e publicidade), mas confirme com seu contador qual é o seu.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "descricao-muda-sozinha",
    tema: "tomadores",
    pergunta: "Como faço o mês mudar sozinho na descrição da nota?",
    resposta:
      "Na ficha do tomador, em “O que vai escrito na nota”, escreva o texto e marque “Colocar o mês e o ano no fim do texto”. Aí escolha “Qual mês aparece?” (o da nota, o anterior...) e como ele é escrito. Embaixo eu mostro a prévia de como vai sair. Se precisar de algo diferente, use “Preciso de um texto diferente (escrever livre)”.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "dia-de-gerar",
    tema: "tomadores",
    pergunta: "Pra que serve a coluna “Dia” na lista de tomadores?",
    resposta:
      "É o dia do mês em que você costuma gerar a nota de cada tomador. Digite o número ali mesmo: ele vira lembrete no Calendário e a lista fica nessa ordem. Na coluna “Neste mês” eu mostro “Gerar hoje” quando chega o dia e “Não gerada” quando passou — aí é só clicar em “Gerar” na mesma linha.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "inativo-ou-excluido",
    tema: "tomadores",
    pergunta: "Qual a diferença entre desativar e excluir um tomador?",
    resposta:
      "Desligar “Ativo” é pra quem você parou de faturar por um tempo: ele vai pro fim da lista, sem perder nada. Excluir (a lixeira) tira o tomador da sua lista e do calendário. Nos dois casos, as notas já geradas pra ele continuam guardadas na tela NFS-e.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "sem-nota",
    tema: "tomadores",
    pergunta: "O que quer dizer o selo “Sem nota” num cliente?",
    resposta:
      "Que você só controla o que esse cliente te paga e não emite nota pra ele por aqui — acontece, por exemplo, quando ele foi criado ao lançar um recebimento. Pra passar a emitir, clique em “Emitir nota pra este cliente”: primeiro você me diz quem ele é (o CNPJ) e depois confere como a nota sai. Nada do que você já lançou sai do lugar.",
    link: "/app/tomadores",
    modulo: "emissor",
    tambemModulo: "financeiro",
  },
  {
    id: "empresa-de-fora",
    tema: "tomadores",
    pergunta: "Quem me paga é uma empresa de fora do Brasil, sem CNPJ. Dá pra emitir nota?",
    resposta:
      "Dá. No passo “Quem é este cliente?” (que abre em “Emitir nota pra este cliente”), escolha “Empresa de fora do Brasil” e informe o nome, o país e o NIF — o número fiscal dela no país de origem, que vem no contrato ou no extrato de pagamento. A nota sai com a identificação estrangeira e o país. Na primeira vez, confirme com seu contador.",
    link: "/app/tomadores",
    modulo: "emissor",
    tambemModulo: "financeiro",
  },

  // --- Gerar, assinar, enviar -------------------------------------------------
  {
    id: "etapas-da-nota",
    tema: "gerar",
    pergunta: "Quais são as etapas de uma nota?",
    resposta:
      "São quatro: gerar, assinar com o certificado, enviar à prefeitura (que autoriza ou recusa) e entregar ao tomador. Só depois de autorizada ela é uma nota fiscal de verdade. Na lista de NFS-e, as colunas “Assinatura”, “Prefeitura” e “Tomador” mostram em que pé cada nota está — clique no selo pra fazer aquele passo.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "gerar-nota",
    tema: "gerar",
    pergunta: "Como gero uma nota?",
    resposta:
      "Na tela NFS-e, clique em “Nova emissão”. Escolha o tomador, confira a data de competência e informe o valor. A alíquota já vem preenchida com a referência de Empresa — confira antes de gerar. Também dá pra clicar em “Gerar” na linha do tomador, na tela Tomadores.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "fazer-tudo",
    tema: "gerar",
    pergunta: "Dá pra gerar, assinar, enviar à prefeitura e mandar pro tomador de uma vez só?",
    resposta:
      "Dá. Na janela “Nova emissão”, em “Ao gerar, a Ana também”, marque as três opções: o botão vira “Gerar e fazer tudo” e eu faço a sequência inteira. Sua escolha fica guardada pra próxima nota. Se um passo falhar, eu paro ali e mostro o motivo.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "conferencia-antes",
    tema: "gerar",
    pergunta: "A Ana confere a nota antes de gerar?",
    resposta:
      "Confiro. Assim que você digita o valor, eu olho os dados do tomador, da empresa e da nota. O que está em vermelho precisa ser corrigido antes (a nota sairia errada) e eu mostro como resolver. O que está em amarelo é só pra você olhar: marque “Conferi e está certo, pode gerar” pra continuar.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "nota-duplicada",
    tema: "gerar",
    pergunta: "Apareceu um aviso de que já existe nota desse tomador no mês. O que eu faço?",
    resposta:
      "Se a nota que existe ainda não foi enviada, você pode continuar por ela (“Abrir a nota que já existe”) ou marcar “Apagar a que não foi enviada e gerar esta no lugar”. Se ela já foi emitida, pra gerar outra é preciso escolher uma data de competência de outro mês.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "baixar-pdf-xml",
    tema: "gerar",
    pergunta: "Como baixo o PDF e o XML de uma nota?",
    resposta:
      "Na lista de NFS-e, a coluna “Arquivos” tem os botões de baixar o PDF e o XML. O PDF sai depois que a prefeitura autoriza a nota. Pra baixar várias de uma vez, marque as notas e clique em “Baixar arquivos (.zip)” — até 250 por vez, ou o mês inteiro se você filtrar o mês e selecionar todas.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "cancelar-ou-apagar",
    tema: "gerar",
    pergunta: "Como cancelo ou apago uma nota?",
    resposta:
      "Depende da etapa. Enquanto a nota não foi autorizada pela prefeitura, abra a nota e use “Apagar nota”: ela some da lista. Depois de autorizada, só dá pra cancelar: clique em “Cancelar nota”, escolha o motivo e escreva a justificativa (de 15 a 255 letras). O cancelamento vai pra Receita e, se aceito, não pode ser desfeito.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "calendario",
    tema: "gerar",
    pergunta: "Pra que serve o Calendário?",
    resposta:
      "Ele mostra os dias de gerar cada nota e os lembretes que você criar. Clique num dia (ou em “Novo evento”) pra criar um lembrete. Clique num aviso pra ajustar: em “Só esta vez” você muda a data só daquele mês; em “Mudar a regra” você muda o dia de todos os meses.",
    link: "/app/calendario",
    modulo: "emissor",
  },

  // --- Notas recusadas e CEP --------------------------------------------------
  {
    id: "nota-recusada",
    tema: "recusadas",
    pergunta: "A prefeitura recusou a minha nota. E agora?",
    resposta:
      "Calma, nada se perde: a nota fica com o selo “Recusada” e eu mostro por que foi recusada. Se eu sei consertar sozinha, aparece o botão “Corrigir e reenviar”. Se precisa de você, corrija o que a prefeitura apontou (no cadastro do tomador, por exemplo) e use “Tentar submeter de novo” na página da nota. Na tela NFS-e, o cartão “Ainda não autorizadas” mostra só as notas que estão esperando.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "recusa-por-cep",
    tema: "recusadas",
    pergunta: "A nota foi recusada por causa do CEP. Como resolvo?",
    resposta:
      "Clique em “Corrigir e reenviar”. Eu uso o endereço que está no cadastro do tomador — ou, se ele não mudou, procuro o CEP certo pelo endereço —, assino de novo e envio à prefeitura. O número da nota não muda. Se você souber o endereço certo, corrija antes no cadastro do tomador.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "corrigir-endereco",
    tema: "recusadas",
    pergunta: "Como corrijo o endereço ou o CEP de um tomador?",
    resposta:
      "Abra a ficha do tomador e, em “Dados do tomador”, clique em “Editar nome e endereço”. Eu ajudo de três jeitos: “Puxar os dados da Receita”, preencher a rua quando você digita o CEP, ou “Achar o CEP pelo endereço”. No fim, clique em “Salvar dados do tomador”. Vale pras próximas notas — e pra nota recusada, se você clicar em “Corrigir e reenviar” nela.",
    link: "/app/tomadores",
    modulo: "emissor",
  },

  // --- Notas em lote / Shopee -------------------------------------------------
  {
    id: "lote-pra-que",
    tema: "lote",
    pergunta: "Pra que serve a tela “Notas em lote”?",
    resposta:
      "É pra quem emite muitas notas de uma vez a partir de um relatório — como as comissões da Shopee, em que sai uma nota pra cada vendedor. Essas notas ficam nessa tela, separadas da lista de NFS-e e da Visão geral. O botão “Enviar relatório da Shopee” aparece quando a Shopee está cadastrada como tomador.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "shopee-relatorio",
    tema: "lote",
    pergunta: "Como envio o relatório da Shopee?",
    resposta:
      "No painel de afiliados da Shopee, baixe o relatório mensal de comissões (um arquivo .csv). Em Notas em lote, clique em “Enviar relatório da Shopee”, escolha o arquivo e clique em “Ler relatório”. Eu mostro o resumo do mês pra você conferir com o painel da Shopee. Em “Depois de gerar, a Ana também”, marque o que eu devo fazer na sequência e clique no botão de gerar.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "lote-pagina-aberta",
    tema: "lote",
    pergunta: "Preciso ficar com a página aberta enquanto as notas em lote são feitas?",
    resposta:
      "Não. Depois do seu OK eu trabalho em segundo plano, uma nota por vez, e você pode fechar a página. Quando acabar, eu deixo um relatório em Notas em lote (em “Últimos processamentos”, botão “Ver relatório”) e mando por e-mail.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "lote-continuar",
    tema: "lote",
    pergunta: "O lote parou no meio ou teve falhas. Como continuo?",
    resposta:
      "No “Passo a passo” do mês, clique em “Continuar de onde parou”: eu faço em sequência só o que falta. Se o lote aparecer como “Interrompido”, use “Retomar”. Se terminou com falhas, use “Refazer falhas” — o relatório mostra, nota por nota, o que aconteceu.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "limite-de-emails",
    tema: "lote",
    pergunta: "Apareceu “Esperando o limite de e-mails”. Deu erro?",
    resposta:
      "Não é falha. O serviço de e-mail tem um limite de envios, e o lote bateu nele. Eu continuo sozinha assim que o limite voltar — você não precisa fazer nada. As notas já estão autorizadas pela prefeitura.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "vendedor-sem-email",
    tema: "lote",
    pergunta: "Alguns vendedores aparecem “sem e-mail”. Preciso fazer alguma coisa?",
    resposta:
      "Não é pendência sua: o vendedor não informou e-mail no relatório, então a nota dele não tem como ser enviada. A situação do mês fica regular do mesmo jeito. Se o vendedor te passar o e-mail, abra a nota e envie por lá.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },
  {
    id: "arquivos-do-mes",
    tema: "lote",
    pergunta: "Como guardo todos os arquivos do mês (zip, e-mail ou Google Drive)?",
    resposta:
      "Em Notas em lote, depois que as notas são autorizadas, aparece “Arquivos do mês”. Escolha o que vai no pacote (PDF e XML, só PDF ou só XML) e use “Baixar (.zip)” ou “Mandar por e-mail” (um e-mail só, com o .zip, pro contador ou pra você). Quando a integração com o Google está disponível, aparece também “Guardar no Google Drive”: os arquivos vão pra pasta “Agente Ana”.",
    link: "/app/nfse/lote",
    modulo: "emissor",
  },

  // --- Envio da nota ----------------------------------------------------------
  {
    id: "drive-por-tomador",
    tema: "envio",
    pergunta: "Dá pra guardar as notas no meu Google Drive automaticamente?",
    resposta:
      "Dá, quando a integração com o Google está disponível. Na ficha do tomador, em “Como este tomador recebe a nota”, marque “Guardar no meu Google Drive” (pode marcar junto com e-mail e as outras formas). Quando a prefeitura autorizar a nota, eu guardo o PDF e o XML numa pasta do seu Drive: Agente Ana › nome do tomador › mês. Pra uma nota só, abra a nota e use “Guardar no Google Drive”. Eu só enxergo a pasta que eu mesma crio lá.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "formas-de-envio",
    tema: "envio",
    pergunta: "De que jeitos eu posso entregar a nota ao tomador?",
    resposta:
      "Na ficha do tomador, em “Envio da nota”, marque como ele recebe: “E-mail” (eu mando com o PDF e o XML em anexo), “WhatsApp”, “Portal do tomador” ou “Baixar o PDF ao finalizar”. Pode marcar mais de uma. Nada marcado quer dizer que ele não precisa receber a nota, e ela não aparece como pendente de envio.",
    link: "/app/tomadores",
    modulo: "emissor",
  },
  {
    id: "texto-do-email",
    tema: "envio",
    pergunta: "Como mudo o texto do e-mail que vai com a nota?",
    resposta:
      "Pra todos os tomadores: Empresa, aba “E-mails”, bloco “E-mail para o tomador” — mude e clique em “Salvar modelo”. Pra um tomador só: na ficha dele, abra “Mudar o texto do e-mail deste tomador”. E na hora de enviar cada nota dá pra editar o assunto e a mensagem antes de clicar em “Enviar e-mail”.",
    link: "/app/empresa?aba=emails",
    modulo: "emissor",
  },
  {
    id: "copia-pro-contador",
    tema: "envio",
    pergunta: "Como mando a nota também pro meu contador?",
    resposta:
      "Tem três jeitos. Em Empresa, aba “E-mails”, o campo “Sempre mandar cópia para” põe alguém em cópia de todo e-mail de nota. Na ficha de um tomador, “Outras pessoas que recebem esta nota” manda um e-mail separado pra cada pessoa. E no envio de cada nota, a aba “Contador/geral” manda pros seus “E-mails gerais” — esse não conta como nota enviada ao tomador.",
    link: "/app/empresa?aba=emails",
    modulo: "emissor",
  },
  {
    id: "whatsapp",
    tema: "envio",
    pergunta: "Como envio a nota pelo WhatsApp?",
    resposta:
      "Clique no selo da coluna “Tomador” (ou vá em “Envio desta nota”, na página da nota) e abra a aba “WhatsApp”. Confira o número e a mensagem e clique em “Abrir WhatsApp”: eu abro a conversa com o texto e o link da nota, e você só aperta enviar. Ao abrir, a nota fica marcada como enviada.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "envio-falhou",
    tema: "envio",
    pergunta: "O envio pro tomador falhou. Como tento de novo?",
    resposta:
      "O selo da coluna “Tomador” fica “Falhou”. Clique nele pra tentar de novo — dá pra trocar pro WhatsApp na hora. Com um tomador e um mês filtrados na lista, o botão “Reenviar falhas” manda de novo todas as que falharam. Na página da nota, o “Histórico de envios” mostra pra quem foi cada envio e se deu certo.",
    link: "/app/nfse",
    modulo: "emissor",
  },
  {
    id: "enviar-todas",
    tema: "envio",
    pergunta: "Como mando várias notas por e-mail de uma vez sem repetir as que já foram?",
    resposta:
      "Marque as notas na lista e clique em “Enviar ao tomador por e-mail” — ou filtre um tomador e um mês e use “Enviar todas por e-mail”. Eu não mando de novo uma nota que já foi entregue. Se quiser reenviar mesmo assim, marque “Incluir as já enviadas (reenviar)” na confirmação.",
    link: "/app/nfse",
    modulo: "emissor",
  },

  // --- Financeiro, Mês a mês e Conciliação -----------------------------------
  {
    id: "registrar-recebimento",
    tema: "financeiro",
    pergunta: "Como registro um dinheiro que entrou?",
    resposta:
      "No Financeiro, clique em “Recebimento”. Escolha de quem veio (dá pra criar um cliente novo ali mesmo, só com o nome), o valor e a data. Se o dinheiro paga uma nota, escolha a nota: ela fica como paga. Se você importa o extrato do banco, eu faço esses lançamentos pra você conferir.",
    link: "/app/financeiro",
    modulo: "financeiro",
  },
  {
    id: "despesa-ou-retirada",
    tema: "financeiro",
    pergunta: "Qual a diferença entre despesa e retirada?",
    resposta:
      "Despesa é o que a empresa gasta (impostos, ferramentas, cartão). Retirada é a distribuição de lucros: ela não entra nas despesas, sai do lucro que sobrou (o “saldo a distribuir”). Pra lançar qualquer uma das duas, clique em “Despesa” no Financeiro e escolha o tipo.",
    link: "/app/financeiro",
    modulo: "financeiro",
  },
  {
    id: "contas-recorrentes",
    tema: "financeiro",
    pergunta: "Como faço as contas de todo mês aparecerem sozinhas?",
    resposta:
      "No card “Contas do mês”, clique em “Contas recorrentes” e cadastre cada uma (pró-labore, Simples, cartão, ferramentas) com nome, valor e dia do vencimento. Cada conta recorrente aparece todo mês em “Contas do mês”, pra você ticar quando pagar. Se o valor varia, deixe em branco: na hora de ticar eu pergunto quanto foi pago.",
    link: "/app/financeiro",
    modulo: "financeiro",
  },
  {
    id: "importar-extrato",
    tema: "financeiro",
    pergunta: "Como importo o extrato do banco?",
    resposta:
      "Clique em “Importar extrato” e envie o arquivo em PDF, OFX ou CSV — no app do banco, “exportar OFX” é o que funciona melhor. Eu leio as transações, separo o que entrou do que saiu e já sugiro de quem é cada uma; você confere antes de gravar. Suas escolhas ficam lembradas pro próximo extrato, e o que você não classificar na hora fica guardado na Conciliação.",
    link: "/app/financeiro",
    modulo: "financeiro",
  },
  {
    id: "conciliacao-o-que-e",
    tema: "financeiro",
    pergunta: "O que é a Conciliação?",
    resposta:
      "São duas conferências. Em “As notas foram pagas?”, eu confiro cada nota emitida com o dinheiro que entrou (precisa do módulo de Notas). Em “O extrato do banco está todo classificado?”, cada linha do banco vira um recebimento ou uma despesa. O “Fechamento do mês” junta as duas: o mês fecha quando está tudo conferido.",
    link: "/app/financeiro/conciliacao",
    modulo: "financeiro",
  },
  {
    id: "dar-baixa",
    tema: "financeiro",
    pergunta: "Como dou baixa numa nota que foi paga?",
    resposta:
      "Na Conciliação, em “As notas foram pagas?”, abra a linha da nota. Use “Registrar o recebimento” (valor e data em que caiu, depois “Dar baixa”) ou “Ligar a um lançamento do extrato”. Quando eu acho no extrato uma entrada que parece o pagamento, eu pergunto e você só confirma. Pra voltar atrás, “Desfazer a baixa”.",
    link: "/app/financeiro/conciliacao?parte=notas",
    modulo: "financeiro",
    tambemModulo: "emissor",
  },
  {
    id: "pagamento-com-diferenca",
    tema: "financeiro",
    pergunta: "O cliente pagou um valor diferente do da nota. O que eu faço?",
    resposta:
      "Dê baixa com o valor que realmente caiu: eu mostro a diferença e a nota aparece no filtro “Com diferença”. Se a diferença é esperada (imposto retido pelo cliente, por exemplo), clique em “A diferença está certa (ex.: imposto retido)” e eu paro de avisar.",
    link: "/app/financeiro/conciliacao?parte=notas",
    modulo: "financeiro",
    tambemModulo: "emissor",
  },
  {
    id: "classificar-extrato",
    tema: "financeiro",
    pergunta: "Sobraram linhas do extrato sem classificar. Como resolvo?",
    resposta:
      "Na Conciliação, em “O extrato do banco está todo classificado?”, escolha um lançamento à esquerda e, à direita, a nota ou a conta que ele paga. Se não é de nenhuma, escolha o cliente (ou a categoria) e clique em “Lançar”. Transferência entre contas suas não é receita nem despesa: use “Ignorar (não é receita nem despesa)”.",
    link: "/app/financeiro/conciliacao?parte=extrato",
    modulo: "financeiro",
  },
  {
    id: "mes-a-mes",
    tema: "financeiro",
    pergunta: "Como vejo quanto um cliente me pagou mês a mês, ou quanto gastei com uma coisa?",
    resposta:
      "No Financeiro, card “Resultado do ano”, a tabela “Mês a mês” mostra cada linha de dinheiro por mês. Clique na seta de uma linha pra abrir o detalhe: quem pagou (por cliente) ou com o que você gastou (por categoria). A busca “Buscar cliente ou gasto…” acha direto.",
    link: "/app/financeiro",
    modulo: "financeiro",
  },

  // --- Anotações e Visão geral -----------------------------------------------
  {
    id: "visao-geral",
    tema: "visao-geral",
    pergunta: "O que aparece na Visão geral?",
    resposta:
      "O mês de relance, com um card pra cada assunto dos módulos que você tem ligados: notas emitidas e a gerar, o que precisa da sua atenção, os próximos passos e o dinheiro do mês. As setas ao lado do nome do mês trocam o mês. Os “Atalhos rápidos” levam pras ações mais usadas.",
    link: "/app",
  },
  {
    id: "editar-disposicao",
    tema: "visao-geral",
    pergunta: "Como mudo a ordem dos cards ou escondo o que não uso?",
    resposta:
      "Na Visão geral (e no Financeiro), clique em “Editar disposição”. Cada card ganha uma barra pra arrastar, trocar a largura, recolher ou esconder. Os escondidos ficam em “Blocos escondidos”, no fim da página — toque num deles pra voltar. Quando terminar, clique em “Concluir”; fica salvo na sua conta. “Voltar ao padrão” desfaz tudo.",
    link: "/app",
  },
  {
    id: "anotacoes",
    tema: "visao-geral",
    pergunta: "Como crio uma anotação?",
    resposta:
      "Clique em “Nova anotação” e escolha o formato: “Texto” (bloco de notas), “Lista” (itens pra ir marcando) ou “Tabela” (colunas, datas e valores somados no fim). Cada anotação vira um card e tudo salva sozinho. Dá pra mudar o nome, trocar o formato depois e apagar.",
    link: "/app",
  },

  // --- Assinatura, planos e módulos ------------------------------------------
  {
    id: "periodo-de-teste",
    tema: "assinatura",
    pergunta: "Como funciona o período de teste?",
    resposta:
      "A conta nova começa com um período de teste gratuito, sem precisar cadastrar cartão. Em Minha conta, aba “Assinatura”, eu mostro quantos dias restam. Quando o teste acabar, é só escolher um plano ali mesmo pra continuar gerando notas e lançando.",
    link: "/app/conta?aba=assinatura",
  },
  {
    id: "teste-acabou",
    tema: "assinatura",
    pergunta: "Meu teste acabou. Perdi minhas notas e meus dados?",
    resposta:
      "Não. Nada é apagado: você continua entrando, vendo e baixando tudo o que já está na conta. O que para é gerar e enviar notas e fazer lançamentos novos. Pra voltar a usar tudo, escolha um plano em Minha conta, aba “Assinatura”.",
    link: "/app/conta?aba=assinatura",
  },
  {
    id: "planos",
    tema: "assinatura",
    pergunta: "Quais são os planos?",
    resposta:
      "São três: “Notas” (emissão de NFS-e, tomadores, envio e calendário), “Financeiro” (recebimentos, contas do mês, conciliação e resultado) e “Notas + Financeiro” (tudo junto: a nota emitida já vira conta a receber). O valor de cada um aparece em Minha conta, aba “Assinatura”. Pra assinar, clique em “Assinar este”.",
    link: "/app/conta?aba=assinatura",
  },
  {
    id: "mudar-plano-cancelar",
    tema: "assinatura",
    pergunta: "Como mudo de plano, troco o cartão ou cancelo?",
    resposta:
      "Em Minha conta, aba “Assinatura”. Pra mudar de plano, clique em “Mudar pra este” no plano novo e confirme — a diferença entra proporcional na próxima fatura e nada é apagado. Pra trocar o cartão, ver faturas ou cancelar, clique em “Forma de pagamento, faturas e cancelamento”.",
    link: "/app/conta?aba=assinatura",
  },
  {
    id: "modulos",
    tema: "assinatura",
    pergunta: "Como ligo ou desligo um módulo? Perco meus dados?",
    resposta:
      "Em Empresa, aba “Módulos”. Desligar um módulo só esconde as telas dele: nada é apagado, e tudo volta quando ele for ligado de novo. Com plano pago, os módulos vêm do plano que você assina — aí, pra mudar, troque o plano em Minha conta, aba “Assinatura”.",
    link: "/app/empresa?aba=modulos",
  },
  {
    id: "indique-e-ganhe",
    tema: "assinatura",
    pergunta: "Como funciona o “Indique e ganhe”?",
    resposta:
      "Em Minha conta, aba “Indique e ganhe”, fica o seu link de indicação. Cada pessoa que assinar pelo seu link vale desconto na sua mensalidade, enquanto ela continuar assinante. A tela mostra o seu desconto, quanto falta pra zerar a mensalidade e quem veio pelo seu link.",
    link: "/app/conta?aba=indique",
  },

  // --- Conta, segurança e suporte --------------------------------------------
  {
    id: "contador-convidar",
    tema: "conta",
    pergunta: "Como dou acesso ao meu contador?",
    resposta:
      "Em Empresa, aba “Contador”. Digite o e-mail dele, marque o que ele pode fazer e clique em “Enviar convite”. Ele entra com o login dele — você não passa a sua senha pra ninguém. Ver as notas e o financeiro é sempre liberado; gerar notas, enviar, cuidar dos tomadores, lançar no financeiro e mexer nos dados da empresa, só o que você marcar.",
    link: "/app/empresa?aba=contador",
  },
  {
    id: "contador-mudar",
    tema: "conta",
    pergunta: "Posso mudar o que o contador faz ou tirar o acesso dele?",
    resposta:
      "Pode, quando quiser, em Empresa, aba “Contador”: marque ou desmarque as permissões (vale na hora) ou clique na lixeira pra tirar o acesso. Ali também fica a lista “O que o contador fez”. A assinatura, os módulos e apagar a empresa ficam sempre só com você.",
    link: "/app/empresa?aba=contador",
  },
  {
    id: "contador-atender",
    tema: "conta",
    pergunta: "Sou contador. Como entro na empresa de um cliente?",
    resposta:
      "Peça pro cliente te convidar pelo seu e-mail em Empresa, aba “Contador”. O convite aparece em “Empresas que atendo”, no menu: clique em “Aceitar” e depois em “Abrir empresa”. As empresas dos clientes também ficam no seletor de empresas, no topo do menu, separadas das suas.",
    link: "/app/atendimentos",
  },
  {
    id: "esqueci-a-senha",
    tema: "conta",
    pergunta: "Esqueci a senha. Como eu entro?",
    resposta:
      "Na tela de login, use “Entrar com código por e-mail”. Eu mando um código de 6 dígitos pro seu e-mail, válido por 10 minutos, e você entra sem precisar da senha. Também dá pra entrar com o Google, se a conta estiver conectada.",
  },
  {
    id: "trocar-senha",
    tema: "conta",
    pergunta: "Como troco a minha senha?",
    resposta:
      "Em Minha conta, aba “Acesso e segurança”, clique em “Trocar senha”. Informe a senha atual e a nova (pelo menos 8 caracteres). Trocar a senha desconecta os outros aparelhos em que você estiver logado. Na mesma aba, “Dispositivos conectados” mostra onde a sua conta está aberta.",
    link: "/app/conta?aba=autenticacao",
  },
  {
    id: "mais-de-uma-empresa",
    tema: "conta",
    pergunta: "Tenho mais de um CNPJ. Preciso de outro login?",
    resposta:
      "Não. No topo do menu, clique no seletor “Empresa” e depois em “Adicionar empresa”. Dá pra “Importar do Emissor Nacional” (com o certificado, eu trago o cadastro, os tomadores e as notas) ou “Cadastrar do zero”. Cada empresa tem seus próprios tomadores, notas e certificado, e você troca entre elas no mesmo seletor.",
  },
  {
    id: "limpar-ou-excluir",
    tema: "conta",
    pergunta: "Como apago dados de teste, ou excluo a empresa ou a conta?",
    resposta:
      "Em Empresa, aba “Limpar e excluir”: “Limpar dados” apaga por categoria (útil pra tirar testes) e “Excluir esta empresa” apaga a empresa inteira. Pra apagar o seu login, vá em Minha conta, aba “Perfil”, “Excluir minha conta”. Nada disso tem como desfazer. As notas já emitidas de verdade continuam válidas na Receita.",
    link: "/app/empresa?aba=dados",
  },
  {
    id: "seguranca-dos-dados",
    tema: "conta",
    pergunta: "Meus dados e meu certificado ficam seguros?",
    resposta:
      "Cada conta só enxerga os próprios dados, e senhas e certificados ficam guardados de forma criptografada. Do seu lado, vale o cuidado de sempre: não passe a sua senha nem o arquivo do certificado pra ninguém — nem pra ferramentas de IA de terceiros.",
  },
  {
    id: "falar-com-suporte",
    tema: "conta",
    pergunta: "Como falo com uma pessoa do suporte?",
    resposta:
      "Use o botão “Falar com o suporte”, no fim desta página, ou o link “Precisa de ajuda? Fale com o suporte”, no menu. Escreva o assunto e a mensagem e clique em “Enviar”. A resposta chega no seu e-mail, normalmente no mesmo dia útil.",
  },
]
