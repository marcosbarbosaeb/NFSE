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
