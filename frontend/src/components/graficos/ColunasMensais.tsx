import { useState } from "react"
import { formatBRL } from "../../lib/format"
import { formatCompacto, marcasDoEixo, useLargura } from "./base"

/** Colunas por mês: uma série ("Faturamento por mês") ou duas lado a lado
 * ("Entrou × saiu"), com uma linha por cima (o lucro) e/ou a média.
 * Tudo na mesma escala de R$ — um eixo só.
 *
 * Passar o mouse (ou andar com as setas do teclado) mostra os valores do
 * mês; com `onSelecionar`, clicar/Enter escolhe o mês. */

export interface SerieColunas {
  nome: string
  valores: number[]
  /** Classes de `fill` da coluna (claro e escuro). */
  classe: string
  /** Meses que não são o `destaque` (gráfico de uma série só). */
  classeApagada?: string
  /** Classes de fundo do quadradinho no balão/legenda. */
  classeChave: string
}

export interface LinhaColunas {
  nome: string
  /** `null` = mês sem dado (a linha é interrompida ali). */
  valores: (number | null)[]
}

const COR_LINHA = { traco: "stroke-slate-800 dark:stroke-slate-100", ponto: "fill-slate-800 dark:fill-slate-100", chave: "bg-slate-800 dark:bg-slate-100" }
export const CHAVE_LINHA = COR_LINHA.chave

function coluna(x: number, largura: number, topo: number, base: number): string {
  const r = Math.max(0, Math.min(4, largura / 2, base - topo))
  return `M${x},${base}V${topo + r}Q${x},${topo} ${x + r},${topo}H${x + largura - r}Q${x + largura},${topo} ${x + largura},${topo + r}V${base}Z`
}

export function ColunasMensais({
  titulo,
  rotulos,
  nomes,
  anos,
  series,
  linha,
  media,
  destaque = null,
  selecionado = null,
  onSelecionar,
  dica,
  altura = 220,
}: {
  /** Nome do gráfico pra leitor de tela. */
  titulo: string
  /** Rótulo curto de cada mês no eixo ("jan"). */
  rotulos: string[]
  /** Nome por extenso de cada mês ("Janeiro de 2026"), pro balão. */
  nomes: string[]
  /** Segunda linha do eixo (o ano), só onde muda — `null` nos outros meses. */
  anos?: (string | null)[]
  series: SerieColunas[]
  linha?: LinhaColunas
  /** Linha de referência (média), com rótulo. */
  media?: number | null
  /** Mês em destaque (ex.: o mês atual): cor cheia e valor escrito em cima. */
  destaque?: number | null
  /** Mês escolhido na tela (fica marcado). */
  selecionado?: number | null
  onSelecionar?: (indice: number) => void
  /** Linha pequena no fim do balão (ex.: "clique pra ver só este mês"). */
  dica?: (indice: number) => string
  altura?: number
}) {
  const [caixa, largura] = useLargura<HTMLDivElement>()
  const [cursor, setCursor] = useState<number | null>(null)
  const [peloTeclado, setPeloTeclado] = useState(false)

  const n = rotulos.length
  const mE = 46
  const mD = 8
  const mT = 22
  const mB = anos ? 36 : 22
  const W = Math.max(largura, 240)
  const plotW = W - mE - mD
  const plotH = altura - mT - mB

  const valoresLinha = (linha?.valores ?? []).filter((v): v is number => v !== null)
  const maior = Math.max(1, ...series.flatMap((s) => s.valores), ...valoresLinha, media ?? 0)
  const menor = Math.min(0, ...valoresLinha)
  const marcas = marcasDoEixo(menor, maior, 4)
  const yMin = marcas[0]
  const yMax = marcas[marcas.length - 1]
  const y = (v: number) => mT + ((yMax - v) / (yMax - yMin)) * plotH

  const faixa = plotW / n
  const k = series.length
  const vao = 2
  const larguraColuna = Math.min(24, Math.max(3, (faixa * 0.72 - vao * (k - 1)) / k))
  const larguraGrupo = k * larguraColuna + (k - 1) * vao
  // Tela estreita: só a inicial do mês (J F M A…), como num calendário.
  const apertado = faixa < 28
  const centro = (i: number) => mE + i * faixa + faixa / 2
  const xColuna = (i: number, s: number) => centro(i) - larguraGrupo / 2 + s * (larguraColuna + vao)


  // Trechos da linha (interrompe onde não tem dado).
  const trechos: string[] = []
  if (linha) {
    let atual: string[] = []
    linha.valores.forEach((v, i) => {
      if (v === null) {
        if (atual.length > 1) trechos.push(atual.join(" "))
        atual = []
      } else atual.push(`${centro(i)},${y(v)}`)
    })
    if (atual.length > 1) trechos.push(atual.join(" "))
  }

  function leitura(i: number): string {
    const partes = series.map((s) => `${s.nome.toLowerCase()} ${formatBRL(s.valores[i] ?? 0)}`)
    if (linha && linha.valores[i] != null) partes.push(`${linha.nome.toLowerCase()} ${formatBRL(linha.valores[i] as number)}`)
    return `${nomes[i]}: ${partes.join(", ")}`
  }

  function tecla(e: React.KeyboardEvent) {
    const atual = cursor ?? selecionado ?? destaque ?? n - 1
    let novo: number | null = null
    if (e.key === "ArrowRight") novo = cursor === null ? atual : Math.min(n - 1, atual + 1)
    else if (e.key === "ArrowLeft") novo = cursor === null ? atual : Math.max(0, atual - 1)
    else if (e.key === "Home") novo = 0
    else if (e.key === "End") novo = n - 1
    else if (e.key === "Escape") {
      setCursor(null)
      return
    } else if ((e.key === "Enter" || e.key === " ") && onSelecionar && cursor !== null) {
      e.preventDefault()
      onSelecionar(cursor)
      return
    } else return
    e.preventDefault()
    setPeloTeclado(true)
    setCursor(novo)
  }

  const rotuloDestaque = destaque !== null && k === 1 && (series[0].valores[destaque] ?? 0) > 0
  const balaoNaDireita = cursor !== null && centro(cursor) < W / 2

  return (
    <div
      ref={caixa}
      className="relative rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary-500"
      role="group"
      tabIndex={0}
      aria-label={`${titulo}. Use as setas pra andar pelos meses${onSelecionar ? " e Enter pra ver só o mês" : ""}.`}
      onKeyDown={tecla}
      onBlur={() => setCursor(null)}
    >
      <span className="sr-only" aria-live="polite">
        {peloTeclado && cursor !== null ? leitura(cursor) : ""}
      </span>
      {largura > 0 && (
        <svg width={W} height={altura} viewBox={`0 0 ${W} ${altura}`} aria-hidden className="block select-none" onPointerLeave={() => setCursor(null)}>
          {/* Grade: fios finos e contínuos, um tom fora do fundo. */}
          {marcas.map((m) => (
            <g key={m}>
              <line
                x1={mE}
                x2={W - mD}
                y1={y(m)}
                y2={y(m)}
                strokeWidth={1}
                className={m === 0 ? "stroke-slate-300 dark:stroke-slate-600" : "stroke-slate-100 dark:stroke-slate-700/70"}
              />
              <text x={mE - 8} y={y(m)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[10px] tabular-nums dark:fill-slate-500">
                {formatCompacto(m, false)}
              </text>
            </g>
          ))}

          {/* Faixa do mês escolhido / do mês sob o mouse. */}
          {rotulos.map((_, i) =>
            i === selecionado || i === cursor ? (
              <rect
                key={i}
                x={mE + i * faixa + 1}
                y={mT - 10}
                width={faixa - 2}
                height={plotH + 10}
                rx={6}
                className={i === selecionado ? "fill-primary-50 dark:fill-primary-900/40" : "fill-slate-100 dark:fill-slate-700/50"}
              />
            ) : null,
          )}

          {series.map((s, si) =>
            s.valores.map((v, i) =>
              v > 0 ? (
                <path
                  key={`${si}-${i}`}
                  d={coluna(xColuna(i, si), larguraColuna, y(v), y(0))}
                  className={destaque !== null && s.classeApagada && i !== destaque ? s.classeApagada : s.classe}
                />
              ) : null,
            ),
          )}

          {media != null && media > 0 && (
            <g>
              {/* Tracejada de propósito: é uma referência, não um dado do mês. */}
              <line x1={mE} x2={W - mD} y1={y(media)} y2={y(media)} strokeWidth={1.5} strokeDasharray="5 4" className="stroke-slate-500 dark:stroke-slate-400" />
              <text
                x={mE + 4}
                y={y(media) - 5}
                className="fill-slate-600 stroke-white text-[10px] font-medium dark:fill-slate-300 dark:stroke-slate-800"
                strokeWidth={3}
                paintOrder="stroke"
              >
                média {formatCompacto(media)}
              </text>
            </g>
          )}

          {trechos.map((pontos, i) => (
            <polyline key={i} points={pontos} fill="none" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" className={COR_LINHA.traco} />
          ))}
          {linha?.valores.map((v, i) =>
            v === null ? null : (
              <circle key={i} cx={centro(i)} cy={y(v)} r={cursor === i ? 5 : 4} strokeWidth={2} className={`${COR_LINHA.ponto} stroke-white dark:stroke-slate-800`} />
            ),
          )}

          {rotuloDestaque && destaque !== null && (
            <text
              x={Math.min(Math.max(centro(destaque), mE + 30), W - mD - 30)}
              y={y(series[0].valores[destaque]) - 7}
              textAnchor="middle"
              className="fill-slate-800 stroke-white text-[11px] font-semibold dark:fill-slate-100 dark:stroke-slate-800"
              strokeWidth={3}
              paintOrder="stroke"
            >
              {formatCompacto(series[0].valores[destaque])}
            </text>
          )}

          {rotulos.map((r, i) => {
            const forte = i === selecionado || i === destaque
            return (
              <g key={i}>
                <text
                  x={centro(i)}
                  y={altura - mB + 15}
                  textAnchor="middle"
                  className={`text-[10.5px] ${forte ? "fill-slate-900 font-semibold dark:fill-white" : "fill-slate-500 dark:fill-slate-400"}`}
                >
                  {apertado ? r.charAt(0).toUpperCase() : r}
                </text>
                {anos?.[i] && (
                  <text x={centro(i)} y={altura - mB + 29} textAnchor="middle" className="fill-slate-400 text-[10px] dark:fill-slate-500">
                    {anos[i]}
                  </text>
                )}
              </g>
            )
          })}

          {/* Área de toque: a faixa inteira do mês, não só a coluna. */}
          {rotulos.map((_, i) => (
            <rect
              key={i}
              x={mE + i * faixa}
              y={0}
              width={faixa}
              height={altura}
              fill="transparent"
              className={onSelecionar ? "cursor-pointer" : undefined}
              onPointerEnter={() => {
                setPeloTeclado(false)
                setCursor(i)
              }}
              onPointerMove={() => {
                if (cursor !== i) setCursor(i)
              }}
              onClick={() => onSelecionar?.(i)}
            />
          ))}
        </svg>
      )}

      {cursor !== null && largura > 0 && (
        <div
          role="presentation"
          className={`pointer-events-none absolute z-10 w-max max-w-[200px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-slate-600 dark:bg-slate-900 ${balaoNaDireita ? "" : "-translate-x-full"}`}
          // Ao lado do mês (nunca em cima dele), do lado que tem mais espaço.
          style={{ left: centro(cursor) + (balaoNaDireita ? 1 : -1) * (faixa / 2 + 6), top: mT - 10 }}
        >
          <p className="mb-1 text-slate-500 dark:text-slate-400">{nomes[cursor]}</p>
          {series.map((s) => (
            <p key={s.nome} className="flex items-center gap-1.5 whitespace-nowrap">
              <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-[2px] ${s.classeChave}`} />
              <strong className="font-semibold tabular-nums text-slate-900 dark:text-white">{formatBRL(s.valores[cursor] ?? 0)}</strong>
              <span className="text-slate-500 dark:text-slate-400">{s.nome.toLowerCase()}</span>
            </p>
          ))}
          {linha && linha.valores[cursor] != null && (
            <p className="flex items-center gap-1.5 whitespace-nowrap">
              <span aria-hidden className={`inline-block h-0.5 w-2.5 shrink-0 rounded-full ${COR_LINHA.chave}`} />
              <strong className="font-semibold tabular-nums text-slate-900 dark:text-white">{formatBRL(linha.valores[cursor] as number)}</strong>
              <span className="text-slate-500 dark:text-slate-400">{linha.nome.toLowerCase()}</span>
            </p>
          )}
          {dica && <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">{dica(cursor)}</p>}
        </div>
      )}
    </div>
  )
}
