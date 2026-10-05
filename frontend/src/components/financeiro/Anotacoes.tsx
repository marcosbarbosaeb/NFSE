import { Check, Pencil, Trash2 } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "../../lib/api"
import { mensagemErro } from "../../lib/financeiro"
import { Card } from "../ui/Card"

/** Anotações (05/10/2026): abas/notas que a pessoa cria no Financeiro pra
 * deixar registrado o que quiser — "controle de recarga de telefone", um
 * lembrete, uma lista. Cada uma vira um card (dá pra recolher e reordenar
 * em "Editar disposição", como os outros). O texto salva sozinho. */

export interface Anotacao {
  id: string
  titulo: string
  texto: string
  atualizado_em?: string
}

export function useAnotacoes(ligado: boolean) {
  const [anotacoes, setAnotacoes] = useState<Anotacao[]>([])
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (!ligado) return
    api.get<Anotacao[]>("/financeiro/anotacoes").then(setAnotacoes).catch(() => undefined)
  }, [ligado])

  const criar = useCallback(async (titulo: string) => {
    setErro(null)
    try {
      const nova = await api.post<Anotacao>("/financeiro/anotacoes", { titulo })
      setAnotacoes((a) => [...a, nova])
      return nova
    } catch (err) {
      setErro(mensagemErro(err))
      return null
    }
  }, [])

  const atualizar = useCallback((id: string, mudanca: Partial<Anotacao>) => {
    setAnotacoes((a) => a.map((n) => (n.id === id ? { ...n, ...mudanca } : n)))
  }, [])

  const apagar = useCallback(async (id: string) => {
    setErro(null)
    try {
      await api.delete(`/financeiro/anotacoes/${id}`)
      setAnotacoes((a) => a.filter((n) => n.id !== id))
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }, [])

  return { anotacoes, erro, criar, atualizar, apagar }
}

export function AnotacaoCard({
  nota,
  onMudou,
  onApagar,
  nova = false,
}: {
  /** Acabou de ser criada: já abre pedindo o nome. */
  nova?: boolean
  nota: Anotacao
  onMudou: (mudanca: Partial<Anotacao>) => void
  onApagar: () => void
}) {
  const [texto, setTexto] = useState(nota.texto)
  const [titulo, setTitulo] = useState(nota.titulo)
  const [renomeando, setRenomeando] = useState(nova)
  const [estado, setEstado] = useState<"salvo" | "salvando" | "erro">("salvo")
  const espera = useRef<number | undefined>(undefined)

  function salvarTexto(valor: string) {
    setTexto(valor)
    setEstado("salvando")
    window.clearTimeout(espera.current)
    espera.current = window.setTimeout(() => {
      api
        .patch<Anotacao>(`/financeiro/anotacoes/${nota.id}`, { texto: valor })
        .then(() => {
          setEstado("salvo")
          onMudou({ texto: valor })
        })
        .catch(() => setEstado("erro"))
    }, 700)
  }

  async function salvarTitulo() {
    const novo = titulo.trim()
    setRenomeando(false)
    if (!novo || novo === nota.titulo) {
      setTitulo(nota.titulo)
      return
    }
    try {
      await api.patch(`/financeiro/anotacoes/${nota.id}`, { titulo: novo })
      onMudou({ titulo: novo })
    } catch {
      setTitulo(nota.titulo)
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2">
        {renomeando ? (
          <form
            className="flex min-w-0 flex-1 items-center gap-1.5"
            onSubmit={(e) => {
              e.preventDefault()
              void salvarTitulo()
            }}
          >
            <input
              autoFocus
              value={titulo}
              maxLength={80}
              onChange={(e) => setTitulo(e.target.value)}
              onBlur={() => void salvarTitulo()}
              aria-label="Nome da anotação"
              className="w-full max-w-sm rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            <button type="submit" aria-label="Salvar nome" className="rounded p-1.5 text-success-600 hover:bg-slate-100 dark:hover:bg-slate-700">
              <Check size={15} />
            </button>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setRenomeando(true)}
            title="Mudar o nome"
            className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs font-medium text-slate-400 hover:text-primary-600 dark:text-slate-500"
          >
            <Pencil size={13} /> mudar o nome
          </button>
        )}
        <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500" aria-live="polite">
          {estado === "salvando" ? "salvando..." : estado === "erro" ? "não salvou — tente de novo" : "salvo"}
        </span>
        <button
          type="button"
          onClick={() => {
            if (window.confirm(`Apagar a anotação "${nota.titulo}"? O texto dela se perde.`)) onApagar()
          }}
          aria-label={`Apagar a anotação ${nota.titulo}`}
          title="Apagar"
          className="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <textarea
        value={texto}
        onChange={(e) => salvarTexto(e.target.value)}
        rows={Math.min(14, Math.max(4, texto.split("\n").length + 1))}
        maxLength={20000}
        placeholder="Escreva o que quiser deixar registrado aqui..."
        aria-label={`Texto da anotação ${nota.titulo}`}
        className="w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-800 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
    </Card>
  )
}
