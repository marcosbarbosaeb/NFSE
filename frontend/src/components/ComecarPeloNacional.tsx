import { useEffect, useState } from "react"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import type { VinculoResumo } from "../lib/types"

// Empresa que ainda não tem tomador nem nota: dá pra trazer as notas do
// Emissor Nacional com o certificado. Desde 06/10/2026 isso NÃO aparece mais
// na Visão geral ("não quero essa importação na tela inicial": primeiro os
// tomadores pré-cadastrados — ver PrimeirosPassos); fica em Empresa › Notas e e-mails.

export const CHAMADA_NACIONAL = "Já emite pelo Emissor Nacional? Eu trago seus tomadores e notas"

/** true = a empresa aberta não tem nenhum tomador (logo, nenhuma nota).
 * null enquanto carrega ou se a consulta falhar — aí ninguém mostra nada. */
export function useEmpresaVazia(): boolean | null {
  const { usuario } = useAuth()
  const [vazia, setVazia] = useState<boolean | null>(null)
  const pular = !usuario || Boolean(usuario.demo)
  useEffect(() => {
    if (pular) return
    let cancelado = false
    api
      .get<VinculoResumo[]>("/vinculos?todos=true")
      .then((v) => !cancelado && setVazia(v.length === 0))
      .catch(() => !cancelado && setVazia(null))
    return () => {
      cancelado = true
    }
  }, [pular])
  return pular ? null : vazia
}
