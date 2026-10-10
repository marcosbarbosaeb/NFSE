import { Check, Search } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { api } from "../lib/api"

// Perfis no cadastro (2026.10.7, ideias/perfis-no-cadastro.md): "Como você
// costuma emitir suas notas?". É o JEITO de emitir, não a profissão: as
// profissões são só exemplos (lista em backend/app/data/perfis.json). Dá pra
// marcar mais de um — o primeiro é o principal. A busca destaca o cartão que
// tem a profissão; as buscas que não acham nada viram a lista de demanda da
// Gestão. Os ids ("lote", "avulso"...) nunca aparecem na tela.

export interface PerfilDaLista {
  id: string
  titulo: string
  profissoes: string[]
}

export interface EscolhaPerfil {
  perfis: string[]
  outro: string | null
  pulou: boolean
  buscas_sem_resultado: string[]
}

export const ESCOLHA_VAZIA: EscolhaPerfil = { perfis: [], outro: null, pulou: false, buscas_sem_resultado: [] }

let cache: Promise<PerfilDaLista[]> | null = null
function carregarPerfis(): Promise<PerfilDaLista[]> {
  cache ??= api
    .get<{ perfis: PerfilDaLista[] }>("/perfis")
    .then((r) => r.perfis)
    .catch(() => {
      cache = null
      return []
    })
  return cache
}

const semAcento = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim()
const VISIVEIS = 5

export function EscolherPerfil({ valor, onChange }: { valor: EscolhaPerfil; onChange: (v: EscolhaPerfil) => void }) {
  const [lista, setLista] = useState<PerfilDaLista[]>([])
  const [busca, setBusca] = useState("")
  const [abertos, setAbertos] = useState<Set<string>>(new Set())
  const [naoMeEncontrei, setNaoMeEncontrei] = useState(Boolean(valor.outro))
  const ultimaSemResultado = useRef<string | null>(null)

  useEffect(() => {
    let vivo = true
    carregarPerfis().then((p) => vivo && setLista(p))
    return () => {
      vivo = false
    }
  }, [])

  const alvo = semAcento(busca)
  const achados = useMemo(
    () =>
      alvo.length < 2
        ? new Set<string>()
        : new Set(lista.filter((p) => semAcento(p.titulo).includes(alvo) || p.profissoes.some((x) => semAcento(x).includes(alvo))).map((p) => p.id)),
    [alvo, lista],
  )

  // A busca que não achou nada é guardada (quando a pessoa para de digitar).
  useEffect(() => {
    if (alvo.length < 3 || achados.size > 0 || lista.length === 0) return
    const t = setTimeout(() => {
      const termo = busca.trim()
      if (termo && termo !== ultimaSemResultado.current && !valor.buscas_sem_resultado.includes(termo)) {
        ultimaSemResultado.current = termo
        onChange({ ...valor, buscas_sem_resultado: [...valor.buscas_sem_resultado, termo].slice(-10) })
      }
    }, 1200)
    return () => clearTimeout(t)
  }, [alvo, achados.size, lista.length, busca, valor, onChange])

  function alternar(id: string) {
    const ja = valor.perfis.includes(id)
    onChange({ ...valor, pulou: false, perfis: ja ? valor.perfis.filter((p) => p !== id) : [...valor.perfis, id] })
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="relative block">
        <span className="sr-only">Buscar pela sua profissão</span>
        <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={busca}
          onChange={(e) => setBusca(e.target.value.slice(0, 80))}
          placeholder="Busque pela sua profissão (ex.: fotógrafo)"
          className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 sm:text-sm"
        />
      </label>
      {alvo.length >= 2 && (
        <p className="text-xs text-slate-500 dark:text-slate-400" role="status" aria-live="polite">
          {achados.size > 0 ? "Destaquei onde a sua profissão aparece." : "Não achei essa profissão nos exemplos. Escolha o jeito mais parecido ou use “Não me encontrei”."}
        </p>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {lista.map((p) => {
          const ordem = valor.perfis.indexOf(p.id)
          const marcado = ordem >= 0
          const destaque = achados.has(p.id)
          const aberto = abertos.has(p.id)
          const mostrar = aberto ? p.profissoes : p.profissoes.slice(0, VISIVEIS)
          return (
            <li key={p.id}>
              <div
                className={`flex h-full flex-col rounded-xl border px-3 py-2.5 transition-colors ${
                  marcado
                    ? "border-primary-500 bg-primary-50 dark:border-primary-400 dark:bg-primary-900/30"
                    : destaque
                      ? "border-accent-400 bg-accent-50 dark:border-accent-500 dark:bg-accent-900/20"
                      : "border-slate-200 dark:border-slate-700"
                }`}
              >
                <button type="button" aria-pressed={marcado} onClick={() => alternar(p.id)} className="flex items-start justify-between gap-2 text-left">
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{p.titulo}</span>
                  <span
                    aria-hidden="true"
                    className={`flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold ${
                      marcado ? "border-primary-600 bg-primary-600 text-white" : "border-slate-300 dark:border-slate-600"
                    }`}
                  >
                    {marcado ? valor.perfis.length > 1 ? ordem + 1 : <Check size={12} /> : null}
                  </span>
                </button>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {mostrar.join(", ")}
                  {p.profissoes.length > VISIVEIS && (
                    <>
                      {" "}
                      <button
                        type="button"
                        onClick={() =>
                          setAbertos((a) => {
                            const n = new Set(a)
                            if (n.has(p.id)) n.delete(p.id)
                            else n.add(p.id)
                            return n
                          })
                        }
                        className="font-medium text-primary-700 underline dark:text-primary-300"
                      >
                        {aberto ? "menos" : "e outros"}
                      </button>
                    </>
                  )}
                </p>
                {marcado && valor.perfis.length > 1 && ordem === 0 && (
                  <span className="mt-1 text-[11px] font-medium text-primary-700 dark:text-primary-300">principal</span>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <div className="rounded-xl border border-slate-200 px-3 py-2.5 dark:border-slate-700">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
          <input
            type="checkbox"
            checked={naoMeEncontrei}
            onChange={(e) => {
              setNaoMeEncontrei(e.target.checked)
              if (!e.target.checked) onChange({ ...valor, outro: null })
            }}
            className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
          />
          Não me encontrei
        </label>
        {naoMeEncontrei && (
          <textarea
            value={valor.outro ?? ""}
            onChange={(e) => onChange({ ...valor, pulou: false, outro: e.target.value.slice(0, 300) || null })}
            rows={2}
            placeholder="Conte o que você faz"
            aria-label="Conte o que você faz"
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 sm:text-sm"
          />
        )}
      </div>
    </div>
  )
}

export function escolhaFeita(v: EscolhaPerfil): boolean {
  return v.perfis.length > 0 || Boolean(v.outro?.trim())
}
