import { Plus } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../lib/format"
import type { Calendario, EventoCalendario, TipoEventoCalendario } from "../lib/types"

const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

// Usa os tons -600 (não -500) de warning/success de propósito: só -50/-600/-700
// estão definidos em src/index.css pra essas duas escalas (ver @theme) — -500
// só existe pra primary. Um bg-warning-500/bg-success-500 aqui renderizaria
// sem cor nenhuma (bolinha invisível), erro encontrado na 1ª verificação visual.
const ESTILO_EVENTO: Record<TipoEventoCalendario, { dot: string; chip: string; label: string }> = {
  prazo_emissao: { dot: "bg-warning-600", chip: "bg-warning-50 text-warning-700", label: "Prazo pra emitir a nota" },
  recebimento_previsto: { dot: "bg-primary-600", chip: "bg-primary-50 text-primary-700", label: "Previsão de recebimento" },
  recebimento_confirmado: { dot: "bg-success-600", chip: "bg-success-50 text-success-700", label: "Recebimento confirmado" },
  revisar_aliquota: { dot: "bg-slate-500", chip: "bg-slate-100 text-slate-700", label: "Revisar alíquota do Simples Nacional" },
  manual: { dot: "bg-accent-600", chip: "bg-accent-50 text-accent-700", label: "Evento (meu)" },
}

function paraISO(data: Date): string {
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, "0")}-${String(data.getDate()).padStart(2, "0")}`
}

// Início da grade visual do mês: volta até o domingo anterior (ou o próprio
// dia 1, se já for domingo) — padrão de calendário estilo Google Agenda.
function inicioGradeDoMes(competencia: string): Date {
  const [ano, mes] = competencia.split("-").map(Number)
  const primeiroDia = new Date(ano, mes - 1, 1)
  const inicio = new Date(primeiroDia)
  inicio.setDate(inicio.getDate() - primeiroDia.getDay())
  return inicio
}

export function CalendarioPage() {
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [calendario, setCalendario] = useState<Calendario | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [recarregarToken, setRecarregarToken] = useState(0)

  // null = fechado; string = modal de "novo evento" pré-preenchido com essa
  // data ISO; EventoCalendario = modal de edição de um evento manual existente.
  const [modalEvento, setModalEvento] = useState<string | EventoCalendario | null>(null)

  const [ano, mes] = competencia.split("-").map(Number)

  // 6 semanas x 7 dias cobre qualquer mês (inclusive os que começam no
  // sábado e têm 31 dias, que precisam de 6 linhas).
  const dias = useMemo(() => {
    const inicio = inicioGradeDoMes(competencia)
    return Array.from({ length: 42 }, (_, i) => {
      const data = new Date(inicio)
      data.setDate(inicio.getDate() + i)
      return data
    })
  }, [competencia])

  useEffect(() => {
    let cancelado = false
    setCarregando(true)
    setErro(null)
    const inicio = paraISO(dias[0])
    const fim = paraISO(dias[dias.length - 1])
    api
      .get<Calendario>(`/calendario?inicio=${inicio}&fim=${fim}`)
      .then((dados) => {
        if (!cancelado) setCalendario(dados)
      })
      .catch((err) => {
        if (!cancelado) setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
      })
      .finally(() => {
        if (!cancelado) setCarregando(false)
      })
    return () => {
      cancelado = true
    }
  }, [dias, recarregarToken])

  const eventosPorDia = useMemo(() => {
    const mapa = new Map<string, EventoCalendario[]>()
    for (const ev of calendario?.eventos ?? []) {
      const lista = mapa.get(ev.data) ?? []
      lista.push(ev)
      mapa.set(ev.data, lista)
    }
    return mapa
  }, [calendario])

  const hojeISO = paraISO(new Date())

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Calendário</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Prazos de emissão, previsões de recebimento e seus próprios eventos.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm">
            <button
              type="button"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))}
              className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              ‹
            </button>
            <span className="min-w-[9rem] text-center font-medium text-slate-700 dark:text-slate-300">{formatCompetenciaLonga(competencia)}</span>
            <button
              type="button"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
              className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              ›
            </button>
          </div>
          <Button type="button" variant="accent" onClick={() => setModalEvento(paraISO(new Date()))}>
            <Plus size={16} /> Novo evento
          </Button>
        </div>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      <div className="flex flex-wrap gap-4">
        {(Object.entries(ESTILO_EVENTO) as [TipoEventoCalendario, (typeof ESTILO_EVENTO)[TipoEventoCalendario]][]).map(
          ([tipo, estilo]) => (
            <div key={tipo} className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <span className={`h-2 w-2 rounded-full ${estilo.dot}`} />
              {estilo.label}
            </div>
          )
        )}
      </div>

      <Card className="overflow-hidden p-0">
        <div className="grid grid-cols-7 border-b border-slate-100 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-900/40 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          {DIAS_SEMANA.map((d) => (
            <div key={d} className="px-3 py-2 text-center">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {dias.map((data) => {
            const iso = paraISO(data)
            const doMes = data.getMonth() === mes - 1 && data.getFullYear() === ano
            const eventos = eventosPorDia.get(iso) ?? []
            const ehHoje = iso === hojeISO
            return (
              <div
                key={iso}
                onClick={() => setModalEvento(iso)}
                className={`group min-h-[7rem] cursor-pointer border-b border-r border-slate-100 dark:border-slate-700/60 p-2 [&:nth-child(7n)]:border-r-0 hover:bg-slate-50 dark:hover:bg-slate-700/40 ${
                  doMes ? "bg-white dark:bg-slate-800" : "bg-slate-50/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      ehHoje ? "bg-primary-600 text-white" : doMes ? "text-slate-700 dark:text-slate-300" : "text-slate-300"
                    }`}
                  >
                    {data.getDate()}
                  </span>
                  <Plus size={13} className="text-slate-300 opacity-0 group-hover:opacity-100 dark:text-slate-500" />
                </div>
                <div className="mt-1 flex flex-col gap-1">
                  {eventos.slice(0, 3).map((ev, i) => (
                    <div
                      key={i}
                      title={ev.descricao ? `${ev.titulo} — ${ev.descricao}` : ev.titulo}
                      onClick={(e) => {
                        if (ev.tipo === "manual") {
                          e.stopPropagation()
                          setModalEvento(ev)
                        }
                      }}
                      className={`truncate rounded px-1.5 py-0.5 text-[11px] font-medium ${ESTILO_EVENTO[ev.tipo].chip}`}
                    >
                      {ev.apelido ?? ev.titulo}
                      {ev.valor != null && <span className="ml-1 opacity-70">{formatBRL(ev.valor)}</span>}
                    </div>
                  ))}
                  {eventos.length > 3 && <span className="text-[11px] text-slate-400 dark:text-slate-500">+{eventos.length - 3} mais</span>}
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {carregando && !calendario && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {modalEvento !== null && (
        <EventoModal
          alvo={modalEvento}
          onClose={() => setModalEvento(null)}
          onSalvo={() => {
            setModalEvento(null)
            setRecarregarToken((t) => t + 1)
          }}
        />
      )}
    </div>
  )
}

function EventoModal({
  alvo,
  onClose,
  onSalvo,
}: {
  alvo: string | EventoCalendario
  onClose: () => void
  onSalvo: () => void
}) {
  const editando = typeof alvo !== "string"
  const [data, setData] = useState(editando ? alvo.data : alvo)
  const [titulo, setTitulo] = useState(editando ? alvo.titulo : "")
  const [descricao, setDescricao] = useState(editando ? (alvo.descricao ?? "") : "")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      if (editando) {
        await api.patch(`/calendario/eventos/${alvo.id}`, { data, titulo, descricao: descricao || null })
      } else {
        await api.post("/calendario/eventos", { data, titulo, descricao: descricao || null })
      }
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  async function onExcluir() {
    if (!editando) return
    setErro(null)
    setEnviando(true)
    try {
      await api.delete(`/calendario/eventos/${alvo.id}`)
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      setEnviando(false)
    }
  }

  return (
    <Modal titulo={editando ? "Editar evento" : "Novo evento"} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
        <Field label="Data" type="date" required value={data} onChange={(e) => setData(e.target.value)} />
        <Field label="Título" required value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder='Ex.: "Reunião com contador"' />
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Descrição (opcional)</span>
          <textarea
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <div className="flex justify-between gap-3 pt-2">
          {editando ? (
            <Button type="button" variant="outline" onClick={onExcluir} disabled={enviando}>
              Excluir
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={enviando}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
