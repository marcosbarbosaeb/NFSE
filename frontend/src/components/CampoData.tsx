import { useId, useRef } from "react"
import { hojeLocal } from "../lib/datas"
import { formatCompetenciaLonga } from "../lib/format"

/** Campo "Data de competência" (29/09/2026): calendário nativo do navegador
 * (abre ao clicar) e atalho "Usar hoje". Mostra embaixo o mês que vira a
 * competência da nota. */
export function CampoData({
  label = "Data de competência",
  valor,
  onChange,
  hint,
  required,
  mostrarCompetencia = true,
}: {
  label?: string
  valor: string
  onChange: (valor: string) => void
  hint?: string
  required?: boolean
  mostrarCompetencia?: boolean
}) {
  const id = useId()
  const idHint = useId()
  const input = useRef<HTMLInputElement>(null)
  const hoje = hojeLocal()
  const valido = /^\d{4}-\d{2}-\d{2}$/.test(valor)

  // Clicar no campo já abre o calendário (o ícone nativo também abre);
  // digitar a data continua funcionando.
  function abrirCalendario() {
    const el = input.current
    if (!el) return
    try {
      el.showPicker?.()
    } catch {
      // showPicker pode não existir/ser bloqueado — o foco no campo já basta.
    }
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
        </label>
        {valor !== hoje && (
          <button
            type="button"
            onClick={() => onChange(hoje)}
            className="rounded px-1 text-xs font-medium text-primary-600 hover:underline dark:text-primary-300"
          >
            Usar hoje
          </button>
        )}
      </div>
      <input
        ref={input}
        id={id}
        type="date"
        required={required}
        value={valor}
        // Vazio enquanto a pessoa digita/apaga — quem usa cai em hoje ao enviar.
        onChange={(e) => onChange(e.target.value)}
        onClick={abrirCalendario}
        aria-describedby={idHint}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:[color-scheme:dark]"
      />
      <span id={idHint} className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
        {mostrarCompetencia && valido && (
          <>
            Competência: <strong className="font-medium text-slate-600 dark:text-slate-300">{formatCompetenciaLonga(valor.slice(0, 7))}</strong>
            {hint ? " · " : ""}
          </>
        )}
        {mostrarCompetencia && !valido && "Sem data, vale a de hoje. "}
        {hint}
      </span>
    </div>
  )
}
