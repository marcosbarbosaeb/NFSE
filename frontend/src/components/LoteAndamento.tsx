import { AlertTriangle, Check, CheckCircle2, Clock, Download, FolderUp, Loader2, Mail, PlayCircle } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import { LOTE_RODANDO } from "../lib/lotes"
import type { AndamentoLote, Lote } from "../lib/types"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"

/** Passo a passo de Notas em lote (05/10/2026): "normalmente esse pack em
 * lote não é pra ter vários comandos. Aqui é seguir o passo a passo
 * sequencial e automatizar tudo". A tela mostra em que etapa o mês está e
 * UM botão pra continuar — sem selecionar nota por nota. No fim, o pacote:
 * baixar os arquivos, mandar num e-mail só ou guardar no Google Drive.
 * Vendedor sem e-mail não é falha: é só indicado, e a situação fica regular. */

const msg = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

type Conteudo = "ambos" | "pdf" | "xml"
const ROTULO_CONTEUDO: Record<Conteudo, string> = { ambos: "PDF e XML", pdf: "Só PDF", xml: "Só XML" }

function Etapa({ n, titulo, feito, total, estado, detalhe }: { n: number; titulo: string; feito?: number; total?: number; estado: "feito" | "atual" | "depois"; detalhe?: ReactNode }) {
  return (
    <li
      className={`flex min-w-0 flex-1 items-start gap-2.5 rounded-xl border px-3 py-2.5 ${
        estado === "feito"
          ? "border-success-100 bg-success-50/60 dark:border-success-900/40 dark:bg-success-900/20"
          : estado === "atual"
            ? "border-primary-400 bg-primary-50 dark:border-primary-600 dark:bg-primary-900/30"
            : "border-slate-200 dark:border-slate-700"
      }`}
      aria-current={estado === "atual" ? "step" : undefined}
    >
      <span
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          estado === "feito" ? "bg-success-600 text-white" : estado === "atual" ? "bg-primary-600 text-white" : "bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-300"
        }`}
      >
        {estado === "feito" ? <Check size={14} aria-label="feito" /> : n}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">{titulo}</span>
        {total != null && (
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            {feito} de {total}
          </span>
        )}
        {detalhe && <span className="mt-0.5 block text-xs">{detalhe}</span>}
      </span>
    </li>
  )
}

export function LoteAndamento({
  vinculoId,
  versao,
  ambienteTeste,
  emailPadrao,
  onLote,
  onVerNotas,
  onMudou,
}: {
  /** Tomador do relatório (Shopee). */
  vinculoId: string | null
  /** Muda quando a lista recarrega (lote terminou, relatório novo): refaz a conta. */
  versao: number
  ambienteTeste?: boolean
  /** E-mail sugerido pro pacote (os "e-mails gerais" da empresa, se houver). */
  emailPadrao?: string | null
  onLote: (lote: Lote) => void
  /** Filtra a lista de baixo pelo mês (e, se pedido, só as não autorizadas). */
  onVerNotas: (competencia: string, soPendentes?: boolean) => void
  onMudou?: () => void
}) {
  const [dados, setDados] = useState<AndamentoLote | null>(null)
  const [competencia, setCompetencia] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState<"" | "continuar" | "zip" | "email" | "drive" | "conectar">("")
  const [conteudo, setConteudo] = useState<Conteudo>("ambos")
  const [para, setPara] = useState(emailPadrao ?? "")
  const [emailAberto, setEmailAberto] = useState(false)
  const [drive, setDrive] = useState<{ disponivel: boolean; conectado: boolean; email: string | null } | null>(null)

  useEffect(() => {
    if (emailPadrao) setPara((p) => p || emailPadrao)
  }, [emailPadrao])

  useEffect(() => {
    let vivo = true
    const q = new URLSearchParams()
    if (vinculoId) q.set("vinculo_id", vinculoId)
    if (competencia) q.set("competencia", competencia)
    api
      .get<AndamentoLote>(`/lotes/andamento?${q.toString()}`)
      .then((d) => vivo && setDados(d))
      .catch(() => vivo && setDados(null))
    return () => {
      vivo = false
    }
  }, [vinculoId, competencia, versao])

  useEffect(() => {
    api.get<{ disponivel: boolean; conectado: boolean; email: string | null }>("/drive").then(setDrive).catch(() => setDrive(null))
    // Volta do Google (?drive=conectado|recusado|falhou)
    const retorno = new URLSearchParams(window.location.search).get("drive")
    if (retorno === "conectado") setAviso("Google Drive conectado. Agora é só clicar em “Guardar no Google Drive”.")
    else if (retorno) setErro("Não consegui conectar o Google Drive. Tente de novo e aceite o acesso que o Google pedir.")
  }, [])

  if (!dados || !dados.total || !dados.competencia) return null
  const d = dados
  const mes = d.competencia as string
  const ativo = d.lote_ativo
  const rodando = ativo != null && LOTE_RODANDO(ativo)
  const esperandoCota = ativo?.status === "aguardando"
  const falta = d.a_assinar + d.a_prefeitura + d.a_enviar
  const passosQueFaltam = [d.a_assinar > 0 && "assinar", (d.a_assinar > 0 || d.a_prefeitura > 0) && "enviar à prefeitura", "mandar aos vendedores"].filter(Boolean) as string[]
  const estado = (pendentes: number, anteriores: number): "feito" | "atual" | "depois" => (pendentes === 0 && anteriores === 0 ? "feito" : anteriores === 0 ? "atual" : "depois")

  // "Guardar os arquivos" não é obrigatório (08/10/2026): dá pra só marcar
  // como concluído. Baixar, mandar por e-mail ou guardar no Drive marca sozinho.
  async function marcarPacote(feito: boolean) {
    try {
      await api.post("/painel/pendencias/ignorar", { chave: `pacote:${d.vinculo_id}:${mes}`, ignorar: feito })
      setDados((atual) => (atual ? { ...atual, pacote_feito: feito } : atual))
    } catch {
      /* é só uma marcação: se falhar, a etapa continua aberta */
    }
  }

  async function continuar() {
    setOcupado("continuar")
    setErro(null)
    setAviso(null)
    try {
      onLote(await api.post<Lote>("/lotes", { acao: "completo", vinculo_id: d.vinculo_id, competencia: mes, so_avulsas: true }))
      onMudou?.()
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  async function baixar() {
    setOcupado("zip")
    setErro(null)
    setAviso(null)
    try {
      const resp = await fetch(`/api/dps/zip?competencia=${mes}&vinculo_id=${d.vinculo_id}&conteudo=${conteudo}`, { credentials: "include" })
      if (!resp.ok) {
        const corpo = await resp.json().catch(() => null)
        throw new ApiError(resp.status, corpo?.detail ?? "Não foi possível montar o pacote.")
      }
      const url = URL.createObjectURL(await resp.blob())
      const a = document.createElement("a")
      a.href = url
      a.download = /filename="([^"]+)"/.exec(resp.headers.get("content-disposition") ?? "")?.[1] ?? `notas_${mes}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 2000)
      void marcarPacote(true)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  async function mandarPorEmail() {
    const destinos = para.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean)
    if (destinos.length === 0) {
      setErro("Escreva o e-mail de quem vai receber o pacote.")
      return
    }
    setOcupado("email")
    setErro(null)
    setAviso(null)
    try {
      const r = await api.post<{ enviado_para: string[]; notas: number }>("/pacote/email", { para: destinos, conteudo, competencia: mes, vinculo_id: d.vinculo_id })
      setAviso(`Pacote com ${r.notas} notas enviado pra ${r.enviado_para.join(", ")}.`)
      setEmailAberto(false)
      void marcarPacote(true)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  async function conectarDrive() {
    setOcupado("conectar")
    setErro(null)
    try {
      const { url } = await api.post<{ url: string }>("/drive/conectar", {})
      window.location.href = url
    } catch (err) {
      setErro(msg(err))
      setOcupado("")
    }
  }

  async function guardarNoDrive() {
    setOcupado("drive")
    setErro(null)
    setAviso(null)
    try {
      onLote(await api.post<Lote>("/lotes", { acao: "drive", vinculo_id: d.vinculo_id, competencia: mes, so_avulsas: true, conteudo }))
      setAviso("Estou guardando os arquivos no seu Google Drive, na pasta Agente Ana. Pode fechar a página — o link da pasta aparece no relatório.")
      void marcarPacote(true)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  const botaoPacote =
    "inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"

  return (
    <Card className="p-5" data-tour="lote-andamento">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Passo a passo — {formatCompetenciaLonga(mes)}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {d.total} notas · {formatBRL(d.valor)}
            {ambienteTeste && " · ambiente de teste"}
          </p>
        </div>
        {d.meses.length > 1 && (
          <select
            aria-label="Mês das notas"
            value={mes}
            onChange={(e) => {
              setCompetencia(e.target.value)
              setErro(null)
              setAviso(null)
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            {d.meses.map((m) => (
              <option key={`${m.competencia}-${m.vinculo_id}`} value={m.competencia}>
                {formatCompetenciaLonga(m.competencia)} ({m.notas})
              </option>
            ))}
          </select>
        )}
      </div>

      <ol className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Etapa n={1} titulo="Assinar" feito={d.assinadas} total={d.total} estado={estado(d.a_assinar, 0)} />
        <Etapa
          n={2}
          titulo="Prefeitura autorizar"
          feito={d.autorizadas}
          total={d.total}
          estado={estado(d.a_prefeitura, d.a_assinar)}
          detalhe={d.total_recusadas > 0 ? <span className="text-danger-600 dark:text-danger-300">{d.total_recusadas} recusada{d.total_recusadas === 1 ? "" : "s"}</span> : undefined}
        />
        <Etapa
          n={3}
          titulo="Enviar aos vendedores"
          feito={d.enviadas}
          total={d.total - d.total_sem_email}
          estado={estado(d.a_enviar, d.a_assinar + d.a_prefeitura)}
          detalhe={d.total_sem_email > 0 ? <span className="text-slate-500 dark:text-slate-400">{d.total_sem_email} sem e-mail</span> : undefined}
        />
        <Etapa
          n={4}
          titulo="Guardar os arquivos"
          estado={d.pacote_feito ? "feito" : d.regular ? "atual" : "depois"}
          detalhe={<span className="text-slate-500 dark:text-slate-400">{d.pacote_feito ? "concluído" : "opcional: baixar, e-mail ou Drive"}</span>}
        />
      </ol>

      {erro && <p role="alert" className="mt-3 rounded-lg bg-danger-50 px-4 py-2.5 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}
      {aviso && <p role="status" className="mt-3 rounded-lg bg-success-50 px-4 py-2.5 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">{aviso}</p>}

      {/* O que fazer agora: uma coisa só. */}
      <div className="mt-4">
        {rodando && ativo ? (
          <p className="flex items-center gap-2 rounded-xl bg-primary-50 px-4 py-3 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
            <Loader2 size={16} className="shrink-0 animate-spin" />
            <span>
              Estou trabalhando nisso em segundo plano — {ativo.feitos + ativo.falhas} de {ativo.total}. <strong>Pode fechar a página</strong>; no fim eu deixo o
              relatório aqui e mando por e-mail.
            </span>
          </p>
        ) : esperandoCota && ativo ? (
          <p className="flex items-start gap-2 rounded-xl bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
            <Clock size={16} className="mt-0.5 shrink-0" />
            <span>
              O serviço de e-mail atingiu o limite de envios {ativo.cota_mensal ? "do mês" : "de hoje"}. Faltam {ativo.total - ativo.feitos - ativo.falhas} e-mails;{" "}
              <strong>eu continuo sozinha</strong> assim que o limite voltar — você não precisa fazer nada. As notas já estão autorizadas.
            </span>
          </p>
        ) : falta > 0 ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-primary-200 bg-primary-50/60 px-4 py-3 dark:border-primary-900/50 dark:bg-primary-900/20">
            <div className="min-w-0 flex-1 text-sm text-slate-700 dark:text-slate-200">
              <p className="font-semibold text-slate-900 dark:text-slate-100">Falta {passosQueFaltam.join(", ").replace(/, ([^,]*)$/, " e $1")}.</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Um clique e eu faço tudo em sequência, em segundo plano. Recusa por CEP eu conserto sozinha; cada nota vai pro e-mail do vendedor que veio no
                relatório.
              </p>
            </div>
            <Button type="button" variant="accent" disabled={ocupado !== ""} onClick={continuar}>
              <PlayCircle size={16} /> {ocupado === "continuar" ? "Começando..." : "Continuar de onde parou"}
            </Button>
          </div>
        ) : (
          <p className="flex items-start gap-2 rounded-xl bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
            <span>
              <strong>Tudo certo com este mês: sua situação está regular.</strong> As {d.autorizadas} notas foram autorizadas pela prefeitura
              {d.enviadas > 0 && ` e ${d.enviadas} chegaram aos vendedores`}.
            </span>
          </p>
        )}
      </div>

      {d.recusadas.length > 0 && !rodando && (
        <div className="mt-3 rounded-xl border border-danger-100 bg-danger-50/60 px-4 py-3 dark:border-danger-900/40 dark:bg-danger-900/20">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-danger-700 dark:text-danger-300">
            <AlertTriangle size={15} /> {d.total_recusadas} nota{d.total_recusadas === 1 ? "" : "s"} recusada{d.total_recusadas === 1 ? "" : "s"} pela prefeitura
          </p>
          <ul className="mt-1.5 flex flex-col gap-1 text-sm">
            {d.recusadas.slice(0, 5).map((r) => (
              <li key={r.emissao_id}>
                <Link to={`/app/nfse/${r.emissao_id}`} className="font-medium text-primary-700 hover:underline dark:text-primary-300">
                  {r.nome || "Nota"} — abrir e corrigir →
                </Link>
                <span className="block text-xs text-slate-600 dark:text-slate-300">{r.motivo}</span>
              </li>
            ))}
          </ul>
          {d.total_recusadas > 5 && (
            <button type="button" onClick={() => onVerNotas(mes, true)} className="mt-1.5 text-xs font-semibold text-primary-600 hover:underline dark:text-primary-300">
              Ver as {d.total_recusadas} na lista
            </button>
          )}
        </div>
      )}

      {d.total_sem_email > 0 && (
        <details className="mt-3 rounded-xl border border-slate-200 px-4 py-2.5 text-sm dark:border-slate-700">
          <summary className="cursor-pointer select-none text-slate-700 dark:text-slate-200">
            {d.total_sem_email} vendedor{d.total_sem_email === 1 ? "" : "es"} não informou e-mail no relatório — essa{d.total_sem_email === 1 ? "" : "s"} nota
            {d.total_sem_email === 1 ? "" : "s"} não te{d.total_sem_email === 1 ? "m" : "êm"} como ser enviada{d.total_sem_email === 1 ? "" : "s"}.{" "}
            <span className="text-slate-400">Não é pendência sua.</span>
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {d.sem_email.map((s) => (
              <li key={s.emissao_id}>
                <Link to={`/app/nfse/${s.emissao_id}`} className="text-primary-700 hover:underline dark:text-primary-300">
                  {s.nome || "Nota"}
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-slate-400">Se o vendedor te passar o e-mail, abra a nota e envie por lá.</p>
        </details>
      )}

      {/* Pacote: os arquivos do mês. */}
      {d.autorizadas > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-700/60">
          <div className="flex flex-wrap items-center gap-2">
            <p className="mr-1 text-sm font-semibold text-slate-800 dark:text-slate-100">Arquivos do mês</p>
            <select
              aria-label="O que vai no pacote"
              value={conteudo}
              onChange={(e) => setConteudo(e.target.value as Conteudo)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            >
              {(Object.keys(ROTULO_CONTEUDO) as Conteudo[]).map((c) => (
                <option key={c} value={c}>
                  {ROTULO_CONTEUDO[c]}
                </option>
              ))}
            </select>
            <button type="button" className={botaoPacote} disabled={ocupado !== ""} onClick={baixar}>
              {ocupado === "zip" ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} {ocupado === "zip" ? "Montando o pacote..." : "Baixar (.zip)"}
            </button>
            <button type="button" className={botaoPacote} disabled={ocupado !== ""} onClick={() => setEmailAberto((v) => !v)} aria-expanded={emailAberto}>
              <Mail size={15} /> Mandar por e-mail
            </button>
            {drive?.disponivel &&
              (drive.conectado ? (
                <button type="button" className={botaoPacote} disabled={ocupado !== "" || rodando} onClick={guardarNoDrive} title={drive.email ? `Drive de ${drive.email}` : undefined}>
                  {ocupado === "drive" ? <Loader2 size={15} className="animate-spin" /> : <FolderUp size={15} />} Guardar no Google Drive
                </button>
              ) : (
                <button type="button" className={botaoPacote} disabled={ocupado !== ""} onClick={conectarDrive}>
                  <FolderUp size={15} /> {ocupado === "conectar" ? "Abrindo o Google..." : "Conectar o Google Drive"}
                </button>
              ))}
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {d.pacote_feito ? (
              <>
                Etapa concluída.{" "}
                <button type="button" className="font-medium underline hover:text-slate-700 dark:hover:text-slate-200" onClick={() => void marcarPacote(false)}>
                  Reabrir
                </button>
              </>
            ) : (
              <>
                Guardar os arquivos é opcional. Não vai compartilhar agora?{" "}
                <button type="button" className="font-semibold text-primary-700 underline hover:text-primary-800 dark:text-primary-300" onClick={() => void marcarPacote(true)}>
                  Marcar como concluído
                </button>
              </>
            )}
          </p>
          {emailAberto && (
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <label className="min-w-[240px] flex-1 text-sm">
                <span className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Pra quem vai o pacote (contador, você...)</span>
                <input
                  value={para}
                  onChange={(e) => setPara(e.target.value)}
                  placeholder="contador@escritorio.com"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <Button type="button" variant="accent" disabled={ocupado !== ""} onClick={mandarPorEmail}>
                {ocupado === "email" ? "Enviando..." : "Enviar o pacote"}
              </Button>
              <p className="w-full text-xs text-slate-400">Vai um e-mail só, com o .zip das {d.autorizadas} notas em anexo.</p>
            </div>
          )}
          {drive?.conectado && drive.email && (
            <p className="mt-2 text-xs text-slate-400">
              Google Drive conectado ({drive.email}) — os arquivos vão pra pasta “Agente Ana”.{" "}
              <button
                type="button"
                className="underline hover:text-slate-600"
                onClick={() => api.delete("/drive").then(() => setDrive({ disponivel: true, conectado: false, email: null })).catch(() => undefined)}
              >
                desconectar
              </button>
            </p>
          )}
        </div>
      )}

      <button type="button" onClick={() => onVerNotas(mes)} className="mt-3 text-xs font-semibold text-primary-600 hover:underline dark:text-primary-300">
        Ver as notas deste mês na lista ↓
      </button>
    </Card>
  )
}
