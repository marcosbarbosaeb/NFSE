import { MapPin } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { api } from "../../lib/api"
import type { Municipio } from "../../lib/types"

// Pedido do Marcos: "tire esse negócio de código IBGE, as pessoas nem sabem
// que existe isso". A pessoa busca a CIDADE pelo nome; o código de 7 dígitos
// que a nota fiscal exige continua existindo, só que guardado por trás
// (ver backend/app/services/municipios.py).
export function CampoCidade({
  label,
  codigo,
  onChange,
  required,
  hint,
}: {
  label: string
  codigo: string
  onChange: (codigo: string) => void
  required?: boolean
  hint?: string
}) {
  const [texto, setTexto] = useState("")
  const [opcoes, setOpcoes] = useState<Municipio[]>([])
  const [aberto, setAberto] = useState(false)
  const [destaque, setDestaque] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const rotuloAtual = useRef<string>("")

  // Código vindo de fora (edição, autopreenchimento pelo CNPJ) -> mostra o nome.
  useEffect(() => {
    if (!codigo) return
    if (rotuloAtual.current && texto === rotuloAtual.current) return
    let cancelado = false
    api
      .get<Municipio>(`/municipios/${codigo}`)
      .then((m) => {
        if (cancelado) return
        rotuloAtual.current = m.rotulo
        setTexto(m.rotulo)
      })
      .catch(() => {})
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codigo])

  // Busca enquanto digita (só quando o texto não é a cidade já escolhida).
  useEffect(() => {
    if (!aberto || texto.trim().length < 2 || texto === rotuloAtual.current) {
      setOpcoes([])
      return
    }
    const controlador = { cancelado: false }
    const t = setTimeout(() => {
      api
        .get<Municipio[]>(`/municipios?q=${encodeURIComponent(texto)}`)
        .then((lista) => {
          if (!controlador.cancelado) {
            setOpcoes(lista)
            setDestaque(0)
          }
        })
        .catch(() => {})
    }, 200)
    return () => {
      controlador.cancelado = true
      clearTimeout(t)
    }
  }, [texto, aberto])

  // Validação nativa do formulário: exige que uma cidade da lista tenha sido escolhida.
  useEffect(() => {
    inputRef.current?.setCustomValidity(required && !codigo ? "Escolha a cidade na lista." : "")
  }, [codigo, required])

  function escolher(m: Municipio) {
    rotuloAtual.current = m.rotulo
    setTexto(m.rotulo)
    setOpcoes([])
    setAberto(false)
    onChange(m.codigo)
  }

  return (
    <label className="relative block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <div className="relative">
        <MapPin size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          autoComplete="off"
          role="combobox"
          aria-expanded={aberto && opcoes.length > 0}
          placeholder="Digite o nome da cidade"
          value={texto}
          required={required}
          onChange={(e) => {
            setTexto(e.target.value)
            setAberto(true)
            if (codigo) onChange("")
            rotuloAtual.current = ""
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          onKeyDown={(e) => {
            if (!opcoes.length) return
            if (e.key === "ArrowDown") {
              e.preventDefault()
              setDestaque((d) => Math.min(d + 1, opcoes.length - 1))
            } else if (e.key === "ArrowUp") {
              e.preventDefault()
              setDestaque((d) => Math.max(d - 1, 0))
            } else if (e.key === "Enter") {
              e.preventDefault()
              escolher(opcoes[destaque])
            }
          }}
          className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      {aberto && opcoes.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          {opcoes.map((m, i) => (
            <li
              key={m.codigo}
              role="option"
              aria-selected={i === destaque}
              onMouseDown={(e) => {
                e.preventDefault()
                escolher(m)
              }}
              onMouseEnter={() => setDestaque(i)}
              className={`cursor-pointer px-3 py-1.5 text-sm ${
                i === destaque ? "bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300" : "text-slate-700 dark:text-slate-200"
              }`}
            >
              {m.nome} <span className="text-slate-400">/ {m.uf}</span>
            </li>
          ))}
        </ul>
      )}
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  )
}
