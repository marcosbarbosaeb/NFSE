import { useEffect, useState } from "react"
import { api } from "./api"
import type { UsoDoPlano } from "./types"

// Uso do plano (07/10/2026): notas autorizadas no mês x limite.

export const EVENTO_USO_MUDOU = "agenteana:uso-do-plano"

/** Chame depois de autorizar notas ou mudar de plano: as faixas se atualizam. */
export function avisarUsoMudou() {
  window.dispatchEvent(new Event(EVENTO_USO_MUDOU))
}

/** `gatilho`: mude (ex.: a tela atual) pra buscar de novo. */
export function useUsoDoPlano(ligado = true, gatilho: unknown = null): UsoDoPlano | null {
  const [uso, setUso] = useState<UsoDoPlano | null>(null)
  useEffect(() => {
    if (!ligado) return
    const buscar = () =>
      api
        .get<UsoDoPlano>("/assinatura/uso")
        .then(setUso)
        .catch(() => undefined)
    buscar()
    window.addEventListener(EVENTO_USO_MUDOU, buscar)
    return () => window.removeEventListener(EVENTO_USO_MUDOU, buscar)
  }, [ligado, gatilho])
  return ligado ? uso : null
}

export const reais = (valor: number) => valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })

/** "30 notas por mês" / "notas sem limite" / "sem emissão de notas" */
export function textoDoLimite(limite: number | null | undefined): string {
  if (limite === null || limite === undefined) return "Notas sem limite"
  if (limite === 0) return "Sem emissão de notas"
  return `Até ${limite.toLocaleString("pt-BR")} notas por mês`
}
