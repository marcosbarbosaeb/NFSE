import { FileText } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { ApiError, useAuth } from "../lib/auth"
import { api, formatarErro } from "../lib/api"

export function LoginPage() {
  const { usuario, login } = useAuth()
  const [email, setEmail] = useState("")
  const [senha, setSenha] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [emailNaoConfirmado, setEmailNaoConfirmado] = useState(false)
  const [reenviado, setReenviado] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEmailNaoConfirmado(false)
    setReenviado(false)
    setEnviando(true)
    try {
      await login(email, senha)
    } catch (err) {
      if (err instanceof ApiError) {
        setErro(formatarErro(err.detail))
        if (err.status === 403) setEmailNaoConfirmado(true)
      } else {
        setErro("Falha de conexão. Tente de novo.")
      }
    } finally {
      setEnviando(false)
    }
  }

  async function onReenviarConfirmacao() {
    await api.post("/cadastro/reenviar-confirmacao", { email }).catch(() => {})
    setReenviado(true)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas dark:bg-canvas-dark px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white">
            <FileText size={22} />
          </div>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Nota<span className="text-primary-600">Fácil</span>
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">NFS-e sem complicação</p>
        </div>

        <form onSubmit={onSubmit} className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-4 w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          />
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Senha</label>
          <input
            type="password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="mb-4 w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          />
          {erro && <p className="mb-2 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
          {emailNaoConfirmado && !reenviado && (
            <button
              type="button"
              onClick={onReenviarConfirmacao}
              className="mb-4 block text-sm font-medium text-primary-600 hover:text-primary-700"
            >
              Reenviar e-mail de confirmação
            </button>
          )}
          {reenviado && <p className="mb-4 text-sm text-success-700">Reenviamos o link — confira sua caixa de entrada.</p>}
          <Button type="submit" disabled={enviando} className="w-full">
            {enviando ? "Entrando..." : "Entrar"}
          </Button>
          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            Ainda não tem conta?{" "}
            <Link to="/cadastro" className="font-medium text-primary-600 hover:text-primary-700">
              Criar conta
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
