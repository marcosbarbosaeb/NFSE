import type { ReactNode } from "react"
import { Card } from "./Card"

export function StatCard({
  icon,
  iconClassName = "bg-primary-50 text-primary-600",
  label,
  value,
  sublabel,
  sublabelClassName = "text-slate-400 dark:text-slate-500",
  onClick,
  ativo = false,
}: {
  icon: ReactNode
  iconClassName?: string
  label: string
  value: ReactNode
  sublabel?: ReactNode
  sublabelClassName?: string
  /** Com onClick o cartão inteiro vira um botão (ex.: filtrar a lista). */
  onClick?: () => void
  ativo?: boolean
}) {
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={ativo}
        className={`flex flex-col gap-3 rounded-2xl border bg-white p-5 text-left shadow-sm shadow-slate-200/50 transition-colors hover:border-primary-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:bg-slate-800 dark:shadow-black/20 dark:hover:border-primary-600 ${
          ativo ? "border-primary-400 ring-1 ring-primary-400 dark:border-primary-500" : "border-slate-200/70 dark:border-slate-700/70"
        }`}
      >
        <div className={`flex h-10 w-10 items-center justify-center rounded-full ${iconClassName}`}>{icon}</div>
        <div>
          <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
        </div>
        {sublabel && <p className={`text-xs ${sublabelClassName}`}>{sublabel}</p>}
      </button>
    )
  }
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className={`flex h-10 w-10 items-center justify-center rounded-full ${iconClassName}`}>{icon}</div>
      <div>
        <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
      </div>
      {sublabel && <p className={`text-xs ${sublabelClassName}`}>{sublabel}</p>}
    </Card>
  )
}
