import { useEffect, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { AnaAvatar } from "../components/brand/Marca"
import { ApiError, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"

// "Testar sem cadastro" — entra numa conta de simulação com dados de
// exemplo (ver backend/app/services/demo.py) e cai direto no painel.
export function SimulacaoPage() {
  const { usuario, carregando, entrarNaSimulacao } = useAuth()
  const navigate = useNavigate()
  const [erro, setErro] = useState<string | null>(null)
  const iniciado = useRef(false)

  useEffect(() => {
    if (carregando || iniciado.current) return
    iniciado.current = true
    // Quem já está logado numa conta de verdade não perde a sessão.
    if (usuario && !usuario.demo) {
      navigate("/app", { replace: true })
      return
    }
    entrarNaSimulacao()
      .then(() => navigate("/app", { replace: true }))
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Não deu pra abrir a simulação agora."))
  }, [carregando, usuario, entrarNaSimulacao, navigate])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas px-4 text-center dark:bg-canvas-dark">
      <AnaAvatar size={72} className="animate-pulse" />
      {erro ? (
        <>
          <p className="text-sm text-danger-700">{erro}</p>
          <Link to="/cadastro" className="text-sm font-medium text-primary-600 hover:underline">
            Criar conta grátis
          </Link>
        </>
      ) : (
        <>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">Preparando sua simulação...</p>
          <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
            Estou montando uma empresa de exemplo com tomadores, notas e recebimentos pra você explorar à vontade.
          </p>
        </>
      )}
    </div>
  )
}
