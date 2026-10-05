import { type ReactNode, useEffect, useRef, useState } from "react"
import { Card } from "../ui/Card"

/** Gráficos da Ana (05/10/2026) — "faltam algumas ferramentas gráficas".
 *
 * Sem biblioteca: SVG/HTML enxutos, com as cores do tema. As regras da casa:
 * - uma cor de destaque (o azul `primary`) e o resto em cinza (`slate`); o
 *   cinza nunca é "a segunda cor", é o que fica em segundo plano;
 * - texto sempre em cor de texto, nunca na cor da série (quem diz qual é
 *   qual é o quadradinho da legenda);
 * - todo valor dá pra ler sem passar o mouse: resumo escrito em cima e
 *   "Ver os números em tabela" embaixo; o balão do mouse é um a mais;
 * - claro e escuro com tons escolhidos pra cada um (não é só inverter).
 */

/** "R$ 12,5 mil", "R$ 1,2 mi" — pra caber em eixo e rótulo. */
export function formatCompacto(valor: number, comMoeda = true): string {
  const abs = Math.abs(valor)
  const sinal = valor < 0 ? "−" : ""
  const prefixo = comMoeda ? "R$ " : ""
  const br = (n: number, casas: number) => n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas })
  if (abs >= 1_000_000) return `${sinal}${prefixo}${br(abs / 1_000_000, abs >= 10_000_000 ? 0 : 1)} mi`
  if (abs >= 1_000) return `${sinal}${prefixo}${br(abs / 1_000, abs >= 100_000 ? 0 : 1)} mil`
  return `${sinal}${prefixo}${br(abs, 0)}`
}

/** Marcas redondas pro eixo (0 · 5 mil · 10 mil), cobrindo de `min` a `max`. */
export function marcasDoEixo(min: number, max: number, quantas = 4): number[] {
  const alcance = Math.max(max - min, 1)
  const bruto = alcance / quantas
  const potencia = 10 ** Math.floor(Math.log10(bruto))
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? 10 * potencia
  const inicio = Math.floor(min / passo) * passo
  const marcas: number[] = []
  for (let v = inicio; v < max + passo - 1e-9; v += passo) marcas.push(Math.round(v * 100) / 100)
  return marcas
}

/** Largura do elemento, acompanhando a tela (o SVG é desenhado no tamanho real). */
export function useLargura<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [largura, setLargura] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    setLargura(el.clientWidth)
    if (typeof ResizeObserver === "undefined") return
    const observador = new ResizeObserver(() => setLargura(el.clientWidth))
    observador.observe(el)
    return () => observador.disconnect()
  }, [])
  return [ref, largura]
}

export interface ItemLegenda {
  nome: string
  /** Classe de fundo do quadradinho (ex.: "bg-primary-500 dark:bg-primary-400"). */
  classe: string
  /** Série desenhada como linha: a chave vira um tracinho. */
  linha?: boolean
}

export function Legenda({ itens }: { itens: ItemLegenda[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300" aria-label="Legenda">
      {itens.map((i) => (
        <li key={i.nome} className="flex items-center gap-1.5">
          <span aria-hidden className={`inline-block shrink-0 ${i.linha ? "h-0.5 w-4 rounded-full" : "h-2.5 w-2.5 rounded-[3px]"} ${i.classe}`} />
          {i.nome}
        </li>
      ))}
    </ul>
  )
}

export interface TabelaGrafico {
  titulo: string
  colunas: string[]
  linhas: (string | number)[][]
}

/** A moldura de todo gráfico: do que é, o resumo em palavras, o desenho e
 * os mesmos números em tabela (pra leitor de tela e pra quem prefere). */
export function CartaoGrafico({
  periodo,
  resumo,
  legenda,
  tabela,
  acao,
  children,
}: {
  /** De quando são os números (ex.: "em 2026", "últimos 12 meses"). */
  periodo?: ReactNode
  /** O que o gráfico mostra, em uma frase — é a leitura dele sem olhar o desenho. */
  resumo?: ReactNode
  legenda?: ItemLegenda[]
  tabela?: TabelaGrafico
  acao?: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="flex h-full flex-col gap-3 p-5">
      {(periodo || legenda || acao) && (
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
            {periodo && <span className="text-xs text-slate-500 dark:text-slate-400">{periodo}</span>}
            {legenda && legenda.length > 1 && <Legenda itens={legenda} />}
          </div>
          {acao}
        </div>
      )}
      {resumo && <p className="text-sm text-slate-700 dark:text-slate-200">{resumo}</p>}
      {children}
      {tabela && tabela.linhas.length > 0 && (
        <details className="group mt-auto text-xs">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded font-medium text-primary-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500 dark:text-primary-300 [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">Ver os números em tabela</span>
            <span className="hidden group-open:inline">Esconder a tabela</span>
          </summary>
          <div className="mt-2 max-h-72 overflow-auto">
            <table className="w-full text-left tabular-nums">
              <caption className="sr-only">{tabela.titulo}</caption>
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  {tabela.colunas.map((c, i) => (
                    <th key={c} scope="col" className={`py-1.5 font-medium ${i === 0 ? "pr-3" : "pl-3 text-right"}`}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tabela.linhas.map((linha, l) => (
                  <tr key={l} className="border-b border-slate-100 last:border-0 dark:border-slate-700/50">
                    {linha.map((celula, i) =>
                      i === 0 ? (
                        <th key={i} scope="row" className="py-1.5 pr-3 font-normal text-slate-700 dark:text-slate-200">
                          {celula}
                        </th>
                      ) : (
                        <td key={i} className="py-1.5 pl-3 text-right text-slate-700 dark:text-slate-200">
                          {celula}
                        </td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Card>
  )
}

export function GraficoVazio({ children }: { children: ReactNode }) {
  return <p className="flex min-h-32 items-center justify-center py-6 text-center text-sm text-slate-400 dark:text-slate-500">{children}</p>
}
