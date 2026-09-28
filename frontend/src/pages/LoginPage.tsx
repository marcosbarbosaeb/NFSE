import { ArrowLeft, Mail } from "lucide-react"
import { type FormEvent, type ReactNode, useState } from "react"
import { Link, Navigate, useSearchParams } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { GoogleIcon } from "../components/ui/GoogleIcon"
import { ApiError, useAuth } from "../lib/auth"
import { api, formatarErro } from "../lib/api"
import { AnaAvatar } from "../components/brand/Marca"
import { urlLanding } from "../lib/dominios"

// Marco 16, item 1 — mensagens do redirect de volta de /api/auth/google/callback
// (ver app/main.py: nunca JSON, sempre um redirect com ?erro=... nessa volta).
const ERRO_GOOGLE: Record<string, string> = {
  google: "Não conseguimos entrar com sua conta Google agora. Tente de novo ou entre com e-mail e senha.",
  "confirme-email": "Essa conta ainda não confirmou o e-mail — confira sua caixa de entrada antes de entrar com o Google.",
}

const classeInput =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function LoginPage() {
  const { usuario, login, loginComGoogle } = useAuth()
  const [modo, setModo] = useState<"senha" | "codigo">("senha")
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState("")
  const [senha, setSenha] = useState("")
  const [erro, setErro] = useState<string | null>(() => {
    const codigo = searchParams.get("erro")
    return codigo ? (ERRO_GOOGLE[codigo] ?? null) : null
  })
  const [enviando, setEnviando] = useState(false)
  const [emailNaoConfirmado, setEmailNaoConfirmado] = useState(false)
  const [reenviado, setReenviado] = useState(false)
  const [erroGoogle, setErroGoogle] = useState<string | null>(null)

  if (usuario) return <Navigate to="/app" replace />

  if (modo === "codigo") {
    return (
      <MolduraLogin>
        <EntrarComCodigo emailInicial={email} onVoltar={(e) => { setEmail(e); setModo("senha") }} />
      </MolduraLogin>
    )
  }

  async function onGoogleClick() {
    setErroGoogle(null)
    try {
      await loginComGoogle()
    } catch (err) {
      setErroGoogle(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    }
  }

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
    <MolduraLogin>
        <form onSubmit={onSubmit}>
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail</span>
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={classeInput} />
          </label>
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Senha</span>
            <input type="password" required autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} className={classeInput} />
          </label>
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

          <div className="my-4 flex items-center gap-3">
            <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            <span className="text-xs text-slate-400 dark:text-slate-500">ou</span>
            <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
          </div>
          {erroGoogle && <p className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroGoogle}</p>}
          <div className="flex flex-col gap-2">
            <Button type="button" variant="outline" onClick={onGoogleClick} className="w-full">
              <GoogleIcon /> Continuar com Google
            </Button>
            <Button type="button" variant="outline" onClick={() => { setErro(null); setModo("codigo") }} className="w-full">
              <Mail size={17} className="text-slate-500 dark:text-slate-400" aria-hidden="true" /> Entrar com código por e-mail
            </Button>
          </div>

          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            Ainda não tem conta?{" "}
            <Link to="/cadastro" className="font-medium text-primary-600 hover:text-primary-700">
              Criar conta
            </Link>
          </p>
          <p className="mt-2 text-center text-sm text-slate-500 dark:text-slate-400">
            Só quer conhecer?{" "}
            <Link to="/simulacao" className="font-medium text-accent-600 hover:text-accent-700">
              Testar sem cadastro
            </Link>
          </p>
        </form>
    </MolduraLogin>
  )
}

function MolduraLogin({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10 dark:bg-canvas-dark">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <a href={urlLanding()} aria-label="Agente Ana — página inicial">
            <AnaAvatar size={56} />
          </a>
          <p className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            <span className="font-normal opacity-80">Agente</span> <span className="text-accent-500">Ana</span>
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">Entre no seu emissor de notas</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">{children}</div>
      </div>
    </div>
  )
}

// Login sem senha (29/09/2026): manda um código de 6 dígitos pro e-mail
// (POST /auth/codigo, que responde igual exista a conta ou não) e entra com
// ele (POST /auth/codigo/entrar).
function EntrarComCodigo({ emailInicial, onVoltar }: { emailInicial: string; onVoltar: (email: string) => void }) {
  const { entrarComCodigo } = useAuth()
  const [etapa, setEtapa] = useState<"email" | "codigo">("email")
  const [email, setEmail] = useState(emailInicial)
  const [codigo, setCodigo] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [reenviado, setReenviado] = useState(false)

  async function pedirCodigo(e?: FormEvent) {
    e?.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await api.post("/auth/codigo", { email: email.trim() })
      if (etapa === "codigo") setReenviado(true)
      setEtapa("codigo")
      setCodigo("")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  async function entrar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await entrarComCodigo(email.trim(), codigo)
      // Com o usuário no contexto, o LoginPage redireciona pra /app.
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      setEnviando(false)
    }
  }

  const voltar = (
    <button
      type="button"
      onClick={() => onVoltar(email)}
      className="mt-4 flex w-full items-center justify-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400"
    >
      <ArrowLeft size={15} aria-hidden="true" /> Entrar com senha ou Google
    </button>
  )

  if (etapa === "email") {
    return (
      <form onSubmit={pedirCodigo}>
        <h1 className="mb-1 text-base font-semibold text-slate-800 dark:text-slate-100">Entrar com código</h1>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Mandamos um código de 6 dígitos pro seu e-mail — sem precisar de senha.</p>
        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail</span>
          <input type="email" required autoFocus autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={classeInput} />
        </label>
        {erro && <p role="alert" className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
        <Button type="submit" disabled={enviando} className="w-full">
          {enviando ? "Enviando..." : "Enviar código"}
        </Button>
        {voltar}
      </form>
    )
  }

  return (
    <form onSubmit={entrar}>
      <h1 className="mb-1 text-base font-semibold text-slate-800 dark:text-slate-100">Digite o código</h1>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400" role="status">
        Se houver conta com <span className="font-medium text-slate-700 dark:text-slate-200">{email}</span>, enviamos um código de 6
        dígitos. Ele vale por 10 minutos.
      </p>
      <label className="mb-4 block">
        <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Código</span>
        <input
          type="text"
          required
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          placeholder="000000"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))}
          className={`${classeInput} text-center font-mono text-xl tracking-[0.5em]`}
        />
      </label>
      {erro && <p role="alert" className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
      {reenviado && !erro && <p className="mb-3 text-sm text-success-700">Mandamos um código novo.</p>}
      <Button type="submit" disabled={enviando || codigo.length !== 6} className="w-full">
        {enviando ? "Entrando..." : "Entrar"}
      </Button>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <button type="button" onClick={() => { setEtapa("email"); setErro(null); setReenviado(false) }} className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200">
          Trocar e-mail
        </button>
        <button type="button" onClick={() => pedirCodigo()} disabled={enviando} className="font-medium text-primary-600 hover:text-primary-700 disabled:opacity-50 dark:text-primary-400">
          Reenviar código
        </button>
      </div>
      {voltar}
    </form>
  )
}
