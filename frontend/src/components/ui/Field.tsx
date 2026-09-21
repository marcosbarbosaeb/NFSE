import type { InputHTMLAttributes, ReactNode } from "react"

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export function Field({ label, hint, className = "", ...props }: Props) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input
        className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 ${className}`}
        {...props}
      />
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}

export function FieldWrap({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}
