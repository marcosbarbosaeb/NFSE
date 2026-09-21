import { FileUp, Plus, Search } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, formatBRL } from "../lib/format"
import type { EmissaoListaLinha, Emissao, GerarDpsRequest, ImportacaoCsvResultado, VinculoResumo } from "../lib/types"

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

const ESTADOS: Record<string, { label: string; variant: "success" | "warning" | "danger" | "neutral" }> = {
  rascunho: { label: "Rascunho", variant: "neutral" },
  montado: { label: "Emitida", variant: "success" },
  assinado: { label: "Assinada", variant: "success" },
  submetido: { label: "Submetida", variant: "success" },
  confirmado: { label: "Confirmada", variant: "success" },
  cancelada: { label: "Cancelada", variant: "neutral" },
  substituida: { label: "Substituída", variant: "neutral" },
  erro: { label: "Erro", variant: "danger" },
}

function badgeEstado(estado: string, label: string) {
  const info = ESTADOS[estado]
  return <Badge variant={info?.variant ?? "neutral"}>{label}</Badge>
}

export function NfsePage() {
  const [ano, setAno] = useState<string>(String(ANO_ATUAL))
  const [vinculoFiltro, setVinculoFiltro] = useState("")
  const [busca, setBusca] = useState("")
  const [emissoes, setEmissoes] = useState<EmissaoListaLinha[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modalNova, setModalNova] = useState(false)
  const [modalCsv, setModalCsv] = useState(false)

  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos)
  }, [])

  function recarregar() {
    setCarregando(true)
    setErro(null)
    const params = new URLSearchParams()
    if (ano) params.set("ano", ano)
    if (vinculoFiltro) params.set("vinculo_id", vinculoFiltro)
    api
      .get<EmissaoListaLinha[]>(`/dps?${params.toString()}`)
      .then(setEmissoes)
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => setCarregando(false))
  }

  useEffect(recarregar, [ano, vinculoFiltro])

  const filtradas = useMemo(() => {
    if (!emissoes) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return emissoes
    return emissoes.filter((e) => e.apelido.toLowerCase().includes(termo) || e.tomador_razao_social.toLowerCase().includes(termo))
  }, [emissoes, busca])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">NFS-e</h1>
          <p className="text-sm text-slate-500">Todas as notas emitidas, por competência.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setModalCsv(true)}>
            <FileUp size={16} /> Importar CSV
          </Button>
          <Button variant="accent" onClick={() => setModalNova(true)}>
            <Plus size={16} /> Nova emissão
          </Button>
        </div>
      </div>

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <select
            value={ano}
            onChange={(e) => setAno(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            {ANOS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select
            value={vinculoFiltro}
            onChange={(e) => setVinculoFiltro(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">Todos os fornecedores</option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido}
              </option>
            ))}
          </select>
          <div className="relative ml-auto w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar fornecedor..."
              className="w-full rounded-lg border border-slate-200 py-1.5 pl-9 pr-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>

        {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
        {carregando && <p className="py-8 text-center text-sm text-slate-400">Carregando...</p>}

        {!carregando && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 font-medium">Fornecedor</th>
                <th className="py-2 font-medium">Competência</th>
                <th className="py-2 font-medium">Valor</th>
                <th className="py-2 font-medium">Nº DPS</th>
                <th className="py-2 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((e) => (
                <tr key={e.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                  <td className="py-3">
                    <Link to={`/nfse/${e.id}`} className="font-medium text-primary-700 hover:underline">
                      {e.apelido}
                    </Link>
                    <p className="text-xs text-slate-400">{e.tomador_razao_social}</p>
                  </td>
                  <td className="py-3 text-slate-600">{e.competencia}</td>
                  <td className="py-3 text-slate-600">{formatBRL(e.valor)}</td>
                  <td className="py-3 text-slate-500">{e.n_dps ?? "—"}</td>
                  <td className="py-3">{badgeEstado(e.estado, e.estado_label)}</td>
                </tr>
              ))}
              {filtradas.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    Nenhuma nota encontrada.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>

      {modalNova && (
        <NovaEmissaoModal
          vinculos={vinculos}
          onClose={() => setModalNova(false)}
          onCriada={() => {
            setModalNova(false)
            recarregar()
          }}
        />
      )}
      {modalCsv && (
        <ImportarCsvModal
          onClose={() => setModalCsv(false)}
          onImportado={() => recarregar()}
        />
      )}
    </div>
  )
}

function NovaEmissaoModal({
  vinculos,
  onClose,
  onCriada,
}: {
  vinculos: VinculoResumo[]
  onClose: () => void
  onCriada: (emissao: Emissao) => void
}) {
  const [vinculoId, setVinculoId] = useState(vinculos[0]?.id ?? "")
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [valor, setValor] = useState("")
  const [ordem, setOrdem] = useState("")
  const [aliqSn, setAliqSn] = useState("")
  const [tpAmb, setTpAmb] = useState<"1" | "2">("2")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const vinculo = vinculos.find((v) => v.id === vinculoId)
  const precisaOrdem = vinculo?.template_descricao.includes("{ordem}") ?? false

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const payload: GerarDpsRequest = {
        vinculo_id: vinculoId,
        competencia,
        valor: Number(valor),
        ordem: ordem || null,
        aliq_sn: aliqSn ? Number(aliqSn) : null,
        tpAmb,
      }
      const criada = await api.post<Emissao>("/dps", payload)
      onCriada(criada)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Nova emissão" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        <FieldWrap label="Fornecedor">
          <select
            required
            value={vinculoId}
            onChange={(e) => setVinculoId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="" disabled>
              Selecione...
            </option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido} — {v.tomador_razao_social}
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
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </FieldWrap>
          <Field
            label="Valor (R$)"
            required
            type="number"
            step="0.01"
            min="0.01"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </div>

        {precisaOrdem && (
          <Field
            label="Número da ordem de pagamento"
            required
            value={ordem}
            onChange={(e) => setOrdem(e.target.value)}
            hint="Esse fornecedor usa {ordem} na descrição do serviço — obrigatório."
          />
        )}

        <Field
          label="Alíquota do Simples Nacional (%)"
          type="number"
          step="0.01"
          min="0"
          value={aliqSn}
          onChange={(e) => setAliqSn(e.target.value)}
          hint="Opcional."
        />

        <FieldWrap label="Ambiente">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTpAmb("2")}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                tpAmb === "2" ? "border-primary-500 bg-primary-50 text-primary-700" : "border-slate-300 text-slate-600"
              }`}
            >
              Homologação (teste)
            </button>
            <button
              type="button"
              onClick={() => setTpAmb("1")}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                tpAmb === "1" ? "border-danger-500 bg-danger-50 text-danger-700" : "border-slate-300 text-slate-600"
              }`}
            >
              Produção
            </button>
          </div>
          {tpAmb === "1" && (
            <p className="mt-2 rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700">
              Produção fica marcada na nota, mas este painel ainda não submete de verdade à prefeitura — a emissão real
              continua pelos scripts que o Marcos já usa.
            </p>
          )}
        </FieldWrap>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando || !vinculoId}>
            {enviando ? "Gerando..." : "Gerar nota"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function ImportarCsvModal({ onClose, onImportado }: { onClose: () => void; onImportado: () => void }) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [resultado, setResultado] = useState<ImportacaoCsvResultado | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setErro(null)
    setEnviando(true)
    try {
      const form = new FormData()
      form.append("arquivo", arquivo)
      const resp = await api.postForm<ImportacaoCsvResultado>("/dps/importar-csv", form)
      setResultado(resp)
      if (resp.sucesso > 0) onImportado()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Importar CSV" onClose={onClose} largura="max-w-xl">
      {!resultado ? (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
          <p className="text-sm text-slate-500">
            Colunas: <code className="rounded bg-slate-100 px-1">apelido, competencia, valor</code> — opcionalmente{" "}
            <code className="rounded bg-slate-100 px-1">ordem, aliq_sn</code>. O apelido precisa bater com um fornecedor
            já cadastrado.
          </p>
          <input
            type="file"
            accept=".csv,text/csv"
            required
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={enviando || !arquivo}>
              {enviando ? "Importando..." : "Importar"}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-slate-700">
            {resultado.sucesso} de {resultado.total} linha(s) importada(s) com sucesso
            {resultado.erro > 0 && `, ${resultado.erro} com erro`}.
          </p>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-100">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-400">
                <tr>
                  <th className="px-3 py-2 font-medium">Linha</th>
                  <th className="px-3 py-2 font-medium">Apelido</th>
                  <th className="px-3 py-2 font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody>
                {resultado.linhas.map((l) => (
                  <tr key={l.linha} className="border-t border-slate-100">
                    <td className="px-3 py-2 text-slate-500">{l.linha}</td>
                    <td className="px-3 py-2 text-slate-700">{l.apelido}</td>
                    <td className="px-3 py-2">
                      {l.ok ? <Badge variant="success">OK — nº DPS {l.n_dps}</Badge> : <Badge variant="danger">{l.mensagem}</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end">
            <Button variant="accent" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
