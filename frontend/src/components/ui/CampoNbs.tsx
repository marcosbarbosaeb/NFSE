import { Search, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { api } from "../../lib/api"
import type { ItemNbs } from "../../lib/types"

// "No cadastro dos tomadores, conseguiríamos deixar as NBS pesquisáveis?"
// (06/10/2026). Mesmo jeito do Código do serviço (CampoServico): a tabela
// oficial (NBS 2.0, ~900 códigos) é carregada uma vez e filtrada aqui — por
// número ("1.1406", "114061") ou por palavra ("publicidade"). A lista ajuda,
// não trava: o campo é opcional e aceita um código de 9 dígitos que não
// esteja nela (a tabela oficial muda; quem valida é a prefeitura).

let cache: Promise<ItemNbs[]> | null = null
function carregarLista(): Promise<ItemNbs[]> {
  if (!cache)
    cache = api.get<ItemNbs[]>("/nbs").catch((e) => {
      cache = null
      throw e
    })
  return cache
}

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

const soDigitos = (v: string) => v.replace(/\D/g, "")

/** 114061100 -> 1.1406.11.00 */
export function formatarNbs(valor: string): string {
  const d = soDigitos(valor).slice(0, 9)
  return [d.slice(0, 1), d.slice(1, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(".")
}

export function CampoNbs({
  label,
  valor,
  onChange,
  usados = [],
  hint,
}: {
  label: string
  /** Código com ou sem pontos ("" = nenhum). */
  valor: string
  /** Devolve o código já com os pontos (1.1406.11.00) ou "". */
  onChange: (codigo: string) => void
  /** Códigos que já saíram nas suas notas com este serviço — aparecem primeiro. */
  usados?: string[]
  hint?: string
}) {
  const [lista, setLista] = useState<ItemNbs[]>([])
  const [texto, setTexto] = useState("")
  const [aberto, setAberto] = useState(false)
  const [destaque, setDestaque] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    carregarLista().then(setLista).catch(() => {})
  }, [])

  const codigo = soDigitos(valor)
  const selecionado = useMemo(() => lista.find((n) => n.codigo === codigo) ?? null, [lista, codigo])
  const rotuloSelecionado = selecionado ? `${selecionado.formatado} — ${selecionado.descricao}` : codigo ? formatarNbs(codigo) : ""
  const usadosDigitos = useMemo(() => usados.map(soDigitos), [usados])

  // Código vindo de fora (edição, sugestão) -> mostra o rótulo.
  useEffect(() => {
    if (!aberto) setTexto(rotuloSelecionado)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rotuloSelecionado])

  const digitados = soDigitos(texto === rotuloSelecionado ? "" : texto)
  const opcoes = useMemo(() => {
    const termo = semAcento(texto === rotuloSelecionado ? "" : texto.trim())
    const digitos = soDigitos(termo)
    const palavras = termo.replace(/[\d.]/g, " ").split(/\s+/).filter(Boolean)
    const filtrados = lista.filter((n) => {
      if (digitos && !n.codigo.includes(digitos)) return false
      const alvo = semAcento(`${n.descricao} ${n.grupo}`)
      return palavras.every((p) => alvo.includes(p))
    })
    const prioridade = (n: ItemNbs) => {
      const i = usadosDigitos.indexOf(n.codigo)
      if (i !== -1) return i
      return digitos && n.codigo.startsWith(digitos) ? 500 : 999
    }
    return [...filtrados].sort((a, b) => prioridade(a) - prioridade(b)).slice(0, 60)
  }, [lista, texto, rotuloSelecionado, usadosDigitos])
  // Digitou os 9 dígitos de um código que a lista não tem: dá pra usar mesmo assim.
  const foraDaLista = digitados.length === 9 && lista.length > 0 && !lista.some((n) => n.codigo === digitados)

  function escolher(n: ItemNbs) {
    onChange(n.formatado)
    setTexto(`${n.formatado} — ${n.descricao}`)
    setAberto(false)
  }

  function limpar() {
    onChange("")
    setTexto("")
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
          onChange={(e) => {
            setTexto(e.target.value)
            setAberto(true)
            setDestaque(0)
            if (!e.target.value.trim()) onChange("")
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
            if (e.key === "Escape") {
              setAberto(false)
              return
            }
            if (e.key === "Enter" && aberto && opcoes.length === 0 && foraDaLista) {
              e.preventDefault()
              onChange(formatarNbs(digitados))
              setAberto(false)
              return
            }
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
          className="w-full truncate rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-9 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
        {codigo && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault()
              limpar()
            }}
            aria-label="Tirar o código NBS"
            title="Nenhum"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {aberto && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          {foraDaLista && (
            <li
              role="option"
              aria-selected={opcoes.length === 0}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange(formatarNbs(digitados))
                setAberto(false)
              }}
              className="cursor-pointer px-3 py-2 text-sm text-slate-700 hover:bg-primary-50 dark:text-slate-200 dark:hover:bg-primary-900/40"
            >
              Usar <span className="font-mono text-xs font-semibold">{formatarNbs(digitados)}</span> mesmo assim
              <span className="block text-xs text-slate-400">Esse código não está na tabela que eu tenho — confira antes.</span>
            </li>
          )}
          {opcoes.length === 0 && !foraDaLista && (
            <li className="px-3 py-2 text-sm text-slate-400">{lista.length ? "Nenhum código encontrado." : "Carregando a lista..."}</li>
          )}
          {opcoes.map((n, i) => (
            <li
              key={n.codigo}
              role="option"
              aria-selected={i === destaque}
              onMouseDown={(e) => {
                e.preventDefault()
                escolher(n)
              }}
              onMouseEnter={() => setDestaque(i)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                i === destaque ? "bg-primary-50 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200" : "text-slate-700 dark:text-slate-200"
              }`}
            >
              <span className="font-mono text-xs font-semibold text-primary-700 dark:text-primary-300">{n.formatado}</span>
              {usadosDigitos.includes(n.codigo) && (
                <span className="ml-2 rounded bg-accent-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-accent-700 dark:bg-accent-900/40 dark:text-accent-200">
                  já usado
                </span>
              )}
              <span className="mt-0.5 block line-clamp-2 leading-snug">{n.descricao}</span>
              {n.grupo && <span className="block truncate text-xs text-slate-400 dark:text-slate-500">{n.grupo}</span>}
            </li>
          ))}
        </ul>
      )}
      {codigo && !selecionado && lista.length > 0 && !aberto && (
        <span className="mt-1 block text-xs text-warning-700 dark:text-warning-300">Esse código não está na tabela NBS que eu tenho — confira.</span>
      )}
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  )
}
