import { AlertTriangle, CheckCircle2, ChevronDown, Loader2, PauseCircle, X, XCircle } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, api, formatarErro } from "../lib/api"
import { LOTE_RODANDO, NOME_ACAO, POR_QUE_NENHUMA, VERBO_ACAO } from "../lib/lotes"
import type { CriarLoteBody, Lote, PreviaLote } from "../lib/types"
import { Badge } from "./ui/Badge"
import { Button } from "./ui/Button"
import { Modal } from "./ui/Modal"

// Ações em lote (29/09/2026) — "enviar todas" da Shopee e a seleção múltipla
// da lista de NFS-e, como no MandaNotas. O backend roda o lote em segundo
// plano (app/services/lotes.py); aqui só confirmamos antes (POST
// /lotes/previa) e acompanhamos o progresso (GET /lotes/{id} a cada 2s).

function mensagemErro(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

/** Confirmação antes de criar o lote: pergunta ao backend quantas notas a
 * ação vai pegar e só cria (POST /lotes) depois do "Confirmar". */
export function ConfirmarLoteModal({
  titulo,
  body,
  totalSelecionadas,
  alvo,
  permitirReenviar = false,
  aviso,
  onClose,
  onCriado,
}: {
  titulo?: string
  body: CriarLoteBody
  /** N da seleção ("X de N"); sem ele (filtro), mostra só X. */
  totalSelecionadas?: number
  /** Complemento da frase quando é por filtro ("de Shopee em Agosto de 2026"). */
  alvo?: string
  /** Mostra "incluir as já enviadas (reenviar)" — só pras ações de e-mail. */
  permitirReenviar?: boolean
  aviso?: string
  onClose: () => void
  onCriado: (lote: Lote) => void
}) {
  const [reenviar, setReenviar] = useState(Boolean(body.reenviar))
  const [previa, setPrevia] = useState<PreviaLote | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [criando, setCriando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const corpo: CriarLoteBody = { ...body, reenviar }
  const chave = JSON.stringify(corpo)

  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .post<PreviaLote>("/lotes/previa", JSON.parse(chave))
      .then((p) => vivo && setPrevia(p))
      .catch((err) => {
        if (!vivo) return
        setPrevia(null)
        setErro(mensagemErro(err))
      })
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [chave])

  async function confirmar() {
    setCriando(true)
    setErro(null)
    try {
      const lote = await api.post<Lote>("/lotes", corpo)
      onCriado(lote)
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setCriando(false)
    }
  }

  const quantidade = previa?.quantidade ?? 0
  const verbo = VERBO_ACAO[body.acao]

  return (
    <Modal titulo={titulo ?? NOME_ACAO[body.acao]} onClose={onClose}>
      <div className="flex flex-col gap-4">
        {erro && (
          <p role="alert" className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
            {erro}
          </p>
        )}

        <div aria-live="polite" className="text-sm text-slate-700 dark:text-slate-200">
          {carregando ? (
            <p className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
              <Loader2 size={16} className="animate-spin" /> Conferindo as notas...
            </p>
          ) : previa && quantidade > 0 ? (
            totalSelecionadas != null ? (
              <p>
                <strong className="text-base text-slate-900 dark:text-slate-100">
                  {quantidade} de {totalSelecionadas}
                </strong>{" "}
                {totalSelecionadas === 1 ? "nota está pronta" : "notas estão prontas"} para {verbo}.
                {quantidade < totalSelecionadas && (
                  <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">
                    {totalSelecionadas - quantidade === 1 ? "A outra fica" : `As outras ${totalSelecionadas - quantidade} ficam`} de fora.{" "}
                    {POR_QUE_NENHUMA[body.acao]}
                  </span>
                )}
              </p>
            ) : (
              <p>
                <strong className="text-base text-slate-900 dark:text-slate-100">{quantidade}</strong>{" "}
                {quantidade === 1 ? "nota" : "notas"}
                {alvo ? ` ${alvo}` : ""} {quantidade === 1 ? "está pronta" : "estão prontas"} para {verbo}.
              </p>
            )
          ) : previa ? (
            <p className="rounded-lg bg-warning-50 px-4 py-3 text-warning-700">
              <strong>Nenhuma nota</strong> {totalSelecionadas != null ? "da seleção " : alvo ? `${alvo} ` : ""}está pronta para {verbo}.{" "}
              {POR_QUE_NENHUMA[body.acao]}
              {permitirReenviar && !reenviar && " Se quiser mandar de novo as que já foram, marque a opção abaixo."}
            </p>
          ) : null}
        </div>

        {permitirReenviar && (
          <label className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={reenviar}
              onChange={(e) => setReenviar(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-primary-600"
            />
            <span>
              Incluir as já enviadas (reenviar)
              <span className="block text-xs text-slate-400 dark:text-slate-500">
                Sem marcar, vão só as que ainda não foram enviadas — inclusive as que falharam.
              </span>
            </span>
          </label>
        )}

        {aviso && <p className="text-xs text-slate-500 dark:text-slate-400">{aviso}</p>}

        {!carregando && quantidade > 0 && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Roda em segundo plano, uma nota por vez — dá pra continuar usando o sistema e acompanhar no canto da tela.
          </p>
        )}

        <div className="flex flex-wrap justify-end gap-3 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            {quantidade > 0 || carregando ? "Cancelar" : "Fechar"}
          </Button>
          {(carregando || quantidade > 0) && (
            <Button type="button" variant="accent" onClick={confirmar} disabled={carregando || criando || quantidade === 0}>
              {criando ? "Iniciando..." : `Confirmar (${quantidade})`}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}

/** Painel fixo no canto da tela com o progresso do lote. */
export function LotePainel({
  lote,
  onMudou,
  onFechar,
  onTerminou,
}: {
  lote: Lote
  /** Lote atualizado (polling, cancelar, retomar) ou NOVO (refazer falhas). */
  onMudou: (lote: Lote) => void
  onFechar: () => void
  /** O lote acabou de sair de fila/executando — hora de recarregar a lista. */
  onTerminou: () => void
}) {
  const [agindo, setAgindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [verErros, setVerErros] = useState(false)
  const rodando = LOTE_RODANDO(lote)

  // Callbacks mais recentes sem reiniciar o polling a cada render do pai.
  const cb = useRef({ onMudou, onTerminou })
  useEffect(() => {
    cb.current = { onMudou, onTerminou }
  })

  // Polling a cada 2s enquanto roda (setTimeout encadeado: nunca sobrepõe
  // duas requisições). Um erro de rede isolado não para o acompanhamento.
  useEffect(() => {
    if (!rodando) return
    let vivo = true
    let timer: ReturnType<typeof setTimeout>
    const passo = () => {
      timer = setTimeout(async () => {
        try {
          const atual = await api.get<Lote>(`/lotes/${lote.id}`)
          if (!vivo) return
          cb.current.onMudou(atual)
          if (LOTE_RODANDO(atual)) passo()
        } catch {
          if (vivo) passo()
        }
      }, 2000)
    }
    passo()
    return () => {
      vivo = false
      clearTimeout(timer)
    }
  }, [lote.id, rodando])

  // Terminou (concluído/cancelado/interrompido) depois de estar rodando.
  const anterior = useRef<{ id: string; rodando: boolean }>({ id: lote.id, rodando })
  useEffect(() => {
    const antes = anterior.current
    if (antes.id === lote.id && antes.rodando && !rodando) cb.current.onTerminou()
    anterior.current = { id: lote.id, rodando }
  }, [lote.id, rodando])

  async function acao(caminho: string) {
    setAgindo(true)
    setErro(null)
    try {
      const resp = await api.post<Lote>(`/lotes/${lote.id}/${caminho}`)
      cb.current.onMudou(resp)
      if (caminho === "refazer-falhas") setVerErros(false)
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setAgindo(false)
    }
  }

  const processadas = lote.feitos + lote.falhas
  const pct = lote.total > 0 ? Math.min(100, Math.round((processadas / lote.total) * 100)) : 0
  const pctFeitos = lote.total > 0 ? (lote.feitos / lote.total) * 100 : 0
  const pctFalhas = lote.total > 0 ? (lote.falhas / lote.total) * 100 : 0

  const status = {
    fila: { label: "Na fila", variant: "info" as const, icone: <Loader2 size={16} className="animate-spin text-primary-600" /> },
    executando: { label: "Em andamento", variant: "info" as const, icone: <Loader2 size={16} className="animate-spin text-primary-600" /> },
    concluido:
      lote.falhas > 0
        ? { label: "Concluído com falhas", variant: "warning" as const, icone: <AlertTriangle size={16} className="text-warning-600" /> }
        : { label: "Concluído", variant: "success" as const, icone: <CheckCircle2 size={16} className="text-success-600" /> },
    cancelado: { label: "Cancelado", variant: "neutral" as const, icone: <XCircle size={16} className="text-slate-500" /> },
    interrompido: { label: "Interrompido", variant: "warning" as const, icone: <PauseCircle size={16} className="text-warning-600" /> },
  }[lote.status]

  return (
    <section
      aria-label={`Ação em lote: ${NOME_ACAO[lote.acao]}`}
      className="fixed inset-x-4 bottom-4 z-40 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-slate-900/10 dark:border-slate-700 dark:bg-slate-800 dark:shadow-black/40 sm:left-auto sm:right-6 sm:w-96"
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0">{status.icone}</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{NOME_ACAO[lote.acao]}</p>
          <div className="mt-0.5" aria-live="polite">
            <Badge variant={status.variant}>{status.label}</Badge>
          </div>
        </div>
        {!rodando && (
          <button
            type="button"
            onClick={onFechar}
            aria-label="Fechar painel"
            className="-mr-1 -mt-1 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div
        role="progressbar"
        aria-label="Progresso"
        aria-valuemin={0}
        aria-valuemax={lote.total}
        aria-valuenow={processadas}
        aria-valuetext={`${processadas} de ${lote.total}`}
        className="mt-3 flex h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"
      >
        <div className="h-full bg-success-500 transition-all duration-500" style={{ width: `${pctFeitos}%` }} />
        <div className="h-full bg-danger-500 transition-all duration-500" style={{ width: `${pctFalhas}%` }} />
      </div>
      <p className="mt-2 flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span>
          <strong className="text-slate-700 dark:text-slate-200">{processadas}</strong> de {lote.total} · {pct}%
        </span>
        <span>
          <span className="text-success-700 dark:text-success-300">{lote.feitos} ok</span>
          {" · "}
          <span className={lote.falhas > 0 ? "text-danger-600 dark:text-danger-300" : ""}>
            {lote.falhas} falha{lote.falhas === 1 ? "" : "s"}
          </span>
        </span>
      </p>

      {rodando && lote.acao === "completo" && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          Pode fechar esta página: eu continuo sozinha e te mando o relatório por e-mail quando acabar. Ele também fica aqui em Notas em
          lote.
        </p>
      )}
      {!rodando && (lote.linhas_relatorio ?? []).length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-slate-600 dark:text-slate-300">
          {(lote.linhas_relatorio ?? []).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      {lote.status === "interrompido" && (
        <p className="mt-2 text-xs text-warning-700 dark:text-warning-300">
          O servidor reiniciou no meio. Retome pra continuar de onde parou.
        </p>
      )}

      {erro && (
        <p role="alert" className="mt-2 rounded-lg bg-danger-50 px-3 py-2 text-xs text-danger-700">
          {erro}
        </p>
      )}

      {lote.erros.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setVerErros((v) => !v)}
            aria-expanded={verErros}
            className="flex items-center gap-1 text-xs font-medium text-primary-700 hover:underline dark:text-primary-300"
          >
            <ChevronDown size={14} className={`transition-transform ${verErros ? "rotate-180" : ""}`} />
            {verErros ? "Esconder" : "Ver"} {lote.erros.length === 1 ? "o erro" : `os ${lote.erros.length} erros`}
          </button>
          {verErros && (
            <ul className="mt-2 max-h-48 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-100 text-xs dark:divide-slate-700/60 dark:border-slate-700/60">
              {lote.erros.map((e, i) => (
                <li key={`${e.emissao_id}-${i}`} className="px-3 py-2">
                  <Link to={`/app/nfse/${e.emissao_id}`} className="font-medium text-primary-700 hover:underline dark:text-primary-300">
                    {e.nome || "Nota"}
                  </Link>
                  <span className="block text-slate-500 dark:text-slate-400">{e.erro}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(rodando || lote.status === "interrompido" || (lote.status === "concluido" && lote.falhas > 0)) && (
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          {(rodando || lote.status === "interrompido") && (
            <Button type="button" variant="outline" className="px-3 py-1.5" disabled={agindo} onClick={() => acao("cancelar")}>
              Cancelar
            </Button>
          )}
          {lote.status === "interrompido" && (
            <Button type="button" variant="accent" className="px-3 py-1.5" disabled={agindo} onClick={() => acao("retomar")}>
              Retomar
            </Button>
          )}
          {lote.status === "concluido" && lote.falhas > 0 && (
            <Button type="button" variant="accent" className="px-3 py-1.5" disabled={agindo} onClick={() => acao("refazer-falhas")}>
              {agindo ? "Iniciando..." : `Refazer falhas (${lote.falhas})`}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}

const PASSO_ROTULO: Record<string, string> = { assinar: "assinar", submeter: "enviar à prefeitura", email: "mandar por e-mail" }

function quando(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  return `${d.toLocaleDateString("pt-BR")} às ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`
}

const STATUS_LOTE: Record<Lote["status"], string> = {
  fila: "Na fila",
  executando: "Em andamento",
  concluido: "Concluído",
  cancelado: "Cancelado",
  interrompido: "Interrompido",
}

/** Relatório de status de um lote (05/10/2026): "quando acabar geramos um
 * relatório pra ela ver o que aconteceu" — o que foi feito em cada passo e,
 * nota por nota, o que ficou pra trás e por quê. */
export function RelatorioLoteModal({ lote, onClose, onRefazer }: { lote: Lote; onClose: () => void; onRefazer?: (novo: Lote) => void }) {
  const [agindo, setAgindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const rodando = LOTE_RODANDO(lote)

  async function refazer() {
    setAgindo(true)
    setErro(null)
    try {
      onRefazer?.(await api.post<Lote>(`/lotes/${lote.id}/refazer-falhas`))
      onClose()
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setAgindo(false)
    }
  }

  function baixarCsv() {
    const linhas = [["Nota", "O que aconteceu"], ...lote.erros.map((e) => [e.nome || "Nota", e.erro])]
    const csv = linhas.map((l) => l.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\r\n")
    const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }))
    const a = document.createElement("a")
    a.href = url
    a.download = "relatorio-notas-em-lote.csv"
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  }

  return (
    <Modal titulo={`Relatório — ${NOME_ACAO[lote.acao]}`} onClose={onClose} largura="max-w-2xl">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {STATUS_LOTE[lote.status]}
          {lote.criado_em && ` · começou em ${quando(lote.criado_em)}`}
          {lote.concluido_em && ` · terminou em ${quando(lote.concluido_em)}`}
          {(lote.passos ?? []).length > 0 && ` · passos: ${(lote.passos ?? []).map((p) => PASSO_ROTULO[p] ?? p).join(", ")}`}
        </p>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-900/40">
            <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{lote.total}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">notas no lote</p>
          </div>
          <div className="rounded-xl bg-success-50 px-3 py-3 dark:bg-success-900/30">
            <p className="text-2xl font-semibold text-success-700 dark:text-success-300">{lote.feitos}</p>
            <p className="text-xs text-success-700 dark:text-success-300">deram certo</p>
          </div>
          <div className={`rounded-xl px-3 py-3 ${lote.falhas > 0 ? "bg-danger-50 dark:bg-danger-900/30" : "bg-slate-50 dark:bg-slate-900/40"}`}>
            <p className={`text-2xl font-semibold ${lote.falhas > 0 ? "text-danger-700 dark:text-danger-300" : "text-slate-900 dark:text-slate-100"}`}>{lote.falhas}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">precisam de atenção</p>
          </div>
        </div>
        {rodando && (
          <p className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
            Ainda está rodando ({lote.feitos + lote.falhas} de {lote.total}). Pode fechar a página — o relatório completo fica aqui.
          </p>
        )}
        {(lote.linhas_relatorio ?? []).length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">O que foi feito</p>
            <ul className="list-disc pl-5 text-sm text-slate-700 dark:text-slate-200">
              {(lote.linhas_relatorio ?? []).map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        )}
        {lote.erros.length > 0 ? (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Notas que precisam de atenção</p>
            <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-100 text-sm dark:divide-slate-700/60 dark:border-slate-700/60">
              {lote.erros.map((e, i) => (
                <li key={`${e.emissao_id}-${i}`} className="px-3 py-2">
                  <Link to={`/app/nfse/${e.emissao_id}`} className="font-medium text-primary-700 hover:underline dark:text-primary-300">
                    {e.nome || "Nota"}
                  </Link>
                  <span className="block text-xs text-slate-500 dark:text-slate-400">{e.erro}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          !rodando && <p className="rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">Nenhuma nota ficou pra trás.</p>
        )}
        {erro && (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            {erro}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          {lote.erros.length > 0 && (
            <Button type="button" variant="outline" onClick={baixarCsv}>
              Baixar a lista (.csv)
            </Button>
          )}
          {onRefazer && lote.status === "concluido" && lote.falhas > 0 && (
            <Button type="button" variant="outline" disabled={agindo} onClick={refazer}>
              {agindo ? "Iniciando..." : `Tentar de novo as ${lote.falhas} que falharam`}
            </Button>
          )}
          <Button type="button" variant="accent" onClick={onClose}>
            Fechar
          </Button>
        </div>
      </div>
    </Modal>
  )
}
