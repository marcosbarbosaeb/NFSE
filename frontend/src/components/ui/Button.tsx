import type { ButtonHTMLAttributes } from "react"

type Variante = "primary" | "accent" | "outline" | "ghost"

const ESTILOS: Record<Variante, string> = {
  primary: "bg-primary-600 text-white hover:bg-primary-700",
  accent: "bg-accent-500 text-white hover:bg-accent-600",
  outline: "border border-slate-300 text-slate-700 hover:bg-slate-50",
  ghost: "text-primary-700 hover:bg-primary-50",
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variante
}

export function Button({ variant = "primary", className = "", ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${ESTILOS[variant]} ${className}`}
      {...props}
    />
  )
}
