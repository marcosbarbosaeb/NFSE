import { CheckCircle2, Clock, FileText, FileUp, Plus, Search } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, formatBRL } from "../lib/format"
import type {
  EmissaoListaLinha,
  Emissao,
  GerarDpsRequest,
  ImportacaoCsvResultado,
  VerificarDuplicata,
  VinculoResumo,
} from "../lib/types"

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

// Marco 16 (item 3, pedido do Marcos: "é importante a pessoa confrontar
// notas emitidas com notas pagas") — mesmo badge do dashboard (só a
// competência corrente), aqui aplicado à lista completa.
function badgePagamento(recebido: boolean) {
  return recebido ? <Badge variant="success">Recebida</Badge> : <Badge variant="warning">Pendente</Badge>
}

export function NfsePage() {
  const [ano, setAno] = useState<string>(String(ANO_ATUAL))
  const [vinculoFiltro, setVinculoFiltro] = useState("")
  const [pagamentoFiltro, setPagamentoFiltro] = useState<"" | "recebido" | "pendente">("")
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

  // Filtro de pagamento aplicado no cliente (não no servidor, embora
  // /api/dps aceite ?pagamento=...): assim o resumo de confronto abaixo
  // continua mostrando emitidas x pagas lado a lado, mesmo com um dos dois
  // lados selecionado no filtro.
  const filtradas = useMemo(() => {
    if (!emissoes) return []
    const termo = busca.trim().toLowerCase()
    return emissoes.filter((e) => {
      if (pagamentoFiltro === "recebido" && !e.pagamento_recebido) return false
      if (pagamentoFiltro === "pendente" && e.pagamento_recebido) return false
      if (!termo) return true
      return e.apelido.toLowerCase().includes(termo) || e.tomador_razao_social.toLowerCase().includes(termo)
    })
  }, [emissoes, busca, pagamentoFiltro])

  // Confronto emitidas x pagas (item 3 do Marco 16) — sempre sobre TODAS as
  // emissões ativas do filtro de ano/fornecedor corrente, independente do
  // filtro de pagamento selecionado (senão o resumo ficaria só de um lado).
  const confronto = useMemo(() => {
    const ativas = (emissoes ?? []).filter((e) => e.estado !== "cancelada" && e.estado !== "substituida")
    const recebidas = ativas.filter((e) => e.pagamento_recebido)
    const pendentes = ativas.filter((e) => !e.pagamento_recebido)
    return {
      totalEmitidas: ativas.length,
      totalRecebidas: recebidas.length,
      totalPendentes: pendentes.length,
      valorRecebido: recebidas.reduce((soma, e) => soma + e.valor, 0),
      valorPendente: pendentes.reduce((soma, e) => soma + e.valor, 0),
    }
  }, [emissoes])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">NFS-e</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Todas as notas emitidas, por competência.</p>
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

      {/* Marco 16 (item 3) — confronto notas emitidas x notas pagas, pedido
          do Marcos. Sempre reflete ano/fornecedor selecionados, independente
          do filtro de pagamento abaixo (senão o resumo ficaria só de um lado). */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<FileText size={18} />}
          iconClassName="bg-primary-50 text-primary-600"
          label="Notas emitidas"
          value={confronto.totalEmitidas}
          sublabel={ano ? `em ${ano}` : "no período"}
        />
        <StatCard
          icon={<CheckCircle2 size={18} />}
          iconClassName="bg-success-50 text-success-600"
          label="Pagas"
          value={confronto.totalRecebidas}
          sublabel={formatBRL(confronto.valorRecebido)}
        />
        <StatCard
          icon={<Clock size={18} />}
          iconClassName="bg-warning-50 text-warning-600"
          label="Emitidas sem pagamento"
          value={confronto.totalPendentes}
          sublabel={formatBRL(confronto.valorPendente)}
          sublabelClassName="text-warning-600"
        />
      </div>

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
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
          <select
            value={vinculoFiltro}
            onChange={(e) => setVinculoFiltro(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Todos os fornecedores</option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido}
              </option>
            ))}
          </select>
          <select
            value={pagamentoFiltro}
            onChange={(e) => setPagamentoFiltro(e.target.value as "" | "recebido" | "pendente")}
            className="rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Pagamento: todos</option>
            <option value="recebido">Só pagas</option>
            <option value="pendente">Só pendentes</option>
          </select>
          <div className="relative ml-auto w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar fornecedor..."
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 py-1.5 pl-9 pr-3 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
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
                <th className="py-2 font-medium">Nº DPS</th>
                <th className="py-2 font-medium">Estado</th>
                <th className="py-2 font-medium">Pagamento</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((e) => (
                <tr key={e.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-700/50">
                  <td className="py-3">
                    <Link to={`/app/nfse/${e.id}`} className="font-medium text-primary-700 hover:underline">
                      {e.apelido}
                    </Link>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{e.tomador_razao_social}</p>
                  </td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{e.competencia}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(e.valor)}</td>
                  <td className="py-3 text-slate-500 dark:text-slate-400">{e.n_dps ?? "—"}</td>
                  <td className="py-3">{badgeEstado(e.estado, e.estado_label)}</td>
                  <td className="py-3">{badgePagamento(e.pagamento_recebido)}</td>
                </tr>
              ))}
              {filtradas.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400 dark:text-slate-500">
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
  const [duplicata, setDuplicata] = useState<VerificarDuplicata | null>(null)

  const vinculo = vinculos.find((v) => v.id === vinculoId)
  const precisaOrdem = vinculo?.template_descricao.includes("{ordem}") ?? false

  // Aviso proativo de nota duplicada (Marco 16, pedido do Marcos): assim que
  // fornecedor+competência ficam preenchidos, consulta se já existe uma
  // emissão ativa pra essa combinação — ANTES do usuário tentar gerar e
  // tomar um erro só depois de preencher tudo. Não bloqueia o envio (a
  // checagem de verdade continua no backend em POST /api/dps) — é só pra
  // avisar com antecedência.
  useEffect(() => {
    setDuplicata(null)
    if (!vinculoId || !competencia) return
    const controlador = new AbortController()
    const tempo = setTimeout(() => {
      api
        .get<VerificarDuplicata>(
          `/dps/verificar-duplicata?vinculo_id=${vinculoId}&competencia=${competencia}`,
        )
        .then((resp) => {
          if (!controlador.signal.aborted) setDuplicata(resp)
        })
        .catch(() => {
          // silencioso de propósito — é só um aviso a mais; se falhar, o
          // usuário ainda tem a checagem de verdade ao tentar submeter.
        })
    }, 300)
    return () => {
      controlador.abort()
      clearTimeout(tempo)
    }
  }, [vinculoId, competencia])

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
            className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
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
              className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
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

        {duplicata?.existe && (
          <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700">
            Já existe uma nota <strong>{ESTADOS[duplicata.estado ?? ""]?.label.toLowerCase() ?? duplicata.estado}</strong>{" "}
            pra {vinculo?.apelido} nessa competência. Gerar outra vai dar erro — cancele a existente primeiro se for
            substituí-la.
          </p>
        )}

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
                tpAmb === "2" ? "border-primary-500 bg-primary-50 text-primary-700" : "border-slate-300 text-slate-600 dark:text-slate-300"
              }`}
            >
              Homologação (teste)
            </button>
            <button
              type="button"
              onClick={() => setTpAmb("1")}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                tpAmb === "1" ? "border-danger-500 bg-danger-50 text-danger-700" : "border-slate-300 text-slate-600 dark:text-slate-300"
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
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Colunas: <code className="rounded bg-slate-100 dark:bg-slate-700 px-1">apelido, competencia, valor</code> — opcionalmente{" "}
            <code className="rounded bg-slate-100 dark:bg-slate-700 px-1">ordem, aliq_sn</code>. O apelido precisa bater com um fornecedor
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
          <p className="text-sm text-slate-700 dark:text-slate-300">
            {resultado.sucesso} de {resultado.total} linha(s) importada(s) com sucesso
            {resultado.erro > 0 && `, ${resultado.erro} com erro`}.
          </p>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-700/60">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-900/40 text-slate-400 dark:text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Linha</th>
                  <th className="px-3 py-2 font-medium">Apelido</th>
                  <th className="px-3 py-2 font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody>
                {resultado.linhas.map((l) => (
                  <tr key={l.linha} className="border-t border-slate-100 dark:border-slate-700/60">
                    <td className="px-3 py-2 text-slate-500 dark:text-slate-400">{l.linha}</td>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{l.apelido}</td>
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
