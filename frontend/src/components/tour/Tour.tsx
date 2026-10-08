import { X } from "lucide-react"
import { type CSSProperties, type ReactNode, useCallback, useEffect, useLayoutEffect, useState } from "react"
import { useLocation } from "react-router-dom"
import { aoMudarTutorial, jaViu, marcarVisto, passeioEmAndamento, tutorialAtivo } from "../../lib/tutorial"
import { AnaAvatar } from "../brand/Marca"
import { type PassoTour, tourDoCaminho } from "./passos"

// Dicas de primeira visita (ver lib/tutorial.ts). Um "holofote" em cima do
// elemento com data-tour="..." e um balão com a Ana explicando; sem
// elemento, o balão aparece no centro.

const LARGURA_BALAO = 320
const MARGEM = 12

interface Caixa {
  top: number
  left: number
  width: number
  height: number
}

function caixaDoAlvo(alvo?: string): Caixa | null {
  if (!alvo) return null
  const el = document.querySelector<HTMLElement>(`[data-tour="${alvo}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) return null
  return { top: r.top - 6, left: r.left - 6, width: r.width + 12, height: r.height + 12 }
}

export const BOTAO_SUAVE = "rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
export const BOTAO_FORTE = "rounded-lg bg-accent-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-600"

/** O balão em que a Ana fala, com o "holofote" no elemento `data-tour={alvo}`
 * (sem alvo, ou se ele não estiver na tela, fica no centro). Quem usa põe os
 * botões no rodapé (`children`). Serve às dicas de primeira visita e ao
 * passeio das novidades. */
export function BalaoDaAna({
  alvo,
  titulo,
  texto,
  onFechar,
  rotuloFechar = "Fechar",
  children,
}: {
  alvo?: string
  titulo: string
  texto: ReactNode
  onFechar: () => void
  rotuloFechar?: string
  children: ReactNode
}) {
  const [caixa, setCaixa] = useState<Caixa | null>(null)
  const medir = useCallback(() => setCaixa(caixaDoAlvo(alvo)), [alvo])

  useLayoutEffect(() => {
    const el = alvo ? document.querySelector<HTMLElement>(`[data-tour="${alvo}"]`) : null
    el?.scrollIntoView({ block: "center", behavior: "smooth" })
    medir()
    const t = setTimeout(medir, 350) // depois do scroll suave
    const t2 = setTimeout(medir, 1200) // ...e de a tela terminar de carregar
    window.addEventListener("resize", medir)
    window.addEventListener("scroll", medir, true)
    return () => {
      clearTimeout(t)
      clearTimeout(t2)
      window.removeEventListener("resize", medir)
      window.removeEventListener("scroll", medir, true)
    }
  }, [alvo, titulo, medir])

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && onFechar()
    window.addEventListener("keydown", tecla)
    return () => window.removeEventListener("keydown", tecla)
  }, [onFechar])

  const vw = window.innerWidth
  const vh = window.innerHeight
  const largura = Math.min(LARGURA_BALAO, vw - 2 * MARGEM)
  let estiloBalao: CSSProperties
  if (caixa) {
    const abaixo = caixa.top + caixa.height + MARGEM
    const cabeAbaixo = abaixo + 200 < vh
    const left = Math.min(Math.max(MARGEM, caixa.left + caixa.width / 2 - largura / 2), vw - largura - MARGEM)
    estiloBalao = cabeAbaixo
      ? { top: abaixo, left, width: largura }
      : { bottom: Math.max(MARGEM, vh - caixa.top + MARGEM), left, width: largura }
  } else {
    estiloBalao = { top: "50%", left: "50%", width: largura, transform: "translate(-50%, -50%)" }
  }

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label={titulo}>
      {caixa ? (
        <div
          className="pointer-events-none fixed rounded-xl ring-2 ring-accent-400 transition-all duration-300"
          style={{ ...caixa, boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.55)" }}
        />
      ) : (
        <div className="fixed inset-0 bg-slate-900/55" />
      )}
      {/* clicar fora não fecha de propósito — só os botões */}
      <div className="fixed rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-800" style={estiloBalao}>
        <div className="flex items-start gap-3">
          <AnaAvatar size={40} />
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-slate-900 dark:text-slate-100">{titulo}</p>
            <div className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{texto}</div>
          </div>
          <button type="button" onClick={onFechar} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700" aria-label={rotuloFechar}>
            <X size={16} />
          </button>
        </div>
        <div className="mt-4 flex items-center justify-between gap-2">{children}</div>
      </div>
    </div>
  )
}

export function TourDaPagina() {
  const { pathname } = useLocation()
  const tour = tourDoCaminho(pathname)
  const [passos, setPassos] = useState<PassoTour[] | null>(null)
  const [indice, setIndice] = useState(0)

  const abrir = useCallback(() => {
    if (!tour) return
    setIndice(0)
    setPassos(tour.passos)
  }, [tour])

  // Primeira visita a esta tela.
  useEffect(() => {
    setPassos(null)
    // Durante o passeio das novidades as dicas da tela esperam (senão abririam as duas juntas).
    if (!tour || !tutorialAtivo() || jaViu(tour.tela) || passeioEmAndamento()) return
    const t = setTimeout(abrir, 700) // espera a tela carregar os dados
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  // Botão "?" do topo e o liga/desliga das Configurações.
  useEffect(
    () =>
      aoMudarTutorial((e) => {
        if ((e as CustomEvent).detail === "abrir") abrir()
        else if (!tutorialAtivo()) setPassos(null)
      }),
    [abrir],
  )

  const passo = passos?.[indice]

  function fechar() {
    if (tour) marcarVisto(tour.tela)
    setPassos(null)
  }

  if (!passos || !passo) return null
  const ultimo = indice === passos.length - 1

  return (
    <BalaoDaAna alvo={passo.alvo} titulo={passo.titulo} texto={passo.texto} onFechar={fechar} rotuloFechar="Fechar dicas">
      <div className="flex gap-1">
        {passos.map((_, i) => (
          <span key={i} className={`h-1.5 w-1.5 rounded-full ${i === indice ? "bg-accent-500" : "bg-slate-300 dark:bg-slate-600"}`} />
        ))}
      </div>
      <div className="flex gap-2">
        {indice > 0 ? (
          <button type="button" onClick={() => setIndice((i) => i - 1)} className={BOTAO_SUAVE}>
            Voltar
          </button>
        ) : (
          <button type="button" onClick={fechar} className={BOTAO_SUAVE}>
            Pular
          </button>
        )}
        <button type="button" onClick={() => (ultimo ? fechar() : setIndice((i) => i + 1))} className={BOTAO_FORTE}>
          {ultimo ? "Entendi" : "Próximo"}
        </button>
      </div>
    </BalaoDaAna>
  )
}
