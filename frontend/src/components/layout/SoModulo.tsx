import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { type Modulo, useModulos } from "../../lib/modulos"

/** Tela de um módulo que a empresa não tem: volta pra Visão geral (o
 * servidor também recusa as rotas — isto é só pra não mostrar uma tela
 * vazia). */
export function SoModulo({ modulo, children }: { modulo: Modulo; children: ReactNode }) {
  const modulos = useModulos()
  if (!modulos[modulo]) return <Navigate to="/app" replace />
  return <>{children}</>
}
