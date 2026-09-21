import type { ReactNode } from "react"
import { Card } from "./Card"

export function StatCard({
  icon,
  iconClassName = "bg-primary-50 text-primary-600",
  label,
  value,
  sublabel,
  sublabelClassName = "text-slate-400",
}: {
  icon: ReactNode
  iconClassName?: string
  label: string
  value: ReactNode
  sublabel?: ReactNode
  sublabelClassName?: string
}) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className={`flex h-10 w-10 items-center justify-center rounded-full ${iconClassName}`}>{icon}</div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-semibold text-slate-900">{value}</p>
      </div>
      {sublabel && <p className={`text-xs ${sublabelClassName}`}>{sublabel}</p>}
    </Card>
  )
}
