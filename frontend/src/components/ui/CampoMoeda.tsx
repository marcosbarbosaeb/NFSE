import type { InputHTMLAttributes } from "react"
import { parseBRL } from "../../lib/format"

/** Campo de valor em reais (05/10/2026), um só pra todos os módulos: os
 * dígitos entram da direita pra esquerda, como em app de banco — digitar
 * 5162661 mostra "R$ 51.626,61". Acaba a dúvida entre ponto e vírgula (e o
 * valor cem vezes maior ou menor nas contas).
 *
 * `valor` é o texto que a tela já guardava; `saida` diz como ela quer
 * receber de volta: "ponto" → "51626.61" (pra `Number(valor)`), "br" →
 * "51.626,61" (pra `parseBRL(valor)`). Campo vazio devolve "". */

const MAX_DIGITOS = 13 // até R$ 99.999.999.999,99

export function formatarMoedaCampo(numero: number | null): string {
  if (numero == null || !Number.isFinite(numero)) return ""
  return numero.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  valor: string
  onChange: (valor: string) => void
  saida?: "ponto" | "br"
  /** Mostra "R$" dentro do campo (padrão). */
  cifrao?: boolean
}

const CLASSE_PADRAO =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function CampoMoeda({ valor, onChange, saida = "ponto", cifrao = true, className, placeholder, ...resto }: Props) {
  const numero = parseBRL(valor)
  const texto = numero == null ? "" : `${cifrao ? "R$ " : ""}${formatarMoedaCampo(numero)}`
  return (
    <input
      {...resto}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder={placeholder ?? (cifrao ? "R$ 0,00" : "0,00")}
      value={texto}
      className={className ?? CLASSE_PADRAO}
      onChange={(e) => {
        const digitos = e.target.value.replace(/\D/g, "").replace(/^0+/, "").slice(0, MAX_DIGITOS)
        if (!digitos) {
          onChange("")
          return
        }
        const novo = Number(digitos) / 100
        onChange(saida === "br" ? formatarMoedaCampo(novo) : novo.toFixed(2))
      }}
    />
  )
}

/** O mesmo campo com rótulo em cima (par do `Field`). */
export function MoedaField({ label, hint, ...props }: Props & { label: string; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <CampoMoeda {...props} />
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  )
}
