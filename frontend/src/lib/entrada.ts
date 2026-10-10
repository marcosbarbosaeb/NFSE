// Entrar como empresa ou como contador(a) (observação de teste 8, 10/10/2026).
// O login é um só; a escolha decide só a tela onde a pessoa cai depois de
// entrar. Fica lembrada no navegador (a pessoa costuma entrar sempre do mesmo
// jeito). Na volta do Google o app abre direto em /app, então a escolha vai
// junto numa marca de uso único (`depoisDoGoogle`), lida em `AppShell`.

export type ComoEntrar = "empresa" | "contador"

const CHAVE = "agenteana.entrada"
const CHAVE_GOOGLE = "agenteana.entrada.google"

export const TELA_DO_CONTADOR = "/app/atendimentos"

export function destinoDeEntrada(como: ComoEntrar): string {
  return como === "contador" ? TELA_DO_CONTADOR : "/app"
}

export function comoEntrarSalvo(): ComoEntrar {
  try {
    return localStorage.getItem(CHAVE) === "contador" ? "contador" : "empresa"
  } catch {
    return "empresa"
  }
}

export function guardarComoEntrar(como: ComoEntrar, { depoisDoGoogle = false } = {}) {
  try {
    localStorage.setItem(CHAVE, como)
    if (depoisDoGoogle && como === "contador") sessionStorage.setItem(CHAVE_GOOGLE, "1")
  } catch {
    /* sem armazenamento: só não lembra */
  }
}

/** Na volta do Google: true uma vez só, se a pessoa escolheu "contador". */
export function voltouDoGoogleComoContador(): boolean {
  try {
    const sim = sessionStorage.getItem(CHAVE_GOOGLE) === "1"
    sessionStorage.removeItem(CHAVE_GOOGLE)
    return sim
  } catch {
    return false
  }
}
