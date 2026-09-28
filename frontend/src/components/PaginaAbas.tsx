import type { LucideIcon } from "lucide-react"
import { type KeyboardEvent, type ReactNode, useId, useRef } from "react"
import { useSearchParams } from "react-router-dom"

// Telas "Minha conta" e "Empresa" (29/09/2026): em vez de uma página só de
// Configurações, cada área tem abas — lista vertical à esquerda no
// computador, faixa rolável no celular. A aba escolhida fica em ?aba=...
// (dá pra mandar link direto, e o voltar do navegador funciona).

export interface Aba {
  id: string
  rotulo: string
  icone: LucideIcon
  /** Aba em vermelho (zona de perigo). */
  perigo?: boolean
  conteudo: () => ReactNode
}

export function PaginaAbas({
  titulo,
  subtitulo,
  abas,
  cabecalho,
}: {
  titulo: string
  subtitulo?: ReactNode
  abas: Aba[]
  /** Algo extra ao lado do título (ex.: CNPJ da empresa). */
  cabecalho?: ReactNode
}) {
  const [params, setParams] = useSearchParams()
  const pedida = params.get("aba")
  const atual = abas.find((a) => a.id === pedida) ?? abas[0]
  const base = useId()
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  function escolher(id: string, focar = false) {
    const novos = new URLSearchParams(params)
    novos.set("aba", id)
    // Parâmetros de uso único (ex.: ?assinatura=sucesso) não seguem pra outra aba.
    for (const chave of [...novos.keys()]) if (chave !== "aba") novos.delete(chave)
    setParams(novos, { replace: false })
    if (focar) requestAnimationFrame(() => refs.current[id]?.focus())
  }

  function teclado(e: KeyboardEvent<HTMLButtonElement>) {
    const i = abas.findIndex((a) => a.id === atual.id)
    let alvo: number | null = null
    if (e.key === "ArrowDown" || e.key === "ArrowRight") alvo = (i + 1) % abas.length
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft") alvo = (i - 1 + abas.length) % abas.length
    else if (e.key === "Home") alvo = 0
    else if (e.key === "End") alvo = abas.length - 1
    if (alvo === null) return
    e.preventDefault()
    escolher(abas[alvo].id, true)
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{titulo}</h1>
          {subtitulo && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitulo}</p>}
        </div>
        {cabecalho}
      </div>

      <div className="flex flex-col gap-6 xl:flex-row xl:items-start">
        <div
          role="tablist"
          aria-label={titulo}
          className="-mx-4 flex gap-1 overflow-x-auto px-4 py-1 sm:-mx-1 sm:px-1 xl:sticky xl:top-6 xl:w-52 xl:shrink-0 xl:flex-col xl:overflow-visible xl:py-0"
        >
          {abas.map((a) => {
            const ativa = a.id === atual.id
            const Icone = a.icone
            return (
              <button
                key={a.id}
                ref={(el) => {
                  refs.current[a.id] = el
                }}
                type="button"
                role="tab"
                id={`${base}-aba-${a.id}`}
                aria-selected={ativa}
                aria-controls={`${base}-painel`}
                tabIndex={ativa ? 0 : -1}
                onClick={() => escolher(a.id)}
                onKeyDown={teclado}
                className={`flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 xl:w-full ${
                  ativa
                    ? a.perigo
                      ? "bg-danger-50 text-danger-700 dark:bg-danger-900/30 dark:text-danger-300"
                      : "bg-white text-primary-700 shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:text-primary-300 dark:ring-slate-700"
                    : a.perigo
                      ? "text-danger-600 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-900/20"
                      : "text-slate-600 hover:bg-white/70 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-100"
                }`}
              >
                <Icone size={16} className={ativa && !a.perigo ? "text-primary-600 dark:text-primary-400" : ""} aria-hidden="true" />
                {a.rotulo}
              </button>
            )
          })}
        </div>

        <div
          role="tabpanel"
          id={`${base}-painel`}
          aria-labelledby={`${base}-aba-${atual.id}`}
          className="flex min-w-0 flex-1 flex-col gap-6"
        >
          {atual.conteudo()}
        </div>
      </div>
    </div>
  )
}

/** Título de seção dentro de um Card, no padrão das telas de ajustes. */
export function TituloSecao({ icone: Icone, children, perigo }: { icone?: LucideIcon; children: ReactNode; perigo?: boolean }) {
  return (
    <h2
      className={`mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide ${
        perigo ? "text-danger-600" : "text-slate-400 dark:text-slate-500"
      }`}
    >
      {Icone && <Icone size={16} aria-hidden="true" />} {children}
    </h2>
  )
}
