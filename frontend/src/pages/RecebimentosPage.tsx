import { FileUp, Plus } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, formatBRL } from "../lib/format"
import type {
  ConfirmarExtratoResultado,
  ExtratoExtraido,
  ItemConfirmarExtrato,
  Pagamento,
  RegistrarPagamentoRequest,
  TransacaoExtraida,
  VinculoResumo,
} from "../lib/types"

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

export function RecebimentosPage() {
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [pagamentos, setPagamentos] = useState<Pagamento[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modalAberto, setModalAberto] = useState(false)
  const [modalExtratoAberto, setModalExtratoAberto] = useState(false)

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
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setModalExtratoAberto(true)}>
            <FileUp size={16} /> Importar extrato (PDF)
          </Button>
          <Button variant="accent" onClick={() => setModalAberto(true)}>
            <Plus size={16} /> Registrar recebimento
          </Button>
        </div>
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

      {modalExtratoAberto && (
        <ImportarExtratoModal
          vinculos={vinculos}
          onClose={() => setModalExtratoAberto(false)}
          onImportado={() => {
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

interface LinhaRevisao {
  linha: number
  incluir: boolean
  descricao: string
  credito: boolean
  vinculoId: string
  competencia: string
  valor: string
  dataRecebimento: string
}

/** Chute de vínculo a partir da descrição da transação (substring
 * case-insensitive contra o apelido do fornecedor) — só pré-preenche
 * quando existe exatamente UM candidato; a pessoa sempre pode trocar na
 * revisão (ver docstring de app/services/extrato_pdf.py: a extração é
 * heurística, nunca decide sozinha o que vira pagamento de verdade). */
function chutarVinculo(descricao: string, vinculos: VinculoResumo[]): string {
  const alvo = descricao.toLowerCase()
  const candidatos = vinculos.filter((v) => alvo.includes(v.apelido.toLowerCase()))
  return candidatos.length === 1 ? candidatos[0].id : ""
}

function ImportarExtratoModal({
  vinculos,
  onClose,
  onImportado,
}: {
  vinculos: VinculoResumo[]
  onClose: () => void
  onImportado: () => void
}) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [extraindo, setExtraindo] = useState(false)
  const [erroExtracao, setErroExtracao] = useState<string | null>(null)
  const [linhas, setLinhas] = useState<LinhaRevisao[] | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<ConfirmarExtratoResultado | null>(null)

  async function extrair(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setErroExtracao(null)
    setExtraindo(true)
    try {
      const form = new FormData()
      form.append("arquivo", arquivo)
      const resp = await api.postForm<ExtratoExtraido>("/recebimentos/extrato", form)
      setLinhas(
        resp.transacoes.map((t: TransacaoExtraida) => ({
          linha: t.linha,
          incluir: t.credito,
          descricao: t.descricao,
          credito: t.credito,
          vinculoId: chutarVinculo(t.descricao, vinculos),
          competencia: t.data ? t.data.slice(0, 7) : competenciaAtual(),
          valor: String(t.valor),
          dataRecebimento: t.data ?? "",
        })),
      )
    } catch (err) {
      setErroExtracao(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setExtraindo(false)
    }
  }

  function atualizarLinha(linha: number, mudancas: Partial<LinhaRevisao>) {
    setLinhas((atuais) => atuais?.map((l) => (l.linha === linha ? { ...l, ...mudancas } : l)) ?? null)
  }

  const selecionadas = (linhas ?? []).filter((l) => l.incluir)
  const prontasParaConfirmar = selecionadas.length > 0 && selecionadas.every((l) => l.vinculoId && l.competencia && Number(l.valor) > 0)

  async function confirmar() {
    if (!linhas) return
    setEnviando(true)
    setErroExtracao(null)
    try {
      const itens: ItemConfirmarExtrato[] = selecionadas.map((l) => ({
        vinculo_id: l.vinculoId,
        competencia: l.competencia,
        valor: Number(l.valor),
        data_recebimento: l.dataRecebimento || null,
      }))
      const resp = await api.post<ConfirmarExtratoResultado>("/recebimentos/extrato/confirmar", { itens })
      setResultado(resp)
      if (resp.sucesso > 0) onImportado()
    } catch (err) {
      setErroExtracao(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Importar extrato bancário (PDF)" onClose={onClose} largura="max-w-3xl">
      {!linhas && (
        <form onSubmit={extrair} className="flex flex-col gap-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Envie o PDF do extrato — a gente tenta reconhecer as transações automaticamente (data, descrição e valor) pra você
            revisar e casar com o fornecedor antes de registrar qualquer recebimento.
          </p>
          {erroExtracao && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroExtracao}</p>}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo PDF</span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              required
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={extraindo || !arquivo}>
              {extraindo ? "Lendo o PDF..." : "Extrair transações"}
            </Button>
          </div>
        </form>
      )}

      {linhas && !resultado && (
        <div className="flex flex-col gap-4">
          {linhas.length === 0 ? (
            <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700">
              Não encontramos nenhuma transação reconhecível neste PDF — ele pode ser uma imagem escaneada, ou usar um formato
              que a gente ainda não entende. Você pode registrar os recebimentos manualmente.
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Encontramos {linhas.length} transaç{linhas.length === 1 ? "ão" : "ões"}. Marque as que são recebimentos de
                verdade e escolha o fornecedor de cada uma antes de confirmar.
              </p>
              {erroExtracao && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroExtracao}</p>}
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-700/60">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-white dark:bg-slate-800">
                    <tr className="border-b border-slate-100 dark:border-slate-700/60 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                      <th className="py-2 pl-3 font-medium"></th>
                      <th className="py-2 font-medium">Descrição</th>
                      <th className="py-2 font-medium">Fornecedor</th>
                      <th className="py-2 font-medium">Competência</th>
                      <th className="py-2 pr-3 font-medium">Valor (R$)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linhas.map((l) => (
                      <tr key={l.linha} className="border-b border-slate-50 dark:border-slate-700/40 last:border-0 align-top">
                        <td className="py-2 pl-3">
                          <input type="checkbox" checked={l.incluir} onChange={(e) => atualizarLinha(l.linha, { incluir: e.target.checked })} />
                        </td>
                        <td className="max-w-[220px] py-2 pr-2 text-slate-700 dark:text-slate-300">
                          <span className="line-clamp-2">{l.descricao}</span>
                          {!l.credito && <Badge variant="neutral">Débito</Badge>}
                        </td>
                        <td className="py-2 pr-2">
                          <select
                            value={l.vinculoId}
                            onChange={(e) => atualizarLinha(l.linha, { vinculoId: e.target.value })}
                            disabled={!l.incluir}
                            className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm text-slate-900 dark:text-slate-100 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                          >
                            <option value="">Selecione...</option>
                            {vinculos.map((v) => (
                              <option key={v.id} value={v.id}>
                                {v.apelido}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="month"
                            value={l.competencia}
                            onChange={(e) => atualizarLinha(l.linha, { competencia: e.target.value })}
                            disabled={!l.incluir}
                            className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm text-slate-900 dark:text-slate-100 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                          />
                        </td>
                        <td className="py-2 pr-3">
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            value={l.valor}
                            onChange={(e) => atualizarLinha(l.linha, { valor: e.target.value })}
                            disabled={!l.incluir}
                            className="w-24 rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm text-slate-900 dark:text-slate-100 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            {linhas.length > 0 && (
              <Button type="button" variant="accent" disabled={enviando || !prontasParaConfirmar} onClick={confirmar}>
                {enviando ? "Importando..." : `Confirmar importação (${selecionadas.length})`}
              </Button>
            )}
          </div>
        </div>
      )}

      {resultado && (
        <div className="flex flex-col gap-4">
          <p className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">
            {resultado.sucesso} de {resultado.total} recebimento{resultado.total === 1 ? "" : "s"} importado
            {resultado.sucesso === 1 ? "" : "s"} com sucesso.
          </p>
          {resultado.erro > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-danger-700">
              {resultado.itens
                .filter((i) => !i.ok)
                .map((i) => (
                  <li key={i.indice} className="rounded-lg bg-danger-50 px-3 py-2">
                    Linha {i.indice + 1}: {i.mensagem}
                  </li>
                ))}
            </ul>
          )}
          <div className="flex justify-end pt-2">
            <Button type="button" variant="accent" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
