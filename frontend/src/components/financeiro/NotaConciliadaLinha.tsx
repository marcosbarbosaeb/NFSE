import { AlertTriangle, CheckCircle2, ChevronDown, Clock, Link2, Sparkles, Undo2 } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { hojeLocal } from "../../lib/datas"
import { NOMES_MESES, formatData, formatDiaMes } from "../../lib/financeiro"
import { formatBRL, parseBRL } from "../../lib/format"
import type { EntradaDoExtrato, NotaConciliada } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { CampoMoeda } from "../ui/CampoMoeda"

/** Uma linha da conciliação "As notas foram pagas?" (05/10/2026): a nota (ou
 * o mês inteiro de notas de vendedores), o estado dela e o que dá pra fazer.
 * Nada aqui grava sozinho — toda ação é um clique da pessoa e usa as rotas
 * de baixa/conciliação que já existiam (POST /pagamentos, POST
 * /conciliacao/{linha}/receita, POST /financeiro/conciliar). */

export type AcaoNaNota =
  | { tipo: "registrar"; valor: number; data: string | null }
  | { tipo: "ligar"; lancamentoId: string }
  | { tipo: "considerar" }
  | { tipo: "desfazer" }
  | { tipo: "conferir"; conferida: boolean }
  | { tipo: "nao_e_esse"; lancamentoId: string }

const classeCampo =
  "mt-0.5 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function mesDaNota(competencia: string): string {
  const [ano, mes] = competencia.split("-").map(Number)
  return `${NOMES_MESES[mes - 1].toLowerCase()} de ${ano}`
}

export function precisaDeAtencao(item: NotaConciliada): boolean {
  return (
    item.status === "atrasada" ||
    ((item.status === "paga_a_menor" || item.status === "paga_a_maior") && !item.conferida) ||
    item.sugestao !== null
  )
}

const COMO: Record<string, string> = {
  extrato: "pelo extrato do banco",
  manual: "baixa registrada à mão",
  planilha: "pela planilha importada",
  conciliacao: "considerada recebida",
}

function diasAte(iso: string | null): number {
  if (!iso) return 0
  const [a, m, d] = iso.split("-").map(Number)
  const hoje = new Date()
  return Math.round((new Date(a, m - 1, d).getTime() - new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()).getTime()) / 86400000)
}

/** O estado da nota em palavras: o selo e a frase que explica. */
export function estadoDaNota(item: NotaConciliada): { variante: "success" | "warning" | "danger" | "info" | "neutral"; rotulo: string; detalhe: string } {
  const quando = item.pago_em ? `em ${formatData(item.pago_em)}` : ""
  if (item.status === "paga") {
    if (item.como === "historico")
      return {
        variante: "success",
        rotulo: "Paga",
        detalhe: `pelo histórico do mês${item.recebido_mes != null ? ` (${formatBRL(item.recebido_mes)} no mês inteiro)` : ""} — não dá pra conferir o valor desta nota`,
      }
    if (item.como === "sem_valor")
      return { variante: "success", rotulo: "Paga", detalhe: "considerada recebida, sem valor lançado — não dá pra conferir o valor" }
    if (item.como === "junto")
      return { variante: "success", rotulo: "Paga", detalhe: "paga junto com a outra nota desse cliente no mesmo mês — sem valor separado" }
    return { variante: "success", rotulo: "Paga", detalhe: [quando, COMO[item.como ?? ""] ?? ""].filter(Boolean).join(" · ") }
  }
  if (item.status === "paga_a_menor" || item.status === "paga_a_maior") {
    const falta = Math.abs(item.diferenca ?? 0)
    const menor = item.status === "paga_a_menor"
    return {
      variante: item.conferida ? "neutral" : "warning",
      rotulo: `${menor ? "Paga a menor" : "Paga a maior"}${item.conferida ? " · conferida" : ""}`,
      detalhe: `recebido ${formatBRL(item.recebido ?? 0)} ${quando} · ${menor ? "faltam" : "sobram"} ${formatBRL(falta)}`.replace("  ", " "),
    }
  }
  if (item.status === "atrasada") {
    return {
      variante: "danger",
      rotulo: "Atrasada",
      detalhe: item.sem_prazo
        ? `há ${item.dias_em_aberto} dias sem pagamento (esse cliente não tem prazo cadastrado: considero 60 dias)`
        : `venceu em ${formatData(item.vencimento)} · ${item.dias_atraso} dia(s) de atraso`,
    }
  }
  const faltam = diasAte(item.vencimento)
  return {
    variante: "info",
    rotulo: "Em aberto · no prazo",
    detalhe: item.sem_prazo
      ? `emitida há ${item.dias_em_aberto} dia(s) — esse cliente não tem prazo cadastrado (considero 60 dias)`
      : `vence em ${formatData(item.vencimento)}${faltam > 0 ? ` (faltam ${faltam} dia(s))` : faltam === 0 ? " (hoje)" : ""}`,
  }
}

function LinhaDoExtrato({ linha }: { linha: EntradaDoExtrato }) {
  return (
    <span className="min-w-0 flex-1">
      <span className="block break-words text-sm text-slate-700 dark:text-slate-200">{linha.descricao}</span>
      <span className="block text-xs text-slate-400 dark:text-slate-500">caiu em {linha.data ? formatData(linha.data) : "data não informada"}</span>
    </span>
  )
}

export function NotaConciliadaLinha({
  item,
  apelido,
  lancamentos,
  emissor,
  aberta,
  ocupado,
  onAlternar,
  onAgir,
}: {
  item: NotaConciliada
  apelido: string
  /** Entradas do extrato ainda sem classificar, por id. */
  lancamentos: Map<string, EntradaDoExtrato>
  emissor: boolean
  aberta: boolean
  ocupado: boolean
  onAlternar: () => void
  onAgir: (acao: AcaoNaNota) => void
}) {
  const estado = estadoDaNota(item)
  const emAberto = item.status === "em_aberto" || item.status === "atrasada"
  const comDiferenca = item.status === "paga_a_menor" || item.status === "paga_a_maior"
  const lote = item.tipo === "lote"
  const falta = comDiferenca && item.status === "paga_a_menor" ? Math.abs(item.diferenca ?? 0) : item.valor
  const [valor, setValor] = useState(falta.toFixed(2))
  const [data, setData] = useState(hojeLocal())
  const [escolhida, setEscolhida] = useState(item.candidatos[0]?.lancamento_id ?? "")
  const [verTodas, setVerTodas] = useState(false)
  const sugerida = item.sugestao ? lancamentos.get(item.sugestao.lancamento_id) : undefined

  const idsCandidatos = new Set(item.candidatos.map((c) => c.lancamento_id))
  const outras = [...lancamentos.values()].filter((l) => !idsCandidatos.has(l.id))
  const titulo = lote ? `Vendedores de ${mesDaNota(item.competencia)}` : `Nota de ${mesDaNota(item.competencia)}`
  const Icone = item.status === "atrasada" ? AlertTriangle : emAberto ? Clock : CheckCircle2
  const corIcone =
    item.status === "atrasada"
      ? "text-danger-600"
      : emAberto
        ? "text-primary-500"
        : comDiferenca && !item.conferida
          ? "text-warning-600"
          : "text-success-600"

  const opcaoDoExtrato = (linha: EntradaDoExtrato, motivos: string[]) => (
    <li key={linha.id}>
      <label
        className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-2.5 py-2 ${escolhida === linha.id ? "border-primary-500 bg-primary-50 dark:bg-primary-900/30" : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40"}`}
      >
        <input type="radio" className="mt-1" name={`extrato-${item.chave}`} checked={escolhida === linha.id} onChange={() => setEscolhida(linha.id)} />
        <span className="min-w-0 flex-1">
          <LinhaDoExtrato linha={linha} />
          {motivos.length > 0 && (
            <span className="mt-1 flex flex-wrap gap-1">
              {motivos.map((m) => (
                <Badge key={m} variant={m.startsWith("mesmo valor") ? "success" : m === "caiu antes da nota" ? "warning" : "info"}>
                  {m}
                </Badge>
              ))}
            </span>
          )}
        </span>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(linha.valor)}</span>
      </label>
    </li>
  )

  return (
    <li className={aberta ? "bg-slate-50/70 dark:bg-slate-900/30" : ""} data-nota={item.chave}>
      <button
        type="button"
        onClick={onAlternar}
        aria-expanded={aberta}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-slate-50 sm:flex-nowrap dark:hover:bg-slate-700/30"
      >
        <Icone size={18} className={`shrink-0 ${corIcone}`} aria-hidden />
        <span className="min-w-0 flex-1 basis-0">
          <span className="block text-sm font-medium text-slate-800 dark:text-slate-100">
            {titulo}
            {lote && (
              <span className="font-normal text-slate-500 dark:text-slate-400">
                {" "}
                · {item.quantidade.toLocaleString("pt-BR")} notas
              </span>
            )}
            {!lote && item.n_dps != null && <span className="font-normal text-slate-400 dark:text-slate-500"> · nº {item.n_dps}</span>}
          </span>
          <span className="block text-xs text-slate-400 dark:text-slate-500">
            {lote ? `emitidas a partir de ${formatDiaMes(item.emitida_em)}` : `emitida em ${formatDiaMes(item.emitida_em)}`}
            {item.antiga ? " · de antes do período escolhido" : ""}
            {item.estado && item.estado !== "confirmado" ? " · ainda não enviada à prefeitura" : ""}
          </span>
        </span>
        <span className="order-3 basis-full pl-[34px] sm:order-none sm:w-[42%] sm:shrink-0 sm:basis-auto sm:pl-0">
          <Badge variant={estado.variante}>{estado.rotulo}</Badge>
          <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">{estado.detalhe}</span>
        </span>
        <span className="shrink-0 text-right sm:w-36">
          <span className="block text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(item.valor)}</span>
          {item.recebido != null && item.recebido > 0 && (
            <span className="block text-xs tabular-nums text-slate-400 dark:text-slate-500">recebido {formatBRL(item.recebido)}</span>
          )}
        </span>
        <ChevronDown size={16} className={`hidden shrink-0 text-slate-400 transition-transform sm:block ${aberta ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {/* Sugestão vinda do extrato: sempre à vista, nunca confirmada sozinha. */}
      {item.sugestao && sugerida && (
        <div className="mx-4 mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-primary-200 bg-primary-50 px-3 py-2.5 dark:border-primary-800 dark:bg-primary-900/30">
          <Sparkles size={16} className="shrink-0 text-primary-600 dark:text-primary-300" aria-hidden />
          <div className="min-w-0 flex-1 basis-56">
            <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
              Parece o pagamento {lote ? "dessas notas" : "desta nota"} — confirmar?
            </p>
            <p className="break-words text-xs text-slate-600 dark:text-slate-300">
              No extrato: “{sugerida.descricao}” · {sugerida.data ? formatData(sugerida.data) : "sem data"} ·{" "}
              <strong className="tabular-nums">{formatBRL(sugerida.valor)}</strong>
            </p>
            <p className="mt-1 flex flex-wrap gap-1">
              {item.sugestao.motivos.map((m) => (
                <Badge key={m} variant={m.startsWith("mesmo valor") ? "success" : m === "caiu antes da nota" ? "warning" : "info"}>
                  {m}
                  {m === "valor quase igual" ? ` (${item.sugestao!.diferenca > 0 ? "+" : "−"} ${formatBRL(Math.abs(item.sugestao!.diferenca))})` : ""}
                </Badge>
              ))}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button disabled={ocupado} onClick={() => onAgir({ tipo: "ligar", lancamentoId: sugerida.id })} className="px-3 py-1.5">
              <CheckCircle2 size={15} /> Confirmar
            </Button>
            <Button
              variant="outline"
              disabled={ocupado}
              onClick={() => onAgir({ tipo: "nao_e_esse", lancamentoId: sugerida.id })}
              className="px-3 py-1.5"
            >
              Não é esse
            </Button>
          </div>
        </div>
      )}

      {aberta && (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3 dark:border-slate-700/60">
          {emAberto || (comDiferenca && item.status === "paga_a_menor") ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {/* 1. Registrar o recebimento */}
              <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {emAberto ? "Registrar o recebimento" : "Registrar o que faltava"}
                </p>
                <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                  {lote
                    ? `O depósito de ${apelido} que pagou as notas desse mês.`
                    : emAberto
                      ? "O dinheiro caiu e você quer dar baixa nesta nota."
                      : `Caiu mais uma parte? Eu somo com o que já entrou (${formatBRL(item.recebido ?? 0)}).`}
                </p>
                <div className="flex flex-wrap items-end gap-2">
                  <label className="min-w-[130px] flex-1 text-xs text-slate-500 dark:text-slate-400">
                    Valor recebido
                    <CampoMoeda valor={valor} onChange={setValor} className={classeCampo} aria-label="Valor recebido" />
                  </label>
                  <label className="min-w-[130px] flex-1 text-xs text-slate-500 dark:text-slate-400">
                    Data em que caiu
                    <input type="date" value={data} onChange={(e) => setData(e.target.value)} className={classeCampo} />
                  </label>
                  <Button
                    disabled={ocupado || !(parseBRL(valor) && (parseBRL(valor) ?? 0) > 0)}
                    onClick={() => onAgir({ tipo: "registrar", valor: parseBRL(valor) ?? 0, data: data || null })}
                    className="bg-success-600 hover:bg-success-700"
                  >
                    Dar baixa
                  </Button>
                </div>
                <p className="mt-1.5 text-[11px] text-slate-400 dark:text-slate-500">
                  Valor {lote ? "das notas" : "da nota"}: {formatBRL(item.valor)}. Se cair um valor diferente, eu mostro a diferença.
                </p>
              </div>

              {/* 2. Ligar a um lançamento do extrato */}
              <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-800 dark:text-slate-100">
                  <Link2 size={15} aria-hidden /> Ligar a um lançamento do extrato
                </p>
                {lancamentos.size === 0 ? (
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Não há entrada do extrato sem classificar. Importe o extrato do banco que eu procuro o pagamento pra você.
                  </p>
                ) : (
                  <>
                    <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                      {item.candidatos.length > 0
                        ? "Entradas do extrato que mais parecem esse pagamento, as melhores primeiro:"
                        : "Nenhuma entrada do extrato parece esse pagamento. Se for uma delas, escolha:"}
                    </p>
                    <ul className="flex max-h-64 flex-col gap-1.5 overflow-y-auto">
                      {item.candidatos.map((c) => {
                        const linha = lancamentos.get(c.lancamento_id)
                        return linha ? opcaoDoExtrato(linha, c.motivos) : null
                      })}
                      {(verTodas || item.candidatos.length === 0) && outras.map((l) => opcaoDoExtrato(l, []))}
                    </ul>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      {item.candidatos.length > 0 && outras.length > 0 ? (
                        <button type="button" onClick={() => setVerTodas((v) => !v)} className="text-xs font-medium text-primary-600 hover:underline dark:text-primary-300">
                          {verTodas ? "mostrar só as parecidas" : `ver as outras ${outras.length} entrada(s) pendente(s)`}
                        </button>
                      ) : (
                        <span />
                      )}
                      <Button variant="outline" disabled={ocupado || !escolhida} onClick={() => onAgir({ tipo: "ligar", lancamentoId: escolhida })}>
                        Ligar e dar baixa
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-600 dark:text-slate-300">
              {item.pagamentos.filter((p) => p.valor > 0).length > 0 ? (
                <ul className="mb-2 flex flex-col gap-1">
                  {item.pagamentos
                    .filter((p) => p.valor > 0)
                    .map((p) => (
                      <li key={p.id} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                        <span className="font-medium tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(p.valor)}</span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          {p.data ? `caiu em ${formatData(p.data)}` : "sem data informada"} · {COMO[p.origem] ?? p.origem}
                        </span>
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">{estado.detalhe}.</p>
              )}
            </div>
          )}

          {/* Rodapé: o que mais dá pra fazer com esta linha */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
            {comDiferenca && (
              <button
                type="button"
                disabled={ocupado}
                onClick={() => onAgir({ tipo: "conferir", conferida: !item.conferida })}
                className="font-semibold text-primary-600 hover:underline disabled:opacity-50 dark:text-primary-300"
                title="Use quando a diferença é esperada — imposto retido pelo cliente, por exemplo"
              >
                {item.conferida ? "Voltar a avisar dessa diferença" : "A diferença está certa (ex.: imposto retido)"}
              </button>
            )}
            {emAberto && !lote && (
              <button
                type="button"
                disabled={ocupado}
                onClick={() => onAgir({ tipo: "considerar" })}
                className="font-medium text-slate-500 underline hover:text-slate-700 disabled:opacity-50 dark:text-slate-400"
                title={`Marca como recebidas as notas em aberto de ${apelido} em ${mesDaNota(item.competencia)}, sem lançar valor`}
              >
                Já recebi por fora (dar baixa sem lançar valor)
              </button>
            )}
            {!emAberto && (
              <button
                type="button"
                disabled={ocupado}
                onClick={() => onAgir({ tipo: "desfazer" })}
                className="inline-flex items-center gap-1 font-medium text-slate-500 underline hover:text-slate-700 disabled:opacity-50 dark:text-slate-400"
              >
                <Undo2 size={13} /> Desfazer a baixa
              </button>
            )}
            {emissor && !lote && item.emissao_id && (
              <Link to={`/app/nfse/${item.emissao_id}`} className="font-medium text-slate-500 underline hover:text-slate-700 dark:text-slate-400">
                Abrir a nota
              </Link>
            )}
            {emissor && lote && (
              <Link to="/app/nfse/lote" className="font-medium text-slate-500 underline hover:text-slate-700 dark:text-slate-400">
                Ver as notas em lote
              </Link>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
