import { CheckCircle2, FileText, XCircle } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { Field } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"

type Estado = "confirmando" | "sucesso" | "erro"

export function ConfirmarEmailPage() {
  const [params] = useSearchParams()
  const token = params.get("token")
  const [estado, setEstado] = useState<Estado>("confirmando")
  const [erro, setErro] = useState<string | null>(null)

  const [emailReenvio, setEmailReenvio] = useState("")
  const [reenviando, setReenviando] = useState(false)
  const [reenviado, setReenviado] = useState(false)

  // Evita chamar /cadastro/confirmar duas vezes pro mesmo token (o token é
  // de uso único — a 2ª chamada sempre falharia). Sem essa trava, o
  // StrictMode do React (dev) roda o efeito 2x e a resposta de erro da
  // segunda chamada sobrescreve o "sucesso" da primeira, mostrando um erro
  // por um instante antes do redirect que a 1ª chamada já tinha agendado.
  const tokenConfirmado = useRef<string | null>(null)

  useEffect(() => {
    if (!token) {
      setEstado("erro")
      setErro("Link de confirmação incompleto — falta o token.")
      return
    }
    if (tokenConfirmado.current === token) return
    tokenConfirmado.current = token
    api
      .post("/cadastro/confirmar", { token })
      .then(() => {
        setEstado("sucesso")
        // Recarrega /app de propósito (em vez de navigate()): o
        // AuthProvider só sabe que a sessão existe reconsultando /auth/me,
        // e confirmar o e-mail já loga (cookie de sessão setado pelo
        // backend) — um reload pego essa sessão nova sem precisar expor um
        // método novo em lib/auth.tsx só pra este caso.
        setTimeout(() => {
          window.location.href = "/app"
        }, 1500)
      })
      .catch((err) => {
        setEstado("erro")
        setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      })
  }, [token])

  async function onReenviar() {
    setReenviando(true)
    try {
      await api.post("/cadastro/reenviar-confirmacao", { email: emailReenvio })
      setReenviado(true)
    } catch {
      setReenviado(true) // resposta é sempre a mesma no backend, não revela se o e-mail existe
    } finally {
      setReenviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas dark:bg-canvas-dark px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white">
            <FileText size={22} />
          </div>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Nota<span className="text-primary-600">Fácil</span>
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 text-center shadow-sm">
          {estado === "confirmando" && <p className="text-sm text-slate-500 dark:text-slate-400">Confirmando seu e-mail...</p>}

          {estado === "sucesso" && (
            <div className="flex flex-col items-center gap-3 py-2">
              <CheckCircle2 size={32} className="text-success-600" />
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200">E-mail confirmado!</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">Te levando pro painel...</p>
            </div>
          )}

          {estado === "erro" && (
            <div className="flex flex-col items-center gap-3 py-2">
              <XCircle size={32} className="text-danger-600" />
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200">Não deu pra confirmar</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{erro}</p>

              {!reenviado ? (
                <div className="mt-3 flex w-full flex-col gap-2 text-left">
                  <Field label="Reenviar link pro e-mail" type="email" value={emailReenvio} onChange={(e) => setEmailReenvio(e.target.value)} />
                  <Button type="button" variant="accent" disabled={reenviando || !emailReenvio} onClick={onReenviar}>
                    {reenviando ? "Enviando..." : "Reenviar confirmação"}
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-success-700">Se esse e-mail tiver um cadastro pendente, reenviamos o link.</p>
              )}

              <Link to="/entrar" className="mt-2 text-sm font-medium text-primary-600 hover:text-primary-700">
                Voltar pro login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
