import { ChevronDown, Plus } from "lucide-react"
import { useEffect, useId, useMemo, useRef, useState } from "react"

/** Caixa de escolha com pesquisa (05/10/2026): digitar vai filtrando a
 * lista — "na caixa de selecionar tomador no extrato é interessante poder
 * digitar e ir pesquisando automaticamente". Opcionalmente cria um item
 * novo com o texto digitado. */

export interface OpcaoBusca {
  id: string
  rotulo: string
  /** Separador de grupo (ex.: "Só controle (sem nota)"). */
  grupo?: string
}

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

export function CaixaBusca({
  valor,
  opcoes,
  onEscolher,
  onCriar,
  rotuloCriar = "Criar",
  placeholder = "Selecione...",
  disabled,
  alerta,
  className = "",
  ariaLabel,
  quebrar = false,
}: {
  /** Opções longas quebram em várias linhas em vez de cortar com "…". */
  quebrar?: boolean
  valor: string
  opcoes: OpcaoBusca[]
  onEscolher: (id: string) => void
  /** Quando existe, a lista oferece criar um item com o texto digitado. */
  onCriar?: (texto: string) => void
  rotuloCriar?: string
  placeholder?: string
  disabled?: boolean
  /** Borda de atenção (campo obrigatório ainda vazio). */
  alerta?: boolean
  className?: string
  ariaLabel?: string
}) {
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState("")
  const [ativo, setAtivo] = useState(0)
  const [pos, setPos] = useState<{ top: number; left: number; width: number; acima: boolean } | null>(null)
  const raiz = useRef<HTMLDivElement>(null)
  const campo = useRef<HTMLInputElement>(null)
  const lista = useRef<HTMLUListElement>(null)
  const idLista = useId()
  const escolhida = opcoes.find((o) => o.id === valor)

  const filtradas = useMemo(() => {
    const alvo = semAcento(texto.trim())
    if (!alvo) return opcoes
    const palavras = alvo.split(/\s+/)
    return opcoes.filter((o) => palavras.every((p) => semAcento(o.rotulo).includes(p)))
  }, [opcoes, texto])
  const podeCriar =
    !!onCriar && texto.trim().length >= 2 && !opcoes.some((o) => semAcento(o.rotulo) === semAcento(texto.trim()))
  const total = filtradas.length + (podeCriar ? 1 : 0)

  function posicionar() {
    const r = campo.current?.getBoundingClientRect()
    if (!r) return
    const acima = window.innerHeight - r.bottom < 260 && r.top > 260
    setPos({ top: acima ? r.top - 4 : r.bottom + 4, left: r.left, width: Math.max(r.width, 240), acima })
  }

  function abrir() {
    if (disabled) return
    setTexto("")
    setAtivo(Math.max(0, opcoes.findIndex((o) => o.id === valor)))
    posicionar()
    setAberto(true)
  }

  function fechar() {
    setAberto(false)
    setTexto("")
  }

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => {
      if (raiz.current?.contains(e.target as Node) || lista.current?.contains(e.target as Node)) return
      fechar()
    }
    // A lista é fixa na tela (não é cortada pela rolagem do modal): rolar a
    // página por fora fecha; rolar a própria lista, não.
    const rolou = (e: Event) => {
      if (lista.current?.contains(e.target as Node)) return
      fechar()
    }
    document.addEventListener("mousedown", fora)
    window.addEventListener("scroll", rolou, true)
    window.addEventListener("resize", fechar)
    return () => {
      document.removeEventListener("mousedown", fora)
      window.removeEventListener("scroll", rolou, true)
      window.removeEventListener("resize", fechar)
    }
  }, [aberto])

  useEffect(() => {
    if (aberto) lista.current?.querySelector<HTMLElement>(`[data-indice="${ativo}"]`)?.scrollIntoView({ block: "nearest" })
  }, [ativo, aberto])

  function escolher(indice: number) {
    if (indice < filtradas.length) onEscolher(filtradas[indice].id)
    else if (podeCriar) onCriar?.(texto.trim())
    fechar()
    campo.current?.blur()
  }

  let grupoAnterior: string | undefined
  return (
    <div ref={raiz} className={`relative ${className}`}>
      <input
        ref={campo}
        role="combobox"
        aria-expanded={aberto}
        aria-controls={idLista}
        aria-autocomplete="list"
        aria-label={ariaLabel}
        disabled={disabled}
        value={aberto ? texto : (escolhida?.rotulo ?? "")}
        placeholder={aberto && escolhida ? escolhida.rotulo : placeholder}
        // Abre no clique ou ao digitar — não no foco: num modal, o primeiro
        // campo recebe o foco sozinho e a lista abriria sem ninguém pedir.
        onClick={() => !aberto && abrir()}
        onChange={(e) => {
          setTexto(e.target.value)
          setAtivo(0)
          if (!aberto) abrir()
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault()
            if (!aberto) abrir()
            else setAtivo((a) => Math.min(total - 1, a + 1))
          } else if (e.key === "ArrowUp") {
            e.preventDefault()
            setAtivo((a) => Math.max(0, a - 1))
          } else if (e.key === "Enter") {
            if (aberto && total > 0) {
              e.preventDefault()
              escolher(ativo)
            }
          } else if (e.key === "Escape" && aberto) {
            e.stopPropagation()
            fechar()
          } else if (e.key === "Tab") {
            fechar()
          }
        }}
        className={`w-full rounded-lg border bg-white py-1.5 pl-2 pr-7 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50 dark:bg-slate-900 dark:text-slate-100 ${alerta ? "border-warning-400" : "border-slate-300 dark:border-slate-600"}`}
      />
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
      {aberto && pos && (
        <ul
          ref={lista}
          id={idLista}
          role="listbox"
          // Dentro de um <label>, o clique numa opção seria repassado pro
          // campo (e reabriria a lista): aqui ele para.
          onClick={(e) => e.preventDefault()}
          style={{
            left: pos.left,
            width: pos.width,
            ...(pos.acima ? { bottom: window.innerHeight - pos.top } : { top: pos.top }),
          }}
          className="fixed z-[70] max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-xl dark:border-slate-700 dark:bg-slate-800"
        >
          {filtradas.map((o, i) => {
            const cabecalho = o.grupo && o.grupo !== grupoAnterior ? o.grupo : null
            grupoAnterior = o.grupo
            return (
              <li key={o.id} role="presentation">
                {cabecalho && <p className="px-3 pb-0.5 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{cabecalho}</p>}
                <button
                  type="button"
                  role="option"
                  aria-selected={o.id === valor}
                  data-indice={i}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setAtivo(i)}
                  onClick={() => escolher(i)}
                  className={`block w-full px-3 py-1.5 text-left ${quebrar ? "whitespace-normal break-words" : "truncate"} ${i === ativo ? "bg-primary-50 text-primary-800 dark:bg-primary-900/40 dark:text-primary-100" : "text-slate-700 dark:text-slate-200"} ${o.id === valor ? "font-semibold" : ""}`}
                >
                  {o.rotulo}
                </button>
              </li>
            )
          })}
          {filtradas.length === 0 && !podeCriar && <li className="px-3 py-2 text-slate-400">Nada encontrado.</li>}
          {podeCriar && (
            <li role="presentation" className={filtradas.length ? "mt-1 border-t border-slate-100 pt-1 dark:border-slate-700" : ""}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                data-indice={filtradas.length}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setAtivo(filtradas.length)}
                onClick={() => escolher(filtradas.length)}
                className={`flex w-full items-center gap-1.5 px-3 py-1.5 text-left font-medium text-primary-700 dark:text-primary-200 ${ativo === filtradas.length ? "bg-primary-50 dark:bg-primary-900/40" : ""}`}
              >
                <Plus className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <span className="truncate">
                  {rotuloCriar} “{texto.trim()}”
                </span>
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
