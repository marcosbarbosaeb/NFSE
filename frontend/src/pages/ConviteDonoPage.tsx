import { type FormEvent, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { AnaAvatar } from "../components/brand/Marca"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { formatarDocumento } from "../lib/documento"

// Convite do dono (2026.10.7): o contador cadastrou a empresa e o dono chega
// aqui pelo link do e-mail. Sem conta: cria o acesso (o e-mail já fica
// confirmado — o link chegou nele). Com conta: entra e aceita, e a empresa
// passa a aparecer no login dele.

interface Convite {
  empresa: string | null
  cnpj: string | null
  email: string
  contador: string | null
  tem_conta: boolean
}

const erroDe = (e: unknown) => (e instanceof ApiError ? formatarErro(e.detail) : "Falha de conexão. Tente de novo.")

export function ConviteDonoPage() {
  const { token = "" } = useParams()
  const { usuario, recarregarUsuario, logout } = useAuth()
  const navigate = useNavigate()
  const [convite, setConvite] = useState<Convite | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [senha, setSenha] = useState("")
  const [senha2, setSenha2] = useState("")
  const [whatsapp, setWhatsapp] = useState("")
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    api
      .get<Convite>(`/convite-dono/${encodeURIComponent(token)}`)
      .then(setConvite)
      .catch((e) => setErro(erroDe(e)))
  }, [token])

  async function criarConta(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (senha !== senha2) {
      setErro("As duas senhas estão diferentes.")
      return
    }
    setEnviando(true)
    try {
      await api.post(`/convite-dono/${encodeURIComponent(token)}/criar-conta`, { senha, whatsapp })
      await recarregarUsuario()
      navigate("/app", { replace: true })
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  async function aceitar() {
    setErro(null)
    setEnviando(true)
    try {
      await api.post(`/convite-dono/${encodeURIComponent(token)}/aceitar`)
      await recarregarUsuario()
      window.location.assign("/app")
    } catch (err) {
      setErro(erroDe(err))
      setEnviando(false)
    }
  }

  const mesmoEmail = usuario && convite && usuario.email.toLowerCase() === convite.email.toLowerCase()

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10 dark:bg-canvas-dark">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-2">
          <AnaAvatar size={56} />
          <p className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            <span className="font-normal opacity-80">Agente</span> <span className="text-accent-500">Ana</span>
          </p>
        </div>
        <Card className="p-6">
          {!convite && !erro && <p className="text-center text-sm text-slate-400">Carregando...</p>}
          {!convite && erro && (
            <div className="flex flex-col gap-3 text-center">
              <p className="text-sm text-slate-700 dark:text-slate-200">{erro}</p>
              <Link to="/entrar" className="text-sm font-medium text-primary-600 hover:text-primary-700">
                Ir para a entrada
              </Link>
            </div>
          )}
          {convite && (
            <div className="flex flex-col gap-4">
              <div>
                <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{convite.empresa}</h1>
                {convite.cnpj && <p className="text-sm text-slate-500 dark:text-slate-400">{formatarDocumento(convite.cnpj)}</p>}
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                  {convite.contador ? <strong>{convite.contador}</strong> : "O seu contador"}, seu contador(a), cadastrou a sua empresa na Agente Ana. Crie o seu acesso
                  para acompanhar as notas e o financeiro.
                </p>
              </div>

              {usuario ? (
                mesmoEmail ? (
                  <Button type="button" variant="accent" onClick={aceitar} disabled={enviando}>
                    {enviando ? "Abrindo..." : "Aceitar e abrir a empresa"}
                  </Button>
                ) : (
                  <div className="flex flex-col gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <p>
                      Você entrou como <strong>{usuario.email}</strong>, mas o convite é para <strong>{convite.email}</strong>.
                    </p>
                    <Button type="button" variant="outline" onClick={() => void logout()}>
                      Sair e entrar com {convite.email}
                    </Button>
                  </div>
                )
              ) : convite.tem_conta ? (
                <div className="flex flex-col gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <p>
                    Você já tem conta com <strong>{convite.email}</strong>. Entre com ela e a empresa passa a aparecer no seu login.
                  </p>
                  <Link
                    to={`/entrar?email=${encodeURIComponent(convite.email)}&volta=${encodeURIComponent(`/convite/${token}`)}`}
                    className="inline-flex justify-center rounded-lg bg-accent-600 px-4 py-2 font-medium text-white hover:bg-accent-700"
                  >
                    Entrar
                  </Link>
                </div>
              ) : (
                <form onSubmit={criarConta} className="flex flex-col gap-3">
                  <Field label="E-mail" value={convite.email} readOnly disabled />
                  <Field label="WhatsApp (com DDD)" inputMode="tel" required value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="(31) 99999-0000" />
                  <Field label="Senha" type="password" required minLength={8} value={senha} onChange={(e) => setSenha(e.target.value)} hint="Pelo menos 8 caracteres." />
                  <Field label="Repita a senha" type="password" required minLength={8} value={senha2} onChange={(e) => setSenha2(e.target.value)} />
                  <Button type="submit" variant="accent" disabled={enviando}>
                    {enviando ? "Criando..." : "Criar meu acesso"}
                  </Button>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Ao criar o acesso você concorda com os <Link to="/termos" className="underline">Termos de uso</Link> e a{" "}
                    <Link to="/privacidade" className="underline">Política de privacidade</Link>.
                  </p>
                </form>
              )}
              {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
