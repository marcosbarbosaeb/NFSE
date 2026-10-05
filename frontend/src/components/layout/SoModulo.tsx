import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { INICIO, type Modulo, useModulos } from "../../lib/modulos"

/** Tela de um módulo que a empresa não tem: manda pra primeira tela do que
 * ela tem (o servidor também recusa as rotas — isto é só pra não mostrar
 * uma tela vazia). */
export function SoModulo({ modulo, children }: { modulo: Modulo; children: ReactNode }) {
  const modulos = useModulos()
  if (!modulos[modulo]) {
    const destino = INICIO[modulos.lista[0]] ?? "/app/empresa"
    return <Navigate to={destino === INICIO[modulo] ? "/app/empresa" : destino} replace />
  }
  return <>{children}</>
}
