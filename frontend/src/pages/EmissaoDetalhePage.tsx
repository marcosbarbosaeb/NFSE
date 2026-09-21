import { CheckCircle2, Copy, Download, MessageSquareText, PenLine, XCircle } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL } from "../lib/format"
import type { CanalEnvio, Envio, NotaVisual } from "../lib/types"

const CANAIS: { value: CanalEnvio; label: string }[] = [
  { value: "download", label: "Baixar XML" },
  { value: "mensagem_pronta", label: "Mensagem pronta" },
  { value: "email", label: "E-mail" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "direto_fornecedor", label: "Direto com o fornecedor" },
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

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/nfse" className="text-sm text-primary-600 hover:underline">
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

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Ações</h2>
        <div className="flex flex-wrap gap-2">
          {nota.estado === "montado" && (
            <Button variant="accent" onClick={assinar} disabled={processando}>
              <PenLine size={15} /> {processando ? "Assinando..." : "Assinar"}
            </Button>
          )}
          <Button variant="outline" onClick={baixarXml} disabled={!nota.xml_disponivel}>
            <Download size={15} /> Baixar XML
          </Button>
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

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Envio ao fornecedor</h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {CANAIS.filter((c) => c.value === "email" || c.value === "whatsapp" || c.value === "direto_fornecedor").map((c) => (
            <Button key={c.value} variant="outline" onClick={() => registrarEnvio(c.value)} disabled={!nota.xml_disponivel}>
              Registrar por {c.label}
            </Button>
          ))}
        </div>

        {envios.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Nenhum envio registrado ainda.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-slate-100 dark:divide-slate-700">
            {envios.map((e) => (
              <li key={e.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="text-slate-700 dark:text-slate-300">{CANAIS.find((c) => c.value === e.canal)?.label ?? e.canal}</span>
                <div className="flex items-center gap-3">
                  {badgeStatusEnvio(e.status)}
                  {e.status === "pendente" && (
                    <div className="flex gap-1">
                      <button
                        type="button"
                        title="Marcar como enviado"
                        onClick={() => marcarEnvio(e.id, "marcar-enviado")}
                        className="rounded p-1 text-success-600 hover:bg-success-50"
                      >
                        <CheckCircle2 size={16} />
                      </button>
                      <button
                        type="button"
                        title="Marcar falha"
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

      <div>
        <Button variant="ghost" onClick={() => navigate("/nfse")}>
          ← Voltar
        </Button>
      </div>
    </div>
  )
}
