import { AgendaAssinatura } from "../components/integracoes/AgendaAssinatura"
import { CaixaBusca } from "../components/ui/CaixaBusca"
import { MoedaField } from "../components/ui/CampoMoeda"
import { Bell, CalendarClock, CalendarPlus, CheckCircle2, ChevronLeft, ChevronRight, FileText, type LucideIcon, Pencil, Percent, Plus, RotateCcw, Wallet } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga, parseBRL } from "../lib/format"
import { useModulos } from "../lib/modulos"
import type { Calendario, CategoriaEventoManual, EventoCalendario, TipoEventoCalendario, VinculoResumo } from "../lib/types"

const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

// Usa os tons -600 (não -500) de warning/success de propósito: só -50/-600/-700
// estão definidos em src/index.css pra essas duas escalas (ver @theme) — -500
// só existe pra primary. Um bg-warning-500/bg-success-500 aqui renderizaria
// sem cor nenhuma (bolinha invisível), erro encontrado na 1ª verificação visual.
// 08/10/2026: "algum símbolo além do código de cores" — cada tipo tem também
// um ícone, na legenda, nos eventos da grade e no painel do dia.
const ESTILO_EVENTO: Record<TipoEventoCalendario, { dot: string; chip: string; label: string; Icone: LucideIcon }> = {
  prazo_emissao: { dot: "bg-warning-600", chip: "bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300", label: "Dia de gerar a nota", Icone: FileText },
  recebimento_previsto: { dot: "bg-primary-600", chip: "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-200", label: "Previsão de recebimento", Icone: CalendarClock },
  recebimento_confirmado: { dot: "bg-success-600", chip: "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300", label: "Recebimento confirmado", Icone: CheckCircle2 },
  revisar_aliquota: { dot: "bg-slate-500", chip: "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200", label: "Revisar alíquota do Simples Nacional", Icone: Percent },
  manual: { dot: "bg-accent-600", chip: "bg-accent-50 text-accent-700 dark:bg-accent-900/30 dark:text-accent-200", label: "Evento (meu)", Icone: Bell },
}

function nomeDoEvento(ev: EventoCalendario): string {
  return ev.tipo === "manual" ? ev.titulo : (ev.apelido ?? ev.titulo)
}

function iconeDoEvento(ev: EventoCalendario): LucideIcon {
  if (ev.tipo === "manual" && ev.categoria === "recebimento_previsto") return Wallet
  if (ev.tipo === "manual" && ev.categoria === "prazo_emissao") return FileText
  return ESTILO_EVENTO[ev.tipo].Icone
}

/** O que dá pra fazer com o evento fora do calendário (a "outra ponta"). */
function acaoDoEvento(ev: EventoCalendario): { rotulo: string; link: string } | null {
  if (ev.tipo === "prazo_emissao" && ev.vinculo_id) {
    const competencia = ev.chave?.split(":")[1]
    return { rotulo: "Gerar a nota", link: `/app/nfse?gerar=${ev.vinculo_id}${competencia ? `&competencia=${competencia}` : ""}` }
  }
  if (ev.tipo === "recebimento_previsto") return { rotulo: "Conferir na conciliação", link: "/app/financeiro/conciliacao?parte=notas&filtro=abertas" }
  if (ev.tipo === "recebimento_confirmado") return { rotulo: "Ver no Financeiro", link: "/app/financeiro" }
  if (ev.tipo === "revisar_aliquota") return { rotulo: "Revisar a alíquota", link: "/app/empresa?aba=emitente" }
  return null
}

// Eventos manuais herdam a cor do tipo que representam (uma previsão de
// recebimento lançada à mão fica azul como as calculadas).
const ESTILO_CATEGORIA: Record<CategoriaEventoManual, { chip: string; label: string }> = {
  lembrete: { chip: ESTILO_EVENTO.manual.chip, label: "Lembrete" },
  recebimento_previsto: { chip: "bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-200", label: "Previsão de recebimento" },
  prazo_emissao: { chip: "bg-warning-50 text-warning-700 ring-1 ring-inset ring-warning-600/30", label: "Prazo" },
}

const AJUSTAVEIS: TipoEventoCalendario[] = ["prazo_emissao", "recebimento_previsto", "revisar_aliquota"]

function estiloChip(ev: EventoCalendario): string {
  if (ev.tipo === "manual" && ev.categoria) return ESTILO_CATEGORIA[ev.categoria].chip
  return ESTILO_EVENTO[ev.tipo].chip
}

function dataBR(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number)
  return new Date(a, m - 1, d).toLocaleDateString("pt-BR")
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
  // Recebimentos no calendário só existem pra quem tem o módulo financeiro.
  const { financeiro } = useModulos()
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [calendario, setCalendario] = useState<Calendario | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [recarregarToken, setRecarregarToken] = useState(0)

  // null = fechado; string = modal de "novo evento" pré-preenchido com essa
  // data ISO; EventoCalendario = modal de edição de um evento manual existente.
  const [modalEvento, setModalEvento] = useState<string | EventoCalendario | null>(null)
  // Alerta calculado clicado -> modal de ajuste (só esta vez / regra).
  const [modalAjuste, setModalAjuste] = useState<EventoCalendario | null>(null)
  // 08/10/2026: "quando a pessoa clicar no dia ela tem que poder editar todos
  // os eventos marcados para aquele dia". Clicar no dia abre o painel do dia;
  // editar um evento fecha o painel e, ao terminar, volta pra ele.
  const [diaAberto, setDiaAberto] = useState<string | null>(null)
  // Link de assinatura (08/10/2026): o mesmo de Empresa › Integrações.
  const [modalAgenda, setModalAgenda] = useState(false)
  const [voltarAoDia, setVoltarAoDia] = useState<string | null>(null)
  function editarDoDia(ev: EventoCalendario) {
    setVoltarAoDia(ev.data)
    setDiaAberto(null)
    if (ev.tipo === "manual") setModalEvento(ev)
    else setModalAjuste(ev)
  }
  function fecharEdicao() {
    setModalEvento(null)
    setModalAjuste(null)
    if (voltarAoDia) setDiaAberto(voltarAoDia)
    setVoltarAoDia(null)
  }
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos).catch(() => {})
  }, [])

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
          <p className="text-sm text-slate-500 dark:text-slate-400">{financeiro ? "Prazos de emissão, previsões de recebimento e seus próprios eventos." : "Prazos de emissão e seus próprios eventos."}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm">
            <button
              type="button"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))}
              className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
              aria-label="Mês anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="min-w-[9rem] text-center font-medium text-slate-700 dark:text-slate-300">{formatCompetenciaLonga(competencia)}</span>
            <button
              type="button"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
              className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
              aria-label="Próximo mês"
            >
              <ChevronRight size={16} />
            </button>
          </div>
          <Button type="button" variant="outline" onClick={() => setModalAgenda(true)} title="Ver estes eventos no Google Agenda (ou Outlook/Apple)">
            <CalendarPlus size={16} /> <span className="hidden sm:inline">No Google Agenda</span>
          </Button>
          <Button type="button" variant="accent" onClick={() => setModalEvento(paraISO(new Date()))}>
            <Plus size={16} /> Novo evento
          </Button>
        </div>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      <div className="flex flex-wrap gap-4">
        {(Object.entries(ESTILO_EVENTO) as [TipoEventoCalendario, (typeof ESTILO_EVENTO)[TipoEventoCalendario]][])
          .filter(([tipo]) => financeiro || !tipo.startsWith("recebimento"))
          .map(([tipo, estilo]) => (
            <div key={tipo} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
              <span className={`inline-flex h-5 w-5 items-center justify-center rounded-md ${estilo.chip}`} aria-hidden>
                <estilo.Icone size={12} />
              </span>
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
              <button
                type="button"
                key={iso}
                onClick={() => setDiaAberto(iso)}
                aria-label={`${dataBR(iso)}: ${eventos.length === 0 ? "nenhum evento" : `${eventos.length} ${eventos.length === 1 ? "evento" : "eventos"}`}. Abrir o dia`}
                className={`group flex min-h-[5.5rem] flex-col border-b border-r border-slate-100 p-1.5 text-left align-top [&:nth-child(7n)]:border-r-0 hover:bg-slate-50 focus-visible:relative focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-primary-500 sm:min-h-[7rem] sm:p-2 dark:border-slate-700/60 dark:hover:bg-slate-700/40 ${
                  doMes ? "bg-white dark:bg-slate-800" : "bg-slate-50/60 dark:bg-slate-900/30"
                } ${ehHoje ? "ring-2 ring-inset ring-primary-500/40" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      ehHoje ? "bg-primary-600 text-white" : doMes ? "text-slate-700 dark:text-slate-300" : "text-slate-300 dark:text-slate-600"
                    }`}
                  >
                    {data.getDate()}
                  </span>
                  {eventos.length > 0 ? (
                    <span className="text-[10px] font-medium text-slate-400 sm:hidden dark:text-slate-500">{eventos.length}</span>
                  ) : (
                    <Plus size={13} className="text-slate-300 opacity-0 group-hover:opacity-100 dark:text-slate-500" />
                  )}
                </div>
                {/* celular: só os ícones; tela grande: ícone + nome */}
                <div className="mt-1 flex flex-wrap gap-0.5 sm:hidden" aria-hidden>
                  {eventos.slice(0, 4).map((ev, i) => {
                    const Icone = iconeDoEvento(ev)
                    return (
                      <span key={i} className={`inline-flex h-4 w-4 items-center justify-center rounded ${estiloChip(ev)}`}>
                        <Icone size={10} />
                      </span>
                    )
                  })}
                </div>
                <div className="mt-1 hidden w-full flex-col gap-1 sm:flex" aria-hidden>
                  {eventos.slice(0, 3).map((ev, i) => {
                    const Icone = iconeDoEvento(ev)
                    return (
                      <span
                        key={i}
                        title={
                          (ev.descricao ? `${ev.titulo} — ${ev.descricao}` : ev.titulo) +
                          (ev.ajustado && ev.data_original ? ` (data ajustada; original ${dataBR(ev.data_original)})` : "")
                        }
                        className={`flex min-w-0 items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${estiloChip(ev)} ${ev.ajustado ? "italic" : ""}`}
                      >
                        <Icone size={11} className="shrink-0" />
                        <span className="truncate">{ev.tipo === "manual" ? ev.titulo : (ev.apelido ?? ev.titulo)}</span>
                        {ev.ajustado && <RotateCcw size={9} className="shrink-0" />}
                      </span>
                    )
                  })}
                  {eventos.length > 3 && <span className="text-[11px] font-medium text-primary-600 dark:text-primary-300">+{eventos.length - 3} mais</span>}
                </div>
              </button>
            )
          })}
        </div>
      </Card>

      {carregando && !calendario && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {modalAgenda && (
        <Modal titulo="Ver no Google Agenda" onClose={() => setModalAgenda(false)}>
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
            Cole este link uma vez na sua agenda e os eventos daqui aparecem lá (o Google atualiza sozinho, com algumas horas de atraso).
          </p>
          <AgendaAssinatura />
        </Modal>
      )}
      {diaAberto !== null && (
        <DiaModal
          dia={diaAberto}
          eventos={eventosPorDia.get(diaAberto) ?? []}
          onClose={() => setDiaAberto(null)}
          onEditar={editarDoDia}
          onNovo={() => {
            setVoltarAoDia(diaAberto)
            setDiaAberto(null)
            setModalEvento(diaAberto)
          }}
        />
      )}
      {modalEvento !== null && (
        <EventoModal
          alvo={modalEvento}
          vinculos={vinculos}
          onClose={fecharEdicao}
          onSalvo={() => {
            setRecarregarToken((t) => t + 1)
            fecharEdicao()
          }}
        />
      )}
      {modalAjuste !== null && (
        <AjusteModal
          evento={modalAjuste}
          onClose={fecharEdicao}
          onSalvo={() => {
            setRecarregarToken((t) => t + 1)
            fecharEdicao()
          }}
        />
      )}
    </div>
  )
}

/** Tudo o que está marcado num dia: cada evento com o que dá pra fazer —
 * editar (meus eventos), mover/ocultar/mudar a regra (alertas calculados;
 * o ajuste vale também em Próximos passos da Visão geral) e ir pra tela onde
 * ele se resolve. */
function DiaModal({
  dia,
  eventos,
  onClose,
  onEditar,
  onNovo,
}: {
  dia: string
  eventos: EventoCalendario[]
  onClose: () => void
  onEditar: (ev: EventoCalendario) => void
  onNovo: () => void
}) {
  const [a, m, d] = dia.split("-").map(Number)
  const titulo = new Date(a, m - 1, d).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })
  return (
    <Modal titulo={titulo.charAt(0).toUpperCase() + titulo.slice(1)} onClose={onClose}>
      <div className="flex flex-col gap-4">
        {eventos.length === 0 ? (
          <p className="rounded-lg bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:bg-slate-900/40 dark:text-slate-400">
            Nada marcado neste dia.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {eventos.map((ev, i) => {
              const Icone = iconeDoEvento(ev)
              const editavel = ev.tipo === "manual" || AJUSTAVEIS.includes(ev.tipo)
              const acao = acaoDoEvento(ev)
              const rotuloTipo = ev.tipo === "manual" && ev.categoria ? ESTILO_CATEGORIA[ev.categoria].label : ESTILO_EVENTO[ev.tipo].label
              return (
                <li key={ev.id ?? ev.chave ?? i} className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                  <span className={`mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${estiloChip(ev)}`} aria-hidden>
                    <Icone size={16} />
                  </span>
                  <div className="min-w-0 flex-1">
                    {nomeDoEvento(ev) !== rotuloTipo && <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{rotuloTipo}</p>}
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{nomeDoEvento(ev)}</p>
                    {(ev.valor != null || ev.descricao || (ev.ajustado && ev.data_original)) && (
                      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                        {[
                          ev.valor != null ? formatBRL(ev.valor) : null,
                          ev.descricao || null,
                          ev.ajustado && ev.data_original ? `data mudada (era ${dataBR(ev.data_original)})` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                    {(editavel || acao) && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {editavel && (
                          <Button type="button" variant="outline" className="!px-2.5 !py-1 text-xs" onClick={() => onEditar(ev)}>
                            <Pencil size={12} /> {ev.tipo === "manual" ? "Editar" : "Mudar data ou regra"}
                          </Button>
                        )}
                        {acao && (
                          <Link
                            to={acao.link}
                            className="inline-flex items-center rounded-lg px-2.5 py-1 text-xs font-medium text-primary-700 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-900/30"
                          >
                            {acao.rotulo} →
                          </Link>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        <div className="flex justify-between gap-3">
          <Button type="button" variant="ghost" onClick={onClose}>
            Fechar
          </Button>
          <Button type="button" variant="accent" onClick={onNovo}>
            <Plus size={16} /> Novo evento neste dia
          </Button>
        </div>
      </div>
    </Modal>
  )
}

const CLASSE_SELECT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

function EventoModal({
  alvo,
  vinculos,
  onClose,
  onSalvo,
}: {
  alvo: string | EventoCalendario
  vinculos: VinculoResumo[]
  onClose: () => void
  onSalvo: () => void
}) {
  const { financeiro } = useModulos()
  const editando = typeof alvo !== "string"
  const [data, setData] = useState(editando ? alvo.data : alvo)
  const [categoria, setCategoria] = useState<CategoriaEventoManual>(editando ? (alvo.categoria ?? "lembrete") : "lembrete")
  const [titulo, setTitulo] = useState(editando ? alvo.titulo : "")
  const [descricao, setDescricao] = useState(editando ? (alvo.descricao ?? "") : "")
  const [vinculoId, setVinculoId] = useState(editando ? (alvo.vinculo_id ?? "") : "")
  const [valor, setValor] = useState(editando && alvo.valor != null ? String(alvo.valor) : "")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const usaFornecedor = categoria !== "lembrete"

  // Título sugerido pela categoria/fornecedor enquanto a pessoa não digitou um.
  const apelido = vinculos.find((v) => v.id === vinculoId)?.apelido
  const tituloSugerido =
    categoria === "recebimento_previsto"
      ? `Previsão de recebimento${apelido ? ` — ${apelido}` : ""}`
      : categoria === "prazo_emissao"
        ? `Prazo${apelido ? ` — ${apelido}` : ""}`
        : ""

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    const corpo = {
      data,
      titulo: titulo.trim() || tituloSugerido,
      descricao: descricao || null,
      categoria,
      vinculo_id: usaFornecedor && vinculoId ? vinculoId : null,
      valor: categoria === "recebimento_previsto" && valor ? parseBRL(valor) : null,
    }
    try {
      if (editando) {
        await api.patch(`/calendario/eventos/${alvo.id}`, corpo)
      } else {
        await api.post("/calendario/eventos", corpo)
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
        <FieldWrap label="Tipo">
          <select value={categoria} onChange={(e) => setCategoria(e.target.value as CategoriaEventoManual)} className={CLASSE_SELECT}>
            {(Object.keys(ESTILO_CATEGORIA) as CategoriaEventoManual[])
              .filter((c) => financeiro || c !== "recebimento_previsto" || categoria === c)
              .map((c) => (
              <option key={c} value={c}>
                {ESTILO_CATEGORIA[c].label}
              </option>
            ))}
          </select>
        </FieldWrap>
        <Field label="Data" type="date" required value={data} onChange={(e) => setData(e.target.value)} />
        {usaFornecedor && (
          <FieldWrap label="Fornecedor (opcional)">
            <CaixaBusca
              valor={vinculoId}
              opcoes={[{ id: "", rotulo: "Nenhum" }, ...vinculos.map((v) => ({ id: v.id, rotulo: v.apelido }))]}
              onEscolher={setVinculoId}
              placeholder="Nenhum (digite pra buscar)"
              ariaLabel="Fornecedor"
              className="[&_input]:py-2 [&_input]:pl-3"
            />
          </FieldWrap>
        )}
        {categoria === "recebimento_previsto" && (
          <MoedaField label="Valor previsto" saida="br" valor={valor} onChange={setValor} />
        )}
        <Field
          label="Título"
          required={!tituloSugerido}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          placeholder={tituloSugerido || 'Ex.: "Reunião com contador"'}
        />
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


function AjusteModal({ evento, onClose, onSalvo }: { evento: EventoCalendario; onClose: () => void; onSalvo: () => void }) {
  const [novaData, setNovaData] = useState(evento.data)
  const [regra, setRegra] = useState(evento.regra_valor != null ? String(evento.regra_valor) : "")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const REGRA: Partial<Record<TipoEventoCalendario, { label: string; hint: string; min: number; max: number }>> = {
    prazo_emissao: { label: "Dia limite pra emitir (todo mês)", hint: "Vale pra todos os meses deste fornecedor.", min: 1, max: 31 },
    recebimento_previsto: { label: "Dias pra receber depois de emitir", hint: "Vale pras próximas notas deste fornecedor.", min: 0, max: 365 },
    revisar_aliquota: { label: "Dia do lembrete (todo mês)", hint: "Vale pra todos os meses.", min: 1, max: 31 },
  }
  const infoRegra = REGRA[evento.tipo]

  async function executar(acao: () => Promise<unknown>) {
    setErro(null)
    setEnviando(true)
    try {
      await acao()
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      setEnviando(false)
    }
  }

  const moverSoEsta = () =>
    executar(() => api.put("/calendario/ajustes", { tipo: evento.tipo, chave: evento.chave, nova_data: novaData }))
  const ocultarSoEsta = () =>
    executar(() => api.put("/calendario/ajustes", { tipo: evento.tipo, chave: evento.chave, oculto: true }))
  const voltarAoOriginal = () =>
    executar(() =>
      api.delete(`/calendario/ajustes?tipo=${evento.tipo}&chave=${encodeURIComponent(evento.chave ?? "")}`),
    )
  const salvarRegra = () =>
    executar(async () => {
      const n = Number(regra)
      if (evento.tipo === "revisar_aliquota") {
        await api.patch("/prestador/lembrete-aliquota", { dia: n })
      } else if (evento.vinculo_id) {
        const campo = evento.tipo === "prazo_emissao" ? "dia_limite_emissao" : "dias_para_recebimento"
        await api.patch(`/vinculos/${evento.vinculo_id}`, { [campo]: n })
      }
    })

  return (
    <Modal titulo="Ajustar alerta" onClose={onClose}>
      <div className="flex flex-col gap-5">
        <div>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{evento.titulo}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {dataBR(evento.data)}
            {evento.ajustado && evento.data_original && ` · data original ${dataBR(evento.data_original)}`}
          </p>
        </div>
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        <section className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Só esta vez</h3>
          <Field label="Mover para" type="date" value={novaData} onChange={(e) => setNovaData(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="accent" onClick={moverSoEsta} disabled={enviando || !novaData}>
              Mover
            </Button>
            <Button type="button" variant="outline" onClick={ocultarSoEsta} disabled={enviando}>
              Ocultar este alerta
            </Button>
            {evento.ajustado && (
              <Button type="button" variant="ghost" onClick={voltarAoOriginal} disabled={enviando}>
                <RotateCcw size={14} /> Voltar à data original
              </Button>
            )}
          </div>
        </section>

        {infoRegra && (
          <section className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Mudar a regra</h3>
            <Field
              label={infoRegra.label}
              type="number"
              min={infoRegra.min}
              max={infoRegra.max}
              value={regra}
              onChange={(e) => setRegra(e.target.value)}
              hint={infoRegra.hint}
            />
            <div>
              <Button type="button" variant="outline" onClick={salvarRegra} disabled={enviando || regra === ""}>
                Salvar regra
              </Button>
            </div>
          </section>
        )}
      </div>
    </Modal>
  )
}
