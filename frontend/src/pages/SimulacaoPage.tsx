import { useEffect, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { AnaAvatar } from "../components/brand/Marca"
import { Button } from "../components/ui/Button"
import { ApiError, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { lerParametroGravacao } from "../lib/gravacao"

// "Testar sem cadastro" — entra numa conta de simulação com dados de
// exemplo (ver backend/app/services/demo.py) e cai direto no painel.
// Modo demonstração (08/10/2026): `?cenario=beleza` escolhe o nicho dos dados
// e `?gravacao=1` deixa a tela limpa pra gravar vídeo (ver lib/gravacao.ts).
// Cada abertura cria uma simulação nova, com os dados do cenário do zero.
export function SimulacaoPage() {
  const [params] = useSearchParams()
  const cenario = params.get("cenario")
  const { usuario, carregando, entrarNaSimulacao, logout } = useAuth()
  const navigate = useNavigate()
  const [erro, setErro] = useState<string | null>(null)
  // Logado numa conta de verdade: pergunta antes de sair dela (um link não
  // pode derrubar a sessão de ninguém sem a pessoa ver).
  const [perguntar, setPerguntar] = useState(false)
  const iniciado = useRef(false)

  function abrir() {
    entrarNaSimulacao(cenario)
      .then(() => navigate("/app", { replace: true }))
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Não deu pra abrir a simulação agora."))
  }

  useEffect(() => {
    if (carregando || iniciado.current) return
    iniciado.current = true
    lerParametroGravacao()
    if (usuario && !usuario.demo) {
      setPerguntar(true)
      return
    }
    abrir()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [carregando, usuario])

  async function sairEAbrir() {
    setPerguntar(false)
    try {
      await logout()
    } catch {
      // a simulação cria uma sessão nova de qualquer jeito
    }
    abrir()
  }

  if (perguntar && usuario) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas px-4 text-center dark:bg-canvas-dark">
        <AnaAvatar size={64} />
        <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">Abrir a simulação?</p>
        <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
          Você está na conta <strong>{usuario.email}</strong>. Pra abrir a simulação eu saio dela — depois é só entrar de novo.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button variant="ghost" onClick={() => navigate("/app", { replace: true })}>
            Voltar pro meu painel
          </Button>
          <Button variant="accent" onClick={sairEAbrir}>
            Sair e abrir a simulação
          </Button>
        </div>
      </div>
    )
  }

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
