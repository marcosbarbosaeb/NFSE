// Programa de indicação: o link é /cadastro?ref=CODIGO. O código fica
// guardado no navegador porque o cadastro pelo Google sai e volta do site
// (e perderia o ?ref no caminho).
const CHAVE = "agenteana.ref"

export function guardarCodigoIndicacao(params: URLSearchParams): string | null {
  const ref = (params.get("ref") ?? "").replace(/[^A-Za-z0-9]/g, "").slice(0, 20)
  try {
    if (ref) localStorage.setItem(CHAVE, ref)
    return ref || localStorage.getItem(CHAVE)
  } catch {
    return ref || null
  }
}

export function esquecerCodigoIndicacao() {
  try {
    localStorage.removeItem(CHAVE)
  } catch {
    // sem armazenamento: nada a fazer
  }
}
