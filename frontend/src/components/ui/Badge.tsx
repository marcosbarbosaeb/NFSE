import type { ReactNode } from "react"

type Variante = "success" | "warning" | "danger" | "neutral" | "info"

const ESTILOS: Record<Variante, string> = {
  success: "bg-success-50 text-success-700",
  warning: "bg-warning-50 text-warning-700",
  danger: "bg-danger-50 text-danger-700",
  neutral: "bg-slate-100 text-slate-600",
  info: "bg-primary-50 text-primary-700",
}

export function Badge({ variant = "neutral", children }: { variant?: Variante; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTILOS[variant]}`}>
      {children}
    </span>
  )
}
