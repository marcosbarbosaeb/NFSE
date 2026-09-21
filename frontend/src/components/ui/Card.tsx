import type { HTMLAttributes } from "react"

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl border border-slate-200/70 bg-white shadow-sm shadow-slate-200/50 dark:border-slate-700/70 dark:bg-slate-800 dark:shadow-black/20 ${className}`}
      {...props}
    />
  )
}
