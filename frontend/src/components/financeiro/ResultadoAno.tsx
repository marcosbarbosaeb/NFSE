import { ChevronDown, ChevronRight, Search, X } from "lucide-react"
import { Fragment, useState, type ReactNode } from "react"
import { formatBRL } from "../../lib/format"
import { MESES_ABREV, NOMES_MESES, formatPct } from "../../lib/financeiro"
import type { ResumoFinanceiro, SecaoMesAMes } from "../../lib/types"
import { Card } from "../ui/Card"
import {
  AvisoDetalhe,
  COLUNA_NOME,
  COLUNA_TOTAL,
  FAIXA_FORTE,
  FUNDO_BASE,
  FUNDO_RESULTADO,
  FUNDO_SECAO_ABERTA,
  GrupoDetalhe,
  VEU_MES,
  Valor,
  contagem,
  montarGrupo,
  palavrasDaBusca,
  useDetalheMesAMes,
  type GrupoVisivel,
} from "./MesAMesDetalhe"

// "Resultado do ano" (28/09/2026) — a parte de cima da planilha "Controle CP"
// dentro da Ana: lucro, margem, retiradas e o saldo que ainda dá pra
// distribuir, mês a mês (GET /financeiro/resumo?ano=).
// 05/10/2026: as linhas de dinheiro abrem no detalhe (quem pagou, com o que
// gastou) e têm busca — ver MesAMesDetalhe.tsx.

function Kpi({ label, valor, detalhe, negativo, destaque }: { label: string; valor: ReactNode; detalhe?: ReactNode; negativo?: boolean; destaque?: boolean }) {
  return (
    <Card className={`flex min-w-0 flex-col gap-1 p-3 sm:p-4 ${destaque ? "ring-1 ring-primary-200 dark:ring-primary-800" : ""}`}>
      <p className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p
        className={`break-words text-base font-semibold leading-snug tabular-nums sm:text-lg ${negativo ? "text-danger-600 dark:text-danger-400" : "text-slate-900 dark:text-slate-100"}`}
      >
        {valor}
      </p>
      {detalhe && <p className="truncate text-xs text-slate-400 dark:text-slate-500">{detalhe}</p>}
    </Card>
  )
}

interface LinhaTabela {
  rotulo: string
  valores: (number | null)[]
  total: number | null
  pct?: boolean
  sub?: boolean
  forte?: boolean
  vermelhoSeNegativo?: boolean
  dica?: string
  /** Linha que abre no detalhe (por cliente ou por categoria → gasto). */
  secao?: SecaoMesAMes
}

const SECAO_VAZIA: Record<SecaoMesAMes, string> = {
  faturado: "Nenhuma nota confirmada",
  recebido: "Nenhum recebimento",
  despesas: "Nenhuma despesa",
  retiradas: "Nenhuma retirada",
}

function soma(valores: number[]): number {
  return valores.reduce((s, v) => s + v, 0)
}

export function ResultadoAno({
  resumo,
  erro,
  ano,
  mes,
  onSelecionarMes,
  semTitulo,
  comNotas = true,
  semCategorias = false,
}: {
  /** A tela já mostra o "Para onde vai o dinheiro" num card próprio (gráfico). */
  semCategorias?: boolean
  /** Módulo de notas ligado: mostra o faturado e o que falta receber. */
  comNotas?: boolean
  /** A tela já mostra o título do card (cards recolhíveis do Financeiro). */
  semTitulo?: boolean
  resumo: ResumoFinanceiro | null
  erro?: string | null
  ano: string
  mes: string
  onSelecionarMes: (mes: string) => void
}) {
  const i = mes ? Number(mes) - 1 : -1
  // Detalhe do mês a mês: linhas abertas, busca e a linha marcada.
  const [abertas, setAbertas] = useState<Set<string>>(() => new Set())
  const [busca, setBusca] = useState("")
  const [destaque, setDestaque] = useState<string | null>(null)
  const palavras = palavrasDaBusca(busca)
  const buscando = palavras.length > 0
  // Só busca o detalhe no servidor quando a pessoa abre uma linha ou pesquisa.
  const detalhe = useDetalheMesAMes(resumo, ano, buscando || abertas.size > 0)
  const alternar = (chave: string) =>
    setAbertas((atual) => {
      const novo = new Set(atual)
      if (!novo.delete(chave)) novo.add(chave)
      return novo
    })

  if (!resumo) {
    return (
      <Card className="p-5">
        {!semTitulo && <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Resultado do ano</h2>}
        <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">{erro ?? "Carregando..."}</p>
      </Card>
    )
  }

  const t = resumo.totais
  const doPeriodo = (serie: number[], total: number) => (i >= 0 ? serie[i] : total)
  const recebido = doPeriodo(resumo.recebido, t.recebido)
  const despesas = doPeriodo(resumo.despesas, t.despesas)
  const impostos = doPeriodo(resumo.impostos, t.impostos)
  const ferramentas = doPeriodo(resumo.ferramentas, t.ferramentas)
  const lucro = doPeriodo(resumo.lucro, t.lucro)
  const retiradas = doPeriodo(resumo.retiradas, t.retiradas)
  const margem = i >= 0 ? resumo.margem[i] : t.margem
  const saldo = i >= 0 ? resumo.saldo_a_distribuir[i] : t.saldo_a_distribuir
  const cargaImpostos = i >= 0 ? (recebido ? Math.round((impostos / recebido) * 1000) / 10 : null) : t.carga_impostos
  const rotuloPeriodo = i >= 0 ? `${NOMES_MESES[i]} de ${ano}` : `em ${ano}`

  const linhas: LinhaTabela[] = [
    ...(comNotas
      ? [{ rotulo: "Faturado (notas)", valores: resumo.faturado, total: t.faturado, dica: "Notas confirmadas, pelo mês de competência.", secao: "faturado" as const }]
      : []),
    {
      rotulo: "Recebido",
      valores: resumo.recebido,
      total: t.recebido,
      dica: comNotas ? "Pagamentos registrados, pelo mês da nota." : "Recebimentos registrados, pelo mês de referência.",
      secao: "recebido",
    },
    { rotulo: "Despesas", valores: resumo.despesas, total: t.despesas, dica: "Sem as retiradas (distribuição de lucros).", secao: "despesas" },
    { rotulo: "dos quais impostos", valores: resumo.impostos, total: t.impostos, sub: true, dica: "Simples, INSS, DAS e afins." },
    { rotulo: "Lucro", valores: resumo.lucro, total: t.lucro, forte: true, vermelhoSeNegativo: true, dica: "Recebido − despesas." },
    { rotulo: "Margem", valores: resumo.margem, total: t.margem, pct: true, sub: true, vermelhoSeNegativo: true, dica: "Lucro ÷ recebido." },
    { rotulo: "Retiradas", valores: resumo.retiradas, total: t.retiradas, dica: "Distribuição de lucros (todas as contas).", secao: "retiradas" },
    {
      rotulo: "Saldo a distribuir",
      valores: resumo.saldo_a_distribuir,
      total: t.saldo_a_distribuir,
      forte: true,
      vermelhoSeNegativo: true,
      dica: "Acumulado no ano: lucro − retiradas até o mês.",
    },
  ]

  // Meses sem nenhum movimento ficam com "—" (deixa a tabela respirar).
  const mesVazio = resumo.meses.map((_, m) => !(comNotas && resumo.faturado[m]) && !resumo.recebido[m] && !resumo.despesas[m] && !resumo.retiradas[m])

  // Detalhe de cada linha que abre. Com busca, abre sozinho o que bate.
  const grupos = new Map<SecaoMesAMes, GrupoVisivel>()
  if (detalhe.dados) {
    for (const l of linhas) {
      if (l.secao && (buscando || abertas.has(l.secao))) grupos.set(l.secao, montarGrupo(l.secao, detalhe.dados[l.secao], palavras, abertas))
    }
  }
  const achados = [...grupos.values()].reduce((n, g) => n + g.linhas.length, 0)
  const algoAberto = buscando || linhas.some((l) => l.secao && abertas.has(l.secao))
  const colunas = resumo.meses.length + 2

  // "Para onde vai o dinheiro": as maiores categorias; o resto vira "Outras".
  const MAX_CATEGORIAS = 7
  const categorias =
    resumo.categorias.length > MAX_CATEGORIAS + 1
      ? [
          ...resumo.categorias.slice(0, MAX_CATEGORIAS),
          { categoria: `Outras (${resumo.categorias.length - MAX_CATEGORIAS})`, total: soma(resumo.categorias.slice(MAX_CATEGORIAS).map((c) => c.total)) },
        ]
      : resumo.categorias
  const totalCategorias = soma(resumo.categorias.map((c) => c.total))
  const maiorCategoria = Math.max(1, ...categorias.map((c) => c.total))

  return (
    <section className="flex flex-col gap-4" aria-labelledby="titulo-resultado-ano">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-resultado-ano" className={semTitulo ? "sr-only" : "text-base font-semibold text-slate-800 dark:text-slate-200"}>
          Resultado {i >= 0 ? `de ${NOMES_MESES[i].toLowerCase()}` : "do ano"}
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          {i >= 0 ? `${NOMES_MESES[i]} de ${ano}` : `Janeiro a dezembro de ${ano}`} · recebimentos pelo mês {comNotas ? "da nota" : "de referência"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 2xl:grid-cols-7" data-tour="financeiro-resumo">
        <Kpi label="Recebido" valor={formatBRL(recebido)} detalhe={rotuloPeriodo} />
        <Kpi label="Despesas" valor={formatBRL(despesas)} detalhe="sem as retiradas" />
        <Kpi label="Lucro" valor={formatBRL(lucro)} negativo={lucro < 0} destaque detalhe="recebido − despesas" />
        <Kpi label="Margem" valor={formatPct(margem)} negativo={margem !== null && margem < 0} detalhe="do que entrou" />
        <Kpi label="Retiradas" valor={formatBRL(retiradas)} detalhe="distribuição de lucros" />
        <Kpi
          label="Saldo a distribuir"
          valor={formatBRL(saldo)}
          negativo={saldo < 0}
          detalhe={i >= 0 ? `acumulado até ${MESES_ABREV[i].toLowerCase()}` : "acumulado no ano"}
        />
        {comNotas && <Kpi label="A receber" valor={formatBRL(t.a_receber)} detalhe="todos os meses" />}
      </div>

      <p className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span>
          Carga de impostos: <strong className="font-semibold text-slate-700 dark:text-slate-200">{formatPct(cargaImpostos)}</strong> do recebido (
          {formatBRL(impostos)})
        </span>
        <span>
          Gasto com ferramentas: <strong className="font-semibold text-slate-700 dark:text-slate-200">{formatBRL(ferramentas)}</strong>
          {recebido > 0 && ferramentas > 0 && ` (${formatPct(Math.round((ferramentas / recebido) * 1000) / 10)} do recebido)`}
        </span>
      </p>

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Mês a mês</h3>
            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
              Valores em R$ · clique no mês pra filtrar a tela · clique na seta pra ver o detalhe
            </p>
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <input
              type="text"
              inputMode="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape" && busca) {
                  e.stopPropagation()
                  setBusca("")
                }
              }}
              placeholder="Buscar cliente ou gasto…"
              aria-label="Buscar cliente ou gasto no mês a mês"
              className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-8 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            {busca && (
              <button
                type="button"
                onClick={() => setBusca("")}
                aria-label="Limpar a busca"
                title="Limpar a busca"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-200"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            )}
          </div>
        </div>
        {buscando && (
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400" role="status">
            {detalhe.erro ? (
              <>
                {detalhe.erro}{" "}
                <button type="button" onClick={detalhe.tentarDeNovo} className="font-medium text-primary-700 underline dark:text-primary-300">
                  Tentar de novo
                </button>
              </>
            ) : !detalhe.dados ? (
              "Buscando…"
            ) : achados === 0 ? (
              `Nada encontrado com “${busca.trim()}” em ${ano}. Confira o nome ou troque o ano.`
            ) : (
              `${achados} ${achados === 1 ? "linha encontrada" : "linhas encontradas"} com “${busca.trim()}” — estão embaixo de cada total, com o trecho pintado.`
            )}
          </p>
        )}
        {/* Com detalhe aberto a tabela rola dentro da própria caixa: os meses ficam presos em cima.
            Sem margem negativa: a 1ª coluna presa precisa encostar na borda da caixa de rolagem. */}
        <div className={`overflow-x-auto ${algoAberto ? "max-h-[78vh] overflow-y-auto overscroll-x-contain" : ""}`}>
          <table className="w-full min-w-[940px] border-separate border-spacing-0 text-right text-xs tabular-nums">
            <caption className="sr-only">Resultado mês a mês de {ano}</caption>
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
                <th scope="col" className={`sticky left-0 top-0 z-30 border-b border-b-slate-200 py-2 pr-3 text-left font-medium dark:border-b-slate-600 ${COLUNA_NOME} ${FUNDO_BASE}`}>
                  <span className="sr-only">Linha</span>
                </th>
                {resumo.meses.map((m, idx) => {
                  const ativo = idx === i
                  return (
                    <th
                      key={m}
                      scope="col"
                      className={`sticky top-0 z-20 border-b border-b-slate-200 px-1 py-1 font-medium dark:border-b-slate-600 ${ativo ? "bg-[#eceffb] dark:bg-[#2c3857]" : FUNDO_BASE}`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelecionarMes(ativo ? "" : m)}
                        aria-pressed={ativo}
                        title={ativo ? "Voltar pro ano inteiro" : `Ver só ${NOMES_MESES[idx].toLowerCase()}`}
                        className={`w-full rounded px-1.5 py-1 text-right uppercase hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200 ${
                          ativo ? "font-bold text-primary-700 dark:text-primary-300" : ""
                        }`}
                      >
                        {MESES_ABREV[idx]}
                      </button>
                    </th>
                  )
                })}
                <th
                  scope="col"
                  title={`Soma de janeiro a dezembro de ${ano}`}
                  className={`sticky top-0 z-30 border-b border-b-slate-200 py-2 font-semibold text-slate-600 dark:border-b-slate-600 dark:text-slate-300 ${COLUNA_TOTAL} ${FUNDO_BASE}`}
                >
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l, pos) => {
                const secao = l.secao
                const grupo = secao ? grupos.get(secao) : undefined
                // Com busca, a linha abre sozinha quando tem algo que bate.
                const aberta = !!secao && (buscando ? !!grupo?.linhas.length : abertas.has(secao))
                const Seta = aberta ? ChevronDown : ChevronRight
                const negativo = (v: number | null) => !!l.vermelhoSeNegativo && v !== null && v < 0
                const cor = (v: number | null) =>
                  negativo(v)
                    ? "text-danger-600 dark:text-danger-400"
                    : l.sub
                      ? "text-slate-500 dark:text-slate-400"
                      : l.forte
                        ? "text-slate-900 dark:text-white"
                        : "text-slate-800 dark:text-slate-100"
                const texto = (v: number | null) => (v === null ? "—" : l.pct ? formatPct(v) : <Valor valor={v} />)
                const exato = (v: number | null) => (v === null ? "" : l.pct ? formatPct(v) : formatBRL(v))
                // Lucro e saldo: faixa colorida, letra maior e uma linha em cima — é a resposta da tabela.
                const borda = l.forte ? "border-t-2 border-t-primary-200 dark:border-t-primary-500/50" : ""
                const altura = l.forte ? "py-2.5" : l.sub ? "py-1" : "py-2"
                const peso = l.forte ? "text-[13px] font-bold" : l.sub ? "text-[11px]" : "font-semibold"
                // O bloco aberto vem depois das linhas "filhas" do total (ex.: "dos quais impostos").
                const dona = l.sub ? linhas.slice(0, pos).reverse().find((x) => !x.sub) : l
                const fechaBloco = pos + 1 === linhas.length || !linhas[pos + 1].sub
                const donaSecao = fechaBloco ? dona?.secao : undefined
                const grupoAqui = donaSecao ? grupos.get(donaSecao) : undefined
                // A linha filha de um total aberto ("dos quais impostos") fica na mesma faixa do total.
                const donaAberta = l.sub && !!dona?.secao && (buscando ? !!grupos.get(dona.secao)?.linhas.length : abertas.has(dona.secao))
                const noCabecalho = aberta || donaAberta
                const fundo = l.forte ? FUNDO_RESULTADO : noCabecalho ? FUNDO_SECAO_ABERTA : FUNDO_BASE
                return (
                  <Fragment key={l.rotulo}>
                    <tr className={fundo}>
                      <th
                        scope="row"
                        title={l.dica}
                        className={`sticky left-0 z-10 pr-2 text-left ${COLUNA_NOME} ${fundo} ${borda} ${altura} ${noCabecalho ? FAIXA_FORTE : ""} ${
                          l.sub
                            ? "pl-[1.9375rem] text-[11px] font-normal text-slate-500 dark:text-slate-400"
                            : l.forte
                              ? "pl-[1.9375rem] text-[13px] font-bold text-slate-900 dark:text-white"
                              : secao
                                ? "pl-[0.5625rem] font-semibold text-slate-800 dark:text-slate-100"
                                : "pl-[1.9375rem] font-semibold text-slate-800 dark:text-slate-100"
                        }`}
                      >
                        {secao ? (
                          <button
                            type="button"
                            onClick={() => alternar(secao)}
                            aria-expanded={aberta}
                            title={aberta ? "Fechar o detalhe" : secao === "despesas" || secao === "retiradas" ? "Ver por categoria" : "Ver por cliente"}
                            className="group/secao -my-1 flex w-full items-start gap-1 rounded py-1 text-left hover:text-primary-700 dark:hover:text-primary-300"
                          >
                            <Seta className={`h-4 w-4 shrink-0 ${aberta ? "text-primary-600 dark:text-primary-300" : "text-slate-400 dark:text-slate-500"}`} aria-hidden />
                            <span className="min-w-0">
                              <span className="block">{l.rotulo}</span>
                              {aberta && grupo && (
                                <span className="block text-[11px] font-normal leading-4 text-slate-500 dark:text-slate-400">
                                  {buscando ? `${grupo.quantidade} ${grupo.quantidade === 1 ? "encontrado" : "encontrados"}` : contagem(secao, grupo.quantidade)}
                                  {!buscando && (
                                    <>
                                      {" · "}
                                      <span className="font-medium text-primary-700 group-hover/secao:underline dark:text-primary-300">recolher</span>
                                    </>
                                  )}
                                </span>
                              )}
                            </span>
                          </button>
                        ) : (
                          l.rotulo
                        )}
                      </th>
                      {l.valores.map((v, idx) => {
                        const vazio = mesVazio[idx] && !l.rotulo.startsWith("Saldo")
                        const zero = vazio || v === 0
                        return (
                          <td
                            key={idx}
                            title={zero || v === null ? undefined : `${l.rotulo} · ${NOMES_MESES[idx]}: ${exato(v)}`}
                            className={`px-2 ${altura} ${peso} ${borda} ${idx === i ? VEU_MES : ""} ${zero && !negativo(v) ? "text-slate-300 dark:text-slate-600" : cor(v)}`}
                          >
                            {vazio || (v === 0 && !l.forte) ? "—" : texto(v)}
                          </td>
                        )
                      })}
                      <td title={`${l.rotulo} · total do ano: ${exato(l.total)}`} className={`z-10 ${altura} ${peso} ${borda} ${COLUNA_TOTAL} ${fundo} ${cor(l.total)}`}>
                        {texto(l.total)}
                      </td>
                    </tr>
                    {donaSecao && grupoAqui && grupoAqui.linhas.length > 0 && (
                      <GrupoDetalhe secao={donaSecao} grupo={grupoAqui} palavras={palavras} mesAtivo={i} destaque={destaque} onDestacar={setDestaque} onAlternar={alternar} />
                    )}
                    {/* Aberta no clique (sem busca): avisa enquanto carrega, se falhou ou se não tem nada. */}
                    {donaSecao && !buscando && abertas.has(donaSecao) && !grupoAqui?.linhas.length && (
                      <AvisoDetalhe colunas={colunas}>
                        {detalhe.erro ? (
                          <>
                            {detalhe.erro}{" "}
                            <button type="button" onClick={detalhe.tentarDeNovo} className="font-medium text-primary-700 underline dark:text-primary-300">
                              Tentar de novo
                            </button>
                          </>
                        ) : !detalhe.dados ? (
                          "Carregando…"
                        ) : (
                          `${SECAO_VAZIA[donaSecao]} em ${ano}.`
                        )}
                      </AvisoDetalhe>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {!semCategorias && (
      <Card className="p-5">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Para onde vai o dinheiro</h3>
          <span className="text-xs text-slate-400 dark:text-slate-500">em {ano}</span>
        </div>
        {categorias.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma despesa em {ano} ainda.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
            {categorias.map((c) => {
              const pct = totalCategorias ? (c.total / totalCategorias) * 100 : 0
              const rotulo = `${c.categoria}: ${formatBRL(c.total)} (${formatPct(Math.round(pct * 10) / 10)} das despesas)`
              return (
                <li key={c.categoria} title={rotulo}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="min-w-0 truncate text-slate-700 dark:text-slate-200">{c.categoria}</span>
                    <span className="shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
                      {formatBRL(c.total)} <span className="text-xs text-slate-400 dark:text-slate-500">· {Math.round(pct)}%</span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60" role="presentation">
                    <div className="h-1.5 rounded-full bg-primary-500 dark:bg-primary-400" style={{ width: `${Math.max(2, (c.total / maiorCategoria) * 100)}%` }} />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
      )}
    </section>
  )
}
