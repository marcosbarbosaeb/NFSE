import { useEffect, useMemo, useState } from "react"
import { Card } from "../components/ui/Card"
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
  }, [dias])

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
          <p className="text-sm text-slate-500 dark:text-slate-400">Prazos de emissão e previsões de recebimento, mês a mês.</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800">
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
                className={`min-h-[7rem] border-b border-r border-slate-100 dark:border-slate-700/60 p-2 [&:nth-child(7n)]:border-r-0 ${
                  doMes ? "bg-white dark:bg-slate-800" : "bg-slate-50/60"
                }`}
              >
                <span
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                    ehHoje ? "bg-primary-600 text-white" : doMes ? "text-slate-700 dark:text-slate-300" : "text-slate-300"
                  }`}
                >
                  {data.getDate()}
                </span>
                <div className="mt-1 flex flex-col gap-1">
                  {eventos.slice(0, 3).map((ev, i) => (
                    <div
                      key={i}
                      title={ev.titulo}
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
    </div>
  )
}
