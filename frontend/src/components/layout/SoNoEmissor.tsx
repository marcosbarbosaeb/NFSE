import { useEffect, type ReactNode } from "react"
import { useLocation } from "react-router-dom"
import { ehDominioRaiz, urlEmissor } from "../../lib/dominios"

// Telas do emissor (entrar, cadastro, painel...) acessadas pelo domínio
// raiz agenteana.com.br são mandadas pro subdomínio notas, mantendo o
// caminho e a query (ex.: link antigo de confirmação de e-mail). A sessão
// (cookie) vive só no subdomínio notas, então o emissor nunca deve rodar
// no domínio raiz.
export function SoNoEmissor({ children }: { children: ReactNode }) {
  const { pathname, search, hash } = useLocation()
  const raiz = ehDominioRaiz()
  useEffect(() => {
    if (raiz) window.location.replace(urlEmissor(pathname + search + hash))
  }, [raiz, pathname, search, hash])
  if (raiz) return null
  return <>{children}</>
}
