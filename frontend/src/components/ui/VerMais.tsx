import { ChevronDown } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"

/** Visão geral (05/10/2026): "coloque um limite de itens e acima disso deixe
 * como ver mais" — nenhum card cresce sem limite e empurra os outros. */

const BOTAO =
  "mt-2 inline-flex items-center gap-1 text-xs font-semibold text-primary-600 hover:underline dark:text-primary-300"

/** Lista com limite de itens: devolve os visíveis e o botão "ver mais N". */
export function useVerMais<T>(itens: T[], limite: number): { visiveis: T[]; botao: ReactNode } {
  const [tudo, setTudo] = useState(false)
  // Sobrando só um, mostra de uma vez — o botão ocuparia a mesma linha.
  const cabe = itens.length <= limite + 1
  const visiveis = tudo || cabe ? itens : itens.slice(0, limite)
  const botao = cabe ? null : (
    <button type="button" onClick={() => setTudo((v) => !v)} aria-expanded={tudo} className={BOTAO}>
      <ChevronDown size={14} className={`transition-transform ${tudo ? "rotate-180" : ""}`} />
      {tudo ? "ver menos" : `ver mais ${itens.length - limite}`}
    </button>
  )
  return { visiveis, botao }
}

/** Conteúdo qualquer com altura máxima: passou disso, corta com um "ver
 * mais". Mexeu dentro (foco num campo), abre sozinho — nada some enquanto
 * a pessoa digita. */
export function AlturaLimitada({ altura = 320, children }: { altura?: number; children: ReactNode }) {
  const caixa = useRef<HTMLDivElement>(null)
  const [aberto, setAberto] = useState(false)
  const [passa, setPassa] = useState(false)

  useEffect(() => {
    const el = caixa.current
    if (!el) return
    const medir = () => setPassa(el.scrollHeight > altura + 40)
    medir()
    if (typeof ResizeObserver === "undefined") return
    const obs = new ResizeObserver(medir)
    obs.observe(el)
    Array.from(el.children).forEach((filho) => obs.observe(filho))
    return () => obs.disconnect()
  }, [altura, children])

  const cortado = passa && !aberto
  return (
    <div>
      <div
        ref={caixa}
        onFocusCapture={(e) => {
          if (cortado && e.target instanceof HTMLElement && e.target.matches("input, textarea, select")) setAberto(true)
        }}
        className={cortado ? "relative overflow-hidden" : "relative"}
        style={cortado ? { maxHeight: altura } : undefined}
      >
        {children}
        {cortado && (
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-14 rounded-b-2xl bg-gradient-to-t from-white to-transparent dark:from-slate-800" />
        )}
      </div>
      {passa && (
        <button type="button" onClick={() => setAberto((v) => !v)} aria-expanded={aberto} className={`${BOTAO} px-1`}>
          <ChevronDown size={14} className={`transition-transform ${aberto ? "rotate-180" : ""}`} />
          {aberto ? "ver menos" : "ver mais"}
        </button>
      )}
    </div>
  )
}
