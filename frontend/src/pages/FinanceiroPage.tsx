import { ArrowDownCircle, ArrowUpCircle, FileUp, Plus, Scale } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaAbrev } from "../lib/format"
import type { Despesa, Pagamento, VinculoResumo } from "../lib/types"
import { RegistrarDespesaModal } from "./DespesasPage"
import { ImportarExtratoModal, RegistrarPagamentoModal } from "./RecebimentosPage"

// Pedido do Marcos (28/09/2026): "coloque a confrontação de recebimentos e
// despesas na mesma aba, deixe como Financeiro". Uma tela só: o resumo do
// ano (entrou x saiu x sobrou), o confronto mês a mês e as duas listas.

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

type Aba = "recebimentos" | "despesas"

const classeSelect =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function FinanceiroPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const aba: Aba = searchParams.get("aba") === "despesas" ? "despesas" : "recebimentos"
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [pagamentos, setPagamentos] = useState<Pagamento[] | null>(null)
  const [despesas, setDespesas] = useState<Despesa[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [modal, setModal] = useState<"recebimento" | "extrato" | "despesa" | null>(null)

  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos).catch(() => {})
  }, [])

  function recarregar() {
    setErro(null)
    Promise.all([api.get<Pagamento[]>(`/pagamentos?ano=${ano}`), api.get<Despesa[]>(`/despesas?ano=${ano}`)])
      .then(([p, d]) => {
        setPagamentos(p)
        setDespesas(d)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
  }

  useEffect(recarregar, [ano])

  const meses = useMemo(() => {
    const linhas = Array.from({ length: 12 }, (_, i) => {
      const competencia = `${ano}-${String(i + 1).padStart(2, "0")}`
      // Recebimento conta no mês em que o dinheiro caiu (quando a data foi
      // informada); sem data, no mês de competência da nota.
      const recebido = (pagamentos ?? [])
        .filter((p) => (p.data_recebimento ? p.data_recebimento.slice(0, 7) : p.competencia) === competencia)
        .reduce((s, p) => s + p.valor, 0)
      const gasto = (despesas ?? []).filter((d) => d.competencia === competencia).reduce((s, d) => s + d.valor, 0)
      return { competencia, recebido, gasto, saldo: recebido - gasto }
    })
    return linhas
  }, [ano, pagamentos, despesas])

  const totais = meses.reduce((t, m) => ({ recebido: t.recebido + m.recebido, gasto: t.gasto + m.gasto }), { recebido: 0, gasto: 0 })
  const maior = Math.max(1, ...meses.map((m) => Math.max(m.recebido, m.gasto)))
  const mesesComMovimento = meses.filter((m) => m.recebido || m.gasto)
  const carregando = pagamentos === null || despesas === null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Financeiro</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">O que entrou, o que saiu e o que sobrou — mês a mês.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setModal("extrato")} data-tour="financeiro-extrato">
            <FileUp size={16} /> Importar extrato
          </Button>
          <Button variant="outline" onClick={() => setModal("despesa")}>
            <Plus size={16} /> Despesa
          </Button>
          <Button variant="accent" onClick={() => setModal("recebimento")}>
            <Plus size={16} /> Recebimento
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <select value={ano} onChange={(e) => setAno(e.target.value)} className={classeSelect}>
          {ANOS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3" data-tour="financeiro-resumo">
        <StatCard
          icon={<ArrowDownCircle size={18} />}
          iconClassName="bg-success-50 text-success-600"
          label="Recebido"
          value={formatBRL(totais.recebido)}
          sublabel={`em ${ano}`}
        />
        <StatCard
          icon={<ArrowUpCircle size={18} />}
          iconClassName="bg-danger-50 text-danger-600"
          label="Despesas"
          value={formatBRL(totais.gasto)}
          sublabel={`em ${ano}`}
        />
        <StatCard
          icon={<Scale size={18} />}
          iconClassName="bg-primary-50 text-primary-600"
          label="Saldo"
          value={formatBRL(totais.recebido - totais.gasto)}
          sublabel={totais.recebido ? `${Math.round(((totais.recebido - totais.gasto) / totais.recebido) * 100)}% do que entrou` : "—"}
          sublabelClassName={totais.recebido - totais.gasto < 0 ? "text-danger-600" : undefined}
        />
      </div>

      <Card className="p-5" data-tour="financeiro-confronto">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Recebimentos x despesas</h2>
        <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">Recebimentos pelo mês em que o dinheiro caiu; despesas pelo mês de competência.</p>
        {carregando ? (
          <p className="py-6 text-center text-sm text-slate-400">Carregando...</p>
        ) : mesesComMovimento.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">Nada registrado em {ano} ainda.</p>
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Mês</th>
                  <th className="py-2 font-medium">Recebido</th>
                  <th className="py-2 font-medium">Despesas</th>
                  <th className="py-2 font-medium">Saldo</th>
                  <th className="w-1/3 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {mesesComMovimento.map((m) => (
                  <tr key={m.competencia} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-2.5 font-medium text-slate-700 dark:text-slate-200">{formatCompetenciaAbrev(m.competencia)}</td>
                    <td className="py-2.5 text-success-700 dark:text-success-300">{formatBRL(m.recebido)}</td>
                    <td className="py-2.5 text-danger-600">{formatBRL(m.gasto)}</td>
                    <td className={`py-2.5 font-semibold ${m.saldo < 0 ? "text-danger-600" : "text-slate-800 dark:text-slate-100"}`}>{formatBRL(m.saldo)}</td>
                    <td className="py-2.5">
                      <div className="flex flex-col gap-1">
                        <div className="h-1.5 rounded-full bg-success-400" style={{ width: `${(m.recebido / maior) * 100}%` }} />
                        <div className="h-1.5 rounded-full bg-danger-400" style={{ width: `${(m.gasto / maior) * 100}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-4 flex rounded-lg bg-slate-100 p-1 text-sm sm:w-fit dark:bg-slate-700">
          {(["recebimentos", "despesas"] as Aba[]).map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setSearchParams(a === "recebimentos" ? {} : { aba: a }, { replace: true })}
              className={`flex-1 whitespace-nowrap rounded-md px-4 py-1.5 font-medium transition-colors ${
                aba === a ? "bg-white text-primary-700 shadow-sm dark:bg-slate-800" : "text-slate-500 dark:text-slate-400"
              }`}
            >
              {a === "recebimentos" ? `Recebimentos (${pagamentos?.length ?? 0})` : `Despesas (${despesas?.length ?? 0})`}
            </button>
          ))}
        </div>

        {aba === "recebimentos" ? (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Tomador</th>
                  <th className="py-2 font-medium">Competência</th>
                  <th className="py-2 font-medium">Valor</th>
                  <th className="py-2 font-medium">Recebido em</th>
                </tr>
              </thead>
              <tbody>
                {pagamentos?.map((p) => (
                  <tr key={p.id} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-3 font-medium text-slate-800 dark:text-slate-200">{p.apelido}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-300">{p.competencia}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(p.valor)}</td>
                    <td className="py-3 text-slate-500 dark:text-slate-400">
                      {p.data_recebimento ? new Date(`${p.data_recebimento}T00:00:00`).toLocaleDateString("pt-BR") : <Badge variant="neutral">Não informada</Badge>}
                    </td>
                  </tr>
                ))}
                {pagamentos?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-400 dark:text-slate-500">
                      Nenhum recebimento em {ano}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Categoria</th>
                  <th className="py-2 font-medium">Competência</th>
                  <th className="py-2 font-medium">Valor</th>
                </tr>
              </thead>
              <tbody>
                {despesas?.map((d) => (
                  <tr key={d.id} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-3 font-medium text-slate-800 dark:text-slate-200">{d.categoria}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-300">{d.competencia}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(d.valor)}</td>
                  </tr>
                ))}
                {despesas?.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 dark:text-slate-500">
                      Nenhuma despesa em {ano}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {modal === "recebimento" && (
        <RegistrarPagamentoModal
          vinculos={vinculos}
          onClose={() => setModal(null)}
          onRegistrado={() => {
            setModal(null)
            recarregar()
          }}
        />
      )}
      {modal === "extrato" && <ImportarExtratoModal vinculos={vinculos} onClose={() => setModal(null)} onImportado={recarregar} />}
      {modal === "despesa" && (
        <RegistrarDespesaModal
          onClose={() => setModal(null)}
          onRegistrada={() => {
            setModal(null)
            recarregar()
          }}
        />
      )}
    </div>
  )
}
