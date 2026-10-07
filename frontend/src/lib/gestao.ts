import { ApiError, formatarErro } from "./api"
import type { ContaGestao } from "./types"

// Painel de gestão da plataforma (06/10/2026): o que as abas têm em comum.

export function erroDe(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

type Variante = "success" | "warning" | "danger" | "neutral" | "info"

/** Situações de assinatura na ordem em que aparecem (a última é a conta sem assinatura). */
export const SEM_ASSINATURA = "sem assinatura"
export const ASSINATURAS: { id: string; rotulo: string; variante: Variante }[] = [
  { id: "ativa", rotulo: "Pagando", variante: "success" },
  { id: "trial", rotulo: "Em teste", variante: "info" },
  { id: "inadimplente", rotulo: "Pagamento atrasado", variante: "warning" },
  { id: "cancelada", rotulo: "Cancelada", variante: "danger" },
  { id: "cortesia", rotulo: "Cortesia", variante: "neutral" },
  { id: SEM_ASSINATURA, rotulo: "Sem assinatura", variante: "neutral" },
]

export function situacaoAssinatura(status: string | null | undefined) {
  const id = status || SEM_ASSINATURA
  return ASSINATURAS.find((a) => a.id === id) ?? { id, rotulo: id, variante: "neutral" as const }
}

const NOME_PLANO: Record<string, string> = { emissor: "Notas", financeiro: "Financeiro", ambos: "Notas + Financeiro" }
export const nomeDoPlano = (plano: string | null) => (plano ? (NOME_PLANO[plano] ?? plano) : "")
const NOME_MODULO: Record<string, string> = { emissor: "Notas", financeiro: "Financeiro" }
export const nomeDoModulo = (modulo: string) => NOME_MODULO[modulo] ?? modulo

export const numero = (n: number) => n.toLocaleString("pt-BR")
/** plural(1, "conta", "contas") -> "1 conta" */
export const plural = (n: number, um: string, varios: string) => `${numero(n)} ${n === 1 ? um : varios}`

/** Data e hora ISO -> "06/10/2026" no horário de quem está olhando. */
export function dia(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" })
}

/** Data e hora ISO -> "06/10/2026 14:32". */
export function diaHora(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

export function haDias(dias: number | null): string {
  if (dias === null) return "nunca entrou"
  if (dias <= 0) return "hoje"
  return dias === 1 ? "há 1 dia" : `há ${numero(dias)} dias`
}

/** Conta "ativa": alguém entrou nos últimos 30 dias (mesma régua do resumo do backend). */
export const DIAS_ATIVA = 30
export const ativa30 = (c: ContaGestao) => c.dias_sem_acesso !== null && c.dias_sem_acesso <= DIAS_ATIVA
export const semAcesso = (c: ContaGestao) => !ativa30(c)

/** Certificado só faz falta pra quem emite nota (conta sem módulos = emissor, regra antiga). */
export const usaEmissor = (c: ContaGestao) => !c.so_contador && (c.modulos.length === 0 || c.modulos.includes("emissor"))
export const semCertificado = (c: ContaGestao) => usaEmissor(c) && c.certificado !== "ok"

/** Dias até o fim do período de teste (negativo = já venceu); null se não está em teste. */
export function diasDoTeste(c: ContaGestao, agora = Date.now()): number | null {
  if (c.assinatura !== "trial" || !c.trial_termina_em) return null
  const fim = new Date(c.trial_termina_em).getTime()
  return Number.isNaN(fim) ? null : Math.ceil((fim - agora) / 86_400_000)
}

export interface Motivo {
  texto: string
  variante: Variante
}

/** Por que uma conta real merece um olhar (bloco "Precisam de atenção"). */
export function motivosDeAtencao(c: ContaGestao, agora = Date.now()): Motivo[] {
  if (c.demo) return []
  const motivos: Motivo[] = []
  const teste = diasDoTeste(c, agora)
  if (teste !== null && teste <= 0) motivos.push({ texto: "período de teste vencido", variante: "danger" })
  else if (teste !== null && teste <= 7) motivos.push({ texto: teste === 1 ? "teste acaba amanhã" : `teste acaba em ${teste} dias`, variante: "warning" })
  if (!c.email_confirmado) motivos.push({ texto: "não confirmou o e-mail", variante: "warning" })
  if (semCertificado(c)) motivos.push({ texto: c.certificado === "vencido" ? "certificado vencido" : "sem certificado", variante: "warning" })
  if (c.dias_sem_acesso === null) motivos.push({ texto: "nunca entrou", variante: "neutral" })
  else if (c.dias_sem_acesso > DIAS_ATIVA) motivos.push({ texto: `sem entrar ${haDias(c.dias_sem_acesso)}`, variante: "neutral" })
  return motivos
}

export const nomeDaConta = (c: ContaGestao) => c.razao_social?.trim() || c.logins[0]?.email || "Empresa sem nome"

/** Baixa um texto como arquivo .csv (separador ";", com BOM pro Excel abrir com acento). */
export function baixarCsv(nome: string, linhas: (string | number)[][]) {
  // Texto que começa com = + - @ viraria fórmula na planilha: ganha um apóstrofo na frente.
  const celula = (c: string | number) => {
    const texto = typeof c === "string" && /^[=+\-@\t\r]/.test(c) ? `'${c}` : String(c)
    return `"${texto.replace(/"/g, '""')}"`
  }
  const csv = linhas.map((l) => l.map(celula).join(";")).join("\r\n")
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }))
  const a = document.createElement("a")
  a.href = url
  a.download = nome
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
