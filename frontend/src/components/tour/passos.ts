// Dicas de cada tela do emissor (ver lib/tutorial.ts). `alvo` é o valor de
// um atributo data-tour="..." na tela; sem alvo (ou se o elemento não
// estiver na tela), a dica aparece centralizada.

export interface PassoTour {
  alvo?: string
  titulo: string
  texto: string
}

export interface TourDaTela {
  tela: string
  passos: PassoTour[]
}

export function tourDoCaminho(caminho: string): TourDaTela | null {
  const c = caminho.replace(/\/+$/, "") || "/"
  if (c === "/app") return { tela: "visao-geral", passos: VISAO_GERAL }
  if (c === "/app/tomadores") return { tela: "tomadores", passos: TOMADORES }
  if (c === "/app/tomadores/novo") return { tela: "tomador-novo", passos: TOMADOR_NOVO }
  if (c === "/app/nfse") return { tela: "nfse", passos: NFSE }
  if (c === "/app/calendario") return { tela: "calendario", passos: CALENDARIO }
  if (c === "/app/financeiro") return { tela: "financeiro", passos: FINANCEIRO }
  if (c === "/app/empresa") return { tela: "empresa", passos: EMPRESA }
  if (c === "/app/conta") return { tela: "conta", passos: CONTA }
  return null
}

const VISAO_GERAL: PassoTour[] = [
  {
    titulo: "Oi! Eu sou a Ana.",
    texto:
      "Vou te mostrar rapidinho o que dá pra fazer em cada tela, na primeira vez que você entrar nela. Pode pular quando quiser.",
  },
  {
    alvo: "menu",
    titulo: "Suas abas",
    texto:
      "Cada módulo tem o seu grupo: em Notas ficam a visão geral, as NFS-e, os tomadores e o calendário; em Financeiro, o painel e a conciliação. Em Empresa ficam os dados comuns e os módulos ligados.",
  },
  {
    titulo: "Visão geral",
    texto: "Aqui você vê o mês de relance: o que já foi emitido, o que falta gerar, quanto você faturou e o que precisa da sua atenção.",
  },
  {
    alvo: "ajuda",
    titulo: "Rever as dicas",
    texto: "Esqueceu alguma coisa? Clique aqui pra ver de novo as dicas da tela em que você estiver. Dá pra desligar em Minha conta › Preferências.",
  },
]

const TOMADORES: PassoTour[] = [
  {
    alvo: "tomadores-adicionar",
    titulo: "Cadastre cada tomador uma vez",
    texto: "Digite o CNPJ e eu puxo razão social e endereço. Se ele já estiver no catálogo, eu sugiro código de serviço, descrição e dia.",
  },
  {
    alvo: "tomadores-progresso",
    titulo: "O que já foi gerado",
    texto: "Quantas notas do mês já saíram. Troque o mês pra conferir meses anteriores.",
  },
  {
    alvo: "tomadores-dia",
    titulo: "Dia de gerar a nota",
    texto: "Digite o dia do mês de cada tomador. Ele vira lembrete no Calendário e a lista fica nessa ordem.",
  },
  {
    alvo: "tomadores-situacao",
    titulo: "Gerado ou não",
    texto: "Verde: nota gerada (clique pra abrir). Vermelho: passou do dia e ainda não gerou — use o botão Gerar na mesma linha.",
  },
  {
    alvo: "tomadores-ativo",
    titulo: "Ativo, inativo ou excluído",
    texto: "Parou de faturar alguém por um tempo? Desligue aqui: ele vai pro fim da lista, sem perder nada. Pra tirar de vez, use a lixeira.",
  },
]

const TOMADOR_NOVO: PassoTour[] = [
  {
    titulo: "Dois jeitos de adicionar",
    texto:
      "Use um tomador que já está no catálogo (eu trago a sugestão de preenchimento com o que já foi usado com ele) ou cadastre um novo só com o CNPJ.",
  },
  {
    alvo: "form-codigo",
    titulo: "Código do serviço",
    texto: "Busque por número ou por palavra (ex.: publicidade). Só vale código da lista oficial da NFS-e, então não tem como errar o formato.",
  },
  {
    alvo: "form-descricao",
    titulo: "Descrição que muda sozinha",
    texto: "O mês e o ano se atualizam todo mês. Embaixo aparece a prévia de como a descrição vai sair na nota.",
  },
]

const NFSE: PassoTour[] = [
  {
    alvo: "nfse-nova",
    titulo: "Gerar uma nota",
    texto: "Escolha o tomador, confira o mês e o valor. Na hora você decide como informar o valor: digitando ou por planilha.",
  },
  {
    alvo: "nfse-csv",
    titulo: "Várias notas de uma vez",
    texto: "Tem muitos tomadores? Importe uma planilha CSV e eu gero todas as notas do mês de uma vez.",
  },
  {
    titulo: "Depois de gerar",
    texto: "Clique em uma nota da lista pra revisar, assinar, enviar à Receita e mandar pro tomador por e-mail ou WhatsApp.",
  },
]

const CALENDARIO: PassoTour[] = [
  {
    titulo: "Seu mês num lugar só",
    texto: "Aqui aparecem os dias de gerar cada nota e os lembretes que você criar.",
  },
  {
    titulo: "Lembretes e ajustes",
    texto: "Clique num dia pra criar um lembrete. Clique num aviso pra mudar a data só daquela vez, sem mexer na regra dos outros meses.",
  },
]

const FINANCEIRO: PassoTour[] = [
  {
    alvo: "financeiro-resumo",
    titulo: "Entrou, saiu, sobrou",
    texto: "O total recebido, as despesas e o saldo do ano escolhido.",
  },
  {
    alvo: "financeiro-extrato",
    titulo: "Importar extrato",
    texto: "Mande o extrato do banco (PDF, OFX ou CSV). Classifique o que quiser na hora — o resto fica guardado na Conciliação.",
  },
  {
    alvo: "financeiro-disposicao",
    titulo: "Do seu jeito",
    texto: "Cada card abre e fecha, e em “Editar disposição” você arrasta pra mudar a ordem. Fica salvo na sua conta.",
  },
]

const EMPRESA: PassoTour[] = [
  {
    titulo: "Empresa",
    texto:
      "O cadastro geral da empresa (vale pra todos os módulos) e, em Módulos, o que está ligado. Com o módulo de notas: e-mails das notas, alíquota, ambiente e certificado digital. Tem mais de uma empresa? Troque ou adicione no topo do menu.",
  },
]

const CONTA: PassoTour[] = [
  {
    titulo: "Minha conta",
    texto: "Seu perfil, senha e dispositivos conectados, assinatura e o Indique e ganhe.",
  },
  {
    alvo: "config-tutorial",
    titulo: "Dicas ligadas ou desligadas",
    texto: "Aqui você desliga estas dicas, ou pede pra ver todas de novo.",
  },
]
