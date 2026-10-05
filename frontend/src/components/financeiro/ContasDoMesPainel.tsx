import { CampoMoeda } from "../ui/CampoMoeda"
import { AlertCircle, GripVertical, ListChecks, Plus, Repeat } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { api } from "../../lib/api"
import { hojeLocal } from "../../lib/datas"
import { classeCampoPequeno, classeCheckbox, estaVencida, formatDiaMes, mensagemErro, valorParaCampo } from "../../lib/financeiro"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga, parseBRL } from "../../lib/format"
import type { AtualizarDespesaRequest, ContasDoMes, Despesa, RotinaDoMes } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"
import { ContasFixasModal } from "./ContasFixasModal"
import { RotinasModal } from "./RotinasModal"

// "Contas e rotina do mês" (28/09/2026) — "é interessante a pessoa poder
// ticar: sacou o pró-labore ✓, pagou o cartão ✓". As contas fixas viram
// lançamentos "a pagar" do mês (GET /financeiro/mes cria na 1ª vez) e a
// rotina de fechamento é o quadro de X da planilha.

interface Edicao {
  id: string
  texto: string
  /** "pagar" = conta de valor variável: pede o valor antes de ticar. */
  modo: "valor" | "pagar"
}

export function ContasDoMesPainel({
  competencia,
  onCompetencia,
  versao,
  onMudou,
  onLancar,
  semTitulo,
}: {
  /** A tela já mostra o título do card. */
  semTitulo?: boolean
  competencia: string
  onCompetencia: (c: string) => void
  /** Muda quando algo de fora (lançamento, importação) mexeu no mês. */
  versao: number
  onMudou: () => void
  /** Sem isso (Visão geral), o botão "Lançar" não aparece. */
  onLancar?: (competencia: string) => void
}) {
  const [dados, setDados] = useState<ContasDoMes | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [recarga, setRecarga] = useState(0)
  const [salvando, setSalvando] = useState<Record<string, boolean>>({})
  const [edicao, setEdicao] = useState<Edicao | null>(null)
  const [modal, setModal] = useState<"contas" | "rotinas" | null>(null)
  // Arrastar um item da rotina pra mudar a ordem (05/10/2026).
  const [arrastando, setArrastando] = useState<string | null>(null)

  function passarSobre(alvoId: string) {
    if (!arrastando || arrastando === alvoId) return
    setDados((d) => {
      if (!d) return d
      const lista = [...d.rotinas]
      const de = lista.findIndex((r) => r.id === arrastando)
      const para = lista.findIndex((r) => r.id === alvoId)
      if (de === -1 || para === -1) return d
      const [item] = lista.splice(de, 1)
      lista.splice(para, 0, item)
      return { ...d, rotinas: lista }
    })
  }

  function soltar() {
    setArrastando(null)
    const ids = (dados?.rotinas ?? []).map((r) => r.id)
    api.put("/financeiro/rotinas/ordem", { ids }).catch((err) => setErro(`Não deu pra salvar a ordem: ${mensagemErro(err)}`))
  }

  useEffect(() => {
    let cancelado = false
    api
      .get<ContasDoMes>(`/financeiro/mes?competencia=${competencia}`)
      .then((d) => {
        if (cancelado) return
        setDados(d)
        setErro(null)
      })
      .catch((err) => {
        if (!cancelado) setErro(mensagemErro(err))
      })
    return () => {
      cancelado = true
    }
  }, [competencia, versao, recarga])

  const carregando = dados === null || dados.competencia !== competencia

  function recarregarTudo() {
    setRecarga((n) => n + 1)
    onMudou()
  }

  function trocarMes(c: string) {
    setEdicao(null)
    onCompetencia(c)
  }

  function atualizarConta(id: string, mudanca: Partial<Despesa>) {
    setDados((d) => (d ? { ...d, contas: d.contas.map((c) => (c.id === id ? { ...c, ...mudanca } : c)) } : d))
  }

  /** PATCH otimista: aplica já, desfaz se a API recusar. */
  async function salvarConta(conta: Despesa, corpo: AtualizarDespesaRequest) {
    const antes: Partial<Despesa> = { pago: conta.pago, pago_em: conta.pago_em, valor: conta.valor, valor_a_definir: conta.valor_a_definir }
    const otimista: Partial<Despesa> = { ...corpo, valor_a_definir: false } as Partial<Despesa>
    if (corpo.pago === true) otimista.pago_em = conta.pago_em ?? hojeLocal()
    if (corpo.pago === false) {
      otimista.pago_em = null
      otimista.valor_a_definir = !!conta.recorrente_id && (corpo.valor ?? conta.valor) === 0
    }
    atualizarConta(conta.id, otimista)
    setSalvando((s) => ({ ...s, [conta.id]: true }))
    setErro(null)
    try {
      const salvo = await api.patch<Despesa>(`/despesas/${conta.id}`, corpo)
      atualizarConta(conta.id, salvo)
      onMudou()
    } catch (err) {
      atualizarConta(conta.id, antes)
      setErro(`Não deu pra salvar "${conta.descricao || conta.categoria}": ${mensagemErro(err)}`)
    } finally {
      setSalvando((s) => {
        const resto = { ...s }
        delete resto[conta.id]
        return resto
      })
    }
  }

  function ticar(conta: Despesa, pago: boolean) {
    if (pago && (conta.valor_a_definir || conta.valor === 0)) {
      setEdicao({ id: conta.id, texto: "", modo: "pagar" })
      return
    }
    if (edicao?.id === conta.id) setEdicao(null)
    void salvarConta(conta, { pago })
  }

  function confirmarEdicao(e: FormEvent, conta: Despesa) {
    e.preventDefault()
    if (!edicao) return
    const valor = parseBRL(edicao.texto)
    if (valor === null || valor < 0 || (edicao.modo === "pagar" && valor === 0)) {
      setErro("Informe um valor válido (ex.: 1.234,56).")
      return
    }
    setEdicao(null)
    void salvarConta(conta, edicao.modo === "pagar" ? { valor, pago: true } : { valor })
  }

  async function ticarRotina(r: RotinaDoMes, feita: boolean) {
    const mudar = (valor: boolean, em: string | null) =>
      setDados((d) => (d ? { ...d, rotinas: d.rotinas.map((x) => (x.id === r.id ? { ...x, feita: valor, feita_em: em } : x)) } : d))
    mudar(feita, feita ? hojeLocal() : null)
    setSalvando((s) => ({ ...s, [r.id]: true }))
    setErro(null)
    try {
      await api.post(`/financeiro/rotinas/${r.id}/check`, { competencia, feita })
    } catch (err) {
      mudar(r.feita, r.feita_em)
      setErro(`Não deu pra marcar "${r.nome}": ${mensagemErro(err)}`)
    } finally {
      setSalvando((s) => {
        const resto = { ...s }
        delete resto[r.id]
        return resto
      })
    }
  }

  const contas = carregando ? [] : dados.contas
  const rotinas = carregando ? [] : dados.rotinas
  const despesasMes = contas.filter((c) => c.tipo !== "retirada")
  const retiradasMes = contas.filter((c) => c.tipo === "retirada")
  const previsto = despesasMes.reduce((s, c) => s + c.valor, 0)
  const pago = despesasMes.filter((c) => c.pago).reduce((s, c) => s + c.valor, 0)
  const aPagar = contas.filter((c) => !c.pago)
  const valorAPagar = aPagar.reduce((s, c) => s + c.valor, 0)
  const aDefinir = aPagar.filter((c) => c.valor_a_definir).length
  const feitas = rotinas.filter((r) => r.feita).length
  const ehMesAtual = competencia === competenciaAtual()

  const linhaConta = (c: Despesa) => {
    const nome = c.descricao || c.categoria
    const vencida = estaVencida(c.vencimento, c.pago)
    const editandoEsta = edicao?.id === c.id
    const detalhes = [c.descricao && c.descricao !== c.categoria ? c.categoria : null, c.conta].filter(Boolean).join(" · ")
    return (
      <li key={c.id} className="py-2.5">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={!!c.pago}
            disabled={!!salvando[c.id]}
            onChange={(e) => ticar(c, e.target.checked)}
            aria-label={`${nome}: marcar como ${c.tipo === "retirada" ? "retirado" : "pago"}`}
            className={`${classeCheckbox} mt-0.5`}
          />
          <div className="min-w-0 flex-1">
            <p className={`truncate text-sm font-medium ${c.pago ? "text-slate-400 line-through decoration-slate-300 dark:text-slate-500 dark:decoration-slate-600" : "text-slate-800 dark:text-slate-200"}`}>
              {nome}
            </p>
            {(detalhes || c.vencimento || c.pago_em) && (
              <p className="flex flex-wrap items-center gap-x-2 text-xs text-slate-400 dark:text-slate-500">
                {detalhes && <span className="truncate">{detalhes}</span>}
                {c.pago && c.pago_em ? (
                  <span>pago em {formatDiaMes(c.pago_em)}</span>
                ) : c.vencimento ? (
                  <span className={vencida ? "font-semibold text-danger-600 dark:text-danger-400" : ""}>
                    vence {formatDiaMes(c.vencimento)}
                    {vencida && " · vencida"}
                  </span>
                ) : null}
              </p>
            )}
          </div>
          {!editandoEsta && (
            <button
              type="button"
              onClick={() => setEdicao({ id: c.id, texto: valorParaCampo(c.valor), modo: c.valor_a_definir && !c.pago ? "pagar" : "valor" })}
              title="Clique pra alterar o valor"
              aria-label={`Alterar valor de ${nome}`}
              className="shrink-0 rounded px-1.5 py-0.5 text-right text-sm tabular-nums text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              {c.valor_a_definir ? <span className="text-xs font-medium text-warning-700 dark:text-warning-300">definir valor</span> : formatBRL(c.valor)}
            </button>
          )}
        </div>
        {editandoEsta && edicao && (
          <form onSubmit={(e) => confirmarEdicao(e, c)} className="mt-2 flex flex-wrap items-center justify-end gap-2 pl-7">
            <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              {edicao.modo === "pagar" ? "Quanto foi pago?" : "Valor"}
              <CampoMoeda
                autoFocus
                saida="br"
                valor={edicao.texto}
                onChange={(texto) => setEdicao({ ...edicao, texto })}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    e.stopPropagation()
                    setEdicao(null)
                  }
                }}
                className={`${classeCampoPequeno} w-28 text-right tabular-nums`}
              />
            </label>
            <Button type="submit" className="px-3 py-1 text-xs">
              {edicao.modo === "pagar" ? "Ticar como pago" : "Salvar"}
            </Button>
            <Button type="button" variant="outline" className="px-3 py-1 text-xs" onClick={() => setEdicao(null)}>
              Cancelar
            </Button>
          </form>
        )}
      </li>
    )
  }

  return (
    <Card className="p-5" aria-labelledby="titulo-contas-mes">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="titulo-contas-mes" className={semTitulo ? "sr-only" : "text-base font-semibold text-slate-800 dark:text-slate-200"}>
            Contas e rotina do mês
          </h2>
          <p className="text-xs text-slate-400 dark:text-slate-500">Tique o que já foi pago e o que já foi conferido.</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800">
          <button
            type="button"
            onClick={() => trocarMes(deslocarCompetencia(competencia, -1))}
            aria-label="Mês anterior"
            className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            ‹
          </button>
          <span className="min-w-[9rem] text-center font-medium text-slate-700 dark:text-slate-300" aria-live="polite">
            {formatCompetenciaLonga(competencia)}
          </span>
          <button
            type="button"
            onClick={() => trocarMes(deslocarCompetencia(competencia, 1))}
            aria-label="Próximo mês"
            className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            ›
          </button>
          {!ehMesAtual && (
            <button type="button" onClick={() => trocarMes(competenciaAtual())} className="rounded px-2 py-0.5 text-xs font-medium text-primary-600 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-900/30">
              Hoje
            </button>
          )}
        </div>
      </div>

      {erro && (
        <p className="mb-3 flex items-start gap-2 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/40 dark:text-danger-300" role="alert">
          <AlertCircle size={16} className="mt-0.5 shrink-0" /> {erro}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* a. Contas do mês */}
        <section className="lg:col-span-3" aria-labelledby="titulo-contas-lista">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 id="titulo-contas-lista" className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Contas do mês
            </h3>
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => setModal("contas")}>
                <Repeat size={14} /> Contas fixas
              </Button>
              {onLancar && (
                <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => onLancar(competencia)}>
                  <Plus size={14} /> Lançar
                </Button>
              )}
            </div>
          </div>

          {!carregando && (
            <div className="mb-2 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs dark:bg-slate-900/40">
              <div>
                <p className="text-slate-400 dark:text-slate-500">Previsto</p>
                <p className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(previsto)}</p>
              </div>
              <div>
                <p className="text-slate-400 dark:text-slate-500">Pago</p>
                <p className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(pago)}</p>
              </div>
              <div>
                <p className="text-slate-400 dark:text-slate-500">A pagar</p>
                <p className={`font-semibold tabular-nums ${aPagar.length ? "text-warning-700 dark:text-warning-300" : "text-success-700 dark:text-success-300"}`}>
                  {aPagar.length === 0 ? "tudo pago ✓" : `${aPagar.length} · ${formatBRL(valorAPagar)}`}
                </p>
                {aDefinir > 0 && <p className="text-slate-400 dark:text-slate-500">{aDefinir} sem valor ainda</p>}
              </div>
            </div>
          )}

          {carregando ? (
            <p className="py-6 text-center text-sm text-slate-400">{erro ? "—" : "Carregando..."}</p>
          ) : contas.length === 0 ? (
            <div className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
              <p>Nenhuma conta em {formatCompetenciaLonga(competencia).toLowerCase()}.</p>
              <p className="mt-1 text-xs">Cadastre as contas fixas (pró-labore, Simples, cartão, ferramentas) pra elas aparecerem aqui todo mês.</p>
              <Button variant="outline" className="mt-3 px-3 py-1.5 text-xs" onClick={() => setModal("contas")}>
                <Repeat size={14} /> Cadastrar contas fixas
              </Button>
            </div>
          ) : (
            <>
              {despesasMes.length > 0 && <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">{despesasMes.map(linhaConta)}</ul>}
              {retiradasMes.length > 0 && (
                <div className="mt-3">
                  <p className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                    Retiradas / distribuição de lucros
                    <span className="tabular-nums text-slate-400 dark:text-slate-500">{formatBRL(retiradasMes.reduce((s, c) => s + c.valor, 0))}</span>
                  </p>
                  <ul className="divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-700/60 dark:border-slate-700/60">
                    {retiradasMes.map(linhaConta)}
                  </ul>
                </div>
              )}
            </>
          )}
        </section>

        {/* b. Rotina de fechamento */}
        <section className="lg:col-span-2" aria-labelledby="titulo-rotina">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 id="titulo-rotina" className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Rotina de fechamento
            </h3>
            <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => setModal("rotinas")}>
              <ListChecks size={14} /> Itens da rotina
            </Button>
          </div>
          {carregando ? (
            <p className="py-6 text-center text-sm text-slate-400">{erro ? "—" : "Carregando..."}</p>
          ) : rotinas.length === 0 ? (
            <div className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
              <p>Monte a sua rotina de fechamento: conferir extratos, investimentos, baixar a NF do Facebook...</p>
              <Button variant="outline" className="mt-3 px-3 py-1.5 text-xs" onClick={() => setModal("rotinas")}>
                <ListChecks size={14} /> Montar rotina
              </Button>
            </div>
          ) : (
            <>
              <div className="mb-2">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-slate-500 dark:text-slate-400">
                    {feitas} de {rotinas.length} feitas
                  </span>
                  {feitas === rotinas.length && <Badge variant="success">mês fechado ✓</Badge>}
                </div>
                <div
                  className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={rotinas.length}
                  aria-valuenow={feitas}
                  aria-label="Rotina de fechamento"
                >
                  <div className="h-1.5 rounded-full bg-success-600 transition-all" style={{ width: `${(feitas / rotinas.length) * 100}%` }} />
                </div>
              </div>
              <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
                {rotinas.map((r) => (
                  <li
                    key={r.id}
                    draggable
                    onDragStart={(e) => {
                      setArrastando(r.id)
                      e.dataTransfer.effectAllowed = "move"
                      e.dataTransfer.setData("text/plain", r.id)
                    }}
                    onDragOver={(e) => {
                      e.preventDefault()
                      passarSobre(r.id)
                    }}
                    onDrop={(e) => e.preventDefault()}
                    onDragEnd={soltar}
                    className={`group flex items-center gap-1 ${arrastando === r.id ? "opacity-50" : ""}`}
                  >
                    <GripVertical
                      className="h-4 w-4 shrink-0 cursor-grab text-slate-300 opacity-0 group-hover:opacity-100 dark:text-slate-600"
                      aria-hidden
                    />
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={r.feita}
                        disabled={!!salvando[r.id]}
                        onChange={(e) => ticarRotina(r, e.target.checked)}
                        className={classeCheckbox}
                      />
                      <span className={`min-w-0 flex-1 text-sm ${r.feita ? "text-slate-400 line-through decoration-slate-300 dark:text-slate-500 dark:decoration-slate-600" : "text-slate-800 dark:text-slate-200"}`}>
                        {r.nome}
                      </span>
                      {r.feita && r.feita_em && <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">{formatDiaMes(r.feita_em)}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      {modal === "contas" && <ContasFixasModal onClose={() => setModal(null)} onMudou={recarregarTudo} />}
      {modal === "rotinas" && <RotinasModal onClose={() => setModal(null)} onMudou={() => setRecarga((n) => n + 1)} />}
    </Card>
  )
}
