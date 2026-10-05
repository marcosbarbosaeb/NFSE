import { ArrowRight, TrendingDown, TrendingUp } from "lucide-react"
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../../lib/api"
import { MESES_ABREV, NOMES_MESES, formatPct } from "../../lib/financeiro"
import { formatBRL, formatCompetenciaAbrev, formatCompetenciaLonga } from "../../lib/format"
import type { DashboardResumo, Despesa, Pagamento, ResumoFinanceiro } from "../../lib/types"
import { BarrasHorizontais, type ItemBarra } from "./BarrasHorizontais"
import { CHAVE_LINHA, ColunasMensais } from "./ColunasMensais"
import { CartaoGrafico, GraficoVazio } from "./base"

/** Os gráficos que entram como cards na Visão geral e no Financeiro
 * (05/10/2026). Cada um é uma seção do PainelCards: a pessoa muda de lugar,
 * de largura ou esconde em "Editar disposição".
 *
 * De onde vêm os números:
 * - Visão geral (notas): GET /painel/graficos?competencia= — uma chamada só
 *   pros dois gráficos, e só quando algum deles está na tela;
 * - Financeiro: tudo do que a página já carrega (resumo do ano, recebimentos
 *   e despesas) — nenhum pedido a mais. */

// As duas cores dos gráficos: o azul da casa e um cinza de segundo plano.
const AZUL = { classe: "fill-primary-500 dark:fill-primary-400", classeChave: "bg-primary-500 dark:bg-primary-400" }
const AZUL_APAGADO = "fill-primary-200 dark:fill-primary-700"
const CINZA = { classe: "fill-slate-400 dark:fill-slate-500", classeChave: "bg-slate-400 dark:bg-slate-500" }

// --- Visão geral: notas ---

export interface GraficosPainel {
  competencia: string
  /** 12 meses, terminando na competência. */
  serie: { competencia: string; valor: number }[]
  /** Média dos meses desde a primeira nota da janela (null sem nota nenhuma). */
  media: number | null
  ano: string
  por_tomador: { vinculo_id: string; nome: string; total: number; notas: number }[]
  total_ano: number
}

// Os dois gráficos da Visão geral pedem a mesma coisa: um pedido só serve os dois.
const pedidos = new Map<string, Promise<GraficosPainel>>()

function useGraficosPainel(competencia: string, versao: number): { dados: GraficosPainel | null; erro: boolean } {
  const [estado, setEstado] = useState<{ chave: string; dados: GraficosPainel | null; erro: boolean }>({ chave: "", dados: null, erro: false })
  const chave = `${competencia}|${versao}`
  useEffect(() => {
    let vivo = true
    let pedido = pedidos.get(chave)
    if (!pedido) {
      pedido = api.get<GraficosPainel>(`/painel/graficos?competencia=${competencia}`)
      pedidos.clear() // só o último mês/versão interessa
      pedidos.set(chave, pedido)
    }
    pedido
      .then((dados) => {
        if (vivo) setEstado({ chave, dados, erro: false })
      })
      .catch(() => {
        pedidos.delete(chave)
        if (vivo) setEstado((e) => ({ chave, dados: e.dados, erro: true }))
      })
    return () => {
      vivo = false
    }
  }, [chave, competencia])
  // Enquanto o mês novo carrega, o desenho anterior continua na tela.
  return { dados: estado.dados, erro: estado.erro && estado.chave === chave }
}

export function GraficoFaturamentoMes({ competencia, versao, resumo }: { competencia: string; versao: number; resumo: DashboardResumo }) {
  const { dados, erro } = useGraficosPainel(competencia, versao)
  const serie = dados?.serie ?? []
  const atual = serie.length - 1
  const doMes = resumo.faturado_no_mes
  const media = dados?.media ?? null
  const semNota = serie.every((p) => p.valor === 0)
  const contraMedia = media && serie.length ? Math.round(((serie[atual].valor - media) / media) * 100) : null
  const mes = formatCompetenciaLonga(competencia).toLowerCase()

  return (
    <CartaoGrafico
      periodo="valor das notas · últimos 12 meses"
      acao={
        <Link to="/app/nfse" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-300">
          Ver notas <ArrowRight size={14} />
        </Link>
      }
      tabela={{
        titulo: "Valor das notas por mês, últimos 12 meses",
        colunas: ["Mês", "Notas"],
        linhas: serie.map((p) => [formatCompetenciaLonga(p.competencia), formatBRL(p.valor)]),
      }}
    >
      <div>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{formatBRL(doMes)}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          em notas em {mes}
          {media !== null && !semNota && (
            <>
              {" · "}
              {doMes === 0 || contraMedia === null
                ? `a média é de ${formatBRL(media)} por mês`
                : `${contraMedia === 0 ? "na média" : `${Math.abs(contraMedia)}% ${contraMedia > 0 ? "acima" : "abaixo"} da média`} (${formatBRL(media)} por mês)`}
            </>
          )}
        </p>
        {resumo.delta_faturamento_pct !== null && (
          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            {resumo.delta_faturamento_pct >= 0 ? (
              <TrendingUp size={14} className="text-success-600 dark:text-success-400" aria-hidden />
            ) : (
              <TrendingDown size={14} className="text-danger-600 dark:text-danger-400" aria-hidden />
            )}
            {Math.abs(Math.round(resumo.delta_faturamento_pct))}% {resumo.delta_faturamento_pct >= 0 ? "a mais" : "a menos"} que no mês anterior
          </p>
        )}
      </div>
      {!dados ? (
        <GraficoVazio>{erro ? "Não deu pra carregar o gráfico. Recarregue a página." : "Carregando..."}</GraficoVazio>
      ) : semNota ? (
        <GraficoVazio>Nenhuma nota nos últimos 12 meses ainda. Quando você emitir, o gráfico aparece aqui.</GraficoVazio>
      ) : (
        <ColunasMensais
          titulo="Valor das notas por mês, últimos 12 meses"
          rotulos={serie.map((p) => formatCompetenciaAbrev(p.competencia).toLowerCase())}
          nomes={serie.map((p) => formatCompetenciaLonga(p.competencia))}
          anos={serie.map((p, i) => (i === 0 || p.competencia.endsWith("-01") ? p.competencia.slice(0, 4) : null))}
          series={[{ nome: "Notas", valores: serie.map((p) => p.valor), ...AZUL, classeApagada: AZUL_APAGADO }]}
          media={media}
          destaque={atual}
        />
      )}
    </CartaoGrafico>
  )
}

export function GraficoTomadores({ competencia, versao }: { competencia: string; versao: number }) {
  const { dados, erro } = useGraficosPainel(competencia, versao)
  const ano = competencia.slice(0, 4)
  const itens: ItemBarra[] = (dados?.por_tomador ?? []).map((t) => ({
    nome: t.nome,
    valor: t.total,
    detalhe: `${t.notas} ${t.notas === 1 ? "nota" : "notas"}`,
  }))
  const primeiro = dados?.por_tomador[0]
  const total = dados?.total_ano ?? 0
  return (
    <CartaoGrafico
      periodo={`valor das notas de ${ano}, por tomador`}
      resumo={
        primeiro && total > 0 ? (
          <>
            <strong className="font-semibold">{primeiro.nome}</strong> responde por {Math.round((primeiro.total / total) * 100)}% dos{" "}
            {formatBRL(total)} em notas de {ano}
            {dados && dados.por_tomador.length > 1 ? ` (${dados.por_tomador.length} tomadores).` : "."}
          </>
        ) : undefined
      }
    >
      {!dados ? (
        <GraficoVazio>{erro ? "Não deu pra carregar o gráfico. Recarregue a página." : "Carregando..."}</GraficoVazio>
      ) : itens.length === 0 ? (
        <GraficoVazio>Nenhuma nota em {ano} ainda.</GraficoVazio>
      ) : (
        <BarrasHorizontais titulo={`Valor das notas de ${ano} por tomador, do maior pro menor`} itens={itens} maximo={6} total={total} />
      )}
    </CartaoGrafico>
  )
}

// --- Financeiro ---

/** Entrou × saiu por mês, com a linha do lucro. Clicar num mês escolhe o
 * mês na tela (`onSelecionarMes("03")`; de novo no mesmo, volta pro ano). */
export function GraficoEntrouSaiu({
  resumo,
  mes,
  onSelecionarMes,
  rotuloEixo = "pelo mês de referência",
  sempreUmMes = false,
}: {
  /** A tela sempre mostra um mês (Visão geral): não tem "voltar pro ano". */
  sempreUmMes?: boolean
  resumo: ResumoFinanceiro | null
  /** "" = ano inteiro; "01".."12". */
  mes: string
  onSelecionarMes?: (mes: string) => void
  rotuloEixo?: string
}) {
  if (!resumo) {
    return (
      <CartaoGrafico>
        <GraficoVazio>Carregando...</GraficoVazio>
      </CartaoGrafico>
    )
  }
  const i = mes ? Number(mes) - 1 : -1
  const comMovimento = resumo.meses.map((_, m) => resumo.recebido[m] !== 0 || resumo.despesas[m] !== 0)
  const vazio = !comMovimento.some(Boolean)
  const t = resumo.totais
  const melhor = comMovimento.reduce<number>((best, tem, m) => (tem && (best === -1 || resumo.lucro[m] > resumo.lucro[best]) ? m : best), -1)
  const frase =
    i >= 0 ? (
      <>
        {NOMES_MESES[i]}: entrou <strong className="font-semibold">{formatBRL(resumo.recebido[i])}</strong>, saiu{" "}
        <strong className="font-semibold">{formatBRL(resumo.despesas[i])}</strong> — {resumo.lucro[i] < 0 ? "faltou" : "sobrou"}{" "}
        <strong className="font-semibold">{formatBRL(Math.abs(resumo.lucro[i]))}</strong>
        {resumo.margem[i] !== null && resumo.lucro[i] >= 0 ? ` (${formatPct(resumo.margem[i])} do que entrou)` : ""}.
      </>
    ) : (
      <>
        Em {resumo.ano} entrou <strong className="font-semibold">{formatBRL(t.recebido)}</strong> e saiu{" "}
        <strong className="font-semibold">{formatBRL(t.despesas)}</strong> — {t.lucro < 0 ? "faltou" : "sobrou"}{" "}
        <strong className="font-semibold">{formatBRL(Math.abs(t.lucro))}</strong>.
        {melhor >= 0 && comMovimento.filter(Boolean).length > 1 && ` Melhor mês: ${NOMES_MESES[melhor].toLowerCase()} (${formatBRL(resumo.lucro[melhor])}).`}
      </>
    )

  return (
    <CartaoGrafico
      periodo={`${resumo.ano} · ${rotuloEixo} · despesas sem as retiradas`}
      legenda={[
        { nome: "Entrou", classe: AZUL.classeChave },
        { nome: "Saiu", classe: CINZA.classeChave },
        { nome: "Lucro", classe: CHAVE_LINHA, linha: true },
      ]}
      resumo={vazio ? undefined : frase}
      acao={
        i >= 0 && onSelecionarMes && !sempreUmMes ? (
          <button type="button" onClick={() => onSelecionarMes("")} className="rounded text-xs font-medium text-primary-700 hover:underline dark:text-primary-300">
            Ver o ano inteiro
          </button>
        ) : undefined
      }
      tabela={
        vazio
          ? undefined
          : {
              titulo: `Entrou, saiu e lucro por mês em ${resumo.ano}`,
              colunas: ["Mês", "Entrou", "Saiu", "Lucro"],
              linhas: resumo.meses
                .map((_, m) => [NOMES_MESES[m], formatBRL(resumo.recebido[m]), formatBRL(resumo.despesas[m]), formatBRL(resumo.lucro[m])])
                .filter((_, m) => comMovimento[m]),
            }
      }
    >
      {vazio ? (
        <GraficoVazio>Nada registrado em {resumo.ano} ainda. Lance um recebimento ou uma despesa e o gráfico aparece aqui.</GraficoVazio>
      ) : (
        <ColunasMensais
          titulo={`Entrou, saiu e lucro por mês em ${resumo.ano}`}
          rotulos={MESES_ABREV.map((m) => m.toLowerCase())}
          nomes={NOMES_MESES.map((m) => `${m} de ${resumo.ano}`)}
          series={[
            { nome: "Entrou", valores: resumo.recebido, ...AZUL },
            { nome: "Saiu", valores: resumo.despesas, ...CINZA },
          ]}
          linha={{ nome: "Lucro", valores: resumo.lucro.map((l, m) => (comMovimento[m] ? l : null)) }}
          selecionado={i >= 0 ? i : null}
          onSelecionar={
            onSelecionarMes
              ? (m) => {
                  if (m !== i) onSelecionarMes(resumo.meses[m])
                  else if (!sempreUmMes) onSelecionarMes("")
                }
              : undefined
          }
          dica={
            onSelecionarMes
              ? (m) => (m !== i ? (sempreUmMes ? "clique pra ver este mês" : "clique pra ver só este mês") : sempreUmMes ? "é o mês que você está vendo" : "clique pra voltar ao ano inteiro")
              : undefined
          }
          altura={240}
        />
      )}
    </CartaoGrafico>
  )
}

/** "Para onde vai o dinheiro": despesas do período por categoria (sem as
 * retiradas — distribuição de lucro não é gasto). Acompanha o mês escolhido. */
export function GraficoParaOndeVai({ despesas, rotuloPeriodo }: { despesas: Despesa[] | null; rotuloPeriodo: string }) {
  const porCategoria = new Map<string, number>()
  for (const d of despesas ?? []) {
    if (d.tipo === "retirada") continue
    porCategoria.set(d.categoria, (porCategoria.get(d.categoria) ?? 0) + d.valor)
  }
  const itens: ItemBarra[] = [...porCategoria].map(([nome, valor]) => ({ nome, valor: Math.round(valor * 100) / 100 })).sort((a, b) => b.valor - a.valor)
  const total = itens.reduce((s, c) => s + c.valor, 0)
  const maior = itens[0]
  return (
    <CartaoGrafico
      periodo={`despesas de ${rotuloPeriodo}, por categoria · sem as retiradas`}
      resumo={
        maior && total > 0 ? (
          <>
            <strong className="font-semibold">{maior.nome}</strong> é o maior gasto: {formatBRL(maior.valor)}, {Math.round((maior.valor / total) * 100)}% dos{" "}
            {formatBRL(total)} em despesas.
          </>
        ) : undefined
      }
    >
      {despesas === null ? (
        <GraficoVazio>Carregando...</GraficoVazio>
      ) : itens.length === 0 ? (
        <GraficoVazio>Nenhuma despesa em {rotuloPeriodo} ainda.</GraficoVazio>
      ) : (
        <BarrasHorizontais titulo={`Despesas de ${rotuloPeriodo} por categoria, da maior pra menor`} itens={itens} maximo={7} rotuloOutros="Outras" total={total} />
      )}
    </CartaoGrafico>
  )
}

/** "Recebido por cliente": os recebimentos do período somados por cliente —
 * os mesmos da lista "Recebimentos" da tela (pelo dia em que o dinheiro caiu). */
export function GraficoRecebidoPorCliente({ pagamentos, rotuloPeriodo }: { pagamentos: Pagamento[] | null; rotuloPeriodo: string }) {
  const porCliente = new Map<string, { nome: string; valor: number; vezes: number }>()
  for (const p of pagamentos ?? []) {
    const chave = p.vinculo_id ?? p.apelido
    const atual = porCliente.get(chave) ?? { nome: p.apelido || "Cliente sem nome", valor: 0, vezes: 0 }
    atual.valor += p.valor
    atual.vezes += 1
    porCliente.set(chave, atual)
  }
  const itens: ItemBarra[] = [...porCliente.values()]
    .map((c) => ({ nome: c.nome, valor: Math.round(c.valor * 100) / 100, detalhe: `${c.vezes} ${c.vezes === 1 ? "recebimento" : "recebimentos"}` }))
    .sort((a, b) => b.valor - a.valor)
  const total = itens.reduce((s, c) => s + c.valor, 0)
  const maior = itens[0]
  return (
    <CartaoGrafico
      periodo={`recebimentos de ${rotuloPeriodo}, por cliente · pelo dia em que o dinheiro caiu`}
      resumo={
        maior && total > 0 ? (
          <>
            <strong className="font-semibold">{maior.nome}</strong> pagou {formatBRL(maior.valor)}: {Math.round((maior.valor / total) * 100)}% dos{" "}
            {formatBRL(total)} recebidos{itens.length > 1 ? ` de ${itens.length} clientes.` : "."}
          </>
        ) : undefined
      }
    >
      {pagamentos === null ? (
        <GraficoVazio>Carregando...</GraficoVazio>
      ) : itens.length === 0 ? (
        <GraficoVazio>Nenhum recebimento em {rotuloPeriodo} ainda.</GraficoVazio>
      ) : (
        <BarrasHorizontais titulo={`Recebido de ${rotuloPeriodo} por cliente, do maior pro menor`} itens={itens} maximo={6} total={total} />
      )}
    </CartaoGrafico>
  )
}
