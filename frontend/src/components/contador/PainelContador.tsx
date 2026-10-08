import { ArrowRight, CircleCheck, Download, Loader2 } from "lucide-react"
import { useState } from "react"
import { ApiError, formatarErro } from "../../lib/api"
import { formatarDocumento } from "../../lib/documento"
import { deslocarCompetencia, formatBRL, formatCompetenciaAbrev, formatCompetenciaLonga } from "../../lib/format"
import type { ClienteAtendido, RaioX, ResumoCarteira } from "../../lib/types"
import { nomeEmpresa } from "../TrocaEmpresa"

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

/** Baixa o .zip (XML + PDF) das notas de um mês, sem entrar na empresa. */
export function BaixarNotasDoMes({ cliente, compacto = false, mesFixo }: { cliente: ClienteAtendido; compacto?: boolean; /** Baixa sempre este mês (sem seletor). */ mesFixo?: string }) {
  const atual = cliente.raio_x?.competencia ?? new Date().toISOString().slice(0, 7)
  const meses = [1, 0, 2, 3, 4, 5].map((n) => deslocarCompetencia(atual, -n)) // o mês passado primeiro: é o que se fecha
  const [mesEscolhido, setMes] = useState(meses[0])
  const mes = mesFixo ?? mesEscolhido
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
        {!compacto && !mesFixo && (
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
          {mesFixo ? "XML + PDF" : compacto ? <span className="sr-only">Notas de {formatCompetenciaAbrev(mes)}</span> : "Baixar notas do mês (XML + PDF)"}
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

// ---------------------------------------------------------------------------
// 08/10/2026 — painel próprio do contador. "É válido ele entrar em cada
// empresa, mas seria mais válido ele ter um painel próprio e trocar as empresas
// e ver os dados que lhe interessa." Três telas em volta da rotina dele:
// Hoje (uma fila só), Fechamento do mês (quadro) e Empresas (a carteira), mais
// a ficha de cada empresa — tudo sem entrar em nenhuma.
// ---------------------------------------------------------------------------

export interface TarefaDoContador {
  chave: string
  cliente: ClienteAtendido
  texto: string
  link: string
  /** 0 urgente · 1 atrasada · 2 atenção · 3 a fazer */
  peso: number
}

/** Tudo o que pede ação, de todas as empresas (ou de uma), numa fila só. */
export function tarefasDe(clientes: ClienteAtendido[]): TarefaDoContador[] {
  const fila: TarefaDoContador[] = []
  for (const c of clientes) {
    ;(c.alertas ?? []).forEach((a, i) =>
      fila.push({ chave: `${c.id}-a-${a.tipo}-${i}`, cliente: c, texto: a.texto, link: a.link, peso: a.nivel === "critico" ? 0 : 2 }),
    )
    ;(c.pendencias ?? []).forEach((p, i) => {
      // nota recusada já está nos alertas: não repete
      if (p.tipo === "erro" || p.tipo === "indisponivel") return
      fila.push({ chave: `${c.id}-p-${p.tipo}-${i}`, cliente: c, texto: p.titulo, link: p.link, peso: p.atrasada ? 1 : 3 })
    })
  }
  return fila.sort((a, b) => a.peso - b.peso)
}

const SELO_TAREFA = [
  { texto: "urgente", cor: "bg-danger-50 text-danger-700 dark:bg-danger-900/40 dark:text-danger-300", ponto: "bg-danger-600" },
  { texto: "atrasada", cor: "bg-danger-50 text-danger-700 dark:bg-danger-900/40 dark:text-danger-300", ponto: "bg-danger-600" },
  { texto: "atenção", cor: "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300", ponto: "bg-warning-600" },
  { texto: "a fazer", cor: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300", ponto: "bg-slate-400" },
]

export function FilaDeTarefas({
  tarefas,
  desligado,
  aoResolver,
  aoVerEmpresa,
  semEmpresa = false,
  limite = 12,
}: {
  tarefas: TarefaDoContador[]
  desligado: boolean
  aoResolver: (c: ClienteAtendido, link: string) => void
  aoVerEmpresa?: (c: ClienteAtendido) => void
  /** Dentro da ficha de uma empresa: não repete o nome dela em cada linha. */
  semEmpresa?: boolean
  limite?: number
}) {
  const [tudo, setTudo] = useState(false)
  if (tarefas.length === 0) {
    return (
      <p className="flex items-center gap-2 rounded-xl bg-success-50 px-4 py-3 text-sm font-medium text-success-700 dark:bg-success-900/30 dark:text-success-300">
        <CircleCheck size={16} aria-hidden /> Nada pedindo a sua atenção agora.
      </p>
    )
  }
  const visiveis = tudo ? tarefas : tarefas.slice(0, limite)
  return (
    <>
      <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
        {visiveis.map((t) => {
          const selo = SELO_TAREFA[t.peso]
          return (
            <li key={t.chave} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${selo.ponto}`} aria-hidden />
              <div className="min-w-0 flex-1 basis-60">
                <p className="text-sm text-slate-800 dark:text-slate-100">{t.texto}</p>
                {!semEmpresa && (
                  <button
                    type="button"
                    onClick={() => aoVerEmpresa?.(t.cliente)}
                    className="text-xs font-medium text-slate-500 hover:text-primary-700 hover:underline dark:text-slate-400 dark:hover:text-primary-300"
                  >
                    {nome(t.cliente)}
                  </button>
                )}
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${selo.cor}`}>{selo.texto}</span>
              <button
                type="button"
                disabled={desligado}
                onClick={() => aoResolver(t.cliente, t.link)}
                title="Abre a empresa já na tela onde isso se resolve"
                className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                Resolver <ArrowRight size={14} aria-hidden />
              </button>
            </li>
          )
        })}
      </ul>
      {tarefas.length > limite && (
        <button type="button" onClick={() => setTudo((v) => !v)} className="mt-2 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300">
          {tudo ? "Mostrar menos" : `Ver as ${tarefas.length} tarefas`}
        </button>
      )}
    </>
  )
}

/** A faixa de números da carteira, numa linha (no lugar dos quatro cartões). */
export function FaixaDaCarteira({ resumo }: { resumo: ResumoCarteira }) {
  const mes = resumo.competencia ? formatCompetenciaLonga(resumo.competencia).toLowerCase() : "este mês"
  const item = (valor: string | number, rotulo: string, cor = "text-slate-900 dark:text-slate-100") => (
    <div className="min-w-0">
      <dd className={`text-xl font-semibold tabular-nums ${cor}`}>{valor}</dd>
      <dt className="text-xs text-slate-500 dark:text-slate-400">{rotulo}</dt>
    </div>
  )
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-2xl border border-slate-200/70 bg-white px-5 py-4 sm:grid-cols-4 dark:border-slate-700/70 dark:bg-slate-800" data-painel="faixa">
      {item(resumo.empresas, resumo.empresas === 1 ? "empresa" : "empresas")}
      {item(resumo.notas_mes.toLocaleString("pt-BR"), `notas em ${mes}`)}
      {item(curto(resumo.faturado_mes), `faturado em notas em ${mes}`)}
      {item(
        resumo.alertas_criticos > 0 ? resumo.alertas_criticos : resumo.alertas + resumo.pendencias,
        resumo.alertas_criticos > 0 ? (resumo.alertas_criticos === 1 ? "coisa urgente" : "coisas urgentes") : "itens pra fazer",
        resumo.alertas_criticos > 0 ? "text-danger-600 dark:text-danger-300" : undefined,
      )}
    </dl>
  )
}

// --- Fechamento do mês -----------------------------------------------------

const COLUNAS_FECHAMENTO = [
  { id: "pendente", titulo: "Falta conferir", dica: "nota atrasada ou extrato sem classificar", cor: "border-warning-600", ponto: "bg-warning-600" },
  { id: "aguardando", titulo: "Aguardando pagamento", dica: "só falta cair o que está no prazo", cor: "border-primary-500", ponto: "bg-primary-500" },
  { id: "fechado", titulo: "Fechado", dica: "notas pagas e extrato classificado", cor: "border-success-600", ponto: "bg-success-600" },
  { id: "sem", titulo: "Sem conciliação", dica: "não usa o Financeiro, ou nada lançado no mês", cor: "border-slate-300 dark:border-slate-600", ponto: "bg-slate-400" },
] as const

export function QuadroDeFechamento({
  clientes,
  desligado,
  aoAbrir,
  aoVerEmpresa,
}: {
  clientes: ClienteAtendido[]
  desligado: boolean
  aoAbrir: (c: ClienteAtendido, link: string) => void
  aoVerEmpresa: (c: ClienteAtendido) => void
}) {
  const atual = clientes.find((c) => c.raio_x)?.raio_x?.competencia ?? new Date().toISOString().slice(0, 7)
  const meses = [1, 0, 2].map((n) => deslocarCompetencia(atual, -n)) // o mês passado primeiro: é o que se fecha
  const [mes, setMes] = useState(meses[0])
  const linha = (c: ClienteAtendido) => {
    const f = c.raio_x?.fechamentos?.find((x) => x.competencia === mes)
    const doMes = c.raio_x?.serie?.find((x) => x.competencia === mes)
    const coluna = !f || f.estado === "vazio" ? "sem" : f.estado
    return { c, f, notas: doMes?.notas ?? 0, valor: doMes?.valor ?? 0, coluna }
  }
  const linhas = clientes.map(linha)
  return (
    <div className="flex flex-col gap-4" data-painel="fechamento">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Em que pé está o fechamento de cada empresa. Baixe as notas do mês (XML + PDF) direto do cartão.
        </p>
        <div className="flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-700" role="group" aria-label="Mês do fechamento">
          {[...meses].sort().map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={m === mes}
              onClick={() => setMes(m)}
              className={`rounded-md px-3 py-1 text-sm font-medium ${m === mes ? "bg-primary-600 text-white" : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"}`}
            >
              {formatCompetenciaAbrev(m)}/{m.slice(2, 4)}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUNAS_FECHAMENTO.map((col) => {
          const daColuna = linhas.filter((l) => l.coluna === col.id)
          return (
            <section key={col.id} aria-label={col.titulo} className={`rounded-2xl border-t-4 bg-slate-50/80 p-3 dark:bg-slate-900/30 ${col.cor}`}>
              <h3 className="flex items-center gap-2 px-1 text-sm font-semibold text-slate-800 dark:text-slate-100">
                <span className={`h-2 w-2 rounded-full ${col.ponto}`} aria-hidden /> {col.titulo}
                <span className="ml-auto rounded-full bg-white px-2 text-xs font-medium tabular-nums text-slate-500 dark:bg-slate-800 dark:text-slate-300">{daColuna.length}</span>
              </h3>
              <p className="mb-2 px-1 text-xs text-slate-500 dark:text-slate-400">{col.dica}</p>
              <ul className="flex flex-col gap-2">
                {daColuna.map(({ c, f, notas, valor }) => (
                  <li key={c.id} className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                    <button type="button" onClick={() => aoVerEmpresa(c)} className="block max-w-full truncate text-left text-sm font-semibold text-slate-900 hover:text-primary-700 hover:underline dark:text-slate-100 dark:hover:text-primary-300">
                      {nome(c)}
                    </button>
                    <p className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                      {notas === 0 ? "nenhuma nota no mês" : `${notas} nota${notas === 1 ? "" : "s"} · ${formatBRL(valor)}`}
                    </p>
                    {f && f.estado === "pendente" && (
                      <p className="mt-1 text-xs text-warning-700 dark:text-warning-300">
                        {[
                          f.notas_atrasadas > 0 && `${f.notas_atrasadas} nota${f.notas_atrasadas === 1 ? "" : "s"} atrasada${f.notas_atrasadas === 1 ? "" : "s"}`,
                          f.extrato_pendentes > 0 && `${f.extrato_pendentes} linha${f.extrato_pendentes === 1 ? "" : "s"} do extrato`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "diferença por conferir"}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {notas > 0 && c.modulos.includes("emissor") && <BaixarNotasDoMes cliente={c} mesFixo={mes} compacto />}
                      {f && f.estado !== "fechado" && f.estado !== "vazio" && (
                        <button
                          type="button"
                          disabled={desligado}
                          onClick={() => aoAbrir(c, "/app/financeiro/conciliacao")}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-primary-700 hover:underline disabled:opacity-60 dark:text-primary-300"
                        >
                          Conferir <ArrowRight size={12} aria-hidden />
                        </button>
                      )}
                    </div>
                  </li>
                ))}
                {daColuna.length === 0 && <li className="px-1 py-2 text-xs text-slate-400 dark:text-slate-500">Nenhuma empresa aqui.</li>}
              </ul>
            </section>
          )
        })}
      </div>
    </div>
  )
}

// --- Empresas (a carteira) --------------------------------------------------

export function ListaDaCarteira({ clientes, ativa, aoVerEmpresa }: { clientes: ClienteAtendido[]; ativa: string; aoVerEmpresa: (c: ClienteAtendido) => void }) {
  return (
    <ul className="flex flex-col gap-2" data-painel="carteira">
      {clientes.map((c) => {
        const r = c.raio_x
        const criticos = (c.alertas ?? []).filter((a) => a.nivel === "critico").length
        const outros = (c.alertas ?? []).length - criticos + (c.total_pendencias ?? 0)
        return (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => aoVerEmpresa(c)}
              className={`grid w-full grid-cols-2 items-center gap-x-4 gap-y-2 rounded-2xl border bg-white px-4 py-3 text-left transition-colors hover:border-primary-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1.1fr)_minmax(0,1.6fr)_minmax(0,1fr)_auto] dark:bg-slate-800 dark:hover:border-primary-600 ${
                c.prestador_id === ativa ? "border-primary-400" : "border-slate-200/70 dark:border-slate-700/70"
              }`}
            >
              <span className="col-span-2 min-w-0 lg:col-span-1">
                <span className="block truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{nome(c)}</span>
                <span className="block text-xs tabular-nums text-slate-500 dark:text-slate-400">{formatarDocumento(c.cnpj)}</span>
              </span>
              <span className="text-sm text-slate-700 dark:text-slate-200">
                <span className="block text-[11px] uppercase tracking-wide text-slate-400 lg:hidden">Regime</span>
                {r?.regime_nome ?? "—"}
              </span>
              <span className="text-sm tabular-nums text-slate-700 dark:text-slate-200">
                <span className="block text-[11px] uppercase tracking-wide text-slate-400 lg:hidden">Notas no mês</span>
                {r ? (
                  <>
                    <strong className="font-semibold">{r.notas_mes}</strong> <span className="text-slate-500 dark:text-slate-400">· {curto(r.faturado_mes)}</span>
                  </>
                ) : "—"}
              </span>
              <span className="col-span-2 lg:col-span-1">{r ? <BarraDoLimite raio={r} compacta /> : null}</span>
              <span className="text-xs">
                {criticos > 0 ? (
                  <span className="font-semibold text-danger-600 dark:text-danger-300">{criticos} urgente{criticos === 1 ? "" : "s"}</span>
                ) : outros > 0 ? (
                  <span className="text-warning-700 dark:text-warning-300">{outros} pra fazer</span>
                ) : (
                  <span className="text-success-700 dark:text-success-300">em dia</span>
                )}
              </span>
              <ArrowRight size={16} className="hidden text-slate-300 lg:block dark:text-slate-600" aria-hidden />
            </button>
          </li>
        )
      })}
    </ul>
  )
}
