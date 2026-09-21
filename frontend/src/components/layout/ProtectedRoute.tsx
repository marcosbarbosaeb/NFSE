import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuth } from "../../lib/auth"

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { usuario, carregando } = useAuth()

  if (carregando) {
    return <div className="flex h-screen items-center justify-center text-sm text-slate-400 dark:text-slate-500">Carregando...</div>
  }
  if (!usuario) {
    return <Navigate to="/entrar" replace />
  }
  return <>{children}</>
}
