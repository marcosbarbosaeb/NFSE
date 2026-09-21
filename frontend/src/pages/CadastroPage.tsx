import { FileText } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { Field } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import type { CadastroRequest } from "../lib/types"

export function CadastroPage() {
  const { usuario } = useAuth()
  const [razaoSocial, setRazaoSocial] = useState("")
  const [cnpj, setCnpj] = useState("")
  const [codMunicipio, setCodMunicipio] = useState("")
  const [email, setEmail] = useState("")
  const [senha, setSenha] = useState("")
  const [confirmacao, setConfirmacao] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviado, setEnviado] = useState<string | null>(null)

  if (usuario) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (senha.length < 8) {
      setErro("A senha precisa ter pelo menos 8 caracteres.")
      return
    }
    if (senha !== confirmacao) {
      setErro("A confirmação não bate com a senha.")
      return
    }
    setEnviando(true)
    try {
      const payload: CadastroRequest = {
        email,
        senha,
        razao_social: razaoSocial,
        cpf_cnpj: cnpj.replace(/\D/g, ""),
        cod_municipio: codMunicipio.replace(/\D/g, ""),
      }
      const resp = await api.post<{ mensagem: string; email: string }>("/cadastro", payload)
      setEnviado(resp.email)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas dark:bg-canvas-dark px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white">
            <FileText size={22} />
          </div>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Nota<span className="text-primary-600">Fácil</span>
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">Crie sua conta gratuita</p>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
          {enviado ? (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200">Quase lá!</p>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Mandamos um link de confirmação pra <span className="font-medium">{enviado}</span>. Abra sua caixa de
                entrada e clique no link pra ativar sua conta.
              </p>
              <Link to="/entrar" className="mt-2 text-sm font-medium text-primary-600 hover:text-primary-700">
                Voltar pro login
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
              <Field label="Razão social" required value={razaoSocial} onChange={(e) => setRazaoSocial(e.target.value)} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="CNPJ" required value={cnpj} onChange={(e) => setCnpj(e.target.value)} placeholder="14 dígitos" />
                <Field
                  label="Município (código IBGE)"
                  required
                  value={codMunicipio}
                  onChange={(e) => setCodMunicipio(e.target.value)}
                  placeholder="7 dígitos"
                />
              </div>
              <Field label="E-mail" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="Senha" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
                <Field label="Confirmar senha" type="password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
              </div>
              <Button type="submit" disabled={enviando} className="mt-2 w-full">
                {enviando ? "Criando conta..." : "Criar conta"}
              </Button>
              <p className="text-center text-sm text-slate-500 dark:text-slate-400">
                Já tem conta?{" "}
                <Link to="/entrar" className="font-medium text-primary-600 hover:text-primary-700">
                  Entrar
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
