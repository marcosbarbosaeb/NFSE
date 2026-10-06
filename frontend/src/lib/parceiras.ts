import type { StatusIndicadoParceira } from "./types"

// Parceiras de indicação (06/10/2026): o que a tela da administração e o
// painel público da parceira têm em comum. Nada aqui depende de login.

export const SITUACAO_INDICADO: Record<
  StatusIndicadoParceira,
  { rotulo: string; variante: "success" | "warning" | "danger" | "neutral" }
> = {
  trial: { rotulo: "Em teste", variante: "neutral" },
  ativa: { rotulo: "Assinatura ativa", variante: "success" },
  inadimplente: { rotulo: "Pagamento atrasado", variante: "warning" },
  cancelada: { rotulo: "Cancelada", variante: "danger" },
}

/** O backend copia o status da assinatura do indicado; além dos quatro
 * previstos pode vir "cortesia" (conta que a plataforma liberou sem cobrar). */
export function situacaoDoIndicado(status: string) {
  if (status === "cortesia") return { rotulo: "Cortesia (não paga)", variante: "neutral" as const }
  return SITUACAO_INDICADO[status as StatusIndicadoParceira] ?? { rotulo: status, variante: "neutral" as const }
}

/** "2026-10-06" (ou data e hora ISO) -> "06/10/2026", sem passar por fuso. */
export function dataBR(iso: string | null | undefined): string {
  const [ano, mes, dia] = (iso ?? "").slice(0, 10).split("-")
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : ""
}

/** 12.5 -> "12,5%"; 10 -> "10%". */
export function formatPct(valor: number): string {
  return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`
}
