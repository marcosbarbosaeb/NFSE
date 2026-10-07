import { CampoMoeda } from "../ui/CampoMoeda"
import { ArrowLeftRight, UploadCloud } from "lucide-react"
import { type DragEvent, type FormEvent, useState } from "react"
import { Link } from "react-router-dom"
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
import { CaixaBusca, type OpcaoBusca } from "../ui/CaixaBusca"
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
}

interface Opcao {
  id: string
  apelido: string
  sem_nota?: boolean
}

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
  const [arrastando, setArrastando] = useState(false)
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
          if (l.linha === alvo.linha) return { ...l, vinculoId, emissaoId: nota(l), origem: null }
          if (alvo.chave && l.chave === alvo.chave && l.credito && !l.vinculoId) return { ...l, vinculoId, emissaoId: nota(l) }
          return l
        }) ?? null,
    )
  }

  function escolherCategoria(alvo: Linha, categoria: string, tipoDespesa: "despesa" | "retirada") {
    setLinhas(
      (atuais) =>
        atuais?.map((l) => {
          if (l.linha === alvo.linha) return { ...l, categoria, tipoDespesa, origem: null }
          if (alvo.chave && l.chave === alvo.chave && !l.credito) return { ...l, categoria, tipoDespesa }
          return l
        }) ?? null,
    )
  }

  async function criarTomador(l: Linha, nome: string) {
    setErro(null)
    try {
      const novo = await api.post<Opcao>("/vinculos/controle", { nome })
      setTomadores((atuais) => (atuais.some((v) => v.id === novo.id) ? atuais : [...atuais, novo]))
      escolherTomador(l, novo.id)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    }
  }

  function criarCategoria(l: Linha, nome: string) {
    const existente = [...categorias, ...retiradas].find((c) => c.toLowerCase() === nome.toLowerCase())
    if (!existente) setCategorias((atuais) => [...atuais, nome].sort((a, b) => a.localeCompare(b, "pt-BR")))
    escolherCategoria(l, existente ?? nome, existente && retiradas.includes(existente) ? "retirada" : "despesa")
  }

  function soltarArquivo(e: DragEvent) {
    e.preventDefault()
    setArrastando(false)
    const solto = e.dataTransfer.files?.[0]
    if (solto) setArquivo(solto)
  }

  const opcoesTomador: OpcaoBusca[] = [
    ...tomadores.filter((v) => !v.sem_nota).map((v) => ({ id: v.id, rotulo: v.apelido })),
    ...tomadores.filter((v) => v.sem_nota).map((v) => ({ id: v.id, rotulo: v.apelido, grupo: "Só controle (sem nota)" })),
  ]
  const opcoesCategoria: OpcaoBusca[] = [
    ...categorias.map((c) => ({ id: `despesa|${c}`, rotulo: c })),
    ...retiradas.map((c) => ({ id: `retirada|${c}`, rotulo: c, grupo: "Retiradas (não entram como despesa)" })),
  ]

  const receitas = (linhas ?? []).filter((l) => l.credito)
  const despesas = (linhas ?? []).filter((l) => !l.credito)
  const receitasMarcadas = receitas.filter((l) => l.incluir)
  const despesasMarcadas = despesas.filter((l) => l.incluir)
  // Vai ser lançada agora: marcada e classificada. O resto (desmarcada ou
  // sem tomador/categoria) fica guardado pra Conciliação — menos o que já
  // tinha sido lançado numa importação anterior.
  const pronta = (l: Linha) => l.incluir && Number(l.valor) > 0 && (l.credito ? !!l.vinculoId : !!l.categoria.trim())
  const receitasAgora = receitas.filter(pronta)
  const despesasAgora = despesas.filter(pronta)
  const paraDepois = (linhas ?? []).filter((l) => !pronta(l) && !l.jaLancado && Number(l.valor) > 0)
  const soma = (lista: Linha[]) => lista.reduce((s, l) => s + (Number(l.valor) || 0), 0)

  async function confirmar() {
    setEnviando(true)
    setErro(null)
    try {
      const itens: ItemConfirmarExtrato[] = receitasAgora.map((l) => ({
        vinculo_id: l.vinculoId,
        emissao_id: l.emissaoId || null,
        competencia: notas.find((n) => n.emissao_id === l.emissaoId)?.competencia ?? l.competenciaReceita,
        valor: Number(l.valor),
        data_recebimento: l.data || null,
        descricao: l.descricao,
      }))
      const saidas = despesasAgora.map((l) => ({
        categoria: l.categoria.trim(),
        tipo: l.tipoDespesa,
        competencia: l.competenciaDespesa,
        valor: Number(l.valor),
        data: l.data || null,
        descricao: l.descricao,
      }))
      const pendentes = paraDepois.map((l) => ({ data: l.data || null, descricao: l.descricao, valor: Number(l.valor), credito: l.credito }))
      const resp = await api.post<ConfirmarExtratoResultado>("/recebimentos/extrato/confirmar", {
        itens,
        despesas: saidas,
        pendentes,
        arquivo: arquivo?.name ?? null,
      })
      setResultado(resp)
      onImportado()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  function linhaDaLista(l: Linha) {
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
            <CampoMoeda
              valor={l.valor}
              onChange={(valor) => mudar(l.linha, { valor })}
              disabled={!l.incluir}
              aria-label="Valor em reais"
              className={`${CAMPO} w-32 shrink-0 text-right tabular-nums`}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {l.credito ? (
              <CaixaBusca
                valor={l.vinculoId}
                opcoes={opcoesTomador}
                onEscolher={(id) => escolherTomador(l, id)}
                onCriar={(nome) => criarTomador(l, nome)}
                rotuloCriar="Novo cliente"
                placeholder="De qual cliente? (digite pra buscar)"
                disabled={!l.incluir}
                alerta={l.incluir && !l.vinculoId}
                ariaLabel="Cliente"
                className="min-w-[200px] flex-1"
              />
            ) : (
              <CaixaBusca
                valor={`${l.tipoDespesa}|${l.categoria}`}
                opcoes={
                  opcoesCategoria.some((o) => o.id === `${l.tipoDespesa}|${l.categoria}`)
                    ? opcoesCategoria
                    : [{ id: `${l.tipoDespesa}|${l.categoria}`, rotulo: l.categoria }, ...opcoesCategoria]
                }
                onEscolher={(id) => {
                  const [tipo, ...resto] = id.split("|")
                  escolherCategoria(l, resto.join("|"), tipo === "retirada" ? "retirada" : "despesa")
                }}
                onCriar={(nome) => criarCategoria(l, nome)}
                rotuloCriar="Nova categoria"
                placeholder="Categoria (digite pra buscar)"
                disabled={!l.incluir}
                ariaLabel="Categoria"
                className="min-w-[220px] flex-1"
              />
            )}
            {notasDoTomador.length > 0 && (
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
              onClick={() => mudar(l.linha, { credito: !l.credito })}
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
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setArrastando(true)
            }}
            onDragLeave={() => setArrastando(false)}
            onDrop={soltarArquivo}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${arrastando ? "border-primary-500 bg-primary-50 dark:bg-primary-900/20" : "border-slate-300 hover:border-primary-400 dark:border-slate-600"}`}
          >
            <UploadCloud className="h-8 w-8 text-slate-400" aria-hidden />
            {arquivo ? (
              <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{arquivo.name}</span>
            ) : (
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Arraste o extrato pra cá</span>
            )}
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {arquivo ? "Clique ou arraste outro arquivo pra trocar" : "ou clique pra escolher o arquivo (PDF, OFX ou CSV)"}
            </span>
            <input
              type="file"
              accept=".pdf,.ofx,.csv,.txt,application/pdf,text/csv"
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="sr-only"
              aria-label="Arquivo do extrato"
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
                Classifique o que quiser agora — o que ficar sem classificar (ou desmarcado) fica guardado na Conciliação pra
                resolver depois. Suas escolhas ficam lembradas: no próximo extrato, o mesmo pagador já vem classificado.
              </p>
              {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
              <div className="flex max-h-[62vh] flex-col gap-4 overflow-y-auto pr-1">
                {bloco(
                  "Receitas",
                  "Escolha de qual cliente é cada entrada (e a nota que ela paga, quando houver).",
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
            {linhas.length > 0 && paraDepois.length > 0 && (
              <p className="mr-auto text-sm text-slate-500 dark:text-slate-400">
                {paraDepois.length === 1 ? "1 linha fica" : `${paraDepois.length} linhas ficam`} pra classificar depois, na Conciliação.
              </p>
            )}
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            {linhas.length > 0 && (
              <Button
                type="button"
                variant="accent"
                disabled={enviando || receitasAgora.length + despesasAgora.length + paraDepois.length === 0}
                onClick={confirmar}
              >
                {enviando
                  ? "Importando..."
                  : receitasAgora.length + despesasAgora.length === 0
                    ? "Guardar pra classificar depois"
                    : `Importar ${receitasAgora.length} receita${receitasAgora.length === 1 ? "" : "s"} e ${despesasAgora.length} despesa${despesasAgora.length === 1 ? "" : "s"}`}
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
          {(resultado.pendentes ?? 0) > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary-100 bg-primary-50/60 px-4 py-3 text-sm text-slate-700 dark:border-primary-900/40 dark:bg-primary-900/20 dark:text-slate-200">
              <span>
                {resultado.pendentes === 1
                  ? "1 lançamento do extrato está sem classificar."
                  : `${resultado.pendentes} lançamentos do extrato estão sem classificar.`}
              </span>
              <Link to="/app/financeiro/conciliacao?parte=extrato" onClick={onClose} className="font-semibold text-primary-700 hover:underline dark:text-primary-200">
                Abrir a Conciliação →
              </Link>
            </div>
          )}
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
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Não era isso? Dá pra desfazer esta importação inteira em Financeiro › Conciliação › Importações feitas.
          </p>
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
