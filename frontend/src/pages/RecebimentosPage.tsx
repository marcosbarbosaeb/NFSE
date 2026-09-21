import { Plus } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, formatBRL } from "../lib/format"
import type { Pagamento, RegistrarPagamentoRequest, VinculoResumo } from "../lib/types"

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

export function RecebimentosPage() {
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [pagamentos, setPagamentos] = useState<Pagamento[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modalAberto, setModalAberto] = useState(false)

  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos)
  }, [])

  function recarregar() {
    setCarregando(true)
    setErro(null)
    api
      .get<Pagamento[]>(`/pagamentos?ano=${ano}`)
      .then(setPagamentos)
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => setCarregando(false))
  }

  useEffect(recarregar, [ano])

  const total = pagamentos?.reduce((soma, p) => soma + p.valor, 0) ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Recebimentos</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Pagamentos recebidos, por fornecedor e competência.</p>
        </div>
        <Button variant="accent" onClick={() => setModalAberto(true)}>
          <Plus size={16} /> Registrar recebimento
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
          {pagamentos && (
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
                <th className="py-2 font-medium">Fornecedor</th>
                <th className="py-2 font-medium">Competência</th>
                <th className="py-2 font-medium">Valor</th>
                <th className="py-2 font-medium">Data do recebimento</th>
              </tr>
            </thead>
            <tbody>
              {pagamentos?.map((p) => (
                <tr key={p.id} className="border-b border-slate-50 last:border-0">
                  <td className="py-3 font-medium text-slate-800 dark:text-slate-200">{p.apelido}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{p.competencia}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(p.valor)}</td>
                  <td className="py-3 text-slate-500 dark:text-slate-400">
                    {p.data_recebimento ? new Date(`${p.data_recebimento}T00:00:00`).toLocaleDateString("pt-BR") : <Badge variant="neutral">Não informada</Badge>}
                  </td>
                </tr>
              ))}
              {pagamentos?.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-400 dark:text-slate-500">
                    Nenhum recebimento neste ano ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>

      {modalAberto && (
        <RegistrarPagamentoModal
          vinculos={vinculos}
          onClose={() => setModalAberto(false)}
          onRegistrado={() => {
            setModalAberto(false)
            recarregar()
          }}
        />
      )}
    </div>
  )
}

function RegistrarPagamentoModal({
  vinculos,
  onClose,
  onRegistrado,
}: {
  vinculos: VinculoResumo[]
  onClose: () => void
  onRegistrado: () => void
}) {
  const [vinculoId, setVinculoId] = useState(vinculos[0]?.id ?? "")
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [valor, setValor] = useState("")
  const [dataRecebimento, setDataRecebimento] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const payload: RegistrarPagamentoRequest = {
        vinculo_id: vinculoId,
        competencia,
        valor: Number(valor),
        data_recebimento: dataRecebimento || null,
      }
      await api.post("/pagamentos", payload)
      onRegistrado()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Registrar recebimento" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        <FieldWrap label="Fornecedor">
          <select
            required
            value={vinculoId}
            onChange={(e) => setVinculoId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="" disabled>
              Selecione...
            </option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido}
              </option>
            ))}
          </select>
        </FieldWrap>

        <div className="grid grid-cols-2 gap-3">
          <FieldWrap label="Competência">
            <input
              required
              type="month"
              value={competencia}
              onChange={(e) => setCompetencia(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </FieldWrap>
          <Field label="Valor (R$)" required type="number" step="0.01" min="0.01" value={valor} onChange={(e) => setValor(e.target.value)} />
        </div>

        <Field
          label="Data do recebimento"
          type="date"
          value={dataRecebimento}
          onChange={(e) => setDataRecebimento(e.target.value)}
          hint="Opcional."
        />

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando || !vinculoId}>
            {enviando ? "Salvando..." : "Registrar"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
