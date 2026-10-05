import { ArrowRight, ChevronDown, EyeOff } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import type { AgendaItem, PendenciaItem, Proximos } from "../lib/types"
import { Card } from "./ui/Card"

/** Card "Próximos passos" da Visão geral (05/10/2026: "essa aba está muito
 * extensa, reduza o tamanho dela"): no máximo 5 linhas de cara — primeiro o
 * que dá pra resolver agora, depois o que vem na agenda —, uma linha por
 * item, e o resto atrás de "ver mais". Linhas repetidas chegam juntas do
 * servidor ("Gerar 8 notas") e abrem aqui mesmo. */

const LINHAS = 5

const COR_PENDENCIA: Record<string, string> = {
  erro: "bg-danger-600",
  prefeitura: "bg-warning-600",
  assinar: "bg-warning-600",
  enviar_tomador: "bg-primary-600",
  nota_recebimento: "bg-accent-600",
  gerar: "bg-accent-600",
  receber: "bg-success-600",
}

/** AAAA-MM-DD -> 15/10 */
function diaMes(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
}

/** Um grupo não muda de chave quando perde um item (senão fecharia ao ignorar um). */
function chaveDaLinha(p: PendenciaItem): string {
  if (p.itens) return `grupo:${p.tipo}:${p.data ?? ""}`
  return `p:${p.chave ?? p.emissao_id ?? `${p.tipo}:${p.titulo}`}`
}

const LINHA = "flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-700/40"
const DETALHE = "shrink-0 text-xs tabular-nums text-slate-400 dark:text-slate-500"
const ACAO = "shrink-0 text-xs font-semibold text-primary-600 dark:text-primary-300"

function Prazo({ p }: { p: PendenciaItem }) {
  if (!p.data) return null
  return (
    <span className={p.atrasada ? "shrink-0 text-xs font-semibold tabular-nums text-danger-600 dark:text-danger-300" : DETALHE}>
      {p.atrasada ? "era" : "até"} {diaMes(p.data)}
    </span>
  )
}

function LinhaPendencia({
  p,
  onIgnorar,
  semPrazo = false,
}: {
  p: PendenciaItem
  onIgnorar: (chave: string) => void
  /** Dentro de um grupo o dia já está na linha de cima. */
  semPrazo?: boolean
}) {
  const [aberto, setAberto] = useState(false)
  const bolinha = <span className={`h-2 w-2 shrink-0 rounded-full ${COR_PENDENCIA[p.tipo] ?? "bg-slate-400"}`} aria-hidden />
  const dica = [p.titulo, p.competencia ? formatCompetenciaLonga(p.competencia) : null, p.valor != null ? formatBRL(p.valor) : null]
    .filter(Boolean)
    .join(" · ")

  if (p.itens && p.itens.length > 0) {
    return (
      <li>
        <button type="button" onClick={() => setAberto((a) => !a)} aria-expanded={aberto} className={`${LINHA} w-full`}>
          {bolinha}
          <span className="min-w-0 flex-1 truncate font-medium text-slate-800 dark:text-slate-200">{p.titulo}</span>
          <Prazo p={p} />
          <span className={`${ACAO} inline-flex items-center gap-0.5`}>
            {aberto ? "fechar" : "ver"}
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${aberto ? "rotate-180" : ""}`} aria-hidden />
          </span>
        </button>
        {aberto && (
          <ul className="mb-1 ml-2.5 border-l border-slate-200 pl-2 dark:border-slate-700">
            {p.itens.map((item) => (
              <LinhaPendencia key={item.chave ?? item.link} p={item} onIgnorar={onIgnorar} semPrazo />
            ))}
          </ul>
        )}
      </li>
    )
  }

  return (
    <li className="group flex items-center">
      <Link to={p.link} title={dica} className={LINHA}>
        {bolinha}
        <span className="min-w-0 flex-1 truncate font-medium text-slate-800 dark:text-slate-200">{p.titulo}</span>
        {!semPrazo && <Prazo p={p} />}
        {p.valor != null && !p.data && <span className={`${DETALHE} hidden sm:inline`}>{formatBRL(p.valor)}</span>}
        <span className={ACAO}>{p.acao} →</span>
      </Link>
      {p.chave && (
        <button
          type="button"
          onClick={() => onIgnorar(p.chave!)}
          title="Ignorar este aviso (atraso consciente)"
          aria-label={`Ignorar o aviso: ${p.titulo}`}
          className="shrink-0 rounded p-1.5 text-slate-300 hover:bg-slate-100 hover:text-slate-500 focus-visible:text-slate-500 group-hover:text-slate-400 dark:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 dark:group-hover:text-slate-400"
        >
          <EyeOff className="h-3.5 w-3.5" />
        </button>
      )}
    </li>
  )
}

function LinhaAgenda({ ev, primeira }: { ev: AgendaItem; primeira: boolean }) {
  return (
    <li className={primeira ? "mt-1 border-t border-slate-100 pt-1 dark:border-slate-700/60" : ""}>
      <Link to="/app/calendario" title={`${ev.detalhe ?? ev.titulo} — ver no calendário`} className={LINHA}>
        <span className="w-10 shrink-0 text-xs font-semibold tabular-nums text-slate-500 dark:text-slate-400">{diaMes(ev.data)}</span>
        <span className="min-w-0 flex-1 truncate text-slate-700 dark:text-slate-300">{ev.detalhe ?? ev.titulo}</span>
        {ev.valor != null && <span className={DETALHE}>{formatBRL(ev.valor)}</span>}
      </Link>
    </li>
  )
}

export function ProximosPassos({ proximos, onIgnorar }: { proximos: Proximos | null; onIgnorar: (chave: string) => void }) {
  const [tudo, setTudo] = useState(false)

  if (proximos === null) {
    return (
      <Card className="px-4 py-3">
        <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
      </Card>
    )
  }

  const linhas: ({ pendencia: PendenciaItem } | { evento: AgendaItem })[] = [
    ...proximos.pendencias.map((pendencia) => ({ pendencia })),
    ...proximos.agenda.map((evento) => ({ evento })),
  ]
  // Sobrando só uma, mostra de uma vez — "ver mais 1" ocuparia a mesma linha.
  const cabeTudo = linhas.length <= LINHAS + 1
  const visiveis = tudo || cabeTudo ? linhas : linhas.slice(0, LINHAS)
  // O servidor manda até 10 pendências; o que passar disso está em Notas.
  const foraDaLista = Math.max(0, proximos.total_pendencias - proximos.pendencias.length)
  const escondidas = linhas.length - visiveis.length + (tudo ? 0 : foraDaLista)
  const primeiraDaAgenda = visiveis.findIndex((l) => "evento" in l)

  return (
    <Card className="px-3 py-2.5">
      {linhas.length === 0 ? (
        <p className="px-1.5 py-1.5 text-sm text-slate-400 dark:text-slate-500">Nada pendente nem na agenda dos próximos 30 dias.</p>
      ) : (
        <ul className="flex flex-col">
          {visiveis.map((l, i) =>
            "pendencia" in l ? (
              <LinhaPendencia
                key={chaveDaLinha(l.pendencia)}
                p={l.pendencia}
                onIgnorar={onIgnorar}
              />
            ) : (
              <LinhaAgenda key={`a:${i}`} ev={l.evento} primeira={i === primeiraDaAgenda && i > 0} />
            ),
          )}
          {tudo && foraDaLista > 0 && (
            <li>
              <Link to="/app/nfse" className={`${LINHA} text-xs text-slate-500 dark:text-slate-400`}>
                + {foraDaLista} {foraDaLista === 1 ? "outra pendência" : "outras pendências"} em Notas
              </Link>
            </li>
          )}
        </ul>
      )}
      <div className="mt-1 flex items-center justify-between gap-3 px-1.5 text-xs">
        {escondidas > 0 || tudo ? (
          <button
            type="button"
            onClick={() => setTudo((t) => !t)}
            aria-expanded={tudo}
            className="inline-flex items-center gap-0.5 py-1 font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            {tudo ? "ver menos" : `ver mais ${escondidas}`}
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${tudo ? "rotate-180" : ""}`} aria-hidden />
          </button>
        ) : (
          <span />
        )}
        <Link to="/app/calendario" className="inline-flex items-center gap-1 py-1 font-medium text-primary-600 hover:text-primary-700 dark:text-primary-300">
          Calendário <ArrowRight size={12} />
        </Link>
      </div>
    </Card>
  )
}
