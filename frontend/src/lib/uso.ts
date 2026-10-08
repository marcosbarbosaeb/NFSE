import { useEffect } from "react"
import { useLocation } from "react-router-dom"
import { useAuth } from "./auth"

// Uso da plataforma (08/10/2026, ver backend/app/services/uso.py): o painel
// avisa qual TELA a pessoa abriu — só o caminho; o servidor tira qualquer id
// e guarda só `?aba=`. Ações e erros o servidor anota sozinho. É estatística:
// se falhar, ninguém fica sabendo (e nada quebra).

export function useRegistrarTela() {
  const { usuario } = useAuth()
  const { pathname, search } = useLocation()
  const aba = new URLSearchParams(search).get("aba")
  const logado = Boolean(usuario) && !usuario?.demo
  useEffect(() => {
    if (!logado || !pathname.startsWith("/app")) return
    const caminho = aba ? `${pathname}?aba=${aba}` : pathname
    // um instante depois: redirecionamentos (ex.: aba antiga -> nova) não contam duas vezes
    const t = setTimeout(() => {
      fetch("/api/uso/tela", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminho }), keepalive: true }).catch(() => undefined)
    }, 600)
    return () => clearTimeout(t)
  }, [logado, pathname, aba])
}
