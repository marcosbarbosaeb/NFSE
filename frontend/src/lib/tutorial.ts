// Tutorial de primeira visita — pedido do Marcos (28/09/2026): "crie um
// tutorial com indicações para a primeira vez que a pessoa entrar em uma aba
// nova, mostrando pra ela as funcionalidades que existem" + "na aba de
// configurações coloque uma opção para ativar e desativar esse tutorial".
//
// Preferência e telas já vistas ficam no navegador (localStorage), por
// usuário — é conveniência de interface, não dado da conta. Tudo em
// try/catch: navegador em modo privado pode recusar o armazenamento, e aí o
// tutorial só aparece de novo, sem quebrar nada.

const CHAVE_ATIVO = "agenteana.tutorial.ativo"
const CHAVE_VISTOS = "agenteana.tutorial.vistos"
const EVENTO = "agenteana:tutorial"

function ler(chave: string): string | null {
  try {
    return window.localStorage.getItem(chave)
  } catch {
    return null
  }
}

function gravar(chave: string, valor: string | null) {
  try {
    if (valor === null) window.localStorage.removeItem(chave)
    else window.localStorage.setItem(chave, valor)
  } catch {
    /* sem armazenamento: segue sem lembrar */
  }
}

export function tutorialAtivo(): boolean {
  return ler(CHAVE_ATIVO) !== "nao"
}

export function definirTutorialAtivo(ativo: boolean) {
  gravar(CHAVE_ATIVO, ativo ? "sim" : "nao")
  window.dispatchEvent(new Event(EVENTO))
}

function vistos(): string[] {
  try {
    return JSON.parse(ler(CHAVE_VISTOS) ?? "[]")
  } catch {
    return []
  }
}

export function jaViu(tela: string): boolean {
  return vistos().includes(tela)
}

export function marcarVisto(tela: string) {
  const lista = vistos()
  if (!lista.includes(tela)) gravar(CHAVE_VISTOS, JSON.stringify([...lista, tela]))
}

export function reverTodasAsDicas() {
  gravar(CHAVE_VISTOS, null)
  window.dispatchEvent(new Event(EVENTO))
}

/** Pede pra tela atual mostrar as dicas agora (botão "?" do topo). */
export function mostrarDicasDaTela() {
  window.dispatchEvent(new CustomEvent(EVENTO, { detail: "abrir" }))
}

export function aoMudarTutorial(callback: (e: Event) => void): () => void {
  window.addEventListener(EVENTO, callback)
  return () => window.removeEventListener(EVENTO, callback)
}
