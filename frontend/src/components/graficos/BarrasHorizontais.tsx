import { formatBRL } from "../../lib/format"

/** Ranking em barras deitadas ("Quem mais te paga", "Para onde vai o
 * dinheiro", "Recebido por cliente"). Uma cor só: a barra maior já diz quem
 * é o maior. Cada linha traz o nome, o valor e a fatia escritos — o desenho
 * é uma lista de verdade, então leitor de tela lê tudo sem precisar de mais
 * nada. O que passa de `maximo` vira uma linha "Outros", em cinza (é uma
 * soma de vários, não um deles). */

export interface ItemBarra {
  nome: string
  valor: number
  /** Texto pequeno ao lado do nome (ex.: "3 notas"). */
  detalhe?: string
}

export function juntarOutros(itens: ItemBarra[], maximo: number, rotuloOutros = "Outros"): (ItemBarra & { outros?: boolean })[] {
  const ordenados = [...itens].filter((i) => i.valor > 0).sort((a, b) => b.valor - a.valor)
  // Só junta se sobrarem pelo menos dois: "Outros (1)" não ajuda ninguém.
  if (ordenados.length <= maximo + 1) return ordenados
  const resto = ordenados.slice(maximo)
  return [
    ...ordenados.slice(0, maximo),
    { nome: `${rotuloOutros} (${resto.length})`, valor: Math.round(resto.reduce((s, i) => s + i.valor, 0) * 100) / 100, outros: true },
  ]
}

export function BarrasHorizontais({
  titulo,
  itens,
  maximo = 6,
  rotuloOutros,
  total,
  formatar = formatBRL,
}: {
  /** Nome do gráfico pra leitor de tela. */
  titulo: string
  itens: ItemBarra[]
  maximo?: number
  rotuloOutros?: string
  /** Base da porcentagem (padrão: a soma dos itens). */
  total?: number
  /** Como escrever o valor (padrão: em reais). Ex.: contagens na Gestão. */
  formatar?: (valor: number) => string
}) {
  const linhas = juntarOutros(itens, maximo, rotuloOutros)
  const soma = total ?? linhas.reduce((s, i) => s + i.valor, 0)
  const maior = Math.max(1, ...linhas.map((i) => i.valor))
  return (
    <ol className="flex flex-col gap-3" aria-label={titulo}>
      {linhas.map((item) => {
        const fatia = soma > 0 ? Math.round((item.valor / soma) * 100) : 0
        return (
          <li key={item.nome} className="group/barra -mx-2 rounded-lg px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-700/40">
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-slate-700 dark:text-slate-200" title={item.nome}>
                {item.nome}
                {item.detalhe && <span className="ml-1.5 hidden text-xs text-slate-400 sm:inline dark:text-slate-500">{item.detalhe}</span>}
              </span>
              <span className="shrink-0 tabular-nums">
                <span className="font-semibold text-slate-800 dark:text-slate-100">{formatar(item.valor)}</span>
                <span className="ml-1.5 inline-block w-9 text-right text-xs text-slate-500 dark:text-slate-400">{fatia}%</span>
              </span>
            </div>
            {/* Ponta arredondada só do lado do dado; a base (esquerda) é reta. */}
            <div aria-hidden className="h-2.5">
              <div
                className={`h-full rounded-r transition-[width] duration-300 ${
                  item.outros ? "bg-slate-300 dark:bg-slate-600" : "bg-primary-500 group-hover/barra:bg-primary-600 dark:bg-primary-400 dark:group-hover/barra:bg-primary-300"
                }`}
                style={{ width: `${Math.max(1, (item.valor / maior) * 100)}%` }}
              />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
