import { useAuth } from "./auth"

/** Produtos da empresa ativa (05/10/2026): emissor de notas e financeiro são
 * vendidos separadamente — cada tela só aparece pra quem tem o módulo. */
export type Modulo = "emissor" | "financeiro"

export function useModulos(): { emissor: boolean; financeiro: boolean; lista: Modulo[] } {
  const { usuario } = useAuth()
  const lista = (usuario?.modulos?.length ? usuario.modulos : ["emissor"]) as Modulo[]
  return { emissor: lista.includes("emissor"), financeiro: lista.includes("financeiro"), lista }
}

/** Primeira tela de cada módulo. */
export const INICIO: Record<Modulo, string> = { emissor: "/app", financeiro: "/app/financeiro" }
