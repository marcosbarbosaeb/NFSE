import { Check, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { api } from "../../lib/api"
import { classeCampo, classeCampoPequeno, mensagemErro } from "../../lib/financeiro"
import type { Rotina } from "../../lib/types"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"

// Itens da rotina de fechamento do mês (28/09/2026): "conferir extrato do
// Inter", "baixar a NF do Facebook"... — o quadro de X da planilha.

export function RotinasModal({ onClose, onMudou }: { onClose: () => void; onMudou: () => void }) {
  const [lista, setLista] = useState<Rotina[] | null>(null)
  const [novo, setNovo] = useState("")
  const [editando, setEditando] = useState<{ id: string; nome: string } | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  function carregar() {
    api
      .get<Rotina[]>("/financeiro/rotinas")
      .then(setLista)
      .catch((err) => {
        setErro(mensagemErro(err))
        setLista([])
      })
  }

  useEffect(carregar, [])

  async function executar(acao: () => Promise<unknown>) {
    setErro(null)
    setEnviando(true)
    try {
      await acao()
      carregar()
      onMudou()
      return true
    } catch (err) {
      setErro(mensagemErro(err))
      return false
    } finally {
      setEnviando(false)
    }
  }

  async function adicionar(e: FormEvent) {
    e.preventDefault()
    const nome = novo.trim()
    if (!nome) return
    if (await executar(() => api.post("/financeiro/rotinas", { nome }))) setNovo("")
  }

  async function renomear(e: FormEvent) {
    e.preventDefault()
    if (!editando || !editando.nome.trim()) return
    const { id, nome } = editando
    if (await executar(() => api.patch(`/financeiro/rotinas/${id}`, { nome: nome.trim() }))) setEditando(null)
  }

  const ativas = (lista ?? []).filter((r) => r.ativa)
  const inativas = (lista ?? []).filter((r) => !r.ativa)
  const botaoIcone =
    "rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"

  return (
    <Modal titulo="Itens da rotina do mês" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">O que você confere todo fechamento de mês. Cada item vira um check em “Rotina de fechamento”.</p>
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/40 dark:text-danger-300">{erro}</p>}

        <form onSubmit={adicionar} className="flex gap-2">
          <label className="min-w-0 flex-1">
            <span className="sr-only">Novo item da rotina</span>
            <input value={novo} onChange={(e) => setNovo(e.target.value)} maxLength={120} placeholder="Ex.: Conferir extrato do Inter" className={classeCampo} />
          </label>
          <Button type="submit" variant="outline" disabled={enviando || !novo.trim()}>
            <Plus size={16} /> Adicionar
          </Button>
        </form>

        {lista === null ? (
          <p className="py-4 text-center text-sm text-slate-400">Carregando...</p>
        ) : ativas.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">Nenhum item ainda.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {ativas.map((r) =>
              editando?.id === r.id ? (
                <li key={r.id} className="py-2">
                  <form onSubmit={renomear} className="flex items-center gap-2">
                    <label className="min-w-0 flex-1">
                      <span className="sr-only">Nome do item</span>
                      <input
                        autoFocus
                        value={editando.nome}
                        maxLength={120}
                        onChange={(e) => setEditando({ id: r.id, nome: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            e.stopPropagation()
                            setEditando(null)
                          }
                        }}
                        className={`${classeCampoPequeno} w-full`}
                      />
                    </label>
                    <button type="submit" aria-label="Salvar nome" className={botaoIcone} disabled={enviando}>
                      <Check size={15} />
                    </button>
                    <button type="button" aria-label="Cancelar" className={botaoIcone} onClick={() => setEditando(null)}>
                      <X size={15} />
                    </button>
                  </form>
                </li>
              ) : (
                <li key={r.id} className="flex items-center gap-2 py-2">
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-800 dark:text-slate-200">{r.nome}</span>
                  <button type="button" aria-label={`Renomear ${r.nome}`} className={botaoIcone} onClick={() => setEditando({ id: r.id, nome: r.nome })}>
                    <Pencil size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Desativar ${r.nome}`}
                    disabled={enviando}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 disabled:opacity-50 dark:hover:bg-danger-900/30"
                    onClick={() => executar(() => api.patch(`/financeiro/rotinas/${r.id}`, { ativa: false }))}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ),
            )}
          </ul>
        )}

        {inativas.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Desativados</p>
            <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {inativas.map((r) => (
                <li key={r.id} className="flex items-center gap-2 py-2">
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-400 line-through dark:text-slate-500">{r.nome}</span>
                  <button
                    type="button"
                    aria-label={`Reativar ${r.nome}`}
                    disabled={enviando}
                    className={botaoIcone}
                    onClick={() => executar(() => api.patch(`/financeiro/rotinas/${r.id}`, { ativa: true }))}
                  >
                    <RotateCcw size={15} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  )
}
