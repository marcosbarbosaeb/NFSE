import { CheckCircle2, KeyRound, Moon, Percent, ShieldAlert, Sun, UploadCloud } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { useAuth } from "../lib/auth"
import { ApiError, api, formatarErro } from "../lib/api"
import { useTheme } from "../lib/theme"
import type { Assinatura, CertificadoStatus, CheckoutSessao, Prestador } from "../lib/types"

export function ConfiguracoesPage() {
  const { tema, definirTema } = useTheme()
  const { usuario } = useAuth()
  const [prestador, setPrestador] = useState<Prestador | null>(null)
  const [certificado, setCertificado] = useState<CertificadoStatus | null>(null)
  const [assinatura, setAssinatura] = useState<Assinatura | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [pfx, setPfx] = useState<File | null>(null)
  const [senha, setSenha] = useState("")
  const [enviandoCert, setEnviandoCert] = useState(false)
  const [erroCert, setErroCert] = useState<string | null>(null)

  function carregar() {
    setCarregando(true)
    setErro(null)
    Promise.all([
      api.get<Prestador>("/prestador"),
      api.get<CertificadoStatus>("/certificado/status"),
      api.get<Assinatura>("/assinatura"),
    ])
      .then(([p, c, a]) => {
        setPrestador(p)
        setCertificado(c)
        setAssinatura(a)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => setCarregando(false))
  }

  useEffect(carregar, [])

  async function enviarCertificado(e: FormEvent) {
    e.preventDefault()
    if (!pfx) return
    setErroCert(null)
    setEnviandoCert(true)
    try {
      const form = new FormData()
      form.append("pfx", pfx)
      form.append("senha", senha)
      const status = await api.postForm<CertificadoStatus>("/certificado", form)
      setCertificado(status)
      setPfx(null)
      setSenha("")
    } catch (err) {
      setErroCert(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviandoCert(false)
    }
  }

  if (carregando) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Configurações</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Aparência, certificado digital e dados do prestador.</p>
      </div>

      <Card className="p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Aparência</h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => definirTema("claro")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
              tema === "claro"
                ? "border-primary-500 bg-primary-50 text-primary-700"
                : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            }`}
          >
            <Sun size={16} /> Claro
          </button>
          <button
            type="button"
            onClick={() => definirTema("escuro")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
              tema === "escuro"
                ? "border-primary-500 bg-primary-50 text-primary-700 dark:border-primary-400 dark:bg-primary-900/40 dark:text-primary-300"
                : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            }`}
          >
            <Moon size={16} /> Escuro
          </button>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Minha conta</h2>
        <div className="mb-4">
          <p className="text-xs text-slate-400 dark:text-slate-500">E-mail de acesso</p>
          <p className="text-sm text-slate-800 dark:text-slate-200">{usuario?.email}</p>
        </div>
        <TrocarSenhaForm />
      </Card>

      {assinatura && <AssinaturaCard assinatura={assinatura} />}

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Certificado digital (A1)</h2>
          {certificado?.carregado ? (
            certificado.vencido ? (
              <Badge variant="danger">Vencido</Badge>
            ) : (
              <Badge variant="success">Carregado</Badge>
            )
          ) : (
            <Badge variant="neutral">Nenhum carregado</Badge>
          )}
        </div>

        {certificado?.carregado && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 px-3 py-2 text-sm text-slate-600 dark:text-slate-300">
            {certificado.vencido ? <ShieldAlert size={16} className="text-danger-600" /> : <CheckCircle2 size={16} className="text-success-600" />}
            {certificado.validade
              ? `Validade: ${new Date(`${certificado.validade}T00:00:00`).toLocaleDateString("pt-BR")}`
              : "Sem data de validade informada."}
          </div>
        )}

        <form onSubmit={enviarCertificado} className="flex flex-col gap-3">
          {erroCert && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroCert}</p>}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo .pfx</span>
            <input
              type="file"
              accept=".pfx,application/x-pkcs12"
              required
              onChange={(e) => setPfx(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </label>
          <Field label="Senha do certificado" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
          <div>
            <Button type="submit" variant="accent" disabled={enviandoCert || !pfx}>
              <UploadCloud size={15} /> {enviandoCert ? "Enviando..." : certificado?.carregado ? "Substituir certificado" : "Enviar certificado"}
            </Button>
          </div>
        </form>
      </Card>

      {prestador && (
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Dados do prestador</h2>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-400 dark:text-slate-500">Razão social</dt>
              <dd className="text-slate-800 dark:text-slate-200">{prestador.razao_social}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400 dark:text-slate-500">CNPJ/CPF</dt>
              <dd className="text-slate-800 dark:text-slate-200">{prestador.cpf_cnpj}</dd>
            </div>
            {prestador.inscricao_municipal && (
              <div>
                <dt className="text-xs text-slate-400 dark:text-slate-500">Inscrição municipal</dt>
                <dd className="text-slate-800 dark:text-slate-200">{prestador.inscricao_municipal}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-slate-400 dark:text-slate-500">Município (IBGE)</dt>
              <dd className="text-slate-800 dark:text-slate-200">{prestador.cod_municipio}</dd>
            </div>
            {(prestador.logradouro || prestador.cep) && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-slate-400 dark:text-slate-500">Endereço</dt>
                <dd className="text-slate-800 dark:text-slate-200">
                  {[prestador.logradouro, prestador.numero, prestador.bairro, prestador.cep].filter(Boolean).join(", ") || "—"}
                </dd>
              </div>
            )}
          </dl>
          <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
            Edição desses dados ainda é administrativa (fora do painel) — fala com quem cuida do backend se precisar mudar algo aqui.
          </p>

          <AliquotaForm prestador={prestador} onAtualizado={setPrestador} />
        </Card>
      )}
    </div>
  )
}

function AliquotaForm({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: (p: Prestador) => void }) {
  const [aliquota, setAliquota] = useState(prestador.aliquota_atual != null ? String(prestador.aliquota_atual) : "")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  const confirmadaEsteMes = (() => {
    if (!prestador.aliquota_atualizada_em) return false
    const hoje = new Date()
    const data = new Date(`${prestador.aliquota_atualizada_em}T00:00:00`)
    return data.getFullYear() === hoje.getFullYear() && data.getMonth() === hoje.getMonth()
  })()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setSucesso(false)
    const numero = Number(aliquota.replace(",", "."))
    if (Number.isNaN(numero) || numero < 0 || numero > 100) {
      setErro("Informe um percentual entre 0 e 100.")
      return
    }
    setEnviando(true)
    try {
      const atualizado = await api.patch<Prestador>("/prestador/aliquota", { aliquota: numero })
      onAtualizado(atualizado)
      setSucesso(true)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mt-6 border-t border-slate-100 dark:border-slate-700/60 pt-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 dark:text-slate-300">
          <Percent size={15} /> Alíquota do Simples Nacional (referência)
        </h3>
        {confirmadaEsteMes ? (
          <Badge variant="success">Confirmada este mês</Badge>
        ) : (
          <Badge variant="warning">{prestador.aliquota_atual == null ? "Não definida" : "Revisar este mês"}</Badge>
        )}
      </div>
      <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">
        Usada só pra pré-preencher o campo de alíquota ao criar uma nova nota — não calcula nem gera boleto de
        imposto, é só pra você não esquecer de conferir o número todo mês (ver lembrete no calendário).
      </p>
      {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {sucesso && <p className="mb-3 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">Alíquota confirmada.</p>}
      <form onSubmit={onSubmit} className="flex items-end gap-3">
        <div className="flex-1">
          <Field
            label="Alíquota (%)"
            type="number"
            step="0.01"
            min="0"
            max="100"
            required
            value={aliquota}
            onChange={(e) => setAliquota(e.target.value)}
          />
        </div>
        <Button type="submit" variant="accent" disabled={enviando}>
          {enviando ? "Salvando..." : "Confirmar"}
        </Button>
      </form>
      {prestador.aliquota_atualizada_em && (
        <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
          Última confirmação: {new Date(`${prestador.aliquota_atualizada_em}T00:00:00`).toLocaleDateString("pt-BR")}
        </p>
      )}
    </div>
  )
}

const STATUS_LABEL: Record<Assinatura["status"], string> = {
  cortesia: "Conta cortesia",
  trial: "Período de teste",
  ativa: "Assinatura ativa",
  inadimplente: "Pagamento pendente",
  cancelada: "Assinatura cancelada",
}

function badgeVariante(assinatura: Assinatura): "success" | "warning" | "danger" | "neutral" {
  if (assinatura.status === "cortesia") return "neutral"
  if (assinatura.status === "ativa") return "success"
  if (assinatura.status === "inadimplente" || assinatura.status === "cancelada") return "danger"
  return "warning" // trial (ainda ativo ou já expirado — ambos avisam, nunca "sucesso" de verdade)
}

function AssinaturaCard({ assinatura }: { assinatura: Assinatura }) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function iniciarCheckoutOuPortal() {
    setErro(null)
    setCarregando(true)
    try {
      const rota = assinatura.tem_assinatura_stripe ? "/assinatura/portal" : "/assinatura/checkout"
      const { url } = await api.post<CheckoutSessao>(rota, {})
      window.location.href = url
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErro("Cobrança ainda não está disponível — a conta Stripe está sendo configurada. Volte em breve.")
      } else {
        setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      }
    } finally {
      setCarregando(false)
    }
  }

  const diasRestantesTrial =
    assinatura.status === "trial" && assinatura.trial_termina_em
      ? Math.max(0, Math.ceil((new Date(assinatura.trial_termina_em).getTime() - Date.now()) / 86_400_000))
      : null

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Assinatura</h2>
        <Badge variant={assinatura.status === "trial" && !assinatura.ativa ? "danger" : badgeVariante(assinatura)}>
          {STATUS_LABEL[assinatura.status]}
        </Badge>
      </div>

      <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
        {assinatura.status === "cortesia" && "Sua conta tem acesso liberado — nada pra fazer aqui."}
        {assinatura.status === "trial" &&
          (diasRestantesTrial !== null && diasRestantesTrial > 0
            ? `Você está no período de teste gratuito — ${diasRestantesTrial} dia${diasRestantesTrial === 1 ? "" : "s"} restante${diasRestantesTrial === 1 ? "" : "s"}.`
            : "Seu período de teste acabou. Assine pra continuar usando o NotaFácil sem interrupção.")}
        {assinatura.status === "ativa" && "Sua assinatura está em dia."}
        {assinatura.status === "inadimplente" && "O último pagamento não foi confirmado — atualize a forma de pagamento pra evitar interrupção."}
        {assinatura.status === "cancelada" && "Sua assinatura foi cancelada. Assine de novo pra recuperar o acesso completo."}
      </p>

      {erro && <p className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {assinatura.status !== "cortesia" && (
        <Button type="button" variant="accent" disabled={carregando} onClick={iniciarCheckoutOuPortal}>
          {carregando ? "Um momento..." : assinatura.tem_assinatura_stripe ? "Gerenciar assinatura" : "Assinar agora"}
        </Button>
      )}
    </Card>
  )
}

function TrocarSenhaForm() {
  const [aberto, setAberto] = useState(false)
  const [senhaAtual, setSenhaAtual] = useState("")
  const [senhaNova, setSenhaNova] = useState("")
  const [confirmacao, setConfirmacao] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  function fechar() {
    setAberto(false)
    setSenhaAtual("")
    setSenhaNova("")
    setConfirmacao("")
    setErro(null)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setSucesso(false)
    if (senhaNova.length < 8) {
      setErro("A nova senha precisa ter pelo menos 8 caracteres.")
      return
    }
    if (senhaNova !== confirmacao) {
      setErro("A confirmação não bate com a nova senha.")
      return
    }
    setEnviando(true)
    try {
      await api.post("/auth/trocar-senha", { senha_atual: senhaAtual, senha_nova: senhaNova })
      setSucesso(true)
      setSenhaAtual("")
      setSenhaNova("")
      setConfirmacao("")
      setTimeout(() => setAberto(false), 1500)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  if (!aberto) {
    return (
      <Button type="button" variant="outline" onClick={() => setAberto(true)}>
        <KeyRound size={15} /> Trocar senha
      </Button>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 border-t border-slate-100 dark:border-slate-700/60 pt-4">
      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {sucesso && <p className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">Senha alterada com sucesso.</p>}
      <Field label="Senha atual" type="password" required value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} />
      <Field label="Nova senha" type="password" required minLength={8} value={senhaNova} onChange={(e) => setSenhaNova(e.target.value)} />
      <Field label="Confirmar nova senha" type="password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
      <div className="flex gap-3">
        <Button type="button" variant="outline" onClick={fechar}>
          Cancelar
        </Button>
        <Button type="submit" variant="accent" disabled={enviando}>
          {enviando ? "Salvando..." : "Salvar nova senha"}
        </Button>
      </div>
    </form>
  )
}
