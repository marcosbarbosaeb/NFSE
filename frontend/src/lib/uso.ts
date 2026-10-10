import { useEffect } from "react"
import { useLocation } from "react-router-dom"
import { useAuth } from "./auth"

// Uso da plataforma (08/10/2026, ver backend/app/services/uso.py): o painel
// avisa qual TELA a pessoa abriu — só o caminho; o servidor tira qualquer id
// e guarda só `?aba=`. Ações e erros o servidor anota sozinho. É estatística:
// se falhar, ninguém fica sabendo (e nada quebra).

// Última tela do painel antes da Ajuda: o "Pergunte à Ana" (2026.10.7) conta
// pra IA de onde a pessoa veio. Fica só na memória da aba.
let telaAnterior: string | null = null
export function telaDeOrigem(): string | null {
  return telaAnterior
}

export function useRegistrarTela() {
  const { usuario } = useAuth()
  const { pathname, search } = useLocation()
  const aba = new URLSearchParams(search).get("aba")
  const logado = Boolean(usuario) && !usuario?.demo
  useEffect(() => {
    if (!pathname.startsWith("/app")) return
    const caminho = aba ? `${pathname}?aba=${aba}` : pathname
    if (!pathname.startsWith("/app/ajuda")) telaAnterior = caminho
    if (!logado) return
    // um instante depois: redirecionamentos (ex.: aba antiga -> nova) não contam duas vezes
    const t = setTimeout(() => {
      fetch("/api/uso/tela", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho }), keepalive: true }).catch(() => undefined)
    }, 600)
    return () => clearTimeout(t)
  }, [logado, pathname, aba])
}
