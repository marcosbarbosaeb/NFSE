import { X } from "lucide-react"
import { type ReactNode, useEffect, useId, useRef } from "react"

export function Modal({
  titulo,
  onClose,
  children,
  largura = "max-w-lg",
}: {
  titulo: string
  onClose: () => void
  children: ReactNode
  largura?: string
}) {
  const idTitulo = useId()
  const painel = useRef<HTMLDivElement>(null)
  const fechar = useRef(onClose)
  fechar.current = onClose

  // Esc fecha, a página de trás não rola e o foco entra no modal (e volta
  // pra onde estava ao fechar).
  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const alvo = painel.current?.querySelector<HTMLElement>("input, select, textarea, button:not([data-fechar])")
    ;(alvo ?? painel.current)?.focus({ preventScroll: true })
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") fechar.current()
    }
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("keydown", esc)
      document.body.style.overflow = overflow
      anterior?.focus?.({ preventScroll: true })
    }
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 px-4 py-10">
      <div
        ref={painel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
        className={`w-full ${largura} rounded-2xl bg-white shadow-xl outline-none dark:bg-slate-800`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-700/60">
          <h2 id={idTitulo} className="text-base font-semibold text-slate-800 dark:text-slate-200">
            {titulo}
          </h2>
          <button
            type="button"
            data-fechar
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700"
          >
            <X size={18} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
