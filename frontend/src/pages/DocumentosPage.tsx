import { AlertTriangle, Download, Eye, FileArchive, History, RefreshCw, Trash2, UploadCloud } from "lucide-react"
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"

// Documentos da empresa (2026.10.7, ideias/documentos-da-empresa.md): guarda
// permanente, separada da pasta do mês. Só o dono e o contador com a permissão
// "Documentos da empresa" veem; só o dono apaga e vê quem abriu cada um.
// 15 MB por arquivo e 100 MB por empresa.

interface Documento {
  id: string
  tipo: string
  tipo_rotulo: string
  nome: string
  nome_arquivo: string
  tamanho: number
  validade: string | null
  situacao: "sem_validade" | "ok" | "vence_em_breve" | "vencido"
  enviado_por: string | null
  papel: "empresa" | "contador"
  enviado_em: string | null
  substituido_em: string | null
}
interface Dados {
  papel: "empresa" | "contador"
  pode_apagar: boolean
  documentos: Documento[]
  uso: { bytes: number; limite_mb: number; limite_arquivo_mb: number }
  tipos: { id: string; rotulo: string }[]
  contadores_sem_permissao: string[]
}
interface Acesso {
  email: string | null
  papel: string
  acao: string
  em: string | null
}

const mb = (b: number) => `${(b / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
const data = (iso: string | null) => (iso ? new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("pt-BR") : "—")
const ACAO: Record<string, string> = { enviou: "enviou", substituiu: "substituiu", abriu: "abriu", baixou: "baixou" }
const erroDe = (e: unknown) => (e instanceof ApiError ? formatarErro(e.detail) : "Falha de conexão. Tente de novo.")

function Situacao({ d }: { d: Documento }) {
  if (d.situacao === "vencido") return <Badge variant="danger">Vencido em {data(d.validade)}</Badge>
  if (d.situacao === "vence_em_breve") return <Badge variant="warning">Vence em {data(d.validade)}</Badge>
  if (d.situacao === "ok") return <span className="text-xs text-slate-500 dark:text-slate-400">Válido até {data(d.validade)}</span>
  return null
}

export function DocumentosPage() {
  const [dados, setDados] = useState<Dados | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [tipo, setTipo] = useState("contrato_social")
  const [nome, setNome] = useState("")
  const [validade, setValidade] = useState("")
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [chave, setChave] = useState(0)
  const [historico, setHistorico] = useState<{ doc: Documento; acessos: Acesso[] } | null>(null)
  const substituirInput = useRef<HTMLInputElement>(null)
  const [substituindo, setSubstituindo] = useState<Documento | null>(null)

  const carregar = useCallback(() => {
    api.get<Dados>("/documentos").then(setDados).catch((e) => setErro(erroDe(e)))
  }, [])
  useEffect(carregar, [carregar])

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setEnviando(true)
    setMsg(null)
    setErro(null)
    const form = new FormData()
    form.append("tipo", tipo)
    if (nome.trim()) form.append("nome", nome.trim())
    if (validade) form.append("validade", validade)
    form.append("arquivo", arquivo)
    try {
      await api.postForm("/documentos", form)
      setMsg("Documento guardado.")
      setNome("")
      setValidade("")
      setArquivo(null)
      setChave((c) => c + 1)
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  async function substituir(doc: Documento, file: File) {
    setErro(null)
    setMsg(null)
    const form = new FormData()
    form.append("arquivo", file)
    try {
      await api.postForm(`/documentos/${doc.id}/substituir`, form)
      setMsg(`“${doc.nome}” substituído.`)
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setSubstituindo(null)
    }
  }

  async function apagar(doc: Documento) {
    if (!window.confirm(`Apagar “${doc.nome}”? Não dá pra desfazer.`)) return
    try {
      await api.delete(`/documentos/${doc.id}`)
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    }
  }

  async function verHistorico(doc: Documento) {
    try {
      const r = await api.get<{ acessos: Acesso[] }>(`/documentos/${doc.id}/acessos`)
      setHistorico({ doc, acessos: r.acessos })
    } catch (err) {
      setErro(erroDe(err))
    }
  }

  if (erro && !dados) {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <h1 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-slate-100">Documentos da empresa</h1>
        <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">{erro}</p>
      </div>
    )
  }
  if (!dados) return <p className="py-10 text-center text-sm text-slate-400">Carregando...</p>

  const usoPct = Math.min(100, (dados.uso.bytes / (dados.uso.limite_mb * 1024 * 1024)) * 100)
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Documentos da empresa</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Os documentos que o contador sempre pede, guardados num lugar só: contrato social, cartão CNPJ, documentos dos sócios, certidões.
          Só você {dados.papel === "contador" ? "(e o dono da empresa)" : "e o contador que você liberar"} enxergam — nem a equipe da Ana abre.
        </p>
      </div>

      {dados.contadores_sem_permissao.length > 0 && (
        <p className="flex items-start gap-2 rounded-lg bg-primary-50 px-4 py-3 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            {dados.contadores_sem_permissao.join(", ")} ainda não vê esta área. Se quiser, libere a permissão “Documentos da empresa” em{" "}
            <Link to="/app/empresa?aba=contador" className="font-semibold underline">
              Empresa › Contador
            </Link>
            .
          </span>
        </p>
      )}
      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {msg && <p role="status" className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">{msg}</p>}

      <Card className="p-5">
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-100">
          <UploadCloud size={18} aria-hidden="true" /> Guardar um documento
        </h2>
        <form onSubmit={enviar} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-300">Tipo</span>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            >
              {dados.tipos.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.rotulo}
                </option>
              ))}
            </select>
          </label>
          <Field label="Nome (opcional)" placeholder="Ex.: 3ª alteração contratual" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={200} />
          <Field label="Validade (opcional)" type="date" value={validade} onChange={(e) => setValidade(e.target.value)} hint="Eu aviso 30 dias antes de vencer." />
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-300">Arquivo (até {dados.uso.limite_arquivo_mb} MB)</span>
            <input
              key={chave}
              type="file"
              required
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 dark:text-slate-300 dark:file:bg-slate-700 dark:file:text-slate-200"
            />
          </label>
          <div className="sm:col-span-2">
            <Button type="submit" variant="accent" disabled={enviando || !arquivo}>
              {enviando ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </form>
        <div className="mt-4">
          <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700" aria-hidden="true">
            <div className="h-full rounded-full bg-primary-500" style={{ width: `${Math.max(1, usoPct)}%` }} />
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {mb(dados.uso.bytes)} de {dados.uso.limite_mb} MB usados.
          </p>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-100">
          <FileArchive size={18} aria-hidden="true" /> Guardados
        </h2>
        {dados.documentos.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Nenhum documento ainda.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {dados.documentos.map((d) => (
              <li key={d.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="font-medium text-slate-800 dark:text-slate-100">{d.nome}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {d.tipo_rotulo} · {d.nome_arquivo} · {mb(d.tamanho)} · {d.substituido_em ? `substituído em ${data(d.substituido_em)}` : `enviado em ${data(d.enviado_em)}`}
                    {d.enviado_por ? ` por ${d.enviado_por}${d.papel === "contador" ? " (contador)" : ""}` : ""}
                  </p>
                  <Situacao d={d} />
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <a href={`/api/documentos/${d.id}/arquivo`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
                    <Eye size={14} aria-hidden="true" /> Abrir
                  </a>
                  <a href={`/api/documentos/${d.id}/arquivo?baixar=true`} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
                    <Download size={14} aria-hidden="true" /> Baixar
                  </a>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setSubstituindo(d)
                      substituirInput.current?.click()
                    }}
                  >
                    <RefreshCw size={14} aria-hidden="true" /> Substituir
                  </Button>
                  {dados.pode_apagar && (
                    <>
                      <Button type="button" variant="ghost" onClick={() => verHistorico(d)}>
                        <History size={14} aria-hidden="true" /> Quem abriu
                      </Button>
                      <Button type="button" variant="ghost" onClick={() => apagar(d)} aria-label={`Apagar ${d.nome}`}>
                        <Trash2 size={14} aria-hidden="true" />
                      </Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        <input
          ref={substituirInput}
          type="file"
          className="hidden"
          aria-hidden="true"
          tabIndex={-1}
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f && substituindo) void substituir(substituindo, f)
            e.target.value = ""
          }}
        />
      </Card>

      {historico && (
        <Modal titulo={`Quem abriu “${historico.doc.nome}”`} onClose={() => setHistorico(null)}>
          <div className="p-5">
            {historico.acessos.length === 0 ? (
              <p className="text-sm text-slate-400">Ninguém ainda.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700/60">
                {historico.acessos.map((a, i) => (
                  <li key={i} className="flex justify-between gap-3 py-2">
                    <span className="text-slate-700 dark:text-slate-200">
                      {a.email ?? "—"} {a.papel === "contador" ? "(contador)" : ""} {ACAO[a.acao] ?? a.acao}
                    </span>
                    <span className="text-slate-500 dark:text-slate-400">{a.em ? new Date(a.em).toLocaleString("pt-BR") : ""}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
