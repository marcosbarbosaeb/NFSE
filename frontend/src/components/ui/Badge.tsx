import type { ReactNode } from "react"

type Variante = "success" | "warning" | "danger" | "neutral" | "info"

const ESTILOS: Record<Variante, string> = {
  success: "bg-success-50 text-success-700 dark:bg-success-900/40 dark:text-success-300",
  warning: "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300",
  danger: "bg-danger-50 text-danger-700 dark:bg-danger-900/40 dark:text-danger-300",
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  info: "bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300",
}

export function Badge({ variant = "neutral", children }: { variant?: Variante; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTILOS[variant]}`}>
      {children}
    </span>
  )
}
