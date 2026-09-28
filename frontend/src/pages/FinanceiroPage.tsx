import { ArrowDownCircle, ArrowUpCircle, FileUp, Plus, Scale } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useLocation, useSearchParams } from "react-router-dom"
import { BaixaPagamento } from "../components/BaixaPagamento"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaAbrev } from "../lib/format"
import type { Despesa, NotaAberta, Pagamento, VinculoResumo } from "../lib/types"
import { RegistrarDespesaModal } from "./DespesasPage"
import { ImportarExtratoModal, RegistrarPagamentoModal } from "./RecebimentosPage"

// Pedido do Marcos (28/09/2026): "coloque a confrontação de recebimentos e
// despesas na mesma aba, deixe como Financeiro". Uma tela só: o resumo do
// ano (entrou x saiu x sobrou), o confronto mês a mês e as duas listas.

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

const NOMES_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

/** Mês em que o dinheiro caiu (ou o de competência, sem data). */
function mesDoRecebimento(p: Pagamento): string {
  return p.data_recebimento ? p.data_recebimento.slice(0, 7) : p.competencia
}

const classeSelect =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function FinanceiroPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [ano, setAno] = useState(String(ANO_ATUAL))
  // "Permita selecionar por mês, além de selecionar por ano" (28/09/2026).
  const [mes, setMes] = useState("") // "" = ano inteiro; "01".."12"
  const [pagamentos, setPagamentos] = useState<Pagamento[] | null>(null)
  const [despesas, setDespesas] = useState<Despesa[] | null>(null)
  const [abertas, setAbertas] = useState<NotaAberta[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [modal, setModal] = useState<"recebimento" | "extrato" | "despesa" | null>(
    searchParams.get("novo") === "despesa" ? "despesa" : searchParams.get("novo") === "recebimento" ? "recebimento" : null,
  )

  function fecharModal() {
    setModal(null)
    if (searchParams.get("novo")) setSearchParams({}, { replace: true })
  }

  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos).catch(() => {})
  }, [])

  function recarregar() {
    setErro(null)
    api.get<NotaAberta[]>("/notas-a-receber").then(setAbertas).catch(() => setAbertas([]))
    Promise.all([api.get<Pagamento[]>(`/pagamentos?ano=${ano}&por=recebimento`), api.get<Despesa[]>(`/despesas?ano=${ano}`)])
      .then(([p, d]) => {
        setPagamentos(p)
        setDespesas(d)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
  }

  useEffect(recarregar, [ano])

  // Links "#a-receber" (Visão geral, Precisa da sua atenção) rolam até a lista.
  const { hash } = useLocation()
  useEffect(() => {
    if (hash === "#a-receber" && abertas !== null) document.getElementById("a-receber")?.scrollIntoView({ behavior: "smooth" })
  }, [hash, abertas !== null])

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

  const periodo = mes ? `${ano}-${mes}` : null
  const rotuloPeriodo = mes ? `${NOMES_MESES[Number(mes) - 1]} de ${ano}` : `em ${ano}`
  const totais = meses
    .filter((m) => !periodo || m.competencia === periodo)
    .reduce((t, m) => ({ recebido: t.recebido + m.recebido, gasto: t.gasto + m.gasto }), { recebido: 0, gasto: 0 })
  const pagamentosDoPeriodo = (pagamentos ?? []).filter((p) => !periodo || mesDoRecebimento(p) === periodo)
  const despesasDoPeriodo = (despesas ?? []).filter((d) => !periodo || d.competencia === periodo)
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
        <select value={mes} onChange={(e) => setMes(e.target.value)} className={classeSelect} aria-label="Mês">
          <option value="">Ano inteiro</option>
          {NOMES_MESES.map((nome, i) => (
            <option key={nome} value={String(i + 1).padStart(2, "0")}>
              {nome}
            </option>
          ))}
        </select>
        <select value={ano} onChange={(e) => setAno(e.target.value)} className={classeSelect} aria-label="Ano">
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
          sublabel={rotuloPeriodo}
        />
        <StatCard
          icon={<ArrowUpCircle size={18} />}
          iconClassName="bg-danger-50 text-danger-600"
          label="Despesas"
          value={formatBRL(totais.gasto)}
          sublabel={rotuloPeriodo}
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
                  <tr
                    key={m.competencia}
                    onClick={() => setMes(m.competencia === periodo ? "" : m.competencia.slice(5))}
                    title="Clique pra ver só este mês"
                    className={`cursor-pointer border-b border-slate-50 last:border-0 dark:border-slate-700/40 ${
                      m.competencia === periodo ? "bg-primary-50/70 dark:bg-primary-900/20" : "hover:bg-slate-50 dark:hover:bg-slate-700/40"
                    }`}
                  >
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

      {/* "Nos recebimentos coloque os pagamentos também" (28/09/2026): as
          notas que ainda não foram pagas, de todos os meses, com a baixa ali
          mesmo (passa o mouse em "Pendente"). */}
      <Card className="scroll-mt-20 p-5" id="a-receber">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">A receber</h2>
            <p className="text-xs text-slate-400 dark:text-slate-500">Notas emitidas sem pagamento registrado, de todos os meses.</p>
          </div>
          <span className="text-sm font-semibold text-warning-700 dark:text-warning-300">
            {formatBRL((abertas ?? []).reduce((s, n) => s + n.valor, 0))}
          </span>
        </div>
        {abertas === null ? (
          <p className="py-4 text-center text-sm text-slate-400">Carregando...</p>
        ) : abertas.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-400">Nenhuma nota em aberto. Tudo recebido!</p>
        ) : (
          <div className="-mx-5 max-h-[420px] overflow-auto px-5">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="sticky top-0 bg-white dark:bg-slate-800">
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Tomador</th>
                  <th className="py-2 font-medium">Nota de</th>
                  <th className="py-2 font-medium">Em aberto há</th>
                  <th className="py-2 text-right font-medium">Valor</th>
                  <th className="py-2 text-right font-medium">Pagamento</th>
                </tr>
              </thead>
              <tbody>
                {abertas.map((n) => (
                  <tr key={`${n.vinculo_id}-${n.competencia}`} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-2.5">
                      <Link to={n.quantidade > 1 ? "/app/nfse" : `/app/nfse/${n.emissao_id}`} className="font-medium text-slate-800 hover:text-primary-600 dark:text-slate-200">
                        {n.apelido}
                      </Link>
                      {n.quantidade > 1 && <span className="block text-xs text-slate-400">{n.quantidade} notas</span>}
                    </td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">{formatCompetenciaAbrev(n.competencia)}</td>
                    <td className={`py-2.5 ${n.dias_em_aberto > 60 ? "font-semibold text-danger-600" : "text-slate-500 dark:text-slate-400"}`}>
                      {n.dias_em_aberto} dia(s)
                    </td>
                    <td className="py-2.5 text-right text-slate-700 dark:text-slate-200">{formatBRL(n.valor)}</td>
                    <td className="py-2.5 text-right">
                      <BaixaPagamento vinculoId={n.vinculo_id} competencia={n.competencia} valor={n.valor} recebido={false} onMudou={recarregar} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Recebimentos e despesas lado a lado (28/09/2026). */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <div className="mb-3 flex items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Recebimentos</h2>
            <span className="text-sm font-semibold text-success-700 dark:text-success-300">
              {formatBRL(pagamentosDoPeriodo.reduce((s, p) => s + p.valor, 0))}
            </span>
          </div>
          <div className="max-h-[480px] overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white dark:bg-slate-800">
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Tomador</th>
                  <th className="py-2 font-medium">Caiu em</th>
                  <th className="py-2 text-right font-medium">Valor</th>
                </tr>
              </thead>
              <tbody>
                {pagamentosDoPeriodo.map((p) => (
                  <tr key={p.id} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-2.5">
                      <span className="font-medium text-slate-800 dark:text-slate-200">{p.apelido}</span>
                      <span className="block text-xs text-slate-400">nota de {p.competencia}</span>
                    </td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">
                      {p.data_recebimento ? new Date(`${p.data_recebimento}T00:00:00`).toLocaleDateString("pt-BR") : <Badge variant="neutral">sem data</Badge>}
                    </td>
                    <td className="py-2.5 text-right text-slate-700 dark:text-slate-200">{formatBRL(p.valor)}</td>
                  </tr>
                ))}
                {pagamentos !== null && pagamentosDoPeriodo.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 dark:text-slate-500">
                      Nenhum recebimento {rotuloPeriodo.startsWith("em") ? rotuloPeriodo : `em ${rotuloPeriodo}`}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-5">
          <div className="mb-3 flex items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Despesas</h2>
            <span className="text-sm font-semibold text-danger-600">{formatBRL(despesasDoPeriodo.reduce((s, d) => s + d.valor, 0))}</span>
          </div>
          <div className="max-h-[480px] overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white dark:bg-slate-800">
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Categoria</th>
                  <th className="py-2 font-medium">Competência</th>
                  <th className="py-2 text-right font-medium">Valor</th>
                </tr>
              </thead>
              <tbody>
                {despesasDoPeriodo.map((d) => (
                  <tr key={d.id} className="border-b border-slate-50 last:border-0 dark:border-slate-700/40">
                    <td className="py-2.5 font-medium text-slate-800 dark:text-slate-200">{d.categoria}</td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">{d.competencia}</td>
                    <td className="py-2.5 text-right text-slate-700 dark:text-slate-200">{formatBRL(d.valor)}</td>
                  </tr>
                ))}
                {despesas !== null && despesasDoPeriodo.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 dark:text-slate-500">
                      Nenhuma despesa {rotuloPeriodo.startsWith("em") ? rotuloPeriodo : `em ${rotuloPeriodo}`}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {modal === "recebimento" && (
        <RegistrarPagamentoModal
          vinculos={vinculos}
          onClose={fecharModal}
          onRegistrado={() => {
            fecharModal()
            recarregar()
          }}
        />
      )}
      {modal === "extrato" && <ImportarExtratoModal vinculos={vinculos} onClose={fecharModal} onImportado={recarregar} />}
      {modal === "despesa" && (
        <RegistrarDespesaModal
          onClose={fecharModal}
          onRegistrada={() => {
            fecharModal()
            recarregar()
          }}
        />
      )}
    </div>
  )
}
