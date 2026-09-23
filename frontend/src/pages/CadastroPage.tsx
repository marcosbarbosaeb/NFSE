import { AlertTriangle, CheckCircle2, FileText, Loader2 } from "lucide-react"
import { type FocusEvent, type FormEvent, useState } from "react"
import { Link, Navigate, useSearchParams } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { CampoCidade } from "../components/ui/CampoCidade"
import { Field } from "../components/ui/Field"
import { GoogleIcon } from "../components/ui/GoogleIcon"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import type { CadastroRequest, ConsultaCnpj } from "../lib/types"

export function CadastroPage() {
  const { usuario, loginComGoogle } = useAuth()
  const [searchParams] = useSearchParams()
  // Marco 16, item 1 — volta de /api/auth/google/callback quando a conta
  // Google usada ainda não tem cadastro aqui (ver app/services/
  // google_oauth.py: não dá pra criar a conta só com o que a Google manda,
  // falta CNPJ/razão social) — só pré-preenche o e-mail, editável como
  // qualquer outro campo.
  const googleEmail = searchParams.get("google_email")
  const googleNome = searchParams.get("google_nome")
  const [razaoSocial, setRazaoSocial] = useState("")
  const [cnpj, setCnpj] = useState("")
  const [codMunicipio, setCodMunicipio] = useState("")
  const [email, setEmail] = useState(googleEmail ?? "")
  const [senha, setSenha] = useState("")
  const [confirmacao, setConfirmacao] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviado, setEnviado] = useState<string | null>(null)
  const [erroGoogle, setErroGoogle] = useState<string | null>(null)

  // Marco 16 — autopreenchimento via CNPJ (pedido do Marcos: "ninguém sabe
  // o número do IBGE do município"). `enderecoAutopreenchido` guarda o que
  // a consulta trouxe pra mandar junto no cadastro (poupa digitar de novo
  // em Configurações depois) — nunca é a palavra final: razão social e
  // município continuam campos normais, editáveis, e a pessoa sempre pode
  // simplesmente preencher tudo na mão se a consulta falhar ou vier errada.
  const [consultandoCnpj, setConsultandoCnpj] = useState(false)
  const [avisoCnpj, setAvisoCnpj] = useState<string | null>(null)
  const [enderecoResolvido, setEnderecoResolvido] = useState<string | null>(null)
  const [enderecoAutopreenchido, setEnderecoAutopreenchido] = useState<{
    cep: string | null
    logradouro: string | null
    numero: string | null
    complemento: string | null
    bairro: string | null
  } | null>(null)

  if (usuario) return <Navigate to="/app" replace />

  async function onCnpjBlur(e: FocusEvent<HTMLInputElement>) {
    const digitos = e.target.value.replace(/\D/g, "")
    setAvisoCnpj(null)
    setEnderecoResolvido(null)
    setEnderecoAutopreenchido(null)
    if (digitos.length !== 14) return

    setConsultandoCnpj(true)
    try {
      const dados = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      setRazaoSocial(dados.razao_social || razaoSocial)
      if (dados.cod_municipio_sugerido) setCodMunicipio(dados.cod_municipio_sugerido)
      setEnderecoAutopreenchido({
        cep: dados.cep, logradouro: dados.logradouro, numero: dados.numero,
        complemento: dados.complemento, bairro: dados.bairro,
      })
      const partes = [dados.logradouro, dados.numero, dados.bairro].filter(Boolean)
      setEnderecoResolvido(`${partes.join(", ")}${partes.length ? " — " : ""}${dados.municipio}/${dados.uf}`)
      if (dados.situacao_cadastral && dados.situacao_cadastral.toUpperCase() !== "ATIVA") {
        setAvisoCnpj(`Situação cadastral deste CNPJ na Receita: ${dados.situacao_cadastral}. Confirme se está certo antes de continuar.`)
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setAvisoCnpj("Não encontramos esse CNPJ — confira se digitou certo, ou preencha os dados manualmente.")
      } else {
        setAvisoCnpj("Não conseguimos consultar esse CNPJ automaticamente agora — preencha os dados manualmente.")
      }
    } finally {
      setConsultandoCnpj(false)
    }
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
        ...(enderecoAutopreenchido ?? {}),
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
              {googleEmail && (
                <p className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700">
                  {googleNome ? `Oi, ${googleNome}! ` : ""}Confirme os dados da sua empresa pra terminar de criar a
                  conta com <span className="font-medium">{googleEmail}</span>.
                </p>
              )}
              {!googleEmail && (
                <>
                  {erroGoogle && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroGoogle}</p>}
                  <Button type="button" variant="outline" onClick={onGoogleClick} className="w-full">
                    <GoogleIcon /> Continuar com Google
                  </Button>
                  <div className="my-1 flex items-center gap-3">
                    <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
                    <span className="text-xs text-slate-400 dark:text-slate-500">ou</span>
                    <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
                  </div>
                </>
              )}
              {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}

              <div>
                <Field
                  label="CNPJ"
                  required
                  value={cnpj}
                  onChange={(e) => setCnpj(e.target.value)}
                  onBlur={onCnpjBlur}
                  placeholder="14 dígitos"
                  hint="Digite o CNPJ e a gente tenta preencher o resto sozinho."
                />
                {consultandoCnpj && (
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                    <Loader2 size={12} className="animate-spin" /> Consultando CNPJ...
                  </p>
                )}
                {enderecoResolvido && !consultandoCnpj && (
                  <p className="mt-1.5 flex items-start gap-1.5 text-xs text-success-700">
                    <CheckCircle2 size={13} className="mt-0.5 shrink-0" /> {enderecoResolvido}
                  </p>
                )}
                {avisoCnpj && !consultandoCnpj && (
                  <p className="mt-1.5 flex items-start gap-1.5 text-xs text-warning-700">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {avisoCnpj}
                  </p>
                )}
              </div>

              <Field label="Razão social" required value={razaoSocial} onChange={(e) => setRazaoSocial(e.target.value)} />

              <CampoCidade
                label="Cidade"
                required
                codigo={codMunicipio}
                onChange={setCodMunicipio}
                hint={enderecoAutopreenchido ? "Preenchida automaticamente a partir do CNPJ — confira se está certa." : undefined}
              />

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
