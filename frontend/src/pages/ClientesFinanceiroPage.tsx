import { ArrowLeft, Check, Pencil, Plus, X } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL } from "../lib/format"
import { useModulos } from "../lib/modulos"

/** Clientes do financeiro (05/10/2026): de quem o dinheiro entra. Só o nome
 * — o cadastro fiscal (CNPJ, código de serviço) é do módulo de notas. Quem
 * tem os dois módulos vê aqui os mesmos clientes da tela Tomadores. */

interface Cliente {
  id: string
  nome: string
  ativo: boolean
  so_controle: boolean
  recebido: number
  recebimentos: number
  ultimo_recebimento: string | null
}

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

const dataBR = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—")

export function ClientesFinanceiroPage() {
  const { emissor } = useModulos()
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [clientes, setClientes] = useState<Cliente[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [novo, setNovo] = useState("")
  const [salvando, setSalvando] = useState(false)
  const [editando, setEditando] = useState<string | null>(null)
  const [nomeEditado, setNomeEditado] = useState("")

  function falhou(err: unknown) {
    setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
  }

  function carregar() {
    api.get<Cliente[]>(`/financeiro/clientes?ano=${ano}`).then(setClientes).catch(falhou)
  }

  useEffect(carregar, [ano]) // eslint-disable-line react-hooks/exhaustive-deps

  async function criar(e: FormEvent) {
    e.preventDefault()
    if (novo.trim().length < 2) return
    setErro(null)
    setSalvando(true)
    try {
      await api.post("/financeiro/clientes", { nome: novo })
      setNovo("")
      carregar()
    } catch (err) {
      falhou(err)
    } finally {
      setSalvando(false)
    }
  }

  async function atualizar(id: string, mudanca: { nome?: string; ativo?: boolean }) {
    setErro(null)
    try {
      await api.patch(`/financeiro/clientes/${id}`, mudanca)
      setEditando(null)
      carregar()
    } catch (err) {
      falhou(err)
    }
  }

  const total = (clientes ?? []).reduce((s, c) => s + c.recebido, 0)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/app/financeiro" className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-primary-600">
            <ArrowLeft size={14} /> Financeiro
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Clientes</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            De quem o dinheiro entra, e quanto cada um já pagou.
            {emissor && " São os mesmos da tela Tomadores — os dados da nota ficam lá."}
          </p>
        </div>
        <select
          aria-label="Ano"
          value={ano}
          onChange={(e) => setAno(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        >
          {ANOS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      <Card className="p-4">
        <form onSubmit={criar} className="flex flex-wrap items-center gap-2">
          <input
            value={novo}
            onChange={(e) => setNovo(e.target.value)}
            maxLength={60}
            placeholder="Nome do cliente novo"
            aria-label="Nome do cliente novo"
            className="min-w-[220px] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          />
          <Button type="submit" variant="accent" disabled={salvando || novo.trim().length < 2}>
            <Plus size={16} /> Adicionar cliente
          </Button>
        </form>
      </Card>

      <Card className="overflow-hidden">
        {clientes === null ? (
          <p className="py-10 text-center text-sm text-slate-400">Carregando...</p>
        ) : clientes.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400">
            Nenhum cliente ainda. Adicione acima — ou crie na hora, ao registrar um recebimento ou importar o extrato.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:border-slate-700">
                  <th className="px-4 py-3">Cliente</th>
                  <th className="px-4 py-3 text-right">Recebido em {ano}</th>
                  <th className="px-4 py-3 text-right">Recebimentos</th>
                  <th className="px-4 py-3">Último</th>
                  <th className="px-4 py-3 text-right">Ativo</th>
                </tr>
              </thead>
              <tbody>
                {clientes.map((c) => (
                  <tr key={c.id} className={`border-b border-slate-100 last:border-0 dark:border-slate-700/60 ${c.ativo ? "" : "opacity-60"}`}>
                    <td className="px-4 py-2.5">
                      {editando === c.id ? (
                        <form
                          className="flex items-center gap-1.5"
                          onSubmit={(e) => {
                            e.preventDefault()
                            atualizar(c.id, { nome: nomeEditado })
                          }}
                        >
                          <input
                            autoFocus
                            value={nomeEditado}
                            onChange={(e) => setNomeEditado(e.target.value)}
                            maxLength={60}
                            aria-label={`Novo nome de ${c.nome}`}
                            className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                          />
                          <button type="submit" aria-label="Salvar nome" className="rounded p-1.5 text-success-600 hover:bg-slate-100 dark:hover:bg-slate-700">
                            <Check size={16} />
                          </button>
                          <button
                            type="button"
                            aria-label="Cancelar"
                            onClick={() => setEditando(null)}
                            className="rounded p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700"
                          >
                            <X size={16} />
                          </button>
                        </form>
                      ) : (
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-800 dark:text-slate-200">{c.nome}</span>
                          {emissor &&
                            (c.so_controle ? (
                              <Badge variant="neutral">sem nota</Badge>
                            ) : (
                              <Link to={`/app/tomadores/${c.id}`} className="text-xs font-medium text-primary-600 hover:underline">
                                dados da nota →
                              </Link>
                            ))}
                          <button
                            type="button"
                            aria-label={`Renomear ${c.nome}`}
                            title="Renomear"
                            onClick={() => {
                              setEditando(c.id)
                              setNomeEditado(c.nome)
                            }}
                            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
                          >
                            <Pencil size={14} />
                          </button>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-800 dark:text-slate-200">{c.recebido ? formatBRL(c.recebido) : "—"}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-500 dark:text-slate-400">{c.recebimentos || "—"}</td>
                    <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{dataBR(c.ultimo_recebimento)}</td>
                    <td className="px-4 py-2.5 text-right">
                      <input
                        type="checkbox"
                        checked={c.ativo}
                        onChange={(e) => atualizar(c.id, { ativo: e.target.checked })}
                        aria-label={`${c.nome} ativo`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-slate-200 text-sm font-semibold dark:border-slate-700">
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{clientes.length} clientes</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-900 dark:text-slate-100">{formatBRL(total)}</td>
                  <td colSpan={3} />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
