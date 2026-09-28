const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
const MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

export function formatBRL(valor: number): string {
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
}

export function competenciaAtual(): string {
  const hoje = new Date()
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`
}

export function formatCompetenciaLonga(competencia: string): string {
  const [ano, mes] = competencia.split("-").map(Number)
  return `${MESES[mes - 1]} de ${ano}`
}

export function formatCompetenciaAbrev(competencia: string): string {
  const [, mes] = competencia.split("-").map(Number)
  return MESES_ABREV[mes - 1]
}

export function deslocarCompetencia(competencia: string, deltaMeses: number): string {
  const [ano, mes] = competencia.split("-").map(Number)
  const indice = ano * 12 + (mes - 1) + deltaMeses
  const novoAno = Math.floor(indice / 12)
  const novoMes = (indice % 12) + 1
  return `${novoAno}-${String(novoMes).padStart(2, "0")}`
}

/** "1.234,56" / "1234,56" / "1234.56" / "1.000" -> número (ou null se não
 * der pra entender). Quem digita em pt-BR usa ponto de milhar e vírgula
 * decimal; `Number("1.000,00")` dava NaN e `Number("1.000")` dava 1. */
export function parseBRL(texto: string | null | undefined): number | null {
  let t = (texto ?? "").replace(/[^\d.,-]/g, "")
  if (!t) return null
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".")
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "")
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}
