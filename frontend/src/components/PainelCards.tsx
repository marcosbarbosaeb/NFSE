import { ArrowDown, ArrowUp, ChevronDown, GripVertical } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { api } from "../lib/api"

/** Cards de uma tela que a pessoa organiza do jeito dela (05/10/2026): cada
 * um abre e fecha, e em "Editar disposição" dá pra arrastar pra mudar a
 * ordem. A escolha fica na conta (e no navegador, pra abrir sem piscar). */

export interface SecaoCard {
  id: string
  titulo: string
  /** Texto curto ao lado do título (um total, uma contagem). */
  resumo?: ReactNode
  conteudo: ReactNode
  /** Âncora pra links (#a-receber). */
  ancora?: string
  /** Não aparece (ex.: card que só existe quando há algo a mostrar). */
  oculto?: boolean
}

interface Disposicao {
  ordem: string[]
  fechados: string[]
}

const chaveLocal = (tela: string) => `ana:disposicao:${tela}`

function lerLocal(tela: string): Disposicao | null {
  try {
    const bruto = localStorage.getItem(chaveLocal(tela))
    const d = bruto ? JSON.parse(bruto) : null
    return d && Array.isArray(d.ordem) && Array.isArray(d.fechados) ? d : null
  } catch {
    return null
  }
}

export function PainelCards({
  tela,
  secoes,
  editando,
  fechadosDePadrao = [],
  abrir,
}: {
  tela: "financeiro" | "visao_geral"
  secoes: SecaoCard[]
  editando: boolean
  fechadosDePadrao?: string[]
  /** Id de um card que precisa estar aberto agora (veio de um link). */
  abrir?: string | null
}) {
  const [disposicao, setDisposicao] = useState<Disposicao>(() => lerLocal(tela) ?? { ordem: [], fechados: fechadosDePadrao })
  const [arrastando, setArrastando] = useState<string | null>(null)
  const salvar = useRef<number | undefined>(undefined)

  useEffect(() => {
    let vivo = true
    api
      .get<Record<string, Disposicao | undefined>>("/conta/preferencias")
      .then((p) => {
        const d = p?.[tela]
        if (vivo && d && Array.isArray(d.ordem) && Array.isArray(d.fechados)) setDisposicao({ ordem: d.ordem, fechados: d.fechados })
      })
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [tela])

  function mudar(nova: Disposicao) {
    setDisposicao(nova)
    try {
      localStorage.setItem(chaveLocal(tela), JSON.stringify(nova))
    } catch {
      // navegador sem armazenamento: vale só nesta visita
    }
    window.clearTimeout(salvar.current)
    salvar.current = window.setTimeout(() => {
      api.put("/conta/preferencias", { tela, ordem: nova.ordem, fechados: nova.fechados }).catch(() => undefined)
    }, 600)
  }

  // Ordem escolhida primeiro; cards novos (que a pessoa ainda não ordenou)
  // entram no lugar padrão deles.
  const visiveis = secoes.filter((s) => !s.oculto)
  const posicao = (id: string) => {
    const i = disposicao.ordem.indexOf(id)
    return i === -1 ? 1000 + secoes.findIndex((s) => s.id === id) : i
  }
  const ordenadas = [...visiveis].sort((a, b) => posicao(a.id) - posicao(b.id))
  const ids = ordenadas.map((s) => s.id)

  // Link pra um card fechado: abre.
  useEffect(() => {
    if (abrir && disposicao.fechados.includes(abrir)) mudar({ ...disposicao, fechados: disposicao.fechados.filter((f) => f !== abrir) })
  }, [abrir]) // eslint-disable-line react-hooks/exhaustive-deps

  function alternar(id: string) {
    const fechados = disposicao.fechados.includes(id) ? disposicao.fechados.filter((f) => f !== id) : [...disposicao.fechados, id]
    mudar({ ordem: disposicao.ordem, fechados })
  }

  function mover(id: string, para: number) {
    const de = ids.indexOf(id)
    if (de === -1 || para < 0 || para >= ids.length || de === para) return
    const nova = [...ids]
    nova.splice(de, 1)
    nova.splice(para, 0, id)
    mudar({ ordem: nova, fechados: disposicao.fechados })
  }

  if (editando) {
    return (
      <ol className="flex flex-col gap-2" aria-label="Ordem dos cards">
        {ordenadas.map((s, i) => (
          <li
            key={s.id}
            draggable
            onDragStart={(e) => {
              setArrastando(s.id)
              e.dataTransfer.effectAllowed = "move"
              e.dataTransfer.setData("text/plain", s.id)
            }}
            onDragOver={(e) => {
              e.preventDefault()
              if (arrastando && arrastando !== s.id) mover(arrastando, i)
            }}
            onDragEnd={() => setArrastando(null)}
            onDrop={(e) => e.preventDefault()}
            className={`flex cursor-grab items-center gap-3 rounded-xl border bg-white px-3 py-3 shadow-sm active:cursor-grabbing dark:bg-slate-800 ${arrastando === s.id ? "border-primary-500 opacity-60" : "border-slate-200 dark:border-slate-700"}`}
          >
            <GripVertical className="h-5 w-5 shrink-0 text-slate-400" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{s.titulo}</span>
            <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <input type="checkbox" checked={!disposicao.fechados.includes(s.id)} onChange={() => alternar(s.id)} />
              aberto
            </label>
            <span className="flex shrink-0 gap-0.5">
              <button
                type="button"
                onClick={() => mover(s.id, i - 1)}
                disabled={i === 0}
                aria-label={`Subir ${s.titulo}`}
                title="Subir"
                className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-700"
              >
                <ArrowUp className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => mover(s.id, i + 1)}
                disabled={i === ordenadas.length - 1}
                aria-label={`Descer ${s.titulo}`}
                title="Descer"
                className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-700"
              >
                <ArrowDown className="h-4 w-4" />
              </button>
            </span>
          </li>
        ))}
      </ol>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {ordenadas.map((s) => {
        const fechado = disposicao.fechados.includes(s.id)
        return (
          <section key={s.id} id={s.ancora} className="scroll-mt-20">
            <button
              type="button"
              onClick={() => alternar(s.id)}
              aria-expanded={!fechado}
              className={`group flex w-full items-center gap-2 text-left ${fechado ? "rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700/60" : "mb-2 px-1"}`}
            >
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:text-slate-600 ${fechado ? "-rotate-90" : ""}`}
                aria-hidden
              />
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{s.titulo}</span>
              {s.resumo != null && <span className="ml-auto text-sm tabular-nums text-slate-500 dark:text-slate-400">{s.resumo}</span>}
            </button>
            {!fechado && s.conteudo}
          </section>
        )
      })}
    </div>
  )
}
