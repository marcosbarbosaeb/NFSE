// Helpers da tela Financeiro (28/09/2026): formatação compacta pra tabela
// mês a mês, datas curtas e as classes de campo compartilhadas pelos
// componentes de src/components/financeiro.

import { ApiError, formatarErro } from "./api"
import { hojeLocal } from "./datas"

export const NOMES_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
export const MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

export const CATEGORIA_RETIRADA = "Distribuição de lucros"

export const classeCampo =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export const classeCampoPequeno =
  "rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export const classeCheckbox =
  "h-4 w-4 shrink-0 cursor-pointer accent-primary-600 disabled:cursor-not-allowed"

/** Valor sem o "R$" (a tabela do ano já diz que é em reais): 1.234,56. */
export function formatValor(valor: number): string {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function formatPct(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—"
  return `${valor.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
}

/** "2026-09-10" → "10/09". */
export function formatDiaMes(iso: string | null | undefined): string {
  if (!iso) return ""
  const [, mes, dia] = iso.slice(0, 10).split("-")
  return `${dia}/${mes}`
}

/** "2026-09-10" → "10/09/2026". */
export function formatData(iso: string | null | undefined): string {
  if (!iso) return ""
  const [ano, mes, dia] = iso.slice(0, 10).split("-")
  return `${dia}/${mes}/${ano}`
}

export function estaVencida(vencimento: string | null | undefined, pago: boolean | undefined): boolean {
  return !pago && !!vencimento && vencimento.slice(0, 10) < hojeLocal()
}

export function mensagemErro(err: unknown, padrao = "Falha de conexão. Tente de novo."): string {
  return err instanceof ApiError ? formatarErro(err.detail) : padrao
}

/** Valor em texto pt-BR pro campo de edição ("1234.5" → "1234,50"). */
export function valorParaCampo(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || valor === 0) return ""
  return valor.toFixed(2).replace(".", ",")
}
