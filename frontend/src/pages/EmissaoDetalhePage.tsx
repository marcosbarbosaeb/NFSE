import { CaixaBusca } from "../components/ui/CaixaBusca"
import {
  ArrowLeftRight,
  Trash2,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Copy,
  Download,
  FileDown,
  Link as LinkIcon,
  MessageSquareText,
  PenLine,
  Send,
  XCircle,
} from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import type { NotaParaAcoes } from "../components/AcoesNota"
import { Conferencia } from "../components/Conferencia"
import { EnvioNota } from "../components/EnvioNota"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL } from "../lib/format"
import type { CanalEnvio, ConferenciaNota, Emissao, Envio, NotaVisual, OpcoesEnvio, PontoConferencia, PreviaEmail, ProximaNota, VinculoResumo } from "../lib/types"

// Marco 16, item 7 — motivos de cancelamento aceitos pela Sefin (mesmo
// vocabulário de app/fiscal/eventos.MOTIVOS_CANCELAMENTO no backend).
const MOTIVOS_CANCELAMENTO: { value: string; label: string }[] = [
  { value: "1", label: "Erro na emissão" },
  { value: "2", label: "Serviço não prestado" },
  { value: "9", label: "Outros" },
]

const CANAIS: { value: CanalEnvio; label: string }[] = [
  { value: "download", label: "Baixar XML" },
  { value: "mensagem_pronta", label: "Mensagem pronta" },
  { value: "email", label: "E-mail" },
  { value: "email_geral", label: "E-mail geral (contador)" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "direto_fornecedor", label: "Marcada como enviada" },
]

function badgeStatusEnvio(status: string) {
  if (status === "enviado") return <Badge variant="success">Enviado</Badge>
  if (status === "falha") return <Badge variant="danger">Falha</Badge>
  return <Badge variant="warning">Pendente</Badge>
}

export function EmissaoDetalhePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [nota, setNota] = useState<NotaVisual | null>(null)
  const [envios, setEnvios] = useState<Envio[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [processando, setProcessando] = useState(false)
  const [mensagemPronta, setMensagemPronta] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)

  // Marco 16, item 7 — submeter/cancelar de verdade na Sefin. As duas são
  // ações irreversíveis com uma chamada de rede real por trás (ao
  // contrário de assinar, que não sai da máquina) — por isso passam por
  // um modal de confirmação em vez de agir no clique direto do botão
  // (mesmo padrão que o resto do painel já usa pra evitar window.confirm:
  // ver Modal.tsx).
  const [modalSubmeter, setModalSubmeter] = useState(false)
  const [modalCancelar, setModalCancelar] = useState(false)
  const [cmotivo, setCmotivo] = useState("1")
  const [xmotivo, setXmotivo] = useState("")
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  // Marco 17 — envio ao tomador. 29/09/2026: o painel (e-mail, WhatsApp,
  // portal, contador) é o mesmo do selo "Fornecedor" das listas — aqui a
  // pessoa entra na nota e configura o envio dela.
  const [opcoes, setOpcoes] = useState<OpcoesEnvio | null>(null)
  const [linkCopiado, setLinkCopiado] = useState(false)

  // 01/10/2026 — apagar nota que não saiu (ex.: teste) e mudar o tomador de
  // nota importada do Emissor Nacional (AWIN x AWIN Rchlo, mesmo CNPJ).
  const [dados, setDados] = useState<Emissao | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [modalApagar, setModalApagar] = useState(false)
  const [modalMover, setModalMover] = useState(false)
  const [destino, setDestino] = useState("")

  useEffect(() => {
    if (!id) return
    api.get<Emissao>(`/dps/${id}`).then(setDados).catch(() => setDados(null))
  }, [id])

  async function apagar() {
    if (!id) return
    setProcessando(true)
    setErroAcao(null)
    try {
      await api.delete(`/dps/${id}`)
      navigate("/app/nfse")
    } catch (err) {
      setErroAcao(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao apagar.")
    } finally {
      setProcessando(false)
    }
  }

  async function mover() {
    if (!id || !destino) return
    setProcessando(true)
    setErroAcao(null)
    try {
      setDados(await api.patch<Emissao>(`/dps/${id}/tomador`, { vinculo_id: destino }))
      setModalMover(false)
      carregar()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao mudar o tomador.")
    } finally {
      setProcessando(false)
    }
  }

  useEffect(() => {
    if (!id) return
    api.get<OpcoesEnvio>(`/dps/${id}/envio-opcoes`).then(setOpcoes).catch(() => setOpcoes(null))
  }, [id])

  // "Próximo passo" (05/10/2026): o que falta nesta nota e, quando ela
  // termina, qual é a próxima com passo pendente — sem voltar pra lista.
  const [proxima, setProxima] = useState<ProximaNota | null>(null)
  const [formas, setFormas] = useState<string[] | null>(null)
  function carregarProxima() {
    if (!id) return
    api.get<ProximaNota>(`/dps/${id}/proxima`).then(setProxima).catch(() => setProxima(null))
  }
  useEffect(() => {
    if (!id) return
    setProxima(null)
    setFormas(null)
    carregarProxima()
    api
      .get<PreviaEmail>(`/dps/${id}/email-previa`)
      .then((p) => setFormas(p.formas ?? [p.canal_preferido === "nenhum" ? "" : (p.canal_preferido ?? "email")].filter(Boolean)))
      .catch(() => setFormas(null))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  function recarregarEnvios() {
    if (!id) return
    api.get<Envio[]>(`/dps/${id}/envios`).then(setEnvios).catch(() => {})
    carregarProxima()
  }

  /** Tomador com "baixar o PDF ao finalizar": baixa assim que a nota é autorizada. */
  function baixarPdfSeConfigurado(estado: string) {
    if (!id || estado !== "confirmado" || !formas?.includes("download")) return
    const a = document.createElement("a")
    a.href = `/api/dps/${id}/pdf`
    a.download = ""
    document.body.appendChild(a)
    a.click()
    a.remove()
    // Só baixar é a entrega deste tomador: já fica marcada como enviada.
    if (formas.every((f) => f === "download")) {
      api.post(`/dps/${id}/marcar-enviada`, { forma: "outro" }).then(recarregarEnvios).catch(() => {})
    }
  }

  async function copiarLink() {
    if (!opcoes) return
    await navigator.clipboard.writeText(opcoes.link_publico)
    setLinkCopiado(true)
    setTimeout(() => setLinkCopiado(false), 2000)
  }

  function carregar() {
    if (!id) return
    setCarregando(true)
    Promise.all([api.get<NotaVisual>(`/dps/${id}/nota`), api.get<Envio[]>(`/dps/${id}/envios`)])
      .then(([n, e]) => {
        setNota(n)
        setEnvios(e)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao carregar."))
      .finally(() => setCarregando(false))
  }

  useEffect(carregar, [id])

  // Conferência (05/10/2026): enquanto a nota não foi autorizada, a Ana
  // confere os dados guardados nela. `undefined` = não se aplica / falhou.
  const estadoDaNota = nota?.estado
  const conferivel = !!estadoDaNota && ["rascunho", "montado", "assinado", "erro"].includes(estadoDaNota)
  const [pontosConferencia, setPontosConferencia] = useState<PontoConferencia[] | null | undefined>(undefined)
  useEffect(() => {
    if (!id || !conferivel) return setPontosConferencia(undefined)
    let cancelado = false
    setPontosConferencia(null)
    api
      .get<ConferenciaNota>(`/dps/${id}/conferencia`)
      .then((c) => !cancelado && setPontosConferencia(c.pontos))
      .catch(() => !cancelado && setPontosConferencia(undefined))
    return () => {
      cancelado = true
    }
  }, [id, conferivel, estadoDaNota])

  async function assinar() {
    if (!id) return
    setErro(null)
    setProcessando(true)
    try {
      await api.post(`/dps/${id}/assinar`)
      carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao assinar.")
    } finally {
      setProcessando(false)
    }
  }

  async function submeterNota() {
    if (!id) return
    setErroAcao(null)
    setProcessando(true)
    try {
      const r = await api.post<Emissao>(`/dps/${id}/submeter`)
      setDados(r)
      setModalSubmeter(false)
      baixarPdfSeConfigurado(r.estado)
      carregar()
      carregarProxima()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao submeter.")
    } finally {
      setProcessando(false)
    }
  }

  /** Recusa por causa da hora (E0008): acerta a hora, assina e reenvia. */
  async function corrigirEReenviar() {
    if (!id) return
    setErroAcao(null)
    setProcessando(true)
    try {
      const r = await api.post<Emissao>(`/dps/${id}/corrigir-reenviar`, {})
      setDados(r)
      baixarPdfSeConfigurado(r.estado)
      carregar()
      carregarProxima()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao reenviar.")
    } finally {
      setProcessando(false)
    }
  }

  async function cancelarNota(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setErroAcao(null)
    setProcessando(true)
    try {
      await api.post(`/dps/${id}/cancelar`, { cmotivo, xmotivo })
      setModalCancelar(false)
      setXmotivo("")
      carregar()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao cancelar.")
    } finally {
      setProcessando(false)
    }
  }

  async function baixarXml() {
    if (!id) return
    const resp = await fetch(`/api/dps/${id}/download`)
    if (!resp.ok) {
      const dados = await resp.json().catch(() => null)
      setErro(dados?.detail ?? "Falha ao baixar o XML.")
      return
    }
    const nomeArquivo = resp.headers.get("content-disposition")?.match(/filename="(.+)"/)?.[1] ?? "nota.xml"
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = nomeArquivo
    a.click()
    URL.revokeObjectURL(url)
    registrarEnvio("download", { silencioso: true })
  }

  async function verMensagemPronta() {
    if (!id) return
    try {
      const resp = await api.get<{ mensagem: string }>(`/dps/${id}/mensagem-pronta`)
      setMensagemPronta(resp.mensagem)
      setCopiado(false)
      registrarEnvio("mensagem_pronta", { silencioso: true })
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao gerar mensagem.")
    }
  }

  async function registrarEnvio(canal: CanalEnvio, opts?: { silencioso?: boolean }) {
    if (!id) return
    try {
      await api.post(`/dps/${id}/envios`, { canal })
      if (!opts?.silencioso) carregar()
      else api.get<Envio[]>(`/dps/${id}/envios`).then(setEnvios)
    } catch (err) {
      if (!opts?.silencioso) setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao registrar envio.")
    }
  }

  async function marcarEnvio(envioId: string, acao: "marcar-enviado" | "marcar-falha") {
    try {
      await api.post(`/envios/${envioId}/${acao}`)
      api.get<Envio[]>(`/dps/${id}/envios`).then(setEnvios)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao atualizar envio.")
    }
  }

  if (carregando) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
  if (!nota) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro ?? "Nota não encontrada."}</p>

  const entregue = envios.some((e) => ["email", "whatsapp", "direto_fornecedor"].includes(e.canal) && e.status === "enviado")
  const notaParaEnvio: NotaParaAcoes = {
    id: id ?? "",
    estado: nota.estado,
    envio_status: entregue ? "enviado" : null,
    tem_pdf: nota.estado === "confirmado",
    homologacao: nota.ambiente === "2",
    vinculo_id: opcoes?.vinculo_id ?? null,
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/app/nfse" className="text-sm text-primary-600 hover:underline">
            ← Voltar para NFS-e
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            NFS-e nº {nota.n_dps} — série {nota.serie}
          </h1>
        </div>
        <Badge variant={nota.estado === "erro" ? "danger" : nota.estado === "rascunho" ? "neutral" : "success"}>
          {nota.estado_label}
        </Badge>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {nota.estado === "erro" && nota.erro_detalhe && (
        <p className="flex flex-wrap items-start gap-2 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span className="min-w-0 flex-1">
            <strong>{nota.erro_detalhe}</strong>
            {!dados?.erro_corrigivel && " Corrija o que for preciso (no cadastro do tomador ou gerando a nota de novo) e envie outra vez."}
            {dados?.erro_corrigivel && /E0240/.test(nota.erro_detalhe) && opcoes?.vinculo_id && !dados.avulsa && (
              <span className="mt-1 block font-normal">
                Se você souber o endereço certo,{" "}
                <Link to={`/app/tomadores/${opcoes.vinculo_id}?editar=endereco`} className="font-semibold underline">
                  corrija no cadastro do tomador
                </Link>{" "}
                antes — a nota vai com o endereço novo.
              </span>
            )}
            {erroAcao && <span className="mt-1 block">{erroAcao}</span>}
          </span>
          {dados?.erro_corrigivel && (
            <Button type="button" variant="accent" disabled={processando} onClick={corrigirEReenviar} className="shrink-0">
              {processando ? "Reenviando..." : "Corrigir e reenviar"}
            </Button>
          )}
        </p>
      )}

      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between border-b border-slate-100 dark:border-slate-700/60 pb-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Competência</p>
            <p className="font-medium text-slate-800 dark:text-slate-200">{nota.competencia}</p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Ambiente</p>
            <p className="font-medium text-slate-800 dark:text-slate-200">{nota.ambiente_label ?? "—"}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Prestador</p>
            <p className="font-medium text-slate-800 dark:text-slate-200">{nota.prestador.razao_social}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">{nota.prestador.cnpj}</p>
            {nota.prestador.endereco && <p className="text-sm text-slate-500 dark:text-slate-400">{nota.prestador.endereco}</p>}
          </div>
          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Tomador</p>
            <p className="font-medium text-slate-800 dark:text-slate-200">{nota.tomador.razao_social ?? "—"}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">{nota.tomador.cnpj}</p>
            {nota.tomador.endereco && <p className="text-sm text-slate-500 dark:text-slate-400">{nota.tomador.endereco}</p>}
          </div>
        </div>

        <div className="mt-6 border-t border-slate-100 dark:border-slate-700/60 pt-4">
          <p className="mb-1 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Serviço</p>
          <p className="text-sm text-slate-700 dark:text-slate-300">{nota.servico.descricao}</p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Cód. tributação nacional {nota.servico.codigo_tributacao_nacional}
            {nota.servico.codigo_tributacao_municipal && ` · municipal ${nota.servico.codigo_tributacao_municipal}`}
          </p>
        </div>

        <div className="mt-6 flex items-center justify-between rounded-xl bg-slate-50 dark:bg-slate-900/40 px-4 py-3">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Valor do serviço</span>
          <span className="text-xl font-semibold text-slate-900 dark:text-slate-100">{formatBRL(nota.valores.valor_servico)}</span>
        </div>

        {nota.chave_acesso && <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">Chave de acesso: {nota.chave_acesso}</p>}
      </Card>

      {conferivel && pontosConferencia !== undefined && (
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Conferência</h2>
          <Conferencia pontos={pontosConferencia} vinculoId={dados?.avulsa ? null : (dados?.vinculo_id ?? opcoes?.vinculo_id ?? null)} />
          {pontosConferencia?.some((p) => p.nivel === "erro") && (
            <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
              Com ponto em vermelho, a prefeitura tende a recusar a nota. Corrija antes de enviar.
            </p>
          )}
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Ações</h2>
        <div className="flex flex-wrap gap-2">
          {nota.estado === "montado" && (
            <Button variant="accent" onClick={assinar} disabled={processando}>
              <PenLine size={15} /> {processando ? "Assinando..." : "Assinar"}
            </Button>
          )}
          {(nota.estado === "assinado" || nota.estado === "erro") && (
            <Button variant="accent" onClick={() => setModalSubmeter(true)} disabled={processando}>
              <Send size={15} /> {nota.estado === "erro" ? "Tentar submeter de novo" : "Submeter à prefeitura"}
            </Button>
          )}
          {nota.estado === "confirmado" && (
            <Button variant="outline" onClick={() => setModalCancelar(true)} disabled={processando} className="!border-danger-300 !text-danger-700 hover:!bg-danger-50">
              <Ban size={15} /> Cancelar nota
            </Button>
          )}
          {nota.estado === "confirmado" && (
            <a
              href={`/api/dps/${id}/pdf`}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              <FileDown size={15} /> Baixar PDF
            </a>
          )}
          <Button variant="outline" onClick={baixarXml} disabled={!nota.xml_disponivel}>
            <Download size={15} /> Baixar XML
          </Button>
          {dados?.origem === "importada" && !dados.avulsa && (
            <Button
              variant="outline"
              onClick={() => {
                setErroAcao(null)
                setDestino(dados.vinculo_id ?? "")
                api.get<VinculoResumo[]>("/vinculos?todos=true").then(setVinculos).catch(() => setVinculos([]))
                setModalMover(true)
              }}
              disabled={processando}
            >
              <ArrowLeftRight size={15} /> Mudar de tomador
            </Button>
          )}
          {["rascunho", "montado", "assinado", "erro"].includes(nota.estado) && (
            <Button
              variant="outline"
              onClick={() => {
                setErroAcao(null)
                setModalApagar(true)
              }}
              disabled={processando}
              className="!border-danger-300 !text-danger-700 hover:!bg-danger-50"
            >
              <Trash2 size={15} /> Apagar nota
            </Button>
          )}
          <Button variant="outline" onClick={verMensagemPronta} disabled={!nota.xml_disponivel}>
            <MessageSquareText size={15} /> Mensagem pronta
          </Button>
        </div>

        {mensagemPronta && (
          <div className="mt-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 p-4 dark:border-slate-700 dark:bg-slate-900/50">
            <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300">{mensagemPronta}</pre>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(mensagemPronta)
                setCopiado(true)
              }}
              className="mt-2 flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
            >
              <Copy size={14} /> {copiado ? "Copiado!" : "Copiar"}
            </button>
          </div>
        )}
      </Card>

      <Card className="scroll-mt-6 p-5" id="envio-da-nota">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Envio desta nota</h2>
            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
              Escolha como esta nota chega ao tomador — por e-mail, WhatsApp, no portal dele — ou mande pro contador.
            </p>
          </div>
          <button
            type="button"
            onClick={copiarLink}
            disabled={!nota.xml_disponivel || !opcoes}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-50 dark:text-primary-300 dark:hover:bg-primary-900/30"
          >
            <LinkIcon size={13} /> {linkCopiado ? "Link copiado!" : "Copiar link da nota"}
          </button>
        </div>
        {id && <EnvioNota nota={notaParaEnvio} onMudou={recarregarEnvios} modo="card" />}

        <h3 className="mb-1 mt-6 border-t border-slate-100 pt-4 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
          Histórico de envios
        </h3>
        {envios.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Nenhum envio registrado ainda.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-slate-100 dark:divide-slate-700">
            {envios.map((e) => (
              <li key={e.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="min-w-0 break-words text-slate-700 dark:text-slate-300">
                  {CANAIS.find((c) => c.value === e.canal)?.label ?? e.canal}
                  {e.destino && <span className="ml-1 text-xs text-slate-400">· {e.destino}</span>}
                  {e.erro && <span className="block text-xs text-danger-600">{e.erro}</span>}
                </span>
                <div className="flex items-center gap-3">
                  {badgeStatusEnvio(e.status)}
                  {e.status === "pendente" && (
                    <div className="flex gap-1">
                      <button
                        type="button"
                        title="Marcar como enviado"
                        aria-label="Marcar como enviado"
                        onClick={() => marcarEnvio(e.id, "marcar-enviado")}
                        className="rounded p-1 text-success-600 hover:bg-success-50"
                      >
                        <CheckCircle2 size={16} />
                      </button>
                      <button
                        type="button"
                        title="Marcar falha"
                        aria-label="Marcar falha"
                        onClick={() => marcarEnvio(e.id, "marcar-falha")}
                        className="rounded p-1 text-danger-600 hover:bg-danger-50"
                      >
                        <XCircle size={16} />
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {(() => {
        // Nota importada do Emissor Nacional já foi entregue por fora: não cobra envio.
        const precisaEnviar =
          nota.estado === "confirmado" && !entregue && dados?.origem !== "importada" && (dados?.avulsa || (formas ?? ["email"]).length > 0)
        const passo: { titulo: string; texto: string; botao?: string; acao?: () => void } | null =
          nota.estado === "montado"
            ? { titulo: "Assinar a nota", texto: "Confira os dados acima. Estando certo, assine com o certificado.", botao: processando ? "Assinando..." : "Assinar", acao: assinar }
            : nota.estado === "assinado"
              ? { titulo: "Enviar à prefeitura", texto: "A nota está assinada. Falta a prefeitura autorizar.", botao: "Enviar à prefeitura", acao: () => setModalSubmeter(true) }
              : nota.estado === "erro"
                ? dados?.erro_corrigivel
                  ? { titulo: "Corrigir e reenviar", texto: "Eu conserto o que a prefeitura recusou e mando de novo.", botao: processando ? "Reenviando..." : "Corrigir e reenviar", acao: corrigirEReenviar }
                  : { titulo: "Resolver a recusa", texto: "Corrija o que a prefeitura apontou e tente de novo.", botao: "Tentar de novo", acao: () => setModalSubmeter(true) }
                : precisaEnviar
                  ? {
                      titulo: "Enviar ao tomador",
                      texto: "A prefeitura autorizou. Falta a nota chegar ao tomador.",
                      botao: "Ir pro envio",
                      acao: () => document.getElementById("envio-da-nota")?.scrollIntoView({ behavior: "smooth", block: "start" }),
                    }
                  : null
        const terminou = passo === null && ["confirmado", "cancelada", "substituida"].includes(nota.estado)
        return (
          <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-3 rounded-2xl border border-primary-200 bg-white/95 px-4 py-3 shadow-lg shadow-slate-900/10 backdrop-blur dark:border-primary-900/60 dark:bg-slate-800/95" data-tour="nota-proximo-passo">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-600 dark:text-primary-300">
                {passo ? "Próximo passo" : terminou ? "Tudo certo com esta nota" : "Esta nota"}
              </p>
              <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
                {passo ? passo.titulo : proxima?.proxima ? `Próxima: ${proxima.proxima.nome} — ${proxima.proxima.passo.toLowerCase()}` : "Não há outra nota esperando por você."}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {passo
                  ? passo.texto
                  : proxima?.proxima
                    ? `${formatBRL(proxima.proxima.valor)} · ${proxima.proxima.competencia}${proxima.restantes > 1 ? ` · mais ${proxima.restantes - 1} na fila` : ""}`
                    : ""}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" onClick={() => navigate(dados?.avulsa ? "/app/nfse/lote" : "/app/nfse")}>
                ← Lista
              </Button>
              {passo?.botao && (
                <Button variant="accent" disabled={processando} onClick={passo.acao}>
                  {passo.botao}
                </Button>
              )}
              {proxima?.proxima && (
                <Button variant={passo ? "outline" : "accent"} onClick={() => navigate(`/app/nfse/${proxima.proxima!.id}`)}>
                  {passo ? "Pular pra próxima nota →" : "Ir pra próxima nota →"}
                </Button>
              )}
            </div>
          </div>
        )
      })()}

      {modalSubmeter && (
        <Modal
          titulo={nota.estado === "erro" ? "Tentar submeter de novo à prefeitura" : "Submeter nota à prefeitura"}
          onClose={() => (processando ? null : setModalSubmeter(false))}
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Isso envia a DPS assinada pra Sefin de verdade — não dá pra desfazer o envio em si (só cancelar a nota
              depois, se ela for confirmada).
            </p>
            <p
              className={`rounded-lg px-3 py-2 text-sm font-medium ${
                nota.ambiente === "1"
                  ? "bg-danger-50 text-danger-700"
                  : "bg-warning-50 text-warning-700"
              }`}
            >
              Ambiente: {nota.ambiente_label ?? "—"}
              {nota.ambiente === "1" && " — isso é uma nota fiscal real, com efeito legal."}
            </p>
            {erroAcao && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroAcao}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setModalSubmeter(false)} disabled={processando}>
                Cancelar
              </Button>
              <Button variant="accent" onClick={submeterNota} disabled={processando}>
                <Send size={15} /> {processando ? "Enviando..." : "Confirmar envio"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {modalCancelar && (
        <Modal titulo="Cancelar nota" onClose={() => (processando ? null : setModalCancelar(false))}>
          <form onSubmit={cancelarNota} className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              O cancelamento é enviado pra Sefin e, se aceito, não pode ser desfeito. Use isso só quando a nota
              realmente não deveria ter sido emitida.
            </p>
            <FieldWrap label="Motivo">
              <select
                value={cmotivo}
                onChange={(e) => setCmotivo(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                {MOTIVOS_CANCELAMENTO.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </FieldWrap>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Justificativa</span>
              <textarea
                value={xmotivo}
                onChange={(e) => setXmotivo(e.target.value)}
                rows={3}
                required
                minLength={15}
                maxLength={255}
                placeholder="Descreva o motivo do cancelamento (mínimo 15 caracteres)"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
              <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
                Entre 15 e 255 caracteres ({xmotivo.length}/255)
              </span>
            </label>
            {erroAcao && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroAcao}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setModalCancelar(false)} disabled={processando}>
                Voltar
              </Button>
              <Button
                type="submit"
                variant="outline"
                disabled={processando || xmotivo.length < 15}
                className="!border-danger-300 !text-danger-700 hover:!bg-danger-50"
              >
                <Ban size={15} /> {processando ? "Cancelando..." : "Confirmar cancelamento"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
      {modalApagar && (
        <Modal titulo="Apagar nota" onClose={() => (processando ? null : setModalApagar(false))}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Esta nota não foi autorizada pela prefeitura, então dá pra apagar sem cancelar. Ela some da lista.
            </p>
            {erroAcao && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroAcao}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setModalApagar(false)} disabled={processando}>
                Voltar
              </Button>
              <Button variant="accent" onClick={apagar} disabled={processando} className="!bg-danger-600 hover:!bg-danger-700">
                <Trash2 size={15} /> {processando ? "Apagando..." : "Apagar"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
      {modalMover && (
        <Modal titulo="Mudar de tomador" onClose={() => (processando ? null : setModalMover(false))}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Nota importada do Emissor Nacional. Escolha a qual tomador ela pertence (útil quando o mesmo CNPJ tem mais de um cadastro,
              como AWIN e AWIN Rchlo). A nota em si não muda.
            </p>
            <CaixaBusca
              valor={destino}
              opcoes={vinculos.map((v) => ({ id: v.id, rotulo: `${v.apelido}${v.tomador_cnpj ? ` — ${v.tomador_cnpj}` : ""}` }))}
              onEscolher={setDestino}
              placeholder="Digite o nome do tomador pra buscar"
              ariaLabel="Tomador"
              className="[&_input]:py-2 [&_input]:pl-3"
            />
            {erroAcao && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erroAcao}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setModalMover(false)} disabled={processando}>
                Voltar
              </Button>
              <Button variant="accent" onClick={mover} disabled={processando || !destino || destino === dados?.vinculo_id}>
                {processando ? "Salvando..." : "Mudar"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
