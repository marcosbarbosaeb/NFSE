import { ChevronDown, ChevronRight, ChevronUp } from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"
import { api } from "../../lib/api"
import { NOMES_MESES, formatValor, mensagemErro } from "../../lib/financeiro"
import { formatBRL } from "../../lib/format"
import type { DetalheMesAMes, LinhaMesAMes, ResumoFinanceiro, SecaoMesAMes } from "../../lib/types"

// Detalhe do "Mês a mês" (05/10/2026) — pedido do Marcos: "devo poder
// consultar quanto um tomador me pagou mês a mês ou quanto eu gastei mês a
// mês com alguma coisa". Cada total da tabela abre em quem/o quê
// (GET /financeiro/mes-a-mes?ano=). Só é buscado quando a pessoa abre uma
// linha ou digita na busca.
//
// Visual (05/10/2026, "ela estendida está confusa"): o que abre fica num bloco
// com fundo e uma faixa na esquerda, com rodapé — dá pra ver onde o detalhe
// começa e acaba. Cliente/categoria num nível, as coisas da categoria menores
// e mais pra dentro. Seção com muita linha mostra as maiores e soma o resto.

export function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

/** "  Conta de Luz " → ["conta", "de", "luz"]. */
export function palavrasDaBusca(busca: string): string[] {
  const alvo = semAcento(busca.trim())
  return alvo ? alvo.split(/\s+/) : []
}

/** Busca o detalhe quando `precisa` liga, e de novo sempre que o resumo é
 * recarregado (lançou uma despesa, registrou um recebimento...): assim o
 * detalhe nunca fica diferente dos totais. Enquanto recarrega, continua
 * mostrando o que já tinha do mesmo ano. */
export function useDetalheMesAMes(resumo: ResumoFinanceiro | null, ano: string, precisa: boolean) {
  const [detalhe, setDetalhe] = useState<{ de: ResumoFinanceiro; dados: DetalheMesAMes } | null>(null)
  const [falha, setFalha] = useState<{ de: ResumoFinanceiro; texto: string } | null>(null)
  const [tentativa, setTentativa] = useState(0)
  const emDia = !!resumo && detalhe?.de === resumo

  useEffect(() => {
    if (!resumo || !precisa || emDia) return
    let vivo = true
    api
      .get<DetalheMesAMes>(`/financeiro/mes-a-mes?ano=${resumo.ano}`)
      .then((dados) => {
        if (!vivo) return
        setDetalhe({ de: resumo, dados })
        setFalha(null)
      })
      .catch((err) => {
        if (vivo) setFalha({ de: resumo, texto: mensagemErro(err, "Não deu pra carregar o detalhe.") })
      })
    return () => {
      vivo = false
    }
  }, [resumo, precisa, emDia, tentativa])

  const erro = falha && falha.de === resumo ? falha.texto : null
  return {
    dados: detalhe && detalhe.dados.ano === ano ? detalhe.dados : null,
    erro,
    carregando: precisa && !!resumo && !emDia && !erro,
    tentarDeNovo: () => {
      setFalha(null)
      setTentativa((n) => n + 1)
    },
  }
}

// ---------------------------------------------------------------------------
// Cores e peças que a tabela inteira usa (ResultadoAno + as linhas daqui).
// Os fundos são sólidos: a 1ª coluna e a do total ficam presas na rolagem.

export const FUNDO_BASE = "bg-white dark:bg-slate-800"
/** Total que está aberto (cabeçalho do bloco). */
export const FUNDO_SECAO_ABERTA = "bg-slate-100 dark:bg-slate-700"
/** Dentro do bloco aberto. */
export const FUNDO_GRUPO = "bg-slate-50 dark:bg-[#182234]"
/** Lucro e saldo. */
export const FUNDO_RESULTADO = "bg-primary-50 dark:bg-[#243057]"
const FUNDO_MARCADA = "bg-primary-100 dark:bg-[#2c3a6b]"
/** Mês escolhido na tela: um véu por cima do fundo da linha, igual em todos os níveis. */
export const VEU_MES = "bg-primary-500/10 dark:bg-primary-400/15"
/** 1ª coluna: larga o bastante pro nome caber em duas linhas. */
export const COLUNA_NOME =
  "w-38 min-w-38 max-w-38 border-r border-r-slate-200/70 sm:w-52 sm:min-w-52 sm:max-w-52 lg:w-60 lg:min-w-60 lg:max-w-60 dark:border-r-slate-600/60"
/** Coluna do total do ano: separada dos meses e presa na direita em tela grande. */
export const COLUNA_TOTAL = "border-l-2 border-l-slate-200 pl-3 pr-2 lg:sticky lg:right-0 dark:border-l-slate-600"
const ZERO = "text-slate-300 dark:text-slate-600"

/** 1.234,56 com os centavos menores e mais claros: o olho pega os reais. */
export function Valor({ valor }: { valor: number }) {
  const [reais, centavos] = formatValor(valor).split(",")
  return (
    <>
      {reais}
      <span className="text-[0.8em] opacity-60">,{centavos}</span>
    </>
  )
}

/** O nome com o trecho que bateu na busca pintado. */
function Marcado({ texto, palavras }: { texto: string; palavras: string[] }) {
  if (palavras.length === 0) return <>{texto}</>
  const letras = [...texto]
  const limpo = letras.map((c) => semAcento(c))
  // Só pinta quando cada letra continua sendo uma letra depois de tirar o acento.
  if (limpo.some((c) => [...c].length !== 1)) return <>{texto}</>
  const alvo = limpo.join("")
  const pintar = new Array<boolean>(letras.length).fill(false)
  for (const p of palavras) {
    for (let i = alvo.indexOf(p); i >= 0; i = alvo.indexOf(p, i + 1)) pintar.fill(true, i, i + [...p].length)
  }
  const pedacos: ReactNode[] = []
  for (let i = 0; i < letras.length; ) {
    let j = i
    while (j < letras.length && pintar[j] === pintar[i]) j++
    const trecho = letras.slice(i, j).join("")
    pedacos.push(
      pintar[i] ? (
        <mark key={i} className="rounded-sm bg-warning-300/70 text-inherit dark:bg-warning-400/40">
          {trecho}
        </mark>
      ) : (
        trecho
      ),
    )
    i = j
  }
  return <>{pedacos}</>
}

// ---------------------------------------------------------------------------
// Quais linhas aparecem embaixo de um total.

/** Seção com mais linhas que isso mostra só as maiores (e soma o resto). */
export const LIMITE_LINHAS = 8

export interface LinhaVisivel {
  chave: string
  nome: string
  /** Na busca (lista corrida): a categoria onde a coisa está. */
  dentroDe?: string
  valores: number[]
  total: number
  nivel: 1 | 2
  /** "outros" = a soma das linhas menores que ficaram escondidas. */
  tipo: "linha" | "outros"
  /** Categoria que abre nas suas coisas. */
  expansivel: boolean
  aberta: boolean
  /** O que o clique abre/fecha (categoria, ou o "ver todos" do resto). */
  alterna?: string
  /** Última coisa de uma categoria aberta (fecha o risco da esquerda). */
  ultima?: boolean
}

export interface GrupoVisivel {
  linhas: LinhaVisivel[]
  /** Clientes ou categorias da seção (na busca: quantas linhas bateram). */
  quantidade: number
  /** Tem mais linhas que o limite: dá pra trocar entre "as maiores" e "todas". */
  cortavel: boolean
  todos: boolean
  chaveTodos: string
}

const porCliente = (secao: SecaoMesAMes) => secao === "faturado" || secao === "recebido"

/** "1 cliente", "19 clientes", "3 categorias". */
export function contagem(secao: SecaoMesAMes, n: number): string {
  if (porCliente(secao)) return `${n} ${n === 1 ? "cliente" : "clientes"}`
  return `${n} ${n === 1 ? "categoria" : "categorias"}`
}

function cortar<T extends { total: number }>(linhas: T[], todos: boolean): { visiveis: T[]; resto: T[] } {
  // Esconder uma linha só pra mostrar "+ 1 outro" não ajuda ninguém.
  if (todos || linhas.length <= LIMITE_LINHAS + 1) return { visiveis: linhas, resto: [] }
  const maiores = new Set([...linhas].sort((a, b) => Math.abs(b.total) - Math.abs(a.total)).slice(0, LIMITE_LINHAS))
  return { visiveis: linhas.filter((l) => maiores.has(l)), resto: linhas.filter((l) => !maiores.has(l)) }
}

function somar(linhas: { valores: number[]; total: number }[]): { valores: number[]; total: number } {
  const centavos = (v: number) => Math.round(v * 100) / 100
  const meses = linhas[0]?.valores.length ?? 12
  return {
    valores: Array.from({ length: meses }, (_, m) => centavos(linhas.reduce((s, l) => s + (l.valores[m] ?? 0), 0))),
    total: centavos(linhas.reduce((s, l) => s + l.total, 0)),
  }
}

/** As linhas de detalhe que aparecem embaixo de um total.
 * Sem busca: clientes/categorias (as maiores, ou todas), e as coisas das
 * categorias abertas. Com busca: uma lista corrida só com o que bate — a
 * coisa de dentro de uma categoria vem com o nome da categoria em cima. */
export function montarGrupo(secao: SecaoMesAMes, linhas: LinhaMesAMes[], palavras: string[], abertas: Set<string>): GrupoVisivel {
  const chaveTodos = `todos:${secao}`
  const saida: LinhaVisivel[] = []
  const chaveDe = (l: LinhaMesAMes) => `${secao}/${l.id ?? l.nome}`
  // Categoria com uma coisa só, de mesmo nome (lançamento sem descrição):
  // não tem o que abrir.
  const itensDe = (l: LinhaMesAMes) => {
    const itens = l.itens ?? []
    return itens.length > 1 || (itens.length === 1 && semAcento(itens[0].nome) !== semAcento(l.nome)) ? itens : []
  }

  if (palavras.length > 0) {
    const bate = (nome: string) => {
      const n = semAcento(nome)
      return palavras.every((p) => n.includes(p))
    }
    for (const l of linhas) {
      const chave = chaveDe(l)
      if (bate(l.nome)) saida.push({ chave, nome: l.nome, valores: l.valores, total: l.total, nivel: 1, tipo: "linha", expansivel: false, aberta: false })
      const itens = itensDe(l)
      // Categoria que já apareceu e só tem uma coisa: seria a mesma linha duas vezes.
      if (itens.length === 1 && bate(l.nome)) continue
      for (const it of itens) {
        if (!bate(it.nome)) continue
        saida.push({ chave: `${chave}/${it.nome}`, nome: it.nome, dentroDe: l.nome, valores: it.valores, total: it.total, nivel: 1, tipo: "linha", expansivel: false, aberta: false })
      }
    }
    return { linhas: saida, quantidade: saida.length, cortavel: false, todos: true, chaveTodos }
  }

  const todos = abertas.has(chaveTodos)
  const { visiveis, resto } = cortar(linhas, todos)
  for (const l of visiveis) {
    const chave = chaveDe(l)
    const itens = itensDe(l)
    const aberta = itens.length > 0 && abertas.has(chave)
    saida.push({ chave, nome: l.nome, valores: l.valores, total: l.total, nivel: 1, tipo: "linha", expansivel: itens.length > 0, aberta, alterna: itens.length > 0 ? chave : undefined })
    if (!aberta) continue
    const chaveItens = `todos:${chave}`
    const dentro = cortar(itens, abertas.has(chaveItens))
    for (const it of dentro.visiveis) {
      saida.push({ chave: `${chave}/${it.nome}`, nome: it.nome, valores: it.valores, total: it.total, nivel: 2, tipo: "linha", expansivel: false, aberta: false })
    }
    if (dentro.resto.length > 0) {
      saida.push({ chave: `${chave}/+outros`, nome: `+ ${dentro.resto.length} menores`, ...somar(dentro.resto), nivel: 2, tipo: "outros", expansivel: false, aberta: false, alterna: chaveItens })
    }
    saida[saida.length - 1].ultima = true
  }
  if (resto.length > 0) {
    const nome = porCliente(secao) ? `+ ${resto.length} clientes menores` : `+ ${resto.length} categorias menores`
    saida.push({ chave: `${secao}/+outros`, nome, ...somar(resto), nivel: 1, tipo: "outros", expansivel: false, aberta: false, alterna: chaveTodos })
  }
  return { linhas: saida, quantidade: linhas.length, cortavel: linhas.length > LIMITE_LINHAS + 1, todos, chaveTodos }
}

// ---------------------------------------------------------------------------

// Faixa na esquerda do bloco aberto. É sombra por dentro (e não borda) pra célula presa continuar tapando o que rola por baixo.
export const FAIXA = "shadow-[inset_3px_0_0_var(--color-primary-300)] dark:shadow-[inset_3px_0_0_var(--color-primary-500)]"
export const FAIXA_FORTE = "shadow-[inset_3px_0_0_var(--color-primary-500)] dark:shadow-[inset_3px_0_0_var(--color-primary-400)]"
const BOTAO_RODAPE =
  "inline-flex items-center gap-0.5 rounded font-medium text-primary-700 hover:underline focus-visible:outline-2 focus-visible:outline-primary-500 dark:text-primary-300"

/** Linha de aviso dentro do bloco aberto ("Carregando...", "Nenhum gasto..."). */
export function AvisoDetalhe({ colunas, children }: { colunas: number; children: ReactNode }) {
  return (
    <tr className={FUNDO_GRUPO}>
      <td colSpan={colunas} className={`border-b border-b-slate-200 py-2.5 text-left text-xs text-slate-500 dark:border-b-slate-600 dark:text-slate-400 ${FAIXA}`}>
        <span className="sticky left-3 inline-block pl-6">{children}</span>
      </td>
    </tr>
  )
}

/** O bloco que abre embaixo de um total: as linhas e o rodapé que fecha. */
export function GrupoDetalhe({
  secao,
  grupo,
  palavras,
  mesAtivo,
  destaque,
  onDestacar,
  onAlternar,
}: {
  secao: SecaoMesAMes
  grupo: GrupoVisivel
  /** Palavras da busca (vazio = sem busca). */
  palavras: string[]
  /** Índice do mês selecionado na tela (-1 = ano inteiro). */
  mesAtivo: number
  destaque: string | null
  onDestacar: (chave: string | null) => void
  onAlternar: (chave: string) => void
}) {
  const buscando = palavras.length > 0
  const meses = grupo.linhas[0]?.valores.length ?? 12
  return (
    <>
      {grupo.linhas.map((l) => {
        const marcada = destaque === l.chave
        const outros = l.tipo === "outros"
        const nivel2 = l.nivel === 2
        const fundo = marcada ? FUNDO_MARCADA : `${FUNDO_GRUPO} group-hover/linha:bg-slate-100 dark:group-hover/linha:bg-slate-700`
        const corNome = outros
          ? "italic text-slate-500 dark:text-slate-400"
          : nivel2
            ? "text-slate-500 dark:text-slate-400"
            : l.aberta
              ? "font-medium text-slate-800 dark:text-slate-100"
              : "text-slate-700 dark:text-slate-200"
        const corValor = marcada
          ? "font-medium text-slate-900 dark:text-white"
          : outros || nivel2
            ? "text-slate-500 dark:text-slate-400"
            : "text-slate-700 dark:text-slate-200"
        const tamanho = nivel2 ? "text-[11px] leading-4" : ""
        const altura = nivel2 ? "py-1" : "py-1.5"
        const titulo = l.dentroDe ? `${l.dentroDe} › ${l.nome}` : l.nome
        const acao = l.alterna
        const nome = (
          <span className="line-clamp-2 min-w-0 break-words">
            {l.dentroDe && <span className="block truncate text-[10px] leading-4 text-slate-400 dark:text-slate-500">{l.dentroDe}</span>}
            <Marcado texto={l.nome} palavras={palavras} />
            {outros && <span className="not-italic text-primary-700 dark:text-primary-300"> · ver</span>}
          </span>
        )
        return (
          <tr
            key={l.chave}
            // Categoria ou "+ N menores": o clique abre. Cliente ou gasto: marca
            // a linha pra acompanhar os meses com o olho.
            onClick={() => (acao ? onAlternar(acao) : onDestacar(marcada ? null : l.chave))}
            className={`group/linha cursor-pointer ${marcada ? FUNDO_MARCADA : `${FUNDO_GRUPO} hover:bg-slate-100 dark:hover:bg-slate-700`} ${tamanho}`}
          >
            <th scope="row" title={titulo} className={`sticky left-0 z-10 pr-2 text-left font-normal ${COLUNA_NOME} ${FAIXA} ${fundo} ${corNome} ${nivel2 ? "py-0 pl-[1.5625rem]" : `${altura} pl-[0.6875rem]`}`}>
              {nivel2 ? (
                // O risco na esquerda liga as coisas à categoria de cima.
                <span className={`flex border-l border-slate-300 pl-2.5 dark:border-slate-600 ${l.ultima ? "pb-1.5 pt-1" : "py-1"}`}>
                  {outros ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        if (acao) onAlternar(acao)
                      }}
                      className="text-left"
                    >
                      {nome}
                    </button>
                  ) : (
                    nome
                  )}
                </span>
              ) : acao ? (
                <button
                  type="button"
                  aria-expanded={l.expansivel ? l.aberta : undefined}
                  onClick={(e) => {
                    e.stopPropagation()
                    onAlternar(acao)
                  }}
                  className="flex w-full items-start gap-1 rounded text-left hover:text-slate-950 dark:hover:text-white"
                >
                  {outros ? (
                    <span className="w-3.5 shrink-0" aria-hidden />
                  ) : l.aberta ? (
                    <ChevronDown className="mt-px h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
                  ) : (
                    <ChevronRight className="mt-px h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
                  )}
                  {nome}
                </button>
              ) : (
                <span className="flex items-start gap-1">
                  <span className="w-3.5 shrink-0" aria-hidden />
                  {nome}
                </span>
              )}
            </th>
            {l.valores.map((v, idx) => (
              <td
                key={idx}
                title={v ? `${titulo} · ${NOMES_MESES[idx]}: ${formatBRL(v)}` : undefined}
                className={`px-2 ${altura} ${idx === mesAtivo ? VEU_MES : ""} ${v === 0 ? ZERO : corValor}`}
              >
                {v === 0 ? "—" : <Valor valor={v} />}
              </td>
            ))}
            <td
              title={`${titulo} · total do ano: ${formatBRL(l.total)}`}
              className={`z-10 ${altura} ${COLUNA_TOTAL} ${fundo} ${l.total === 0 ? ZERO : `${corValor} ${nivel2 || outros ? "" : "font-semibold"}`}`}
            >
              {l.total === 0 ? "—" : <Valor valor={l.total} />}
            </td>
          </tr>
        )
      })}
      {/* Rodapé: fecha o bloco (linha embaixo) e, sem busca, troca entre as maiores e todas. */}
      <tr className={FUNDO_GRUPO}>
        <th scope="row" className={`sticky left-0 z-10 border-b border-b-slate-200 text-left font-normal dark:border-b-slate-600 ${COLUNA_NOME} ${FAIXA} ${FUNDO_GRUPO} ${buscando ? "h-2 p-0" : "py-2 pl-[1.8125rem] pr-2"}`}>
          {buscando ? (
            <span className="sr-only">Fim dos encontrados</span>
          ) : (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] leading-4">
              {grupo.cortavel && (
                <button type="button" onClick={() => onAlternar(grupo.chaveTodos)} aria-expanded={grupo.todos} className={BOTAO_RODAPE}>
                  {grupo.todos ? `ver só os ${LIMITE_LINHAS} maiores` : `ver todos (${grupo.quantidade})`}
                </button>
              )}
              <button type="button" onClick={() => onAlternar(secao)} className={BOTAO_RODAPE} title="Fechar o detalhe">
                <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                recolher
              </button>
            </span>
          )}
        </th>
        <td colSpan={meses} className="border-b border-b-slate-200 p-0 dark:border-b-slate-600" />
        <td className={`z-10 border-b border-b-slate-200 p-0 dark:border-b-slate-600 ${COLUNA_TOTAL} ${FUNDO_GRUPO}`} />
      </tr>
    </>
  )
}
