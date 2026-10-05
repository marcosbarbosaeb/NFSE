import { CaixaBusca } from "../ui/CaixaBusca"

/** Código escolhido numa lista (05/10/2026), como no emissor nacional: as
 * opções são os códigos que já saíram nas notas da empresa, com a descrição
 * que a Receita devolveu. Dá pra digitar outro. */

export interface CodigoUsado {
  codigo: string
  descricao: string | null
  vezes: number
}

export function CampoCodigoUsado({
  label,
  valor,
  onChange,
  opcoes,
  formatar = (c) => c,
  hint,
  placeholder,
}: {
  label: string
  valor: string
  onChange: (codigo: string) => void
  opcoes: CodigoUsado[]
  /** Como o código aparece (ex.: máscara do NBS). */
  formatar?: (codigo: string) => string
  hint?: string
  placeholder?: string
}) {
  const limpo = valor.replace(/[^\dA-Za-z]/g, "")
  const lista = [
    { id: "", rotulo: "Nenhum (não informar)" },
    ...opcoes.map((o) => ({ id: o.codigo, rotulo: `${formatar(o.codigo)}${o.descricao ? ` - ${o.descricao}` : ""}` })),
    // Código já salvo que não está entre os usados nas notas.
    ...(limpo && !opcoes.some((o) => o.codigo === limpo) ? [{ id: limpo, rotulo: formatar(limpo) }] : []),
  ]
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <CaixaBusca
        valor={limpo}
        opcoes={lista}
        onEscolher={onChange}
        onCriar={(texto) => onChange(texto.replace(/[^\dA-Za-z]/g, ""))}
        rotuloCriar="Usar o código"
        placeholder={placeholder ?? "Escolha ou digite o código"}
        ariaLabel={label}
        quebrar
        className="[&_input]:py-2 [&_input]:pl-3"
      />
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </div>
  )
}
