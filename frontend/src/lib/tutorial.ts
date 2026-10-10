import { api } from "./api"
import { gravacaoLigada } from "./gravacao"
// Tutorial de primeira visita — pedido do Marcos (28/09/2026): "crie um
// tutorial com indicações para a primeira vez que a pessoa entrar em uma aba
// nova, mostrando pra ela as funcionalidades que existem" + "na aba de
// configurações coloque uma opção para ativar e desativar esse tutorial".
//
// Preferência e telas já vistas ficam no navegador (localStorage), separadas
// por login, e desde a 2026.10.7 também na conta (PUT /api/conta/tutorial):
// em outro navegador as dicas já vistas não voltam. Tudo em try/catch:
// navegador em modo privado pode recusar o armazenamento, e aí vale o que
// veio da conta.

const BASE_ATIVO = "agenteana.tutorial.ativo"
const BASE_VISTOS = "agenteana.tutorial.vistos"
const EVENTO = "agenteana:tutorial"
let dono = ""
const CHAVE_ATIVO = () => (dono ? `${BASE_ATIVO}.${dono}` : BASE_ATIVO)
const CHAVE_VISTOS = () => (dono ? `${BASE_VISTOS}.${dono}` : BASE_VISTOS)

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
  // Gravando vídeo na simulação (?gravacao=1): nenhuma dica abre sozinha.
  if (gravacaoLigada()) return false
  return ler(CHAVE_ATIVO()) !== "nao"
}

export function definirTutorialAtivo(ativo: boolean) {
  gravar(CHAVE_ATIVO(), ativo ? "sim" : "nao")
  void api.put("/conta/tutorial", { ativo }).catch(() => undefined)
  window.dispatchEvent(new Event(EVENTO))
}

function vistos(): string[] {
  try {
    return JSON.parse(ler(CHAVE_VISTOS()) ?? "[]")
  } catch {
    return []
  }
}

export function jaViu(tela: string): boolean {
  return vistos().includes(tela)
}

export function marcarVisto(tela: string) {
  const lista = vistos()
  if (!lista.includes(tela)) gravar(CHAVE_VISTOS(), JSON.stringify([...lista, tela]))
  // Na conta também: em outro navegador esta dica não volta.
  void api.put("/conta/tutorial", { vistos: [tela] }).catch(() => undefined)
}

export function reverTodasAsDicas() {
  gravar(CHAVE_VISTOS(), null)
  void api.put("/conta/tutorial", { limpar: true, vistos: [] }).catch(() => undefined)
  window.dispatchEvent(new Event(EVENTO))
}

/** Liga o tutorial ao login atual e soma as dicas vistas guardadas na conta
 * (2026.10.7). Chamado pelo painel quando a pessoa entra. */
export function sincronizarTutorial(email: string, daConta?: { vistos?: string[]; ativo?: boolean } | null) {
  const novoDono = email.trim().toLowerCase()
  if (novoDono !== dono) {
    // Primeira vez por login: aproveita o que o navegador já guardava sem separar por login.
    const antigos = ler(BASE_VISTOS)
    dono = novoDono
    if (antigos && ler(CHAVE_VISTOS()) === null) gravar(CHAVE_VISTOS(), antigos)
    const ativoAntigo = ler(BASE_ATIVO)
    if (ativoAntigo && ler(CHAVE_ATIVO()) === null) gravar(CHAVE_ATIVO(), ativoAntigo)
  }
  if (!daConta) return
  const locais = vistos()
  const juntos = Array.from(new Set([...locais, ...(daConta.vistos ?? [])]))
  if (juntos.length !== locais.length) gravar(CHAVE_VISTOS(), JSON.stringify(juntos))
  const faltamNaConta = locais.filter((t) => !(daConta.vistos ?? []).includes(t))
  if (faltamNaConta.length) void api.put("/conta/tutorial", { vistos: faltamNaConta }).catch(() => undefined)
  if (typeof daConta.ativo === "boolean") gravar(CHAVE_ATIVO(), daConta.ativo ? "sim" : "nao")
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

// Passeio das novidades (08/10/2026): enquanto ele está aberto, as dicas de
// primeira visita de cada tela esperam — senão abririam as duas juntas.
let passeio = false
export function definirPasseio(aberto: boolean) {
  passeio = aberto
}
export function passeioEmAndamento(): boolean {
  return passeio
}
