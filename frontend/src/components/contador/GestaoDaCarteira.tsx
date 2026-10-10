import { CheckCircle2, CircleDashed, MailCheck, MailWarning, RefreshCw, UserPlus } from "lucide-react"
import { type FormEvent, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { formatarDocumento, mascararCnpj, soDigitos } from "../../lib/documento"
import type { Atendimento, ClienteAtendido, ConsultaCnpj, ResumoCarteira } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { CampoCidade } from "../ui/CampoCidade"
import { Card } from "../ui/Card"
import { Field } from "../ui/Field"
import { Modal } from "../ui/Modal"

// Carteira do contador (2026.10.7): "o contador deve poder fazer a gestão de
// seus clientes no módulo contador". Os números de cada cliente e o cadastro
// de cliente novo (o dono recebe o convite por e-mail). "Ativo no mês" é a
// base da cobrança por cliente — a regra mora em backend/app/services/carteira.py.

const erroDe = (e: unknown) => (e instanceof ApiError ? formatarErro(e.detail) : "Falha de conexão. Tente de novo.")
const brl = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
const dataCurta = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "—")

const SITUACAO: Record<string, { texto: string; tom: "success" | "warning" | "danger" | "neutral" }> = {
  teste: { texto: "Em teste", tom: "warning" },
  assinatura: { texto: "Assinante", tom: "success" },
  cortesia: { texto: "Cortesia", tom: "success" },
  liberacao: { texto: "Liberada", tom: "success" },
  pagamento_pendente: { texto: "Pagamento pendente", tom: "warning" },
  teste_acabou: { texto: "Teste acabou", tom: "danger" },
  cancelada: { texto: "Cancelada", tom: "danger" },
  bloqueada: { texto: "Bloqueada", tom: "danger" },
  sem_assinatura: { texto: "Sem assinatura", tom: "danger" },
}

const CERT: Record<string, string> = { ok: "Em dia", vencendo: "Vencendo", vencido: "Vencido", falta: "Falta" }

export function GestaoDaCarteira({
  clientes,
  resumo,
  aoAtualizar,
  aoVerEmpresa,
}: {
  clientes: ClienteAtendido[]
  resumo?: ResumoCarteira
  aoAtualizar: () => void
  aoVerEmpresa: (c: ClienteAtendido) => void
}) {
  const [cadastrando, setCadastrando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)
  const [reenviando, setReenviando] = useState<string | null>(null)

  async function reenviar(c: ClienteAtendido) {
    setReenviando(c.id)
    setMsg(null)
    try {
      const r = await api.post<{ email_enviado: boolean }>(`/contador/clientes/${c.id}/reenviar-convite`)
      setMsg({ ok: true, texto: r.email_enviado ? `Mandei um link novo para ${c.convite_dono?.email}.` : "O link foi renovado, mas o e-mail não saiu agora. Tente de novo daqui a pouco." })
      aoAtualizar()
    } catch (e) {
      setMsg({ ok: false, texto: erroDe(e) })
    } finally {
      setReenviando(null)
    }
  }

  return (
    <section className="flex flex-col gap-4" aria-label="Gestão da carteira">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Numero titulo="Clientes na carteira" valor={resumo?.na_carteira ?? clientes.length} />
        <Numero titulo="Ativos neste mês" valor={resumo?.ativos_no_mes ?? 0} dica="Emitiram nota autorizada ou usaram a Ana neste mês, sem bloqueio." />
        <Numero titulo="Cadastrados por você" valor={resumo?.cadastrados_pelo_contador ?? 0} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500 dark:text-slate-400">Os números de cada cliente, sem precisar entrar na empresa.</p>
        <Button type="button" variant="accent" onClick={() => setCadastrando(true)}>
          <UserPlus size={16} aria-hidden="true" /> Cadastrar cliente
        </Button>
      </div>
      {msg && (
        <p role="status" className={`rounded-lg px-4 py-3 text-sm ${msg.ok ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300" : "bg-danger-50 text-danger-700"}`}>
          {msg.texto}
        </p>
      )}

      {clientes.length === 0 ? (
        <Card className="p-5 text-sm text-slate-500 dark:text-slate-400">Nenhum cliente ainda. Cadastre o primeiro ou peça a ele que convide você em Empresa › Contador.</Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Empresa</th>
                  <th className="px-3 py-2.5 font-medium">Situação</th>
                  <th className="px-3 py-2.5 text-right font-medium">Notas no mês</th>
                  <th className="px-3 py-2.5 text-right font-medium">Faturado no mês</th>
                  <th className="px-3 py-2.5 font-medium">Certificado</th>
                  <th className="px-3 py-2.5 font-medium">Último uso</th>
                  <th className="px-3 py-2.5 font-medium">Ativo no mês</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                {clientes.map((c) => {
                  const sit = SITUACAO[c.situacao?.motivo] ?? { texto: c.situacao?.motivo ?? "—", tom: "neutral" as const }
                  const cert = c.raio_x?.certificado
                  return (
                    <tr key={c.id} className="align-top">
                      <td className="px-4 py-3">
                        <button type="button" onClick={() => aoVerEmpresa(c)} className="text-left font-medium text-slate-800 hover:text-primary-700 dark:text-slate-100 dark:hover:text-primary-300">
                          {c.nome_fantasia || c.empresa}
                        </button>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{formatarDocumento(c.cnpj)}</p>
                        {c.convite_dono && !c.convite_dono.aceito && (
                          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-warning-700 dark:text-warning-300">
                            {c.convite_dono.vencido ? <MailWarning size={13} aria-hidden="true" /> : <CircleDashed size={13} aria-hidden="true" />}
                            {c.convite_dono.vencido ? "Convite do dono venceu" : `Esperando ${c.convite_dono.email} criar o acesso`}
                            <button
                              type="button"
                              disabled={reenviando === c.id}
                              onClick={() => reenviar(c)}
                              className="inline-flex items-center gap-1 font-semibold underline disabled:opacity-60"
                            >
                              <RefreshCw size={12} aria-hidden="true" /> {reenviando === c.id ? "Enviando..." : "Reenviar"}
                            </button>
                          </p>
                        )}
                        {c.convite_dono?.aceito && (
                          <p className="mt-1 flex items-center gap-1.5 text-xs text-success-700 dark:text-success-300">
                            <MailCheck size={13} aria-hidden="true" /> O dono já entrou
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <Badge variant={sit.tom}>{sit.texto}</Badge>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{c.raio_x?.notas_mes ?? 0}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{brl(c.raio_x?.faturado_mes ?? 0)}</td>
                      <td className="px-3 py-3">{cert ? CERT[cert.situacao] ?? cert.situacao : "—"}</td>
                      <td className="px-3 py-3 text-slate-600 dark:text-slate-300">{dataCurta(c.ultimo_uso)}</td>
                      <td className="px-3 py-3">
                        {c.ativo_no_mes ? (
                          <span className="inline-flex items-center gap-1 text-success-700 dark:text-success-300">
                            <CheckCircle2 size={15} aria-hidden="true" /> Sim
                          </span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500">Não</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {cadastrando && (
        <CadastrarCliente
          aoFechar={() => setCadastrando(false)}
          aoCadastrar={(texto) => {
            setCadastrando(false)
            setMsg({ ok: true, texto })
            aoAtualizar()
          }}
        />
      )}
    </section>
  )
}

function Numero({ titulo, valor, dica }: { titulo: string; valor: number; dica?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{valor}</p>
      {dica && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{dica}</p>}
    </Card>
  )
}

function CadastrarCliente({ aoFechar, aoCadastrar }: { aoFechar: () => void; aoCadastrar: (texto: string) => void }) {
  const [cnpj, setCnpj] = useState("")
  const [razao, setRazao] = useState("")
  const [cidade, setCidade] = useState("")
  const [email, setEmail] = useState("")
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [consultado, setConsultado] = useState("")

  async function consultar(valor: string) {
    const digitos = soDigitos(valor)
    if (digitos.length !== 14 || digitos === consultado) return
    setConsultado(digitos)
    setAviso(null)
    try {
      const d = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      setRazao(d.razao_social)
      if (d.cod_municipio_sugerido) setCidade(d.cod_municipio_sugerido)
    } catch {
      // consulta fora do ar: preenche à mão
    }
    try {
      const a = await api.get<Atendimento>(`/atendimento?cnpj=${digitos}`)
      if (a.titulo) setAviso({ ok: a.pode_criar, texto: `${a.titulo}. ${a.mensagem ?? ""}` })
    } catch {
      // sem veredito: o servidor confere de novo ao cadastrar
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (!cidade) {
      setErro("Escolha a cidade da empresa.")
      return
    }
    setSalvando(true)
    try {
      const r = await api.post<{ empresa: string; email_dono: string; email_enviado: boolean }>("/contador/clientes", {
        cpf_cnpj: soDigitos(cnpj),
        razao_social: razao.trim(),
        cod_municipio: cidade,
        email_dono: email.trim(),
      })
      aoCadastrar(
        r.email_enviado
          ? `${r.empresa} cadastrada. Mandei o convite para ${r.email_dono} criar o acesso dele.`
          : `${r.empresa} cadastrada, mas o e-mail do convite não saiu agora. Use “Reenviar” na lista.`,
      )
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal titulo="Cadastrar cliente" onClose={aoFechar}>
      <form onSubmit={enviar} className="flex flex-col gap-4 p-5">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Eu crio a empresa com o teste grátis dela, você fica com acesso para emitir e cuidar de tudo, e o dono recebe um convite por e-mail para criar o
          acesso dele. Documentos da empresa ficam de fora até o dono liberar.
        </p>
        <Field
          label="CNPJ do cliente"
          inputMode="numeric"
          required
          value={cnpj}
          onChange={(e) => {
            const v = mascararCnpj(e.target.value)
            setCnpj(v)
            void consultar(v)
          }}
          placeholder="00.000.000/0000-00"
        />
        {aviso && (
          <p className={`rounded-lg px-3 py-2 text-sm ${aviso.ok ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300" : "bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300"}`}>
            {aviso.texto}
          </p>
        )}
        <Field label="Razão social" required value={razao} onChange={(e) => setRazao(e.target.value)} maxLength={200} />
        <CampoCidade label="Cidade da empresa" codigo={cidade} onChange={setCidade} required />
        <Field
          label="E-mail do dono da empresa"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          hint="É para ele que vai o convite. Não use o seu e-mail."
        />
        {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={salvando || (aviso !== null && !aviso.ok)}>
            {salvando ? "Cadastrando..." : "Cadastrar e convidar o dono"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
