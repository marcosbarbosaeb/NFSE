import type { ReactNode } from "react"
import { formatBRL } from "../../lib/format"
import { MESES_ABREV, NOMES_MESES, formatPct, formatValor } from "../../lib/financeiro"
import type { ResumoFinanceiro } from "../../lib/types"
import { Card } from "../ui/Card"

// "Resultado do ano" (28/09/2026) — a parte de cima da planilha "Controle CP"
// dentro da Ana: lucro, margem, retiradas e o saldo que ainda dá pra
// distribuir, mês a mês (GET /financeiro/resumo?ano=).

function Kpi({ label, valor, detalhe, negativo, destaque }: { label: string; valor: ReactNode; detalhe?: ReactNode; negativo?: boolean; destaque?: boolean }) {
  return (
    <Card className={`flex min-w-0 flex-col gap-1 p-3 sm:p-4 ${destaque ? "ring-1 ring-primary-200 dark:ring-primary-800" : ""}`}>
      <p className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p
        className={`break-words text-base font-semibold leading-snug tabular-nums sm:text-lg ${negativo ? "text-danger-600 dark:text-danger-400" : "text-slate-900 dark:text-slate-100"}`}
      >
        {valor}
      </p>
      {detalhe && <p className="truncate text-xs text-slate-400 dark:text-slate-500">{detalhe}</p>}
    </Card>
  )
}

interface LinhaTabela {
  rotulo: string
  valores: (number | null)[]
  total: number | null
  pct?: boolean
  sub?: boolean
  forte?: boolean
  vermelhoSeNegativo?: boolean
  dica?: string
}

function soma(valores: number[]): number {
  return valores.reduce((s, v) => s + v, 0)
}

export function ResultadoAno({
  resumo,
  erro,
  ano,
  mes,
  onSelecionarMes,
  semTitulo,
}: {
  /** A tela já mostra o título do card (cards recolhíveis do Financeiro). */
  semTitulo?: boolean
  resumo: ResumoFinanceiro | null
  erro?: string | null
  ano: string
  mes: string
  onSelecionarMes: (mes: string) => void
}) {
  const i = mes ? Number(mes) - 1 : -1

  if (!resumo) {
    return (
      <Card className="p-5">
        {!semTitulo && <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Resultado do ano</h2>}
        <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">{erro ?? "Carregando..."}</p>
      </Card>
    )
  }

  const t = resumo.totais
  const doPeriodo = (serie: number[], total: number) => (i >= 0 ? serie[i] : total)
  const recebido = doPeriodo(resumo.recebido, t.recebido)
  const despesas = doPeriodo(resumo.despesas, t.despesas)
  const impostos = doPeriodo(resumo.impostos, t.impostos)
  const ferramentas = doPeriodo(resumo.ferramentas, t.ferramentas)
  const lucro = doPeriodo(resumo.lucro, t.lucro)
  const retiradas = doPeriodo(resumo.retiradas, t.retiradas)
  const margem = i >= 0 ? resumo.margem[i] : t.margem
  const saldo = i >= 0 ? resumo.saldo_a_distribuir[i] : t.saldo_a_distribuir
  const cargaImpostos = i >= 0 ? (recebido ? Math.round((impostos / recebido) * 1000) / 10 : null) : t.carga_impostos
  const rotuloPeriodo = i >= 0 ? `${NOMES_MESES[i]} de ${ano}` : `em ${ano}`

  const linhas: LinhaTabela[] = [
    { rotulo: "Faturado (notas)", valores: resumo.faturado, total: t.faturado, dica: "Notas confirmadas, pelo mês de competência." },
    { rotulo: "Recebido", valores: resumo.recebido, total: t.recebido, dica: "Pagamentos registrados, pelo mês da nota." },
    { rotulo: "Despesas", valores: resumo.despesas, total: t.despesas, dica: "Sem as retiradas (distribuição de lucros)." },
    { rotulo: "dos quais impostos", valores: resumo.impostos, total: t.impostos, sub: true, dica: "Simples, INSS, DAS e afins." },
    { rotulo: "Lucro", valores: resumo.lucro, total: t.lucro, forte: true, vermelhoSeNegativo: true, dica: "Recebido − despesas." },
    { rotulo: "Margem", valores: resumo.margem, total: t.margem, pct: true, vermelhoSeNegativo: true, dica: "Lucro ÷ recebido." },
    { rotulo: "Retiradas", valores: resumo.retiradas, total: t.retiradas, dica: "Distribuição de lucros (todas as contas)." },
    {
      rotulo: "Saldo a distribuir",
      valores: resumo.saldo_a_distribuir,
      total: t.saldo_a_distribuir,
      forte: true,
      vermelhoSeNegativo: true,
      dica: "Acumulado no ano: lucro − retiradas até o mês.",
    },
  ]

  // Meses sem nenhum movimento ficam com "—" (deixa a tabela respirar).
  const mesVazio = resumo.meses.map((_, m) => !resumo.faturado[m] && !resumo.recebido[m] && !resumo.despesas[m] && !resumo.retiradas[m])

  // "Para onde vai o dinheiro": as maiores categorias; o resto vira "Outras".
  const MAX_CATEGORIAS = 7
  const categorias =
    resumo.categorias.length > MAX_CATEGORIAS + 1
      ? [
          ...resumo.categorias.slice(0, MAX_CATEGORIAS),
          { categoria: `Outras (${resumo.categorias.length - MAX_CATEGORIAS})`, total: soma(resumo.categorias.slice(MAX_CATEGORIAS).map((c) => c.total)) },
        ]
      : resumo.categorias
  const totalCategorias = soma(resumo.categorias.map((c) => c.total))
  const maiorCategoria = Math.max(1, ...categorias.map((c) => c.total))

  return (
    <section className="flex flex-col gap-4" aria-labelledby="titulo-resultado-ano">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-resultado-ano" className={semTitulo ? "sr-only" : "text-base font-semibold text-slate-800 dark:text-slate-200"}>
          Resultado {i >= 0 ? `de ${NOMES_MESES[i].toLowerCase()}` : "do ano"}
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          {i >= 0 ? `${NOMES_MESES[i]} de ${ano}` : `Janeiro a dezembro de ${ano}`} · recebimentos pelo mês da nota
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 2xl:grid-cols-7" data-tour="financeiro-resumo">
        <Kpi label="Recebido" valor={formatBRL(recebido)} detalhe={rotuloPeriodo} />
        <Kpi label="Despesas" valor={formatBRL(despesas)} detalhe="sem as retiradas" />
        <Kpi label="Lucro" valor={formatBRL(lucro)} negativo={lucro < 0} destaque detalhe="recebido − despesas" />
        <Kpi label="Margem" valor={formatPct(margem)} negativo={margem !== null && margem < 0} detalhe="do que entrou" />
        <Kpi label="Retiradas" valor={formatBRL(retiradas)} detalhe="distribuição de lucros" />
        <Kpi
          label="Saldo a distribuir"
          valor={formatBRL(saldo)}
          negativo={saldo < 0}
          detalhe={i >= 0 ? `acumulado até ${MESES_ABREV[i].toLowerCase()}` : "acumulado no ano"}
        />
        <Kpi label="A receber" valor={formatBRL(t.a_receber)} detalhe="todos os meses" />
      </div>

      <p className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span>
          Carga de impostos: <strong className="font-semibold text-slate-700 dark:text-slate-200">{formatPct(cargaImpostos)}</strong> do recebido (
          {formatBRL(impostos)})
        </span>
        <span>
          Gasto com ferramentas: <strong className="font-semibold text-slate-700 dark:text-slate-200">{formatBRL(ferramentas)}</strong>
          {recebido > 0 && ferramentas > 0 && ` (${formatPct(Math.round((ferramentas / recebido) * 1000) / 10)} do recebido)`}
        </span>
      </p>

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Mês a mês</h3>
          <p className="text-xs text-slate-400 dark:text-slate-500">Valores em R$ · clique no mês pra filtrar a tela</p>
        </div>
        <div className="-mx-5 overflow-x-auto px-5">
          <table className="w-full min-w-[980px] border-separate border-spacing-0 text-right text-xs tabular-nums">
            <caption className="sr-only">Resultado mês a mês de {ano}</caption>
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
                <th scope="col" className="sticky left-0 z-10 min-w-[8.5rem] border-b border-slate-100 bg-white py-2 pr-3 text-left font-medium dark:border-slate-700/60 dark:bg-slate-800">
                  <span className="sr-only">Linha</span>
                </th>
                {resumo.meses.map((m, idx) => {
                  const ativo = idx === i
                  return (
                    <th
                      key={m}
                      scope="col"
                      className={`border-b border-slate-100 px-1 py-1 font-medium dark:border-slate-700/60 ${ativo ? "bg-primary-50 dark:bg-primary-900/30" : ""}`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelecionarMes(ativo ? "" : m)}
                        aria-pressed={ativo}
                        title={ativo ? "Voltar pro ano inteiro" : `Ver só ${NOMES_MESES[idx].toLowerCase()}`}
                        className={`w-full rounded px-1.5 py-1 text-right uppercase hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200 ${
                          ativo ? "font-semibold text-primary-700 dark:text-primary-300" : ""
                        }`}
                      >
                        {MESES_ABREV[idx]}
                      </button>
                    </th>
                  )
                })}
                <th scope="col" className="border-b border-l border-slate-100 py-2 pl-3 font-semibold text-slate-500 dark:border-slate-700/60 dark:text-slate-400">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => {
                const cor = (v: number | null) =>
                  l.vermelhoSeNegativo && v !== null && v < 0
                    ? "text-danger-600 dark:text-danger-400"
                    : l.sub
                      ? "text-slate-400 dark:text-slate-500"
                      : "text-slate-700 dark:text-slate-200"
                const texto = (v: number | null) => (v === null ? "—" : l.pct ? formatPct(v) : formatValor(v))
                const bordaTopo = l.forte ? "border-t border-slate-200 dark:border-slate-600" : ""
                return (
                  <tr key={l.rotulo}>
                    <th
                      scope="row"
                      title={l.dica}
                      className={`sticky left-0 z-10 whitespace-nowrap bg-white py-2 pr-3 text-left dark:bg-slate-800 ${bordaTopo} ${
                        l.sub ? "pl-3 font-normal italic text-slate-400 dark:text-slate-500" : l.forte ? "font-semibold text-slate-800 dark:text-slate-100" : "font-medium text-slate-600 dark:text-slate-300"
                      }`}
                    >
                      {l.rotulo}
                    </th>
                    {l.valores.map((v, idx) => {
                      const vazio = mesVazio[idx] && !l.rotulo.startsWith("Saldo")
                      return (
                        <td
                          key={idx}
                          className={`px-2 py-2 ${bordaTopo} ${idx === i ? "bg-primary-50 dark:bg-primary-900/30" : ""} ${l.forte ? "font-semibold" : ""} ${
                            vazio || v === 0 ? "text-slate-300 dark:text-slate-600" : cor(v)
                          }`}
                        >
                          {vazio || (v === 0 && !l.forte) ? "—" : texto(v)}
                        </td>
                      )
                    })}
                    <td className={`border-l border-slate-100 py-2 pl-3 font-semibold dark:border-slate-700/60 ${bordaTopo} ${cor(l.total)}`}>{texto(l.total)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Para onde vai o dinheiro</h3>
          <span className="text-xs text-slate-400 dark:text-slate-500">em {ano}</span>
        </div>
        {categorias.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma despesa em {ano} ainda.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
            {categorias.map((c) => {
              const pct = totalCategorias ? (c.total / totalCategorias) * 100 : 0
              const rotulo = `${c.categoria}: ${formatBRL(c.total)} (${formatPct(Math.round(pct * 10) / 10)} das despesas)`
              return (
                <li key={c.categoria} title={rotulo}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="min-w-0 truncate text-slate-700 dark:text-slate-200">{c.categoria}</span>
                    <span className="shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
                      {formatBRL(c.total)} <span className="text-xs text-slate-400 dark:text-slate-500">· {Math.round(pct)}%</span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60" role="presentation">
                    <div className="h-1.5 rounded-full bg-primary-500 dark:bg-primary-400" style={{ width: `${Math.max(2, (c.total / maiorCategoria) * 100)}%` }} />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </section>
  )
}
