import { ChevronDown, ChevronRight } from "lucide-react"
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

export interface LinhaVisivel {
  chave: string
  nome: string
  valores: number[]
  total: number
  nivel: 1 | 2
  /** Categoria que abre nas suas coisas. */
  expansivel: boolean
  aberta: boolean
}

/** As linhas de detalhe que aparecem embaixo de um total. Com busca, só o
 * que bate com o texto (a categoria aparece quando ela ou uma coisa dela
 * bate, já aberta nas coisas encontradas). */
export function linhasVisiveis(secao: SecaoMesAMes, linhas: LinhaMesAMes[], palavras: string[], abertas: Set<string>): LinhaVisivel[] {
  const buscando = palavras.length > 0
  const bate = (nome: string) => {
    const n = semAcento(nome)
    return palavras.every((p) => n.includes(p))
  }
  const saida: LinhaVisivel[] = []
  for (const l of linhas) {
    const chave = `${secao}/${l.id ?? l.nome}`
    const itens = l.itens ?? []
    // Categoria com uma coisa só, de mesmo nome (lançamento sem descrição):
    // não tem o que abrir.
    const temItens = itens.length > 1 || (itens.length === 1 && semAcento(itens[0].nome) !== semAcento(l.nome))
    const achados = buscando && temItens ? itens.filter((it) => bate(it.nome)) : []
    if (buscando && !bate(l.nome) && achados.length === 0) continue
    const aberta = temItens && (achados.length > 0 || abertas.has(chave))
    saida.push({ chave, nome: l.nome, valores: l.valores, total: l.total, nivel: 1, expansivel: temItens, aberta })
    if (!aberta) continue
    for (const it of achados.length > 0 ? achados : itens) {
      saida.push({ chave: `${chave}/${it.nome}`, nome: it.nome, valores: it.valores, total: it.total, nivel: 2, expansivel: false, aberta: false })
    }
  }
  return saida
}

const FUNDO = "bg-white dark:bg-slate-800"
// Fundo sólido (a 1ª coluna fica presa na rolagem: não pode ser transparente).
const FUNDO_DESTAQUE = "bg-primary-50 dark:bg-slate-700"

/** Linha de aviso dentro da tabela ("Carregando...", "Nenhum gasto..."). */
export function AvisoDetalhe({ colunas, children }: { colunas: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colunas} className="py-2 text-left text-xs text-slate-400 dark:text-slate-500">
        <span className="sticky left-0 inline-block pl-[1.875rem]">{children}</span>
      </td>
    </tr>
  )
}

export function LinhasDetalhe({
  linhas,
  mesAtivo,
  destaque,
  onDestacar,
  onAlternar,
}: {
  linhas: LinhaVisivel[]
  /** Índice do mês selecionado na tela (-1 = ano inteiro). */
  mesAtivo: number
  destaque: string | null
  onDestacar: (chave: string | null) => void
  onAlternar: (chave: string) => void
}) {
  return (
    <>
      {linhas.map((l) => {
        const marcada = destaque === l.chave
        const fundo = marcada ? FUNDO_DESTAQUE : FUNDO
        const corNome = l.nivel === 1 ? "text-slate-600 dark:text-slate-300" : "text-slate-500 dark:text-slate-400"
        const corValor = marcada
          ? "font-medium text-slate-800 dark:text-slate-100"
          : l.nivel === 1
            ? "text-slate-600 dark:text-slate-300"
            : "text-slate-500 dark:text-slate-400"
        return (
          <tr
            key={l.chave}
            // Categoria: o clique abre/fecha. Cliente ou gasto: marca a linha
            // pra acompanhar os meses com o olho.
            onClick={() => (l.expansivel ? onAlternar(l.chave) : onDestacar(marcada ? null : l.chave))}
            className="cursor-pointer"
          >
            <th
              scope="row"
              title={l.nome}
              className={`sticky left-0 z-10 max-w-[11rem] py-1.5 pr-3 text-left font-normal sm:max-w-[16rem] ${fundo} ${corNome} ${l.nivel === 1 ? "pl-[1.875rem]" : "pl-11"}`}
            >
              {l.expansivel ? (
                <button
                  type="button"
                  aria-expanded={l.aberta}
                  onClick={(e) => {
                    e.stopPropagation()
                    onAlternar(l.chave)
                  }}
                  className="-ml-[1.125rem] flex w-[calc(100%+1.125rem)] items-center gap-1 rounded text-left hover:text-slate-900 dark:hover:text-slate-100"
                >
                  {l.aberta ? <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden />}
                  <span className="truncate">{l.nome}</span>
                </button>
              ) : (
                <span className="block truncate">{l.nome}</span>
              )}
            </th>
            {l.valores.map((v, idx) => (
              <td
                key={idx}
                title={v ? `${l.nome} · ${NOMES_MESES[idx]}: ${formatBRL(v)}` : undefined}
                className={`px-2 py-1.5 ${marcada ? FUNDO_DESTAQUE : idx === mesAtivo ? "bg-primary-50 dark:bg-primary-900/30" : ""} ${
                  v === 0 ? "text-slate-300 dark:text-slate-600" : corValor
                }`}
              >
                {v === 0 ? "—" : formatValor(v)}
              </td>
            ))}
            <td
              title={`${l.nome} · total: ${formatBRL(l.total)}`}
              className={`border-l border-slate-100 py-1.5 pl-3 dark:border-slate-700/60 ${marcada ? FUNDO_DESTAQUE : ""} ${
                l.total === 0 ? "text-slate-300 dark:text-slate-600" : `font-medium ${corValor}`
              }`}
            >
              {l.total === 0 ? "—" : formatValor(l.total)}
            </td>
          </tr>
        )
      })}
    </>
  )
}
