import { ArrowLeftRight, Check, X } from "lucide-react"
import { type FormEvent, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { competenciaAtual, formatBRL, formatCompetenciaLonga } from "../../lib/format"
import type {
  ConfirmarExtratoResultado,
  ExtratoExtraido,
  ItemConfirmarExtrato,
  NotaParaBaixa,
  TransacaoExtraida,
  VinculoResumo,
} from "../../lib/types"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"
import { ListaSemNota } from "./RecebimentosSemNota"

/** Revisão do extrato (refeita em 03/10/2026): descrição inteira, receitas e
 * despesas em blocos separados (tomador de um lado, categoria do outro),
 * troca de tipo por linha, criar tomador/categoria aqui mesmo, e a
 * classificação vem sugerida pelo servidor (o que já foi escolhido antes, o
 * nome do tomador, ou a nota em aberto do mesmo valor). */

interface Linha {
  linha: number
  incluir: boolean
  descricao: string
  data: string
  chave: string
  credito: boolean
  valor: string
  // receita
  vinculoId: string
  /** A nota que esse dinheiro paga ("" = nenhuma: caiu antes da nota). */
  emissaoId: string
  competenciaReceita: string
  // despesa
  categoria: string
  tipoDespesa: "despesa" | "retirada"
  competenciaDespesa: string
  // avisos
  origem: TransacaoExtraida["origem_sugestao"]
  jaLancado: boolean
  // campo de "novo tomador"/"nova categoria" aberto nesta linha
  criando: boolean
  nome: string
}

interface Opcao {
  id: string
  apelido: string
  sem_nota?: boolean
}

const NOVO = "__novo__"
const CAMPO =
  "rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

function dataBR(iso: string): string {
  return iso ? iso.split("-").reverse().join("/") : ""
}

export function ImportarExtratoModal({
  vinculos,
  onClose,
  onImportado,
}: {
  vinculos: VinculoResumo[]
  onClose: () => void
  onImportado: () => void
}) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [extraindo, setExtraindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [linhas, setLinhas] = useState<Linha[] | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<ConfirmarExtratoResultado | null>(null)
  const [info, setInfo] = useState<{ formato?: string; linhas_lidas?: number } | null>(null)
  const [tomadores, setTomadores] = useState<Opcao[]>(vinculos)
  const [categorias, setCategorias] = useState<string[]>([])
  const [retiradas, setRetiradas] = useState<string[]>([])
  const [criandoTomador, setCriandoTomador] = useState(false)
  const [notas, setNotas] = useState<NotaParaBaixa[]>([])

  const notasDe = (vinculoId: string) => notas.filter((n) => n.vinculo_id === vinculoId)
  const igual = (a: number, b: number) => Math.abs(a - b) < 0.005
  /** Nota que um recebimento desse valor paga: a do mesmo valor; senão a única em aberto. */
  function notaPara(vinculoId: string, valor: number, mes: string): string {
    const doTomador = notasDe(vinculoId).filter((n) => n.competencia <= mes)
    const exata = doTomador.find((n) => igual(n.valor, valor))
    return exata?.emissao_id ?? (doTomador.length === 1 ? doTomador[0].emissao_id : "")
  }

  async function extrair(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setErro(null)
    setExtraindo(true)
    try {
      const form = new FormData()
      form.append("arquivo", arquivo)
      const resp = await api.postForm<ExtratoExtraido>("/recebimentos/extrato", form)
      setInfo({ formato: resp.formato, linhas_lidas: resp.linhas_lidas })
      setCategorias(resp.categorias ?? [])
      setRetiradas(resp.categorias_retirada ?? [])
      setNotas(resp.notas_abertas ?? [])
      setLinhas(
        resp.transacoes.map((t) => {
          const mes = t.data ? t.data.slice(0, 7) : competenciaAtual()
          return {
            linha: t.linha,
            incluir: !t.ja_lancado,
            descricao: t.descricao,
            data: t.data ?? "",
            chave: t.chave ?? "",
            credito: t.credito,
            valor: String(t.valor),
            vinculoId: t.vinculo_id ?? "",
            emissaoId: t.emissao_id ?? "",
            competenciaReceita: mes,
            categoria: t.categoria ?? "Outras despesas",
            tipoDespesa: t.tipo_despesa ?? "despesa",
            competenciaDespesa: mes,
            origem: t.origem_sugestao ?? null,
            jaLancado: Boolean(t.ja_lancado),
            criando: false,
            nome: "",
          }
        }),
      )
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setExtraindo(false)
    }
  }

  function mudar(linha: number, mudancas: Partial<Linha>) {
    setLinhas((atuais) => atuais?.map((l) => (l.linha === linha ? { ...l, ...mudancas } : l)) ?? null)
  }

  /** Escolheu o tomador de uma linha: as outras linhas do mesmo pagador que
   * ainda estão sem tomador ganham o mesmo. */
  function escolherTomador(alvo: Linha, vinculoId: string) {
    setLinhas(
      (atuais) =>
        atuais?.map((l) => {
          const nota = (x: Linha) => notaPara(vinculoId, Number(x.valor) || 0, x.competenciaDespesa)
          if (l.linha === alvo.linha) return { ...l, vinculoId, emissaoId: nota(l), criando: false, nome: "", origem: null }
          if (alvo.chave && l.chave === alvo.chave && l.credito && !l.vinculoId) return { ...l, vinculoId, emissaoId: nota(l) }
          return l
        }) ?? null,
    )
  }

  function escolherCategoria(alvo: Linha, categoria: string, tipoDespesa: "despesa" | "retirada") {
    setLinhas(
      (atuais) =>
        atuais?.map((l) => {
          if (l.linha === alvo.linha) return { ...l, categoria, tipoDespesa, criando: false, nome: "", origem: null }
          if (alvo.chave && l.chave === alvo.chave && !l.credito) return { ...l, categoria, tipoDespesa }
          return l
        }) ?? null,
    )
  }

  async function criarTomador(l: Linha) {
    const nome = l.nome.trim()
    if (nome.length < 2) return
    setErro(null)
    setCriandoTomador(true)
    try {
      const novo = await api.post<Opcao>("/vinculos/controle", { nome })
      setTomadores((atuais) => (atuais.some((v) => v.id === novo.id) ? atuais : [...atuais, novo]))
      escolherTomador(l, novo.id)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setCriandoTomador(false)
    }
  }

  function criarCategoria(l: Linha) {
    const nome = l.nome.trim()
    if (!nome) return
    const existente = [...categorias, ...retiradas].find((c) => c.toLowerCase() === nome.toLowerCase())
    if (!existente) setCategorias((atuais) => [...atuais, nome].sort((a, b) => a.localeCompare(b, "pt-BR")))
    escolherCategoria(l, existente ?? nome, existente && retiradas.includes(existente) ? "retirada" : "despesa")
  }

  const receitas = (linhas ?? []).filter((l) => l.credito)
  const despesas = (linhas ?? []).filter((l) => !l.credito)
  const receitasMarcadas = receitas.filter((l) => l.incluir)
  const despesasMarcadas = despesas.filter((l) => l.incluir)
  const valorOk = (l: Linha) => Number(l.valor) > 0
  const semTomador = receitasMarcadas.filter((l) => !l.vinculoId).length
  const semCategoria = despesasMarcadas.filter((l) => !l.categoria.trim()).length
  const pronto =
    receitasMarcadas.length + despesasMarcadas.length > 0 &&
    semTomador === 0 &&
    semCategoria === 0 &&
    [...receitasMarcadas, ...despesasMarcadas].every(valorOk)
  const soma = (lista: Linha[]) => lista.reduce((s, l) => s + (Number(l.valor) || 0), 0)

  async function confirmar() {
    setEnviando(true)
    setErro(null)
    try {
      const itens: ItemConfirmarExtrato[] = receitasMarcadas.map((l) => ({
        vinculo_id: l.vinculoId,
        emissao_id: l.emissaoId || null,
        competencia: notas.find((n) => n.emissao_id === l.emissaoId)?.competencia ?? l.competenciaReceita,
        valor: Number(l.valor),
        data_recebimento: l.data || null,
        descricao: l.descricao,
      }))
      const saidas = despesasMarcadas.map((l) => ({
        categoria: l.categoria.trim(),
        tipo: l.tipoDespesa,
        competencia: l.competenciaDespesa,
        valor: Number(l.valor),
        data: l.data || null,
        descricao: l.descricao,
      }))
      const resp = await api.post<ConfirmarExtratoResultado>("/recebimentos/extrato/confirmar", { itens, despesas: saidas })
      setResultado(resp)
      if (resp.sucesso > 0 || (resp.despesas_registradas ?? 0) > 0) onImportado()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  function linhaDaLista(l: Linha) {
    const comNota = tomadores.filter((v) => !v.sem_nota)
    const soControle = tomadores.filter((v) => v.sem_nota)
    const notasDoTomador = l.credito && l.vinculoId ? notasDe(l.vinculoId) : []
    const notaEscolhida = notasDoTomador.find((n) => n.emissao_id === l.emissaoId)
    const rotuloNota = (n: NotaParaBaixa) =>
      `Nota de ${formatCompetenciaLonga(n.competencia)} · ${formatBRL(n.valor)}` +
      (notasDoTomador.some((o) => o !== n && o.competencia === n.competencia && igual(o.valor, n.valor)) && n.n_dps ? ` · nº ${n.n_dps}` : "")
    return (
      <li key={l.linha} className={`flex gap-3 px-3 py-3 ${l.incluir ? "" : "opacity-50"}`}>
        <input
          type="checkbox"
          className="mt-1 shrink-0 self-start"
          checked={l.incluir}
          onChange={(e) => mudar(l.linha, { incluir: e.target.checked })}
          aria-label={`Incluir: ${l.descricao}`}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="break-words text-sm text-slate-800 dark:text-slate-200">{l.descricao}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400 dark:text-slate-500">
                {l.data && <span>{dataBR(l.data)}</span>}
                {l.jaLancado && (
                  <span className="rounded bg-warning-50 px-1.5 py-0.5 font-medium text-warning-700">já lançado antes</span>
                )}
                {l.origem === "lembrado" && (
                  <span className="rounded bg-primary-50 px-1.5 py-0.5 font-medium text-primary-700 dark:bg-primary-900/30 dark:text-primary-200">
                    como da última vez
                  </span>
                )}
                {notaEscolhida &&
                  (igual(notaEscolhida.valor, Number(l.valor) || 0) ? (
                    <span className="rounded bg-success-50 px-1.5 py-0.5 font-medium text-success-700">mesmo valor da nota</span>
                  ) : (
                    <span className="rounded bg-warning-50 px-1.5 py-0.5 font-medium text-warning-700">
                      valor diferente do da nota ({formatBRL(notaEscolhida.valor)})
                    </span>
                  ))}
                {l.credito && l.vinculoId && notasDoTomador.length > 0 && !notaEscolhida && (
                  <span className="rounded bg-warning-50 px-1.5 py-0.5 font-medium text-warning-700">não dá baixa em nenhuma nota</span>
                )}
              </p>
            </div>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={l.valor}
              onChange={(e) => mudar(l.linha, { valor: e.target.value })}
              disabled={!l.incluir}
              aria-label="Valor em reais"
              className={`${CAMPO} w-28 shrink-0 text-right tabular-nums`}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {l.criando ? (
              <form
                className="flex min-w-[220px] flex-1 items-center gap-1.5"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (l.credito) criarTomador(l)
                  else criarCategoria(l)
                }}
              >
                <input
                  autoFocus
                  value={l.nome}
                  maxLength={60}
                  onChange={(e) => mudar(l.linha, { nome: e.target.value })}
                  placeholder={l.credito ? "Nome do novo tomador" : "Nome da nova categoria"}
                  className={`${CAMPO} min-w-0 flex-1`}
                />
                <button
                  type="submit"
                  disabled={criandoTomador || l.nome.trim().length < 2}
                  title="Criar"
                  aria-label="Criar"
                  className="rounded-lg bg-primary-600 p-2 text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => mudar(l.linha, { criando: false, nome: "" })}
                  title="Cancelar"
                  aria-label="Cancelar"
                  className="rounded-lg border border-slate-300 p-2 text-slate-500 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"
                >
                  <X className="h-4 w-4" />
                </button>
              </form>
            ) : l.credito ? (
              <select
                value={l.vinculoId}
                onChange={(e) => (e.target.value === NOVO ? mudar(l.linha, { criando: true }) : escolherTomador(l, e.target.value))}
                disabled={!l.incluir}
                aria-label="Tomador"
                className={`${CAMPO} min-w-[200px] flex-1 ${l.incluir && !l.vinculoId ? "border-warning-400" : ""}`}
              >
                <option value="">De qual tomador?</option>
                {comNota.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.apelido}
                  </option>
                ))}
                {soControle.length > 0 && (
                  <optgroup label="Só controle (sem nota)">
                    {soControle.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.apelido}
                      </option>
                    ))}
                  </optgroup>
                )}
                <option value={NOVO}>+ Novo tomador…</option>
              </select>
            ) : (
              <select
                value={`${l.tipoDespesa}|${l.categoria}`}
                onChange={(e) => {
                  if (e.target.value === NOVO) return mudar(l.linha, { criando: true })
                  const [tipo, ...resto] = e.target.value.split("|")
                  escolherCategoria(l, resto.join("|"), tipo === "retirada" ? "retirada" : "despesa")
                }}
                disabled={!l.incluir}
                aria-label="Categoria"
                className={`${CAMPO} min-w-[220px] flex-1`}
              >
                {!categorias.includes(l.categoria) && !retiradas.includes(l.categoria) && (
                  <option value={`${l.tipoDespesa}|${l.categoria}`}>{l.categoria}</option>
                )}
                {categorias.map((c) => (
                  <option key={c} value={`despesa|${c}`}>
                    {c}
                  </option>
                ))}
                {retiradas.length > 0 && (
                  <optgroup label="Retiradas (não entram como despesa)">
                    {retiradas.map((c) => (
                      <option key={c} value={`retirada|${c}`}>
                        {c}
                      </option>
                    ))}
                  </optgroup>
                )}
                <option value={NOVO}>+ Nova categoria…</option>
              </select>
            )}
            {notasDoTomador.length > 0 && !l.criando && (
              <select
                value={l.emissaoId}
                onChange={(e) => mudar(l.linha, { emissaoId: e.target.value })}
                disabled={!l.incluir}
                aria-label="Nota que esse dinheiro paga"
                title="Nota que esse dinheiro paga"
                className={`${CAMPO} min-w-[200px] flex-1`}
              >
                {notasDoTomador.map((n) => (
                  <option key={n.emissao_id} value={n.emissao_id}>
                    {rotuloNota(n)}
                  </option>
                ))}
                <option value="">Nenhuma nota (escolher o mês)</option>
              </select>
            )}
            {!(l.credito && notaEscolhida) && (
              <input
                type="month"
                value={l.credito ? l.competenciaReceita : l.competenciaDespesa}
                onChange={(e) => mudar(l.linha, l.credito ? { competenciaReceita: e.target.value } : { competenciaDespesa: e.target.value })}
                disabled={!l.incluir}
                aria-label={l.credito ? "Mês do recebimento" : "Mês da despesa"}
                title={l.credito ? "Mês do recebimento" : "Mês da despesa"}
                className={`${CAMPO} w-40`}
              />
            )}
            <button
              type="button"
              onClick={() => mudar(l.linha, { credito: !l.credito, criando: false, nome: "" })}
              className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden />
              {l.credito ? "É despesa" : "É receita"}
            </button>
          </div>
        </div>
      </li>
    )
  }

  function bloco(titulo: string, ajuda: string, lista: Linha[], marcadas: Linha[], cor: string) {
    if (lista.length === 0) return null
    const faltaMarcar = lista.some((l) => !l.incluir)
    return (
      <section className="shrink-0 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
        <header className={`flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-3 py-2 ${cor}`}>
          <div>
            <h3 className="text-sm font-semibold">
              {titulo} · {marcadas.length} de {lista.length} · <span className="tabular-nums">{formatBRL(soma(marcadas))}</span>
            </h3>
            <p className="text-xs opacity-80">{ajuda}</p>
          </div>
          <button
            type="button"
            className="text-xs font-medium underline"
            onClick={() => setLinhas((atuais) => atuais?.map((l) => (lista.includes(l) ? { ...l, incluir: faltaMarcar } : l)) ?? null)}
          >
            {faltaMarcar ? "marcar todas" : "desmarcar todas"}
          </button>
        </header>
        <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">{lista.map(linhaDaLista)}</ul>
      </section>
    )
  }

  return (
    <Modal titulo="Importar extrato bancário" onClose={onClose} largura="max-w-4xl">
      {!linhas && (
        <form onSubmit={extrair} className="flex flex-col gap-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Envie o extrato do seu banco em <strong>PDF</strong>, <strong>OFX</strong> ou <strong>CSV</strong>. A Ana lê as transações e
            você confere cada uma antes de gravar. Dica: no app do banco, a opção “exportar OFX” é a que funciona melhor.
          </p>
          {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo do extrato</span>
            <input
              type="file"
              accept=".pdf,.ofx,.csv,.txt,application/pdf,text/csv"
              required
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={extraindo || !arquivo}>
              {extraindo ? "Lendo o extrato..." : "Ler o extrato"}
            </Button>
          </div>
        </form>
      )}

      {linhas && !resultado && (
        <div className="flex flex-col gap-4">
          {linhas.length === 0 ? (
            <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700">
              {info?.formato === "pdf" && !info.linhas_lidas
                ? "Esse PDF não tem texto — parece uma imagem ou foto do extrato. Baixe o extrato de novo no app do banco (de preferência em OFX) e tente outra vez."
                : `Não encontramos nenhuma transação reconhecível neste arquivo${info?.linhas_lidas ? ` (lemos ${info.linhas_lidas} linhas)` : ""}. Tente exportar o extrato em OFX, ou mande o arquivo pro suporte pra gente ensinar a Ana a ler o formato do seu banco.`}
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Confira cada linha. O que você escolher aqui fica lembrado: no próximo extrato, o mesmo pagador já vem classificado.
              </p>
              {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
              <div className="flex max-h-[62vh] flex-col gap-4 overflow-y-auto pr-1">
                {bloco(
                  "Receitas",
                  "Escolha o tomador e a nota que o dinheiro paga. A baixa é por nota.",
                  receitas,
                  receitasMarcadas,
                  "bg-success-50 text-success-700 dark:bg-success-900/20 dark:text-success-300",
                )}
                {bloco(
                  "Despesas",
                  "Escolha a categoria.",
                  despesas,
                  despesasMarcadas,
                  "bg-danger-50 text-danger-700 dark:bg-danger-900/20 dark:text-danger-300",
                )}
              </div>
            </>
          )}
          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            {linhas.length > 0 && semTomador + semCategoria > 0 && (
              <p className="mr-auto text-sm text-warning-700">
                {semTomador > 0 && `${semTomador} receita${semTomador === 1 ? "" : "s"} sem tomador`}
                {semTomador > 0 && semCategoria > 0 && " · "}
                {semCategoria > 0 && `${semCategoria} despesa${semCategoria === 1 ? "" : "s"} sem categoria`}
              </p>
            )}
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            {linhas.length > 0 && (
              <Button type="button" variant="accent" disabled={enviando || !pronto} onClick={confirmar}>
                {enviando
                  ? "Importando..."
                  : `Importar ${receitasMarcadas.length} receita${receitasMarcadas.length === 1 ? "" : "s"} e ${despesasMarcadas.length} despesa${despesasMarcadas.length === 1 ? "" : "s"}`}
              </Button>
            )}
          </div>
        </div>
      )}

      {resultado && (
        <div className="flex flex-col gap-4">
          <p className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">
            {resultado.sucesso} de {resultado.total} recebimento{resultado.total === 1 ? "" : "s"} importado
            {resultado.sucesso === 1 ? "" : "s"}
            {(resultado.despesas_registradas ?? 0) > 0 && ` e ${resultado.despesas_registradas} despesa(s) registrada(s)`}.
          </p>
          <ListaSemNota itens={resultado.sem_nota ?? []} />
          {resultado.erro > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-danger-700">
              {resultado.itens
                .filter((i) => !i.ok)
                .map((i) => (
                  <li key={i.indice} className="rounded-lg bg-danger-50 px-3 py-2">
                    Linha {i.indice + 1}: {i.mensagem}
                  </li>
                ))}
            </ul>
          )}
          <div className="flex justify-end pt-2">
            <Button type="button" variant="accent" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
