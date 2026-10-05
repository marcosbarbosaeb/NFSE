import { AlertTriangle, CheckCircle2, ChevronDown, EyeOff, FilePlus2, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../../lib/api"
import { formatData, mensagemErro } from "../../lib/financeiro"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../../lib/format"
import type { EntradaDoExtrato, NotaConciliada, PainelConciliacaoNotas, RecebimentoSemNota, TomadorConciliado } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { CaixaBusca } from "../ui/CaixaBusca"
import { Card } from "../ui/Card"
import { type AcaoNaNota, NotaConciliadaLinha, mesDaNota, precisaDeAtencao } from "./NotaConciliadaLinha"
import { linkGerarNota } from "./RecebimentosSemNota"

/** Parte 1 da Conciliação — "As notas foram pagas?" (05/10/2026, pedido do
 * Marcos: "a segunda, mais importante, é se as notas geradas foram pagas").
 * Notas x recebimentos: o resumo do período em cima (faturado, recebido, em
 * aberto, atrasado), depois cada tomador com as notas dele e o estado de
 * cada uma. Notas de vendedores (Shopee) entram como uma linha por mês.
 * No fim, o problema espelhado: dinheiro que entrou sem nota. */

export type FiltroNotas = "todas" | "pendentes" | "abertas" | "atrasadas" | "diferenca" | "pagas"
const FILTROS: FiltroNotas[] = ["todas", "pendentes", "abertas", "atrasadas", "diferenca", "pagas"]
export const ehFiltroNotas = (v: string | null): v is FiltroNotas => FILTROS.includes(v as FiltroNotas)

const emAberto = (i: NotaConciliada) => i.status === "em_aberto" || i.status === "atrasada"
// Diferença ainda por conferir — a marcada como resolvida sai daqui (continua em "Pagas").
const comDiferenca = (i: NotaConciliada) => (i.status === "paga_a_menor" || i.status === "paga_a_maior") && !i.conferida

function passa(item: NotaConciliada, filtro: FiltroNotas): boolean {
  if (filtro === "pendentes") return precisaDeAtencao(item)
  if (filtro === "abertas") return emAberto(item)
  if (filtro === "atrasadas") return item.status === "atrasada"
  if (filtro === "diferenca") return comDiferenca(item)
  if (filtro === "pagas") return !emAberto(item)
  return true
}

const plural = (n: number, um: string, varios: string) => `${n.toLocaleString("pt-BR")} ${n === 1 ? um : varios}`

function consultaDoPeriodo(periodo: string): string {
  const atual = competenciaAtual()
  if (periodo === "6m") return `?desde=${deslocarCompetencia(atual, -6)}`
  if (periodo === "ano") return `?desde=${atual.slice(0, 4)}-01`
  if (periodo === "tudo") return "?tudo=true"
  if (periodo.startsWith("mes:")) return `?desde=${periodo.slice(4)}&ate=${periodo.slice(4)}`
  return ""
}

export function ConciliacaoNotas({
  recarga,
  filtroInicial,
  onMudou,
  onImportar,
  onFiltro,
}: {
  /** Muda quando um extrato novo foi importado: recarrega (as sugestões vêm dele). */
  recarga: number
  filtroInicial?: FiltroNotas
  /** Uma baixa foi dada ou desfeita: a tela atualiza o estado das duas conciliações. */
  onMudou: () => void
  onImportar: () => void
  onFiltro?: (filtro: FiltroNotas) => void
}) {
  const [dados, setDados] = useState<PainelConciliacaoNotas | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [periodo, setPeriodo] = useState("3m")
  const [filtro, setFiltroLocal] = useState<FiltroNotas>(filtroInicial ?? "todas")
  const [busca, setBusca] = useState("")
  const [aberta, setAberta] = useState<string | null>(null)
  // Tomadores abertos/fechados à mão (o padrão: aberto quem tem algo em aberto).
  const [grupos, setGrupos] = useState<Record<string, boolean>>({})
  const [ligando, setLigando] = useState<Record<string, string>>({})

  function setFiltro(novo: FiltroNotas) {
    setFiltroLocal(novo)
    onFiltro?.(novo)
  }

  function carregar() {
    return api
      .get<PainelConciliacaoNotas>(`/conciliacao/notas${consultaDoPeriodo(periodo)}`)
      .then((d) => {
        setDados(d)
        setErro(null)
      })
      .catch((err) => setErro(mensagemErro(err, "Não deu pra carregar as notas. Tente de novo.")))
  }

  useEffect(() => {
    void carregar()
  }, [periodo, recarga]) // eslint-disable-line react-hooks/exhaustive-deps

  const lancamentos = useMemo(() => new Map<string, EntradaDoExtrato>((dados?.lancamentos ?? []).map((l) => [l.id, l])), [dados])

  async function executar(acao: () => Promise<string>) {
    setOcupado(true)
    setErro(null)
    setFeito(null)
    try {
      const texto = await acao()
      setFeito(texto)
      setAberta(null)
      await carregar()
      onMudou()
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setOcupado(false)
    }
  }

  function agir(grupo: TomadorConciliado, item: NotaConciliada, acao: AcaoNaNota) {
    const oQue = item.tipo === "lote" ? `nas notas dos vendedores de ${mesDaNota(item.competencia)}` : `na nota de ${mesDaNota(item.competencia)}`
    const de = `${oQue} de ${grupo.apelido}`
    // O tomador em que a pessoa mexeu continua aberto (mesmo que fique "tudo pago").
    setGrupos((atuais) => ({ ...atuais, [grupo.vinculo_id]: true }))
    if (acao.tipo === "registrar") {
      void executar(async () => {
        await api.post("/pagamentos", {
          vinculo_id: item.vinculo_id, competencia: item.competencia, valor: acao.valor, data_recebimento: acao.data, emissao_id: item.emissao_id,
        })
        return `Baixa dada ${de}.`
      })
    } else if (acao.tipo === "ligar") {
      void executar(async () => {
        await api.post(`/conciliacao/${acao.lancamentoId}/receita`, { vinculo_id: item.vinculo_id, emissao_id: item.emissao_id })
        return `Lançamento do extrato ligado: baixa dada ${de}.`
      })
    } else if (acao.tipo === "nao_e_esse") {
      void executar(async () => {
        await api.post("/painel/pendencias/ignorar", { chave: `sugestao:${acao.lancamentoId}:${item.chave}` })
        return "Certo, não sugiro mais esse lançamento pra essa nota."
      })
    } else if (acao.tipo === "conferir") {
      const chave = item.tipo === "lote" ? `diferenca:${item.vinculo_id}:${item.competencia}` : `diferenca:${item.emissao_id}`
      void executar(async () => {
        await api.post("/painel/pendencias/ignorar", { chave, ignorar: acao.conferida })
        return acao.conferida ? "Marcado como resolvido — saiu das pendências." : "Reaberto: voltei a avisar dessa diferença."
      })
    } else if (acao.tipo === "considerar") {
      const outras = grupo.itens.filter((i) => i.tipo === "nota" && emAberto(i) && i.competencia === item.competencia).length
      const aviso =
        outras > 1
          ? `Isso marca como recebidas as ${outras} notas em aberto de ${grupo.apelido} em ${mesDaNota(item.competencia)}, sem lançar valor. Continuar?`
          : `Marcar a nota de ${mesDaNota(item.competencia)} de ${grupo.apelido} como recebida, sem lançar valor? O total recebido não muda.`
      if (!window.confirm(aviso)) return
      void executar(async () => {
        await api.post("/financeiro/conciliar", { itens: [{ vinculo_id: item.vinculo_id, competencia: item.competencia }] })
        return `Nota de ${grupo.apelido} marcada como recebida, sem valor.`
      })
    } else {
      if (!window.confirm(`Desfazer a baixa ${de}? ${item.tipo === "lote" ? "Os recebimentos ligados a esse mês são apagados." : "A nota volta a ficar em aberto."}`)) return
      void executar(async () => {
        if (item.tipo === "lote") {
          for (const p of item.pagamentos) await api.delete(`/pagamentos/${p.id}`)
        } else {
          await api.delete(`/pagamentos?emissao_id=${item.emissao_id}`)
        }
        return `Baixa desfeita ${de}.`
      })
    }
  }

  function ignorarSemNota(r: RecebimentoSemNota) {
    void executar(async () => {
      await api.post("/painel/pendencias/ignorar", { chave: r.chave })
      return `Não aviso mais do recebimento de ${r.apelido} sem nota.`
    })
  }

  function ligarSemNota(r: RecebimentoSemNota, emissaoId: string) {
    void executar(async () => {
      await api.patch(`/pagamentos/${r.pagamento_id}`, { emissao_id: emissaoId })
      return `Recebimento de ${r.apelido} ligado à nota.`
    })
  }

  if (dados === null) {
    return erro ? (
      <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
    ) : (
      <p className="py-10 text-center text-sm text-slate-400">Carregando...</p>
    )
  }

  const seletorDePeriodo = (
    <select
      value={periodo}
      onChange={(e) => setPeriodo(e.target.value)}
      aria-label="Período"
      className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
    >
      <option value="3m">Últimos 3 meses</option>
      <option value="6m">Últimos 6 meses</option>
      <option value="ano">Este ano</option>
      <optgroup label="Um mês só">
        {[0, 1, 2, 3, 4, 5].map((n) => {
          const c = deslocarCompetencia(competenciaAtual(), -n)
          return (
            <option key={c} value={`mes:${c}`}>
              {formatCompetenciaLonga(c)}
            </option>
          )
        })}
      </optgroup>
      <option value="tudo">Desde sempre</option>
    </select>
  )

  // Empresa só com o Financeiro: não há nota pra conferir.
  if (dados.modo === "recebimentos") {
    const total = dados.clientes.reduce((s, c) => s + c.recebido, 0)
    return (
      <div className="flex flex-col gap-5">
        <Card className="p-5">
          <p className="font-medium text-slate-800 dark:text-slate-100">Aqui eu conferiria se cada nota foi paga — mas sua conta tem só o Financeiro.</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Sem o módulo de Notas eu não sei o que você faturou, então não tenho como dizer quem está devendo. O que eu consigo conferir é a outra
            parte: se tudo que passou pelo banco foi classificado. Abaixo, de quem o dinheiro entrou no período.
          </p>
          <p className="mt-2 text-sm">
            <Link to="/app/empresa" className="font-semibold text-primary-600 hover:underline dark:text-primary-300">
              Ligar o módulo de Notas em Empresa →
            </Link>
          </p>
        </Card>
        <Card className="p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">De quem o dinheiro entrou</h3>
            {seletorDePeriodo}
          </div>
          {dados.clientes.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-400">Nenhum recebimento lançado nesse período.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {dados.clientes.map((c) => (
                <li key={c.vinculo_id} className="flex items-center gap-3 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-200">{c.nome}</span>
                    <span className="block text-xs text-slate-400 dark:text-slate-500">
                      {plural(c.recebimentos, "recebimento", "recebimentos")}
                      {c.ultimo ? ` · último em ${formatData(c.ultimo)}` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(c.recebido)}</span>
                </li>
              ))}
              <li className="flex items-center justify-between py-2.5 text-sm font-semibold text-slate-800 dark:text-slate-100">
                <span>Total recebido</span>
                <span className="tabular-nums">{formatBRL(total)}</span>
              </li>
            </ul>
          )}
        </Card>
      </div>
    )
  }

  const r = dados.resumo
  const estado = dados.estado
  const todos = dados.tomadores.flatMap((g) => g.itens)
  const contagem: Record<FiltroNotas, number> = {
    todas: todos.length,
    pendentes: todos.filter(precisaDeAtencao).length,
    abertas: todos.filter(emAberto).length,
    atrasadas: todos.filter((i) => i.status === "atrasada").length,
    diferenca: todos.filter(comDiferenca).length,
    pagas: todos.filter((i) => !emAberto(i)).length,
  }
  const ROTULOS: Record<FiltroNotas, string> = {
    todas: "Todas", pendentes: "Precisam de você", abertas: "Em aberto", atrasadas: "Atrasadas", diferenca: "Com diferença", pagas: "Pagas",
  }
  const alvo = busca.trim().toLowerCase()
  const visiveis = dados.tomadores
    .filter((g) => !alvo || g.apelido.toLowerCase().includes(alvo))
    .map((g) => ({ grupo: g, itens: g.itens.filter((i) => passa(i, filtro)) }))
    .filter((g) => g.itens.length > 0)
  const pctPagas = r.notas ? (r.pagas / r.notas) * 100 : 0
  const pctPrazo = r.notas ? (r.notas_no_prazo / r.notas) * 100 : 0
  const pctAtraso = r.notas ? (r.notas_atrasadas / r.notas) * 100 : 0

  const numero = (rotulo: string, valor: number, detalhe: string, cor: string, ir?: FiltroNotas) => (
    <button
      type="button"
      onClick={ir ? () => setFiltro(ir) : undefined}
      disabled={!ir}
      className={`rounded-xl px-3 py-3 text-left sm:px-4 ${ir ? "hover:bg-slate-50 dark:hover:bg-slate-700/40" : "cursor-default"}`}
    >
      <span className="block text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{rotulo}</span>
      <span className={`block text-lg font-semibold tabular-nums sm:text-2xl ${cor}`}>{formatBRL(valor)}</span>
      <span className="block text-xs text-slate-500 dark:text-slate-400">{detalhe}</span>
    </button>
  )

  const pendencias = [
    estado.atrasadas > 0 && {
      // (um mês de notas de vendedores é uma cobrança só, com centenas de notas)
      texto:
        r.notas_atrasadas === estado.atrasadas
          ? plural(estado.atrasadas, "nota atrasada", "notas atrasadas")
          : `${plural(estado.atrasadas, "cobrança atrasada", "cobranças atrasadas")} (${plural(r.notas_atrasadas, "nota", "notas")})`,
      ir: "atrasadas" as FiltroNotas,
    },
    estado.diferencas > 0 && { texto: plural(estado.diferencas, "pagamento com diferença", "pagamentos com diferença"), ir: "diferenca" as FiltroNotas },
    estado.sugestoes > 0 && {
      texto: `${plural(estado.sugestoes, "pagamento que achei", "pagamentos que achei")} no extrato pra você confirmar`,
      ir: "pendentes" as FiltroNotas,
    },
  ].filter((p): p is { texto: string; ir: FiltroNotas } => !!p)

  return (
    <div className="flex flex-col gap-5">
      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {feito && (
        <p className="flex items-center gap-2 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300" role="status">
          <CheckCircle2 size={16} className="shrink-0" /> {feito}
        </p>
      )}

      {/* O resumo do período: grande e sem dúvida */}
      <Card className="p-2 sm:p-3">
        <div className="flex flex-wrap items-center justify-between gap-3 px-3 pt-2 sm:px-2">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Notas emitidas em{" "}
            <span className="font-medium text-slate-800 dark:text-slate-100">
              {dados.periodo.desde
                ? dados.periodo.ate === dados.periodo.desde
                  ? mesDaNota(dados.periodo.desde)
                  : `${mesDaNota(dados.periodo.desde)} até hoje`
                : "todo o histórico"}
            </span>
            {dados.periodo.antigas > 0 && <> · mais {plural(dados.periodo.antigas, "nota antiga", "notas antigas")} que ainda não foi resolvida</>}
          </p>
          {seletorDePeriodo}
        </div>
        <div className="mt-1 grid grid-cols-2 gap-1 lg:grid-cols-4">
          {numero("Faturado", r.faturado, plural(r.notas, "nota emitida", "notas emitidas"), "text-slate-900 dark:text-slate-100", "todas")}
          {numero(
            "Recebido",
            r.recebido,
            `${plural(r.pagas, "nota paga", "notas pagas")}${r.notas_sem_valor > 0 ? ` · ${r.notas_sem_valor} sem valor pra conferir` : ""}`,
            "text-success-700 dark:text-success-300",
            "pagas",
          )}
          {numero(
            "Em aberto",
            r.em_aberto,
            r.notas_em_aberto === 0 ? "nenhuma nota esperando" : `${plural(r.notas_em_aberto, "nota", "notas")} · ${r.notas_no_prazo} ainda no prazo`,
            r.em_aberto > 0 ? "text-primary-700 dark:text-primary-300" : "text-slate-900 dark:text-slate-100",
            "abertas",
          )}
          {numero(
            "Atrasado",
            r.atrasado,
            r.notas_atrasadas === 0 ? "nada vencido" : `${plural(r.notas_atrasadas, "nota passou", "notas passaram")} do prazo`,
            r.atrasado > 0 ? "text-danger-600 dark:text-danger-300" : "text-slate-900 dark:text-slate-100",
            "atrasadas",
          )}
        </div>
        {r.notas > 0 && (
          <div className="px-3 pb-3 pt-1 sm:px-4">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {r.pagas.toLocaleString("pt-BR")} de {plural(r.notas, "nota paga", "notas pagas")}
              </p>
              {r.diferenca !== 0 && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  diferença nos pagamentos: {r.diferenca > 0 ? "+" : "−"} {formatBRL(Math.abs(r.diferenca))}
                </p>
              )}
            </div>
            <div
              className="mt-1.5 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"
              role="img"
              aria-label={`${r.pagas} de ${r.notas} notas pagas, ${r.notas_no_prazo} em aberto no prazo, ${r.notas_atrasadas} atrasadas`}
            >
              {pctPagas > 0 && <div className="h-full rounded-full bg-success-600" style={{ width: `${pctPagas}%` }} />}
              {pctPrazo > 0 && <div className="h-full rounded-full bg-primary-400" style={{ width: `${pctPrazo}%` }} />}
              {pctAtraso > 0 && <div className="h-full rounded-full bg-danger-600" style={{ width: `${pctAtraso}%` }} />}
            </div>
            <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-success-600" /> pagas
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-primary-400" /> em aberto, no prazo
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-danger-600" /> atrasadas
              </span>
            </p>
          </div>
        )}
      </Card>

      {/* O que precisa de você nesta parte */}
      {(pendencias.length > 0 || estado.sem_nota > 0) && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-xl border border-warning-100 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-900/40 dark:bg-warning-900/20 dark:text-warning-300">
          <AlertTriangle size={16} className="shrink-0" aria-hidden />
          <span className="-ml-3 font-medium">Pra resolver:</span>
          {pendencias.map((p) => (
            <button key={p.texto} type="button" onClick={() => setFiltro(p.ir)} className="text-left font-semibold underline">
              {p.texto}
            </button>
          ))}
          {estado.sem_nota > 0 && (
            <a href="#sem-nota" className="font-semibold underline">
              {plural(estado.sem_nota, "recebimento sem nota", "recebimentos sem nota")}
            </a>
          )}
        </div>
      )}

      {todos.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="font-medium text-slate-800 dark:text-slate-100">Nenhuma nota emitida nesse período.</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Troque o período acima pra ver as notas mais antigas.</p>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Filtrar as notas" className="flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-800">
              {FILTROS.filter((f) => f === "todas" || f === filtro || contagem[f] > 0).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={filtro === f}
                  onClick={() => setFiltro(f)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium ${filtro === f ? "bg-primary-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"}`}
                >
                  {ROTULOS[f]} <span className="tabular-nums opacity-80">({contagem[f]})</span>
                </button>
              ))}
            </div>
            <label className="relative ml-auto">
              <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
              <input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar tomador"
                aria-label="Buscar tomador"
                className="w-44 rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-2 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
          </div>

          {visiveis.length === 0 && (
            <p className="py-6 text-center text-sm text-slate-400">
              {filtro === "pendentes" ? "Nenhuma nota precisa de você agora." : "Nenhuma nota com esse filtro."}
            </p>
          )}

          {visiveis.map(({ grupo, itens }) => {
            const g = grupo.resumo
            const padrao = filtro !== "todas" || !!alvo || g.notas_em_aberto > 0 || grupo.pendencias > 0
            const expandido = grupos[grupo.vinculo_id] ?? padrao
            return (
              <Card key={grupo.vinculo_id} className="overflow-hidden">
                <button
                  type="button"
                  aria-expanded={expandido}
                  onClick={() => setGrupos((atuais) => ({ ...atuais, [grupo.vinculo_id]: !expandido }))}
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-700/30"
                >
                  <span className="min-w-0 flex-1 basis-48">
                    <span className="block truncate text-base font-semibold text-slate-900 dark:text-slate-100">{grupo.apelido}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {plural(g.notas, "nota", "notas")} ·{" "}
                      {grupo.prazo_dias != null ? `costuma pagar em ${grupo.prazo_dias} dia(s)` : "sem prazo de pagamento cadastrado"}
                    </span>
                  </span>
                  <span className="flex flex-wrap items-center gap-x-5 gap-y-1 text-right text-xs text-slate-500 dark:text-slate-400">
                    <span>
                      faturado
                      <span className="block text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(g.faturado)}</span>
                    </span>
                    <span>
                      recebido
                      <span className="block text-sm font-semibold tabular-nums text-success-700 dark:text-success-300">{formatBRL(g.recebido)}</span>
                    </span>
                    <span>
                      em aberto
                      <span
                        className={`block text-sm font-semibold tabular-nums ${g.atrasado > 0 ? "text-danger-600 dark:text-danger-300" : g.em_aberto > 0 ? "text-primary-700 dark:text-primary-300" : "text-slate-400 dark:text-slate-500"}`}
                      >
                        {formatBRL(g.em_aberto)}
                      </span>
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {g.notas_atrasadas > 0 ? (
                      <Badge variant="danger">{plural(g.notas_atrasadas, "atrasada", "atrasadas")}</Badge>
                    ) : grupo.pendencias > 0 ? (
                      <Badge variant="warning">{plural(grupo.pendencias, "pra conferir", "pra conferir")}</Badge>
                    ) : g.notas_em_aberto > 0 ? (
                      <Badge variant="info">{plural(g.notas_em_aberto, "no prazo", "no prazo")}</Badge>
                    ) : (
                      <Badge variant="success">tudo pago ✓</Badge>
                    )}
                    <ChevronDown size={16} className={`text-slate-400 transition-transform ${expandido ? "rotate-180" : ""}`} aria-hidden />
                  </span>
                </button>
                {expandido && (
                  <ul className="divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-700/60 dark:border-slate-700/60">
                    {itens.map((item) => (
                      <NotaConciliadaLinha
                        // (a baixa muda a linha: o formulário dela recomeça do zero)
                        key={`${item.chave}:${item.status}:${item.recebido ?? ""}`}
                        item={item}
                        apelido={grupo.apelido}
                        lancamentos={lancamentos}
                        emissor={dados.emissor}
                        aberta={aberta === item.chave}
                        ocupado={ocupado}
                        onAlternar={() => setAberta((a) => (a === item.chave ? null : item.chave))}
                        onAgir={(acao) => agir(grupo, item, acao)}
                      />
                    ))}
                    {grupo.prazo_dias == null && dados.emissor && g.notas_em_aberto > 0 && (
                      <li className="px-4 py-2 text-xs text-slate-500 dark:text-slate-400">
                        Sem o prazo desse cliente eu só aviso de atraso depois de 60 dias.{" "}
                        <Link to={`/app/tomadores/${grupo.vinculo_id}`} className="font-semibold text-primary-600 hover:underline dark:text-primary-300">
                          Cadastrar em quantos dias ele paga →
                        </Link>
                      </li>
                    )}
                  </ul>
                )}
              </Card>
            )
          })}
        </>
      )}

      {/* O problema espelhado: dinheiro que entrou sem nota */}
      {dados.recebimentos_sem_nota.length > 0 && (
        <Card className="p-5" id="sem-nota">
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <h3 className="flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-200">
              <FilePlus2 className="h-4 w-4 text-accent-600" aria-hidden />
              O contrário: dinheiro que entrou sem nota
            </h3>
            <span className="text-sm font-semibold tabular-nums text-slate-700 dark:text-slate-200">
              {formatBRL(dados.recebimentos_sem_nota.reduce((s, x) => s + x.valor, 0))}
            </span>
          </div>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            Recebimentos que não estão ligados a nenhuma nota — comum em quem paga antes, como Mercado Livre e Amazon. Gere a nota do valor que
            caiu, ligue a uma nota que já existe ou ignore se não precisa de nota.
          </p>
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {dados.recebimentos_sem_nota.map((s) => {
              const abertasDele = (dados.tomadores.find((g) => g.vinculo_id === s.vinculo_id)?.itens ?? []).filter((i) => i.tipo === "nota" && emAberto(i))
              return (
                <li key={s.chave} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2.5">
                  <div className="min-w-0 flex-1 basis-44">
                    <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{s.apelido}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      {formatCompetenciaLonga(s.competencia)}
                      {s.data_recebimento ? ` · caiu em ${formatData(s.data_recebimento)}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(s.valor)}</span>
                  {abertasDele.length > 0 && (
                    <span className="flex items-center gap-1.5">
                      <CaixaBusca
                        valor={ligando[s.chave] ?? ""}
                        opcoes={abertasDele.map((i) => ({ id: i.emissao_id ?? "", rotulo: `Nota de ${mesDaNota(i.competencia)} · ${formatBRL(i.valor)}` }))}
                        onEscolher={(id) => setLigando((atuais) => ({ ...atuais, [s.chave]: id }))}
                        placeholder="Ligar a uma nota em aberto"
                        ariaLabel={`Nota em aberto de ${s.apelido}`}
                        className="w-60"
                      />
                      <Button variant="outline" className="px-3 py-1.5" disabled={ocupado || !ligando[s.chave]} onClick={() => ligarSemNota(s, ligando[s.chave])}>
                        Ligar
                      </Button>
                    </span>
                  )}
                  {dados.emissor && (
                    <Link to={linkGerarNota(s)} className="shrink-0 rounded-md bg-primary-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-primary-700">
                      Gerar nota
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => ignorarSemNota(s)}
                    disabled={ocupado}
                    title="Ignorar este aviso"
                    aria-label={`Ignorar o recebimento de ${s.apelido} sem nota`}
                    className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
                  >
                    <EyeOff className="h-4 w-4" />
                  </button>
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      {dados.lancamentos.length === 0 && r.notas_em_aberto > 0 && (
        <p className="text-center text-xs text-slate-500 dark:text-slate-400">
          Quer que eu procure esses pagamentos?{" "}
          <button type="button" onClick={onImportar} className="font-semibold text-primary-600 hover:underline dark:text-primary-300">
            Importe o extrato do banco
          </button>{" "}
          e eu sugiro qual entrada paga qual nota.
        </p>
      )}
    </div>
  )
}
