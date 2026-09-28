import { useEffect, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, parseBRL } from "../lib/format"
import { Badge } from "./ui/Badge"

// Status de pagamento clicável (28/09/2026): "Pendente" -> dar baixa (registra
// o recebimento com o valor da nota); "Recebida" -> desfazer. A importação do
// extrato continua dando baixa sozinha — o recebimento é por
// tomador+competência, então a nota já aparece como recebida.

function hojeISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export function BaixaPagamento({
  vinculoId,
  competencia,
  valor,
  recebido,
  onMudou,
}: {
  vinculoId: string | null | undefined
  competencia: string
  valor: number
  recebido: boolean
  onMudou: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [data, setData] = useState(hojeISO())
  const [valorTexto, setValorTexto] = useState(valor.toFixed(2))
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  // Painel com position:fixed — tabelas com overflow cortariam um popover comum.
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setAberto(false)
    // Rolar a página fecha (o painel é fixo e ficaria solto) — menos quando
    // a pessoa está digitando nele: no celular o teclado rola a tela.
    const fechar = () => {
      if (ref.current?.contains(document.activeElement)) return
      setAberto(false)
    }
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false)
    document.addEventListener("mousedown", fora)
    document.addEventListener("keydown", esc)
    window.addEventListener("scroll", fechar, true)
    return () => {
      document.removeEventListener("mousedown", fora)
      document.removeEventListener("keydown", esc)
      window.removeEventListener("scroll", fechar, true)
    }
  }, [aberto])

  if (!vinculoId) return recebido ? <Badge variant="success">Recebida</Badge> : <Badge variant="warning">Pendente</Badge>

  async function confirmar() {
    setEnviando(true)
    setErro(null)
    try {
      if (recebido) {
        await api.delete(`/pagamentos?vinculo_id=${vinculoId}&competencia=${competencia}`)
      } else {
        const valorNum = parseBRL(valorTexto)
        if (valorNum == null || valorNum <= 0) throw new ApiError(422, "Informe o valor recebido.")
        await api.post("/pagamentos", { vinculo_id: vinculoId, competencia, valor: valorNum, data_recebimento: data || null })
      }
      setAberto(false)
      onMudou()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          const r = e.currentTarget.getBoundingClientRect()
          const largura = 256
          const top = r.bottom + 8 + 230 > window.innerHeight ? Math.max(8, r.top - 238) : r.bottom + 8
          setPos({ top, left: Math.max(8, Math.min(r.right - largura, window.innerWidth - largura - 8)) })
          setAberto((a) => !a)
        }}
        title={recebido ? "Recebida — clique pra desfazer a baixa" : "Pendente — clique pra dar baixa"}
        className="rounded-full focus:outline-none focus:ring-2 focus:ring-primary-300"
      >
        {recebido ? (
          <Badge variant="success">Recebida ✓</Badge>
        ) : (
          <span className="group inline-flex">
            <span className="group-hover:hidden">
              <Badge variant="warning">Pendente</Badge>
            </span>
            <span className="hidden group-hover:inline-flex">
              <Badge variant="info">Dar baixa</Badge>
            </span>
          </span>
        )}
      </button>
      {aberto && pos && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{ top: pos.top, left: pos.left }}
          className="fixed z-50 w-64 rounded-xl border border-slate-200 bg-white p-3 text-left shadow-xl dark:border-slate-700 dark:bg-slate-800"
        >
          {recebido ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">Desfazer a baixa? A nota volta a ficar pendente.</p>
          ) : (
            <div className="flex flex-col gap-2 text-sm">
              <p className="font-medium text-slate-800 dark:text-slate-100">Registrar que o pagamento caiu</p>
              <label className="text-xs text-slate-500">
                Valor recebido
                <input
                  type="number"
                  step="0.01"
                  value={valorTexto}
                  onChange={(e) => setValorTexto(e.target.value)}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <label className="text-xs text-slate-500">
                Data em que caiu
                <input
                  type="date"
                  value={data}
                  onChange={(e) => setData(e.target.value)}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <p className="text-[11px] text-slate-400">Valor da nota: {formatBRL(valor)}</p>
            </div>
          )}
          {erro && <p className="mt-2 text-xs text-danger-600">{erro}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setAberto(false)} className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700">
              Cancelar
            </button>
            <button
              type="button"
              disabled={enviando}
              onClick={confirmar}
              className={`rounded-md px-3 py-1 text-xs font-semibold text-white disabled:opacity-50 ${recebido ? "bg-slate-500 hover:bg-slate-600" : "bg-success-600 hover:bg-success-700"}`}
            >
              {enviando ? "..." : recebido ? "Desfazer" : "Dar baixa"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
