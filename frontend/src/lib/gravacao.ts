import { useEffect } from "react"
import { useAuth } from "./auth"

/** Tela limpa pra gravar vídeo (modo demonstração, 08/10/2026): abrir
 * `/simulacao?gravacao=1` (ou qualquer tela com `?gravacao=1`) esconde a faixa
 * "Modo simulação", o aviso amarelo de homologação e as dicas do tutorial.
 * `?gravacao=0` desliga. Fica guardado só nesta aba (sessionStorage).
 *
 * Trava: só vale numa conta de SIMULAÇÃO (`usuario.demo`). Numa conta de
 * verdade o parâmetro é ignorado — os avisos continuam todos lá. */

const CHAVE = "agenteana.gravacao"
let ligadaNaConta = false

function lerGuardado(): boolean {
  try {
    return sessionStorage.getItem(CHAVE) === "1"
  } catch {
    return false
  }
}

/** Lê `?gravacao=1|0` do endereço (chamado na abertura do app e na /simulacao). */
export function lerParametroGravacao() {
  const valor = new URLSearchParams(window.location.search).get("gravacao")
  if (valor === null) return
  try {
    if (valor === "1") sessionStorage.setItem(CHAVE, "1")
    else sessionStorage.removeItem(CHAVE)
  } catch {
    // sem sessionStorage: não liga
  }
}

/** Pros trechos fora do React (ex.: dicas do tutorial). */
export function gravacaoLigada(): boolean {
  return ligadaNaConta
}

export function useModoGravacao(): boolean {
  const { usuario } = useAuth()
  const ligada = Boolean(usuario?.demo) && lerGuardado()
  useEffect(() => {
    ligadaNaConta = ligada
  }, [ligada])
  ligadaNaConta = ligada
  return ligada
}
