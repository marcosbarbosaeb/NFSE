import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { type FocusEvent, type FormEvent, useEffect, useState } from "react"
import { Link, Navigate, useSearchParams } from "react-router-dom"
import { esquecerCodigoIndicacao, guardarCodigoIndicacao } from "../lib/indicacao"
import { Button } from "../components/ui/Button"
import { CampoCidade } from "../components/ui/CampoCidade"
import { Field } from "../components/ui/Field"
import { GoogleIcon } from "../components/ui/GoogleIcon"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import type { CadastroRequest, Compatibilidade, ConsultaCnpj } from "../lib/types"
import { AnaAvatar } from "../components/brand/Marca"
import { urlLanding } from "../lib/dominios"

export function CadastroPage() {
  const { usuario, loginComGoogle } = useAuth()
  const [searchParams] = useSearchParams()
  const [codigoIndicacao] = useState(() => guardarCodigoIndicacao(searchParams))
  // /cadastro?teste=1 — conta de teste (notas só em homologação).
  const modoTeste = searchParams.get("teste") === "1"
  // /cadastro?produto=financeiro (ou ambos) — qual produto a pessoa veio
  // contratar; sem isso, o emissor de notas.
  const produtoPedido = searchParams.get("produto")
  const produto = produtoPedido === "financeiro" || produtoPedido === "ambos" ? produtoPedido : "emissor"
  // Marco 16, item 1 — volta de /api/auth/google/callback quando a conta
  // Google usada ainda não tem cadastro aqui (ver app/services/
  // google_oauth.py: não dá pra criar a conta só com o que a Google manda,
  // falta CNPJ/razão social) — só pré-preenche o e-mail, editável como
  // qualquer outro campo.
  // Conta só de contador (07/10/2026): /cadastro?tipo=contador — sem CNPJ,
  // sem teste e sem assinatura; ele trabalha nas empresas dos clientes.
  const [tipo, setTipo] = useState<"empresa" | "contador">(searchParams.get("tipo") === "contador" ? "contador" : "empresa")
  const [nome, setNome] = useState(searchParams.get("google_nome") ?? "")
  const [escritorio, setEscritorio] = useState("")
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
  // O e-mail de confirmação saiu? (05/10/2026: o serviço de e-mail tem limite diário.)
  const [emailSaiu, setEmailSaiu] = useState(true)
  // "Reenviar e-mail" na tela de "Quase lá" (05/10/2026), com uma pausa entre os cliques.
  const [reenviando, setReenviando] = useState(false)
  const [avisoReenvio, setAvisoReenvio] = useState<{ ok: boolean; texto: string } | null>(null)
  const [espera, setEspera] = useState(0)
  useEffect(() => {
    if (espera <= 0) return
    const t = setTimeout(() => setEspera((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [espera])

  async function reenviarEmail() {
    if (!enviado) return
    setReenviando(true)
    setAvisoReenvio(null)
    try {
      const r = await api.post<{ mensagem: string; email_enviado?: boolean }>("/cadastro/reenviar-confirmacao", { email: enviado })
      if (r.email_enviado === false) {
        setAvisoReenvio({ ok: false, texto: "Não consegui mandar o e-mail agora — o serviço de e-mail está no limite. Tente de novo mais tarde." })
      } else {
        setEmailSaiu(true)
        setAvisoReenvio({ ok: true, texto: "Reenviei o link. Confira a caixa de entrada e o spam." })
      }
      setEspera(60)
    } catch (err) {
      setAvisoReenvio({
        ok: false,
        texto:
          err instanceof ApiError && err.status === 429
            ? "Você já pediu o reenvio várias vezes. Espere um pouco e tente de novo."
            : "Falha de conexão. Tente de novo.",
      })
    } finally {
      setReenviando(false)
    }
  }
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

  // "A Ana funciona na minha cidade?" (05/10/2026): a emissão depende de a
  // prefeitura usar o Emissor Nacional da NFS-e — conferido pela lista da
  // Receita assim que a cidade é conhecida (pelo CNPJ ou escolhida à mão).
  const [compat, setCompat] = useState<Compatibilidade | null>(null)
  useEffect(() => {
    setCompat(null)
    if (!/^\d{7}$/.test(codMunicipio)) return
    let vivo = true
    api
      .get<Compatibilidade>(`/compatibilidade?cod_municipio=${codMunicipio}`)
      .then((c) => vivo && setCompat(c))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [codMunicipio])
  const querNotas = produto !== "financeiro"

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
    if (tipo === "contador") {
      try {
        const resp = await api.post<{ mensagem: string; email: string; email_enviado?: boolean }>("/cadastro/contador", {
          email,
          senha,
          nome: nome.trim(),
          escritorio: escritorio.trim() || null,
        })
        setEmailSaiu(resp.email_enviado !== false)
        setEnviado(resp.email)
      } catch (err) {
        setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      } finally {
        setEnviando(false)
      }
      return
    }
    try {
      const payload: CadastroRequest = {
        email,
        senha,
        razao_social: razaoSocial,
        cpf_cnpj: cnpj.replace(/\D/g, ""),
        cod_municipio: codMunicipio.replace(/\D/g, ""),
        ...(enderecoAutopreenchido ?? {}),
        codigo_indicacao: modoTeste ? null : codigoIndicacao,
        modo_teste: modoTeste,
        produto,
      }
      const resp = await api.post<{ mensagem: string; email: string; email_enviado?: boolean }>("/cadastro", payload)
      esquecerCodigoIndicacao()
      setEmailSaiu(resp.email_enviado !== false)
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
          <a href={urlLanding()} aria-label="Agente Ana — página inicial">
            <AnaAvatar size={56} />
          </a>
          <p className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            <span className="font-normal opacity-80">Agente</span> <span className="text-accent-500">Ana</span>
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Crie sua conta gratuita
            {produto === "financeiro" ? " · Financeiro" : produto === "ambos" ? " · Notas e Financeiro" : ""}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
          {enviado ? (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200">Quase lá!</p>
              {emailSaiu ? (
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Mandamos um link de confirmação pra <span className="font-medium">{enviado}</span>. Abra sua caixa de
                  entrada e clique no link pra ativar sua conta. Se não achar, olhe no spam.
                </p>
              ) : (
                <p role="alert" className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
                  Sua conta foi criada, mas <strong>não consegui mandar agora o e-mail de confirmação</strong> pra{" "}
                  <span className="font-medium">{enviado}</span>. Use o botão abaixo pra tentar de novo.
                </p>
              )}
              <Button type="button" variant="outline" disabled={reenviando || espera > 0} onClick={reenviarEmail}>
                {reenviando ? "Reenviando..." : espera > 0 ? `Reenviar de novo em ${espera}s` : emailSaiu ? "Não chegou? Reenviar e-mail" : "Reenviar e-mail"}
              </Button>
              {avisoReenvio && (
                <p role="status" className={`text-sm ${avisoReenvio.ok ? "text-success-700 dark:text-success-300" : "text-warning-700 dark:text-warning-300"}`}>
                  {avisoReenvio.texto}
                </p>
              )}
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Digitou o e-mail errado? Faça o cadastro de novo com o e-mail certo.
              </p>
              <Link to="/entrar" className="mt-2 text-sm font-medium text-primary-600 hover:text-primary-700">
                Voltar pro login
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              <div role="tablist" aria-label="Tipo de conta" className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-900/60">
                {(
                  [
                    ["empresa", "Tenho empresa"],
                    ["contador", "Sou contador(a)"],
                  ] as const
                ).map(([id, rotulo]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={tipo === id}
                    onClick={() => {
                      setTipo(id)
                      setErro(null)
                    }}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                      tipo === id
                        ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100"
                        : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                  >
                    {rotulo}
                  </button>
                ))}
              </div>
              {tipo === "contador" && (
                <p className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700 dark:bg-primary-900/30 dark:text-primary-200">
                  <strong>Conta de contador: grátis e sem CNPJ.</strong> Você entra nas empresas dos clientes que te convidarem e cuida das
                  notas e do financeiro por eles. Use o mesmo e-mail em que recebeu o convite.
                </p>
              )}
              {modoTeste && tipo === "empresa" && (
                <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
                  <strong>Conta de teste.</strong> Faça tudo como um cliente novo: as notas saem só em homologação (sem valor fiscal) e os
                  e-mails de nota vão só pro e-mail desta conta. Pode usar o mesmo CNPJ de uma conta real.
                </p>
              )}
              {codigoIndicacao && !modoTeste && (
                <p className="rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700">
                  Você chegou por indicação de um amigo (código {codigoIndicacao.toUpperCase()}).
                </p>
              )}
              {googleEmail && (
                <p className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700">
                  {googleNome ? `Oi, ${googleNome}! ` : ""}Confirme os dados {tipo === "contador" ? "abaixo" : "da sua empresa"} pra terminar de criar a
                  conta com <span className="font-medium">{googleEmail}</span>.
                </p>
              )}
              {!googleEmail && tipo === "empresa" && (
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

              {tipo === "contador" && (
                <>
                  <Field label="Seu nome" required minLength={2} maxLength={120} autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} />
                  <Field
                    label="Nome do escritório (opcional)"
                    maxLength={200}
                    value={escritorio}
                    onChange={(e) => setEscritorio(e.target.value)}
                  />
                </>
              )}
              {tipo === "empresa" && (
                <>
              <div>
                <Field
                  label="CNPJ"
                  required
                  value={cnpj}
                  onChange={(e) => setCnpj(e.target.value)}
                  onBlur={onCnpjBlur}
                  inputMode="numeric"
                  placeholder="14 dígitos"
                  hint="Digite o CNPJ: eu preencho o resto e já confiro se a Ana emite nota na sua cidade."
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

              {compat && querNotas && compat.emissor === "sim" && (
                <p className="flex items-start gap-2 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300" role="status">
                  <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> <span>{compat.mensagem}</span>
                </p>
              )}
              {compat && querNotas && compat.emissor === "nao" && (
                <div className="rounded-lg bg-warning-50 px-3 py-2.5 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300" role="status">
                  <p className="flex items-start gap-2">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" /> <span>{compat.mensagem}</span>
                  </p>
                  <p className="mt-1.5 pl-6 text-xs">
                    Você pode{" "}
                    <Link to="/cadastro?produto=financeiro" className="font-semibold underline">
                      criar a conta só com o Financeiro
                    </Link>{" "}
                    — ou criar assim mesmo, se a prefeitura já liberou o Emissor Nacional pra sua empresa (a lista da Receita é de{" "}
                    {compat.lista_atualizada_em?.split("-").reverse().join("/") ?? "alguns dias atrás"}).
                  </p>
                </div>
              )}

                </>
              )}

              <Field label="E-mail" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="Senha" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
                <Field label="Confirmar senha" type="password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
              </div>
              <Button type="submit" disabled={enviando} className="mt-2 w-full">
                {enviando ? "Criando conta..." : "Criar conta"}
              </Button>
              <p className="text-center text-xs text-slate-400 dark:text-slate-500">
                Ao criar a conta você concorda com os{" "}
                <Link to="/termos" className="underline hover:text-accent-600">Termos de uso</Link> e a{" "}
                <Link to="/privacidade" className="underline hover:text-accent-600">Política de privacidade</Link>.
              </p>
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
