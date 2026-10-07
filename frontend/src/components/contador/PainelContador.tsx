import { AlertTriangle, ArrowRight, Building2, CircleCheck, Download, FileText, Loader2, ShieldAlert, Wallet } from "lucide-react"
import { useState } from "react"
import { ApiError, formatarErro } from "../../lib/api"
import { formatarDocumento } from "../../lib/documento"
import { deslocarCompetencia, formatBRL, formatCompetenciaAbrev, formatCompetenciaLonga } from "../../lib/format"
import type { AlertaDoCliente, ClienteAtendido, RaioX, ResumoCarteira } from "../../lib/types"
import { nomeEmpresa } from "../TrocaEmpresa"
import { Card } from "../ui/Card"
import { StatCard } from "../ui/StatCard"

// Painel do contador (07/10/2026) — a contraproposta à ideia que o Marcos
// trouxe: números da carteira, central de alertas e o raio-x de cada empresa,
// tudo sem entrar em nenhuma. As contas ficam em backend/app/services/raio_x.py.

const nome = (c: ClienteAtendido) => nomeEmpresa({ nome_fantasia: c.nome_fantasia, razao_social: c.empresa })

/** R$ 81 mil, R$ 4,8 mi — pra caber na barra. */
function curto(valor: number): string {
  if (valor >= 1_000_000) return `R$ ${(valor / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`
  if (valor >= 10_000) return `R$ ${(valor / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`
  return formatBRL(valor)
}

export function CardsDaCarteira({ resumo }: { resumo: ResumoCarteira }) {
  const mes = resumo.competencia ? formatCompetenciaLonga(resumo.competencia).toLowerCase() : "este mês"
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard icon={<Building2 size={18} />} label="Empresas que atendo" value={resumo.empresas} />
      <StatCard icon={<FileText size={18} />} label="Notas autorizadas" value={resumo.notas_mes.toLocaleString("pt-BR")} sublabel={`em ${mes}`} />
      <StatCard icon={<Wallet size={18} />} label="Faturado em notas" value={curto(resumo.faturado_mes)} sublabel={`em ${mes}, somando todas`} />
      <StatCard
        icon={<ShieldAlert size={18} />}
        iconClassName={
          resumo.alertas_criticos > 0
            ? "bg-danger-50 text-danger-600 dark:bg-danger-900/40 dark:text-danger-300"
            : resumo.alertas > 0
              ? "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300"
              : "bg-success-50 text-success-600 dark:bg-success-900/40 dark:text-success-300"
        }
        label="Alertas"
        value={resumo.alertas}
        sublabel={resumo.alertas === 0 ? "nada pedindo atenção" : resumo.alertas_criticos > 0 ? `${resumo.alertas_criticos} urgente${resumo.alertas_criticos === 1 ? "" : "s"}` : "nenhum urgente"}
        sublabelClassName={resumo.alertas_criticos > 0 ? "text-danger-600 dark:text-danger-300" : undefined}
      />
    </div>
  )
}

/** Central de alertas: o que é urgente em toda a carteira, primeiro. */
export function CentralDeAlertas({
  clientes,
  desligado,
  aoAbrir,
}: {
  clientes: ClienteAtendido[]
  desligado: boolean
  aoAbrir: (c: ClienteAtendido, link: string) => void
}) {
  const linhas = clientes
    .flatMap((c) => (c.alertas ?? []).map((a) => ({ c, a })))
    .sort((x, y) => Number(y.a.nivel === "critico") - Number(x.a.nivel === "critico"))
  const [todos, setTodos] = useState(false)
  if (linhas.length === 0) return null
  const visiveis = todos ? linhas : linhas.slice(0, 6)
  return (
    <Card className="p-5" data-painel="alertas">
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <AlertTriangle size={16} aria-hidden /> Precisa da sua atenção
      </h2>
      <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">Clique pra abrir a empresa já na tela onde isso se resolve.</p>
      <ul className="flex flex-col">
        {visiveis.map(({ c, a }, i) => (
          <li key={`${c.id}-${a.tipo}-${i}`}>
            <button
              type="button"
              disabled={desligado}
              onClick={() => aoAbrir(c, a.link)}
              className="group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:opacity-60 dark:hover:bg-slate-700/40"
            >
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${a.nivel === "critico" ? "bg-danger-600" : "bg-warning-600"}`} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="font-semibold text-slate-800 dark:text-slate-100">{nome(c)}</span>
                <span className="text-slate-400"> · </span>
                <span className="text-slate-600 dark:text-slate-300">{a.texto}</span>
              </span>
              <span className="sr-only">{a.nivel === "critico" ? "urgente" : "atenção"}</span>
              <ArrowRight size={14} className="shrink-0 text-slate-300 group-hover:text-primary-600 dark:text-slate-600" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      {linhas.length > 6 && (
        <button type="button" onClick={() => setTodos((v) => !v)} className="mt-1 px-2 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300">
          {todos ? "Mostrar menos" : `Ver os ${linhas.length} alertas`}
        </button>
      )}
    </Card>
  )
}

const FECHAMENTO: Record<string, { texto: string; cor: string }> = {
  fechado: { texto: "fechado", cor: "text-success-700 dark:text-success-300" },
  pendente: { texto: "falta conferir", cor: "text-warning-700 dark:text-warning-300" },
  aguardando: { texto: "aguardando pagamentos", cor: "text-slate-600 dark:text-slate-300" },
  vazio: { texto: "nada lançado", cor: "text-slate-400 dark:text-slate-500" },
}

export function BarraDoLimite({ raio, compacta = false }: { raio: RaioX; compacta?: boolean }) {
  if (raio.limite == null || raio.limite_pct == null) {
    return <span className="text-xs text-slate-400 dark:text-slate-500">{compacta ? "—" : "Sem limite de faturamento pra acompanhar neste regime."}</span>
  }
  const pct = raio.limite_pct
  const cor = pct >= 100 ? "bg-danger-600" : pct >= 80 ? "bg-warning-600" : "bg-primary-500"
  return (
    <div className={compacta ? "min-w-[9.5rem]" : ""}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="whitespace-nowrap text-slate-600 dark:text-slate-300">
          {curto(raio.faturado_ano)} <span className="text-slate-400">de {curto(raio.limite)}</span>
        </span>
        <span className={`font-semibold ${pct >= 100 ? "text-danger-600" : pct >= 80 ? "text-warning-700 dark:text-warning-300" : "text-slate-500 dark:text-slate-400"}`}>
          {pct.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%
        </span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(100, Math.round(pct))}
        aria-label={`Faturado no ano: ${Math.round(pct)}% do limite do regime`}
      >
        <div className={`h-full rounded-full ${cor}`} style={{ width: `${Math.min(100, Math.max(pct, 1.5))}%` }} />
      </div>
    </div>
  )
}

function Fechamento({ raio }: { raio: RaioX }) {
  if (!raio.fechamento) return <span className="text-slate-400 dark:text-slate-500">—</span>
  const f = FECHAMENTO[raio.fechamento.estado] ?? FECHAMENTO.vazio
  return (
    <span className={f.cor}>
      {raio.fechamento.estado === "fechado" && <CircleCheck size={13} className="mr-1 inline align-[-2px]" aria-hidden />}
      {formatCompetenciaAbrev(raio.fechamento.competencia)}: {f.texto}
    </span>
  )
}

/** Baixa o .zip (XML + PDF) das notas de um mês, sem entrar na empresa. */
export function BaixarNotasDoMes({ cliente, compacto = false }: { cliente: ClienteAtendido; compacto?: boolean }) {
  const atual = cliente.raio_x?.competencia ?? new Date().toISOString().slice(0, 7)
  const meses = [1, 0, 2, 3, 4, 5].map((n) => deslocarCompetencia(atual, -n)) // o mês passado primeiro: é o que se fecha
  const [mes, setMes] = useState(meses[0])
  const [baixando, setBaixando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  async function baixar() {
    setBaixando(true)
    setErro(null)
    try {
      const resp = await fetch(`/api/contador/atendimentos/${cliente.id}/pacote?competencia=${mes}`)
      if (!resp.ok) {
        const corpo = await resp.json().catch(() => null)
        throw new ApiError(resp.status, corpo?.detail ?? "Não consegui montar o pacote agora.")
      }
      const url = URL.createObjectURL(await resp.blob())
      const a = document.createElement("a")
      a.href = url
      a.download = `notas-${cliente.cnpj.replace(/\W/g, "")}-${mes}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setBaixando(false)
    }
  }
  return (
    <div className={compacto ? "" : "mt-3"}>
      <div className="flex flex-wrap items-center gap-2">
        {!compacto && (
          <>
        <label className="sr-only" htmlFor={`mes-${cliente.id}`}>
          Mês das notas de {nome(cliente)}
        </label>
        <select
          id={`mes-${cliente.id}`}
          value={mes}
          onChange={(e) => setMes(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
        >
          {[...meses].sort().reverse().map((m) => (
            <option key={m} value={m}>
              {formatCompetenciaAbrev(m)}
            </option>
          ))}
        </select>
          </>
        )}
        <button
          type="button"
          onClick={() => void baixar()}
          disabled={baixando}
          title={`Baixar o .zip com os XMLs e PDFs das notas autorizadas de ${formatCompetenciaLonga(mes).toLowerCase()}`}
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {baixando ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <Download size={15} aria-hidden />}
          {compacto ? <span className="sr-only">Notas de {formatCompetenciaAbrev(mes)}</span> : "Baixar notas do mês (XML + PDF)"}
        </button>
      </div>
      {erro && (
        <p role="alert" className="mt-1 max-w-[16rem] whitespace-normal text-xs text-danger-600">
          {erro}
        </p>
      )}
    </div>
  )
}

/** A faixa de números dentro do cartão de cada empresa. */
export function RaioXDoCliente({ cliente }: { cliente: ClienteAtendido }) {
  const r = cliente.raio_x
  if (!r) return null
  const mes = formatCompetenciaAbrev(r.competencia)
  const cert = r.certificado
  return (
    <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/30" data-raio-x>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Regime</dt>
          <dd className="font-medium text-slate-800 dark:text-slate-100">{r.regime_nome}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Notas em {mes}</dt>
          <dd className="font-medium text-slate-800 dark:text-slate-100">
            {r.notas_mes} <span className="font-normal text-slate-500 dark:text-slate-400">· {formatBRL(r.faturado_mes)}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">12 meses anteriores</dt>
          <dd className="font-medium text-slate-800 dark:text-slate-100" title="Soma das notas autorizadas nos 12 meses antes deste (a base do RBT12)">
            {formatBRL(r.faturado_12m)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Fechamento</dt>
          <dd className="font-medium">
            <Fechamento raio={r} />
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Faturado em notas no ano × limite do regime
          </dt>
          <dd>
            <BarraDoLimite raio={r} />
          </dd>
        </div>
        {cert && (
          <div className="col-span-2">
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Certificado digital</dt>
            <dd
              className={`font-medium ${
                cert.situacao === "ok" ? "text-slate-800 dark:text-slate-100" : cert.situacao === "vencendo" && (cert.dias ?? 0) > 15 ? "text-warning-700 dark:text-warning-300" : "text-danger-600 dark:text-danger-300"
              }`}
            >
              {cert.situacao === "falta"
                ? "Não enviado"
                : cert.situacao === "vencido"
                  ? "Vencido"
                  : cert.validade
                    ? `Vale até ${cert.validade.split("-").reverse().join("/")}${cert.situacao === "vencendo" ? ` (${cert.dias === 0 ? "vence hoje" : `faltam ${cert.dias} dia${cert.dias === 1 ? "" : "s"}`})` : ""}`
                    : "Em dia"}
            </dd>
          </div>
        )}
      </dl>
      {cliente.modulos.includes("emissor") && <BaixarNotasDoMes cliente={cliente} />}
    </div>
  )
}

/** Raio-X em tabela: a carteira inteira numa tela (pra quem atende várias). */
export function TabelaRaioX({
  clientes,
  ativa,
  desligado,
  aoAbrir,
}: {
  clientes: ClienteAtendido[]
  ativa: string
  desligado: boolean
  aoAbrir: (c: ClienteAtendido, link?: string) => void
}) {
  const th = "px-2.5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
  const td = "px-2.5 py-3 align-top text-sm text-slate-700 dark:text-slate-200"
  return (
    <Card className="overflow-hidden" data-painel="tabela">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[62rem] border-collapse">
          <thead className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-700 dark:bg-slate-900/30">
            <tr>
              <th scope="col" className={th}>Empresa</th>
              <th scope="col" className={th}>Regime</th>
              <th scope="col" className={`${th} whitespace-nowrap text-right`}>Notas no mês</th>
              <th scope="col" className={th}>No ano × limite</th>
              <th scope="col" className={`${th} whitespace-nowrap text-right`}>12 meses ant.</th>
              <th scope="col" className={th}>Fechamento</th>
              <th scope="col" className={th}>Situação</th>
              <th scope="col" className={`${th} text-right`}>Baixar · abrir</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {clientes.map((c) => {
              const r = c.raio_x
              const criticos = (c.alertas ?? []).filter((a: AlertaDoCliente) => a.nivel === "critico").length
              const avisos = (c.alertas ?? []).length - criticos
              const pend = c.total_pendencias ?? 0
              return (
                <tr key={c.id} className={c.prestador_id === ativa ? "bg-primary-50/40 dark:bg-primary-900/10" : ""}>
                  <th scope="row" className={`${td} max-w-[13rem] text-left font-normal`}>
                    <span className="block truncate font-semibold text-slate-900 dark:text-slate-100">{nome(c)}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">{formatarDocumento(c.cnpj)}</span>
                  </th>
                  <td className={`${td} whitespace-nowrap`}>{r?.regime_nome ?? "—"}</td>
                  <td className={`${td} whitespace-nowrap text-right`}>
                    {r ? (
                      <>
                        <span className="font-semibold">{r.notas_mes}</span>
                        <span className="block text-xs text-slate-500 dark:text-slate-400">{formatBRL(r.faturado_mes)}</span>
                      </>
                    ) : "—"}
                  </td>
                  <td className={td}>{r ? <BarraDoLimite raio={r} compacta /> : "—"}</td>
                  <td className={`${td} whitespace-nowrap text-right`}>{r ? formatBRL(r.faturado_12m) : "—"}</td>
                  <td className={`${td} whitespace-nowrap text-xs`}>{r ? <Fechamento raio={r} /> : "—"}</td>
                  <td className={`${td} whitespace-nowrap text-xs`}>
                    {criticos + avisos + pend === 0 ? (
                      <span className="text-success-700 dark:text-success-300">em dia</span>
                    ) : (
                      <span className="flex flex-col gap-0.5">
                        {criticos > 0 && <span className="font-semibold text-danger-600 dark:text-danger-300">{criticos} urgente{criticos === 1 ? "" : "s"}</span>}
                        {avisos > 0 && <span className="text-warning-700 dark:text-warning-300">{avisos} alerta{avisos === 1 ? "" : "s"}</span>}
                        {pend > 0 && <span className="text-slate-600 dark:text-slate-300">{pend} pendência{pend === 1 ? "" : "s"}</span>}
                      </span>
                    )}
                  </td>
                  <td className={`${td} whitespace-nowrap`}>
                    <div className="flex items-center justify-end gap-2">
                      {c.modulos.includes("emissor") && <BaixarNotasDoMes cliente={c} compacto />}
                      <button
                        type="button"
                        disabled={desligado || c.prestador_id === ativa}
                        onClick={() => aoAbrir(c)}
                        className="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                      >
                        {c.prestador_id === ativa ? "Aberta" : "Abrir"}
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
