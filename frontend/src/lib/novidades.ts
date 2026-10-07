import { useCallback, useEffect, useState } from "react"
import { api } from "./api"

// Versões e novidades (08/10/2026) — ver backend/app/novidades.py.

export type PerfilNovidade = "todos" | "empresa" | "contador"

export interface ItemNovidade {
  perfil: PerfilNovidade
  titulo: string
  texto: string
  link?: string
}

export interface VersaoNovidades {
  versao: string
  data: string
  resumo: string
  itens: ItemNovidade[]
  /** A pessoa ainda não viu esta versão. */
  nova: boolean
}

export interface Novidades {
  versao: string
  versoes: VersaoNovidades[]
  novas: number
}

export const EVENTO_NOVIDADES_VISTAS = "ana:novidades-vistas"

/** Pro sino do topo: quantas versões a pessoa ainda não abriu. */
export function useNovidades(): { dados: Novidades | null; marcarVistas: () => void } {
  const [dados, setDados] = useState<Novidades | null>(null)
  useEffect(() => {
    let vivo = true
    api
      .get<Novidades>("/novidades")
      .then((d) => vivo && setDados(d))
      .catch(() => vivo && setDados(null))
    const zerar = () => setDados((d) => (d ? { ...d, novas: 0 } : d))
    window.addEventListener(EVENTO_NOVIDADES_VISTAS, zerar)
    return () => {
      vivo = false
      window.removeEventListener(EVENTO_NOVIDADES_VISTAS, zerar)
    }
  }, [])
  const marcarVistas = useCallback(() => {
    api
      .post("/conta/novidades-vistas", {})
      .then(() => window.dispatchEvent(new Event(EVENTO_NOVIDADES_VISTAS)))
      .catch(() => undefined)
  }, [])
  return { dados, marcarVistas }
}

/** Versão e ambiente que estão no ar (rodapé do menu). */
export function useVersao(): { versao: string; ambiente: "teste" | "producao" } | null {
  const [v, setV] = useState<{ versao: string; ambiente: "teste" | "producao" } | null>(null)
  useEffect(() => {
    api
      .get<{ versao: string; ambiente: "teste" | "producao" }>("/versao")
      .then(setV)
      .catch(() => setV(null))
  }, [])
  return v
}
