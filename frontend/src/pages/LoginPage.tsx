import { FileText } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Navigate } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { ApiError, useAuth } from "../lib/auth"
import { formatarErro } from "../lib/api"

export function LoginPage() {
  const { usuario, login } = useAuth()
  const [email, setEmail] = useState("")
  const [senha, setSenha] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await login(email, senha)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white">
            <FileText size={22} />
          </div>
          <p className="text-lg font-semibold text-slate-900">
            Nota<span className="text-primary-600">Fácil</span>
          </p>
          <p className="text-sm text-slate-500">NFS-e sem complicação</p>
        </div>

        <form onSubmit={onSubmit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <label className="mb-1 block text-sm font-medium text-slate-700">E-mail</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <label className="mb-1 block text-sm font-medium text-slate-700">Senha</label>
          <input
            type="password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          {erro && <p className="mb-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
          <Button type="submit" disabled={enviando} className="w-full">
            {enviando ? "Entrando..." : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  )
}
