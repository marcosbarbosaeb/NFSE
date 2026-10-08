import { BarChart3, ChartPie, RectangleHorizontal } from "lucide-react"
import { useState } from "react"
import { formatBRL } from "../../lib/format"
import { BarrasHorizontais, type ItemBarra, juntarOutros } from "./BarrasHorizontais"

/** Escolha do tipo de gráfico nos rankings do Financeiro (08/10/2026: "permita
 * alterar o tipo de gráfico" em "Para onde vai o dinheiro" e "Recebido por
 * cliente"). Três formas pro mesmo dado:
 *   - barras deitadas (o padrão: a melhor pra comparar valores parecidos);
 *   - rosca e faixa: a parte de cada um no todo, de relance — por isso no
 *     máximo 6 fatias (o resto vira "Outros"/"Outras").
 * A escolha fica guardada neste navegador, por gráfico.
 *
 * Cores: as 6 primeiras da paleta categórica de referência, na ordem fixa
 * (validadas para vizinhas, claro e escuro); "Outros" é sempre cinza. O texto
 * nunca usa a cor da fatia: nome, valor e % ficam na legenda, em tinta normal. */

export type TipoRanking = "barras" | "rosca" | "faixa"

const TIPOS: { id: TipoRanking; rotulo: string; Icone: typeof BarChart3 }[] = [
  { id: "barras", rotulo: "Barras", Icone: BarChart3 },
  { id: "rosca", rotulo: "Rosca", Icone: ChartPie },
  { id: "faixa", rotulo: "Faixa", Icone: RectangleHorizontal },
]

const FATIAS_MAX = 5 // + "Outros" = 6 no máximo

/** fill/bg/stroke por posição (claro | escuro). */
const CORES = [
  { fill: "fill-[#2a78d6] dark:fill-[#3987e5]", bg: "bg-[#2a78d6] dark:bg-[#3987e5]", stroke: "stroke-[#2a78d6] dark:stroke-[#3987e5]" },
  { fill: "fill-[#eb6834] dark:fill-[#d95926]", bg: "bg-[#eb6834] dark:bg-[#d95926]", stroke: "stroke-[#eb6834] dark:stroke-[#d95926]" },
  { fill: "fill-[#1baf7a] dark:fill-[#199e70]", bg: "bg-[#1baf7a] dark:bg-[#199e70]", stroke: "stroke-[#1baf7a] dark:stroke-[#199e70]" },
  { fill: "fill-[#eda100] dark:fill-[#c98500]", bg: "bg-[#eda100] dark:bg-[#c98500]", stroke: "stroke-[#eda100] dark:stroke-[#c98500]" },
  { fill: "fill-[#e87ba4] dark:fill-[#d55181]", bg: "bg-[#e87ba4] dark:bg-[#d55181]", stroke: "stroke-[#e87ba4] dark:stroke-[#d55181]" },
  { fill: "fill-[#008300] dark:fill-[#008300]", bg: "bg-[#008300] dark:bg-[#008300]", stroke: "stroke-[#008300] dark:stroke-[#008300]" },
]
const COR_OUTROS = { fill: "fill-slate-300 dark:fill-slate-600", bg: "bg-slate-300 dark:bg-slate-600", stroke: "stroke-slate-300 dark:stroke-slate-600" }

function lerTipo(chave: string): TipoRanking {
  try {
    const salvo = window.localStorage.getItem(`agenteana:grafico:${chave}`)
    return salvo === "rosca" || salvo === "faixa" ? salvo : "barras"
  } catch {
    return "barras"
  }
}

export function useTipoDeGrafico(chave: string): [TipoRanking, (tipo: TipoRanking) => void] {
  const [tipo, setTipo] = useState<TipoRanking>(() => lerTipo(chave))
  function trocar(novo: TipoRanking) {
    setTipo(novo)
    try {
      window.localStorage.setItem(`agenteana:grafico:${chave}`, novo)
    } catch {
      // sem armazenamento (aba anônima): vale só até recarregar
    }
  }
  return [tipo, trocar]
}

export function SeletorDeGrafico({ tipo, onTipo }: { tipo: TipoRanking; onTipo: (tipo: TipoRanking) => void }) {
  return (
    <div role="radiogroup" aria-label="Tipo de gráfico" className="inline-flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
      {TIPOS.map(({ id, rotulo, Icone }) => {
        const ativo = tipo === id
        return (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={ativo}
            title={rotulo}
            onClick={() => onTipo(id)}
            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              ativo
                ? "bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
            }`}
          >
            <Icone size={14} aria-hidden />
            <span className="hidden sm:inline">{rotulo}</span>
          </button>
        )
      })}
    </div>
  )
}

type Fatia = ItemBarra & { outros?: boolean; cor: { fill: string; bg: string; stroke: string } }

function fatiasDe(itens: ItemBarra[], rotuloOutros?: string): Fatia[] {
  return juntarOutros(itens, FATIAS_MAX, rotuloOutros).map((item, i) => ({ ...item, cor: item.outros ? COR_OUTROS : CORES[i % CORES.length] }))
}

/** Lista que acompanha rosca e faixa: cor, nome, valor e %. Passar o mouse
 * numa linha destaca a fatia (e vice-versa). */
function LegendaDasFatias({
  fatias,
  soma,
  ativa,
  onAtiva,
  formatar,
}: {
  fatias: Fatia[]
  soma: number
  ativa: number | null
  onAtiva: (i: number | null) => void
  formatar: (v: number) => string
}) {
  return (
    <ol className="flex min-w-0 flex-1 flex-col gap-0.5">
      {fatias.map((f, i) => (
        <li
          key={f.nome}
          onMouseEnter={() => onAtiva(i)}
          onMouseLeave={() => onAtiva(null)}
          className={`-mx-2 flex items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors ${
            ativa === i ? "bg-slate-100 dark:bg-slate-700/60" : ""
          }`}
        >
          <span aria-hidden className={`h-2.5 w-2.5 shrink-0 rounded-[3px] ${f.cor.bg}`} />
          <span className="min-w-0 flex-1 truncate text-slate-700 dark:text-slate-200" title={f.nome}>
            {f.nome}
          </span>
          <span className="shrink-0 tabular-nums">
            <span className="font-semibold text-slate-800 dark:text-slate-100">{formatar(f.valor)}</span>
            <span className="ml-1.5 inline-block w-9 text-right text-xs text-slate-500 dark:text-slate-400">
              {soma > 0 ? Math.round((f.valor / soma) * 100) : 0}%
            </span>
          </span>
        </li>
      ))}
    </ol>
  )
}

/** Arco de rosca de `a0` a `a1` (radianos, 0 = topo, sentido horário). */
function arco(cx: number, cy: number, rFora: number, rDentro: number, a0: number, a1: number): string {
  const ponto = (r: number, a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)]
  const grande = a1 - a0 > Math.PI ? 1 : 0
  const [x0, y0] = ponto(rFora, a0)
  const [x1, y1] = ponto(rFora, a1)
  const [x2, y2] = ponto(rDentro, a1)
  const [x3, y3] = ponto(rDentro, a0)
  return `M${x0},${y0} A${rFora},${rFora} 0 ${grande} 1 ${x1},${y1} L${x2},${y2} A${rDentro},${rDentro} 0 ${grande} 0 ${x3},${y3} Z`
}

function Rosca({ fatias, soma, ativa, onAtiva, formatar }: { fatias: Fatia[]; soma: number; ativa: number | null; onAtiva: (i: number | null) => void; formatar: (v: number) => string }) {
  const lado = 184
  const c = lado / 2
  const rFora = c - 4
  const rDentro = rFora * 0.62
  let angulo = 0
  const destaque = ativa != null ? fatias[ativa] : null
  return (
    <svg viewBox={`0 0 ${lado} ${lado}`} width={lado} height={lado} className="shrink-0" aria-hidden>
      {fatias.length === 1 ? (
        <circle
          cx={c}
          cy={c}
          r={(rFora + rDentro) / 2}
          strokeWidth={rFora - rDentro}
          className={`fill-none ${fatias[0].cor.stroke}`}
        />
      ) : (
        fatias.map((f, i) => {
          const a0 = angulo
          const a1 = angulo + (soma > 0 ? (f.valor / soma) * Math.PI * 2 : 0)
          angulo = a1
          return (
            <path
              key={f.nome}
              d={arco(c, c, ativa === i ? rFora + 2 : rFora, rDentro, a0, a1)}
              // 2px da cor do cartão entre as fatias
              className={`${f.cor.fill} stroke-white stroke-2 transition-opacity dark:stroke-slate-800 ${ativa != null && ativa !== i ? "opacity-40" : ""}`}
              onMouseEnter={() => onAtiva(i)}
              onMouseLeave={() => onAtiva(null)}
            />
          )
        })
      )}
      <text x={c} y={c - 4} textAnchor="middle" className="fill-slate-500 text-[10px] dark:fill-slate-400">
        {destaque ? (destaque.nome.length > 18 ? `${destaque.nome.slice(0, 17)}…` : destaque.nome) : "Total"}
      </text>
      <text x={c} y={c + 12} textAnchor="middle" className="fill-slate-800 text-[12px] font-semibold dark:fill-slate-100">
        {formatar(destaque ? destaque.valor : soma)}
      </text>
    </svg>
  )
}

function Faixa({ fatias, soma, ativa, onAtiva, formatar }: { fatias: Fatia[]; soma: number; ativa: number | null; onAtiva: (i: number | null) => void; formatar: (v: number) => string }) {
  const destaque = ativa != null ? fatias[ativa] : null
  return (
    <div className="flex flex-col gap-1.5">
      <p className="h-5 truncate text-xs text-slate-500 dark:text-slate-400" aria-hidden>
        {destaque ? (
          <>
            <span className="font-medium text-slate-700 dark:text-slate-200">{destaque.nome}</span> · {formatar(destaque.valor)} ·{" "}
            {soma > 0 ? Math.round((destaque.valor / soma) * 100) : 0}%
          </>
        ) : (
          "Passe o mouse numa parte da faixa"
        )}
      </p>
      {/* 2px de folga entre as partes; cantos de 4px só nas pontas da faixa */}
      <div aria-hidden className="flex h-5 w-full gap-0.5 overflow-hidden rounded">
        {fatias.map((f, i) => (
          <div
            key={f.nome}
            onMouseEnter={() => onAtiva(i)}
            onMouseLeave={() => onAtiva(null)}
            className={`h-full min-w-[3px] transition-opacity ${f.cor.bg} ${ativa != null && ativa !== i ? "opacity-40" : ""}`}
            style={{ flexGrow: Math.max(f.valor, 0), flexBasis: 0 }}
          />
        ))}
      </div>
    </div>
  )
}

/** O ranking na forma escolhida. Barras = o componente de sempre. */
export function RankingEmGrafico({
  tipo,
  titulo,
  itens,
  maximo = 6,
  rotuloOutros,
  total,
  formatar = formatBRL,
}: {
  tipo: TipoRanking
  titulo: string
  itens: ItemBarra[]
  maximo?: number
  rotuloOutros?: string
  total?: number
  formatar?: (v: number) => string
}) {
  const [ativa, setAtiva] = useState<number | null>(null)
  if (tipo === "barras") {
    return <BarrasHorizontais titulo={titulo} itens={itens} maximo={maximo} rotuloOutros={rotuloOutros} total={total} formatar={formatar} />
  }
  const fatias = fatiasDe(itens, rotuloOutros)
  const soma = total ?? fatias.reduce((s, f) => s + f.valor, 0)
  const legenda = <LegendaDasFatias fatias={fatias} soma={soma} ativa={ativa} onAtiva={setAtiva} formatar={formatar} />
  return (
    <figure aria-label={titulo} className="m-0">
      {tipo === "rosca" ? (
        // cartão estreito (meia largura): a legenda desce pra baixo da rosca em vez de espremer os nomes
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Rosca fatias={fatias} soma={soma} ativa={ativa} onAtiva={setAtiva} formatar={formatar} />
          <div className="min-w-[17rem] flex-1 basis-[17rem]">{legenda}</div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Faixa fatias={fatias} soma={soma} ativa={ativa} onAtiva={setAtiva} formatar={formatar} />
          {legenda}
        </div>
      )}
    </figure>
  )
}
