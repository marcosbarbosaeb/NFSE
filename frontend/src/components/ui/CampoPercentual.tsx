import { Field } from "./Field"

// Campo de percentual no formato brasileiro "xx,xx" com máscara que preenche
// da direita pra esquerda (igual campo de valor em app de banco): digitar
// 6, 0, 0 mostra 0,06 → 0,60 → 6,00. Pedido do Marcos: quem digita alíquota
// pensa em "6,00", não em "600" nem em "6.00".

const MAX_DIGITOS = 5 // até 100,00

export function formatarPercentual(valor: number | null): string {
  if (valor == null || Number.isNaN(valor)) return ""
  return valor.toFixed(2).replace(".", ",")
}

export function CampoPercentual({
  label,
  valor,
  onChange,
  hint,
  required,
  id,
}: {
  label: string
  valor: number | null
  onChange: (valor: number | null) => void
  hint?: string
  required?: boolean
  id?: string
}) {
  return (
    <Field
      id={id}
      label={label}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder="0,00"
      required={required}
      value={formatarPercentual(valor)}
      hint={hint}
      onChange={(e) => {
        const digitos = e.target.value.replace(/\D/g, "").replace(/^0+/, "").slice(0, MAX_DIGITOS)
        if (!digitos) {
          onChange(null)
          return
        }
        const numero = Number(digitos) / 100
        onChange(numero > 100 ? 100 : numero)
      }}
    />
  )
}
