import { Search } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { api } from "../../lib/api"
import type { ServicoNacional } from "../../lib/types"

// Pedido do Marcos (28/09/2026): "coloque a relação de código com um
// pesquisar para a pessoa buscar o código e não criar códigos novos". A
// lista oficial (cTribNac, ~340 códigos) é carregada uma vez e filtrada
// aqui mesmo — por número ("1706", "17.06.01") ou por palavra
// ("publicidade"). Só dá pra escolher um item da lista; o backend também
// recusa código que não existe.

let cache: Promise<ServicoNacional[]> | null = null
function carregarLista(): Promise<ServicoNacional[]> {
  if (!cache) cache = api.get<ServicoNacional[]>("/servicos-nacionais?limite=400").catch((e) => {
    cache = null
    throw e
  })
  return cache
}

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

export function formatarCodigoServico(codigo: string): string {
  return codigo.length === 6 ? `${codigo.slice(0, 2)}.${codigo.slice(2, 4)}.${codigo.slice(4)}` : codigo
}

export function CampoServico({
  label,
  codigo,
  onChange,
  required,
  hint,
  destaques = [],
}: {
  label: string
  codigo: string
  onChange: (codigo: string) => void
  required?: boolean
  hint?: string
  /** Códigos sugeridos (já usados com este tomador / por você) — aparecem primeiro. */
  destaques?: string[]
}) {
  const [lista, setLista] = useState<ServicoNacional[]>([])
  const [texto, setTexto] = useState("")
  const [aberto, setAberto] = useState(false)
  const [destaque, setDestaque] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    carregarLista().then(setLista).catch(() => {})
  }, [])

  const selecionado = useMemo(() => lista.find((s) => s.codigo === codigo) ?? null, [lista, codigo])
  const rotuloSelecionado = selecionado ? `${formatarCodigoServico(selecionado.codigo)} — ${selecionado.descricao}` : ""

  // Código vindo de fora (edição, sugestão) -> mostra o rótulo.
  useEffect(() => {
    if (!aberto) setTexto(rotuloSelecionado)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rotuloSelecionado])

  useEffect(() => {
    inputRef.current?.setCustomValidity(required && !selecionado ? "Escolha um código da lista." : "")
  }, [selecionado, required])

  const opcoes = useMemo(() => {
    const termo = semAcento(texto === rotuloSelecionado ? "" : texto.trim())
    const digitos = termo.replace(/\D/g, "")
    const palavras = termo.replace(/[\d.]/g, " ").split(/\s+/).filter(Boolean)
    const filtrados = lista.filter((s) => {
      if (digitos && !s.codigo.includes(digitos)) return false
      const alvo = semAcento(`${s.descricao} ${s.grupo}`)
      return palavras.every((p) => alvo.includes(p))
    })
    const prioridade = (s: ServicoNacional) => {
      const i = destaques.indexOf(s.codigo)
      return i === -1 ? 999 : i
    }
    return [...filtrados].sort((a, b) => prioridade(a) - prioridade(b)).slice(0, 60)
  }, [lista, texto, rotuloSelecionado, destaques])

  function escolher(s: ServicoNacional) {
    onChange(s.codigo)
    setTexto(`${formatarCodigoServico(s.codigo)} — ${s.descricao}`)
    setAberto(false)
  }

  return (
    <label className="relative block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <div className="relative">
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          autoComplete="off"
          role="combobox"
          aria-expanded={aberto}
          placeholder="Busque por número ou palavra (ex.: publicidade)"
          value={texto}
          required={required}
          onChange={(e) => {
            setTexto(e.target.value)
            setAberto(true)
            setDestaque(0)
          }}
          onFocus={(e) => {
            setAberto(true)
            e.target.select()
          }}
          onBlur={() =>
            setTimeout(() => {
              setAberto(false)
              setTexto(rotuloSelecionado)
            }, 150)
          }
          onKeyDown={(e) => {
            if (!opcoes.length) return
            if (e.key === "ArrowDown") {
              e.preventDefault()
              setDestaque((d) => Math.min(d + 1, opcoes.length - 1))
            } else if (e.key === "ArrowUp") {
              e.preventDefault()
              setDestaque((d) => Math.max(d - 1, 0))
            } else if (e.key === "Enter" && aberto) {
              e.preventDefault()
              escolher(opcoes[destaque])
            }
          }}
          className="w-full truncate rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      {aberto && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          {opcoes.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-400">{lista.length ? "Nenhum código encontrado." : "Carregando a lista..."}</li>
          )}
          {opcoes.map((s, i) => (
            <li
              key={s.codigo}
              role="option"
              aria-selected={i === destaque}
              onMouseDown={(e) => {
                e.preventDefault()
                escolher(s)
              }}
              onMouseEnter={() => setDestaque(i)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                i === destaque ? "bg-primary-50 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200" : "text-slate-700 dark:text-slate-200"
              }`}
            >
              <span className="font-mono text-xs font-semibold text-primary-700 dark:text-primary-300">
                {formatarCodigoServico(s.codigo)}
              </span>
              {destaques.includes(s.codigo) && (
                <span className="ml-2 rounded bg-accent-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-accent-700 dark:bg-accent-900/40 dark:text-accent-200">
                  sugerido
                </span>
              )}
              <span className="mt-0.5 block line-clamp-2 leading-snug">{s.descricao}</span>
            </li>
          ))}
        </ul>
      )}
      {selecionado && !aberto && (
        <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">Grupo: {selecionado.grupo}</span>
      )}
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  )
}
