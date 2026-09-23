import { Plus, RotateCcw } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../lib/format"
import type { Calendario, CategoriaEventoManual, EventoCalendario, TipoEventoCalendario, VinculoResumo } from "../lib/types"

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
                      title={
                        (ev.descricao ? `${ev.titulo} — ${ev.descricao}` : ev.titulo) +
                        (ev.ajustado && ev.data_original ? ` (data ajustada; original ${dataBR(ev.data_original)})` : "")
                      }
                      onClick={(e) => {
                        if (ev.tipo === "manual") {
                          e.stopPropagation()
                          setModalEvento(ev)
                        } else if (AJUSTAVEIS.includes(ev.tipo)) {
                          e.stopPropagation()
                          setModalAjuste(ev)
                        }
                      }}
                      className={`truncate rounded px-1.5 py-0.5 text-[11px] font-medium ${estiloChip(ev)} ${ev.ajustado ? "italic" : ""}`}
                    >
                      {ev.ajustado && <RotateCcw size={9} className="mr-0.5 inline -translate-y-px" />}
                      {ev.tipo === "manual" ? ev.titulo : (ev.apelido ?? ev.titulo)}
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
          vinculos={vinculos}
          onClose={() => setModalEvento(null)}
          onSalvo={() => {
            setModalEvento(null)
            setRecarregarToken((t) => t + 1)
          }}
        />
      )}
      {modalAjuste !== null && (
        <AjusteModal
          evento={modalAjuste}
          onClose={() => setModalAjuste(null)}
          onSalvo={() => {
            setModalAjuste(null)
            setRecarregarToken((t) => t + 1)
          }}
        />
      )}
    </div>
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
      valor: categoria === "recebimento_previsto" && valor ? Number(valor.replace(",", ".")) : null,
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
            {(Object.keys(ESTILO_CATEGORIA) as CategoriaEventoManual[]).map((c) => (
              <option key={c} value={c}>
                {ESTILO_CATEGORIA[c].label}
              </option>
            ))}
          </select>
        </FieldWrap>
        <Field label="Data" type="date" required value={data} onChange={(e) => setData(e.target.value)} />
        {usaFornecedor && (
          <FieldWrap label="Fornecedor (opcional)">
            <select value={vinculoId} onChange={(e) => setVinculoId(e.target.value)} className={CLASSE_SELECT}>
              <option value="">Nenhum</option>
              {vinculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.apelido}
                </option>
              ))}
            </select>
          </FieldWrap>
        )}
        {categoria === "recebimento_previsto" && (
          <Field
            label="Valor previsto (R$)"
            inputMode="decimal"
            value={valor}
            onChange={(e) => setValor(e.target.value.replace(/[^\d,.]/g, ""))}
            placeholder="0,00"
          />
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
