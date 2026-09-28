// Datas locais (AAAA-MM-DD) pro campo "Data de competência" (29/09/2026).

/** Hoje no fuso do navegador, AAAA-MM-DD (não usar toISOString: em UTC,
 * depois das 21h no Brasil já seria amanhã). */
export function hojeLocal(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

/** Dia padrão pra uma competência AAAA-MM: hoje se for o mês corrente, o
 * último dia se for um mês passado, o primeiro se for futuro. */
export function dataPadraoDaCompetencia(competencia: string | null | undefined): string {
  const hoje = hojeLocal()
  if (!competencia || !/^\d{4}-(0[1-9]|1[0-2])$/.test(competencia)) return hoje
  const mesAtual = hoje.slice(0, 7)
  if (competencia === mesAtual) return hoje
  if (competencia > mesAtual) return `${competencia}-01`
  const [ano, mes] = competencia.split("-").map(Number)
  const ultimo = new Date(ano, mes, 0).getDate()
  return `${competencia}-${String(ultimo).padStart(2, "0")}`
}
