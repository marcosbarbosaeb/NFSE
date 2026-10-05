import { EyeOff, FilePlus2 } from "lucide-react"
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../../lib/api"
import { useModulos } from "../../lib/modulos"
import { formatBRL, formatCompetenciaLonga } from "../../lib/format"
import type { RecebimentoSemNota } from "../../lib/types"
import { Card } from "../ui/Card"

/** Link pra pedir ao emissor a nota de um recebimento que chegou sem nota.
 * É o ponto de integração entre os dois módulos: o financeiro manda o
 * tomador, o valor e uma "origem" que o emissor devolve quando a nota nasce
 * (aí o recebimento fica ligado a ela). */
export function linkGerarNota(r: { vinculo_id: string; pagamento_id: string; valor?: number }) {
  const valor = r.valor != null ? `&valor=${r.valor}` : ""
  return `/app/nfse?gerar=${r.vinculo_id}${valor}&origem=fin:pagamento:${r.pagamento_id}`
}

/** Lista curta (dentro de um modal, depois de registrar/importar). */
export function ListaSemNota({ itens }: { itens: RecebimentoSemNota[] }) {
  // Sem o módulo de notas não há o que gerar: o aviso nem aparece.
  const { emissor } = useModulos()
  if (itens.length === 0 || !emissor) return null
  return (
    <div className="rounded-lg border border-accent-200 bg-accent-50 p-3 dark:border-accent-800 dark:bg-accent-900/20">
      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
        {itens.length === 1 ? "Este recebimento chegou sem nota" : `${itens.length} recebimentos chegaram sem nota`}
      </p>
      <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
        Esse dinheiro não está ligado a nenhuma nota. Se o cliente paga antes (como Mercado Livre e Amazon), gere a nota desse valor.
      </p>
      <ul className="flex flex-col gap-1.5">
        {itens.map((r) => (
          <li key={r.chave} className="flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-slate-700 dark:text-slate-200">
              {r.apelido} · {formatCompetenciaLonga(r.competencia)} · <strong>{formatBRL(r.valor)}</strong>
            </span>
            <Link to={linkGerarNota(r)} className="shrink-0 text-xs font-semibold text-primary-600 hover:underline dark:text-primary-300">
              Gerar nota →
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Card do Financeiro: recebimentos dos últimos 12 meses sem nota no mês. */
export function RecebimentosSemNotaCard({ recarga, semTitulo }: { recarga?: number; semTitulo?: boolean }) {
  const [itens, setItens] = useState<RecebimentoSemNota[] | null>(null)

  useEffect(() => {
    let vivo = true
    api
      .get<RecebimentoSemNota[]>("/financeiro/recebimentos-sem-nota")
      .then((r) => vivo && setItens(r))
      .catch(() => vivo && setItens([]))
    return () => {
      vivo = false
    }
  }, [recarga])

  if (!itens || itens.length === 0) return null

  function ignorar(chave: string) {
    setItens((atual) => (atual ?? []).filter((x) => x.chave !== chave))
    api.post("/painel/pendencias/ignorar", { chave }).catch(() => undefined)
  }

  const total = itens.reduce((s, r) => s + r.valor, 0)
  return (
    <Card className="p-5">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <h2 className={semTitulo ? "sr-only" : "flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-200"}>
          <FilePlus2 className="h-4 w-4 text-accent-600" aria-hidden />
          Recebimentos sem nota
        </h2>
        <span className="text-sm font-semibold tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(total)}</span>
      </div>
      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        Dinheiro que caiu sem estar ligado a uma nota — comum em quem paga antes, como Mercado Livre e Amazon. Gere a nota do valor que
        caiu, ou ignore se não precisa.
      </p>
      <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
        {itens.map((r) => (
          <li key={r.chave} className="flex items-center gap-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{r.apelido}</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                recebido em {formatCompetenciaLonga(r.competencia)}
                {r.data_recebimento ? ` · caiu ${r.data_recebimento.split("-").reverse().join("/")}` : ""}
              </p>
            </div>
            <span className="shrink-0 text-sm tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(r.valor)}</span>
            <Link
              to={linkGerarNota(r)}
              className="shrink-0 rounded-md bg-primary-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-primary-700"
            >
              Gerar nota
            </Link>
            <button
              type="button"
              onClick={() => ignorar(r.chave)}
              title="Ignorar este aviso"
              aria-label={`Ignorar o recebimento de ${r.apelido} sem nota`}
              className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
            >
              <EyeOff className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
