import { Plus } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, formatBRL } from "../lib/format"
import type { Despesa, RegistrarDespesaRequest } from "../lib/types"

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

export function DespesasPage() {
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [despesas, setDespesas] = useState<Despesa[] | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modalAberto, setModalAberto] = useState(false)

  function recarregar() {
    setCarregando(true)
    setErro(null)
    api
      .get<Despesa[]>(`/despesas?ano=${ano}`)
      .then(setDespesas)
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => setCarregando(false))
  }

  useEffect(recarregar, [ano])

  const total = despesas?.reduce((soma, d) => soma + d.valor, 0) ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Despesas</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Despesas por categoria (Pró-labore, INSS, Simples Nacional...).</p>
        </div>
        <Button variant="accent" onClick={() => setModalAberto(true)}>
          <Plus size={16} /> Registrar despesa
        </Button>
      </div>

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <select
            value={ano}
            onChange={(e) => setAno(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            {ANOS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          {despesas && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Total no ano: <span className="font-semibold text-slate-800 dark:text-slate-200">{formatBRL(total)}</span>
            </p>
          )}
        </div>

        {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
        {carregando && <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

        {!carregando && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700/60 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                <th className="py-2 font-medium">Categoria</th>
                <th className="py-2 font-medium">Competência</th>
                <th className="py-2 font-medium">Valor</th>
              </tr>
            </thead>
            <tbody>
              {despesas?.map((d) => (
                <tr key={d.id} className="border-b border-slate-50 last:border-0">
                  <td className="py-3 font-medium text-slate-800 dark:text-slate-200">{d.categoria}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{d.competencia}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(d.valor)}</td>
                </tr>
              ))}
              {despesas?.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-slate-400 dark:text-slate-500">
                    Nenhuma despesa neste ano ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>

      {modalAberto && (
        <RegistrarDespesaModal
          onClose={() => setModalAberto(false)}
          onRegistrada={() => {
            setModalAberto(false)
            recarregar()
          }}
        />
      )}
    </div>
  )
}

function RegistrarDespesaModal({ onClose, onRegistrada }: { onClose: () => void; onRegistrada: () => void }) {
  const [categoria, setCategoria] = useState("")
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [valor, setValor] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const payload: RegistrarDespesaRequest = { categoria, competencia, valor: Number(valor) }
      await api.post("/despesas", payload)
      onRegistrada()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Registrar despesa" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        <Field
          label="Categoria"
          required
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          placeholder='Ex.: "Pró-labore", "INSS", "Simples Nacional"'
        />

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Competência</span>
            <input
              required
              type="month"
              value={competencia}
              onChange={(e) => setCompetencia(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <Field label="Valor (R$)" required type="number" step="0.01" min="0.01" value={valor} onChange={(e) => setValor(e.target.value)} />
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando}>
            {enviando ? "Salvando..." : "Registrar"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
