// Agente Ana — separação por domínio:
//   agenteana.com.br        → só a landing (vitrine da marca e dos produtos)
//   notas.agenteana.com.br  → o emissor de notas (login, cadastro, painel)
// Os dois domínios apontam pro MESMO serviço (um build só); quem decide o
// que mostrar é o hostname. Em qualquer outro host (railway.app, localhost,
// testes) tudo continua funcionando junto no mesmo domínio, como antes.

export const DOMINIO_RAIZ = "agenteana.com.br"
export const DOMINIO_NOTAS = `notas.${DOMINIO_RAIZ}`

function host(): string {
  return typeof window === "undefined" ? "" : window.location.hostname
}

export function ehDominioRaiz(h: string = host()): boolean {
  return h === DOMINIO_RAIZ || h === `www.${DOMINIO_RAIZ}`
}

export function ehDominioNotas(h: string = host()): boolean {
  return h === DOMINIO_NOTAS
}

// Gestão num endereço próprio (2026.10.7): gestao.agenteana.com.br (e, no
// ambiente de teste, um domínio do Railway que comece com "gestao-"). Aqui é
// só a aparência — quem trava de verdade é o servidor (GESTAO_HOST,
// backend/app/services/area_gestao.py).
export function ehDominioGestao(h: string = host()): boolean {
  return h.startsWith("gestao.") || h.startsWith("gestao-")
}

// URL de uma tela do emissor, vista de onde o usuário está agora: no
// domínio raiz vira link absoluto pro subdomínio notas; em qualquer outro
// host continua relativa (mesmo domínio).
export function urlEmissor(caminho: string, h: string = host()): string {
  return ehDominioRaiz(h) ? `https://${DOMINIO_NOTAS}${caminho}` : caminho
}

// URL da landing vista do emissor: no subdomínio notas, volta pro domínio
// raiz; em outro host, "/" mesmo.
export function urlLanding(h: string = host()): string {
  return ehDominioNotas(h) ? `https://${DOMINIO_RAIZ}/` : "/"
}
