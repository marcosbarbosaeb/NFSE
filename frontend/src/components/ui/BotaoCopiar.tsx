import { Check, Copy } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Button } from "./Button"

/** Copia um texto e mostra "Copiado!" por 2 segundos. Se o navegador não
 * deixar copiar (http, permissão negada), avisa em vez de fingir que copiou. */
export function BotaoCopiar({
  texto,
  rotulo,
  variant = "outline",
  className = "",
}: {
  texto: string
  rotulo: string
  variant?: "primary" | "accent" | "outline" | "ghost"
  className?: string
}) {
  const [estado, setEstado] = useState<"parado" | "copiado" | "falhou">("parado")
  const relogio = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(relogio.current), [])

  async function copiar() {
    let ok = true
    try {
      await navigator.clipboard.writeText(texto)
    } catch {
      ok = false
    }
    setEstado(ok ? "copiado" : "falhou")
    window.clearTimeout(relogio.current)
    relogio.current = window.setTimeout(() => setEstado("parado"), ok ? 2000 : 4000)
  }

  return (
    <Button type="button" variant={variant} className={className} onClick={copiar}>
      {estado === "copiado" ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
      <span aria-live="polite">
        {estado === "copiado" ? "Copiado!" : estado === "falhou" ? "Não deu pra copiar" : rotulo}
      </span>
    </Button>
  )
}
