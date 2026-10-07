import { Check, Infinity as Infinito, MessagesSquare } from "lucide-react"
import { useState } from "react"
import { api } from "../lib/api"
import { avisarUsoMudou, reais, textoDoLimite } from "../lib/planos"
import type { Assinatura, PlanoAssinatura, UsoDoPlano } from "../lib/types"
import { BotaoSuporte } from "./SuporteModal"
import { Badge } from "./ui/Badge"
import { Button } from "./ui/Button"

// Planos por limite de notas (07/10/2026): Básico 30, Empreendedor 150,
// Empresa 300 + Financeiro, Avançado 500 + Financeiro, Ilimitado; Financeiro
// sozinho ou somado ao Básico/Empreendedor; Personalizado pelo suporte.

/** Barra de uso do mês, aviso dos 80% e o aceite da nota excedente. */
export function UsoDoMes({ uso, aoMudar, somenteLeitura = false }: { uso: UsoDoPlano; aoMudar?: (u: UsoDoPlano) => void; somenteLeitura?: boolean }) {
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  if (uso.limite === null || uso.limite === 0) {
    return (
      <div className="mb-5 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
        {uso.limite === 0 ? (
          "Este plano não inclui emissão de notas."
        ) : (
          <span className="flex items-center gap-2">
            <Infinito size={16} className="text-primary-600 dark:text-primary-400" aria-hidden="true" />
            <span>
              <strong>{uso.usadas.toLocaleString("pt-BR")}</strong> {uso.usadas === 1 ? "nota autorizada" : "notas autorizadas"} este mês — sem limite.
            </span>
          </span>
        )}
      </div>
    )
  }
  const pct = Math.min(100, uso.pct ?? 0)
  const cor = uso.aviso === "limite" ? "bg-danger-600" : uso.aviso === "perto" ? "bg-warning-600" : "bg-primary-600"
  const preco = reais(uso.excedente_preco)

  async function aceitar(valor: boolean) {
    setSalvando(true)
    setErro(null)
    try {
      const novo = await api.post<UsoDoPlano>("/assinatura/excedente", { aceitar: valor })
      aoMudar?.(novo)
      avisarUsoMudou()
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não consegui salvar. Tente de novo.")
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="mb-5 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
          Notas deste mês{uso.em_teste ? " (teste grátis)" : uso.plano_nome ? ` · plano ${uso.plano_nome}` : ""}
        </p>
        <p className="text-sm tabular-nums text-slate-600 dark:text-slate-300">
          <strong className="text-slate-900 dark:text-slate-100">{uso.usadas.toLocaleString("pt-BR")}</strong> de {uso.limite.toLocaleString("pt-BR")}
        </p>
      </div>
      <div
        className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={uso.limite}
        aria-valuenow={Math.min(uso.usadas, uso.limite)}
        aria-label="Notas autorizadas no mês"
      >
        <div className={`h-full rounded-full ${cor}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Conta só nota autorizada pela prefeitura. Cancelada, recusada e de teste não contam. O contador zera no dia 1º.
      </p>

      {uso.aviso === "perto" && (
        <p className="mt-3 rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-800 dark:bg-warning-900/30 dark:text-warning-200">
          Você já usou {uso.pct}% das notas do mês — faltam {uso.restantes}.
          {uso.proximo_plano && (
            <>
              {" "}
              O plano <strong>{uso.proximo_plano.nome}</strong> comporta{" "}
              {uso.proximo_plano.limite_notas === null ? "notas sem limite" : `${uso.proximo_plano.limite_notas} notas por mês`}
              {uso.proximo_plano.valor != null && ` por ${reais(uso.proximo_plano.valor)}`}.
            </>
          )}
        </p>
      )}
      {uso.aviso === "limite" && !uso.excedente_aceito && (
        <p className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-200">
          Você chegou no limite de notas deste mês.{" "}
          {uso.trava_ligada ? "Pra continuar emitindo, " : "Pra não parar quando a cobrança começar, "}
          {uso.em_teste ? "assine um plano abaixo." : uso.excedente_pode ? `suba de plano ou aceite pagar ${preco} por nota a mais.` : "suba de plano abaixo."}
        </p>
      )}
      {uso.excedente_aceito && uso.excedentes > 0 && (
        <p className="mt-3 rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
          {uso.excedentes} {uso.excedentes === 1 ? "nota" : "notas"} acima do limite este mês: <strong>{reais(uso.excedente_valor)}</strong> a mais na
          próxima fatura.
          {uso.proximo_plano?.valor != null && ` Se for ficar assim todo mês, o plano ${uso.proximo_plano.nome} (${reais(uso.proximo_plano.valor)}) pode sair mais barato.`}
        </p>
      )}

      {uso.excedente_pode && !somenteLeitura && (
        <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-700">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            checked={uso.excedente_aceito}
            disabled={salvando}
            onChange={(e) => aceitar(e.target.checked)}
          />
          <span className="text-sm">
            <span className="font-medium text-slate-700 dark:text-slate-200">Continuar emitindo depois do limite por {preco} cada nota</span>
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Sem isso, a emissão para ao chegar no limite. Com isso, as notas a mais entram na fatura seguinte. Você pode desmarcar quando quiser.
            </span>
          </span>
        </label>
      )}
      {erro && <p className="mt-2 text-sm text-danger-700 dark:text-danger-300">{erro}</p>}
    </div>
  )
}

export function GradeDePlanos({
  assinatura,
  carregando,
  aoEscolher,
}: {
  assinatura: Assinatura
  carregando: boolean
  aoEscolher: (plano: PlanoAssinatura, comFinanceiro: boolean) => void
}) {
  const planos = assinatura.planos ?? []
  const pagando = assinatura.tem_assinatura_stripe && assinatura.status !== "cancelada"
  const [comFinanceiro, setComFinanceiro] = useState(Boolean(assinatura.com_financeiro))
  const extra = assinatura.financeiro_a_parte
  const recomendado = assinatura.uso?.proximo_plano?.id
  if (planos.length === 0) return null
  return (
    <div className="mb-4">
      <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">{pagando ? "Seu plano" : "Escolha o plano"}</p>

      {extra && planos.some((p) => p.aceita_financeiro) && (
        <label className="mb-3 flex cursor-pointer items-start gap-3 rounded-xl bg-slate-50 px-4 py-3 dark:bg-slate-900/40">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            checked={comFinanceiro}
            onChange={(e) => setComFinanceiro(e.target.checked)}
          />
          <span className="text-sm">
            <span className="font-medium text-slate-700 dark:text-slate-200">Somar o Financeiro ao Básico ou ao Empreendedor (+ {reais(extra.valor)}/mês)</span>
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Recebimentos, contas do mês e conciliação do extrato. Empresa, Avançado e Ilimitado já vêm com ele.
            </span>
          </span>
        </label>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {planos.map((p) => {
          const somando = Boolean(p.aceita_financeiro && comFinanceiro && extra)
          const mesmoPlano = p.atual && pagando
          // o plano é o mesmo, mas a pessoa marcou/desmarcou o Financeiro
          const mudouExtra = mesmoPlano && p.aceita_financeiro && comFinanceiro !== Boolean(assinatura.com_financeiro)
          const atual = mesmoPlano && !mudouExtra
          const total = p.valor != null ? p.valor + (somando ? extra!.valor : 0) : null
          return (
            <div
              key={p.id}
              className={`flex flex-col rounded-xl border p-4 ${
                atual
                  ? "border-primary-500 bg-primary-50/60 dark:bg-primary-900/20"
                  : p.id === recomendado
                    ? "border-accent-400 dark:border-accent-500"
                    : "border-slate-200 dark:border-slate-700"
              }`}
            >
              <p className="flex flex-wrap items-center justify-between gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                {p.nome}
                {atual ? <Badge variant="success">seu plano</Badge> : p.id === recomendado && assinatura.uso?.aviso ? <Badge variant="warning">cabe o seu mês</Badge> : null}
              </p>
              {total != null && (
                <p className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">
                  {reais(total)}
                  <span className="text-xs font-normal text-slate-500 dark:text-slate-400"> /{p.intervalo === "year" ? "ano" : "mês"}</span>
                </p>
              )}
              <ul className="mt-2 flex flex-1 flex-col gap-1 text-xs text-slate-600 dark:text-slate-300">
                <Linha>{textoDoLimite(p.limite_notas)}</Linha>
                {p.modulos.includes("emissor") && <Linha>Emissão, tomadores, envio e calendário</Linha>}
                {(p.modulos.includes("financeiro") || somando) && <Linha>{p.id === "financeiro" ? "Recebimentos, contas do mês e conciliação" : somando ? "Financeiro somado" : "Financeiro incluído"}</Linha>}
              </ul>
              {!atual && (
                <Button
                  type="button"
                  variant={p.id === recomendado ? "accent" : "outline"}
                  className="mt-3 px-3 py-1.5"
                  disabled={carregando || !p.disponivel}
                  title={p.disponivel ? undefined : "A cobrança deste plano ainda está sendo ligada"}
                  onClick={() => aoEscolher(p, somando)}
                >
                  {!p.disponivel ? "Em breve" : mudouExtra ? (comFinanceiro ? "Somar o Financeiro" : "Tirar o Financeiro") : pagando ? "Mudar pra este" : "Assinar este"}
                </Button>
              )}
            </div>
          )
        })}

        <div className="flex flex-col rounded-xl border border-dashed border-slate-300 p-4 dark:border-slate-600">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Personalizado</p>
          <p className="mt-1 flex-1 text-xs text-slate-600 dark:text-slate-300">
            Várias empresas, volume muito alto ou uma necessidade diferente? A gente monta um plano pra você.
          </p>
          <BotaoSuporte
            logado
            className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <MessagesSquare size={15} aria-hidden="true" /> Fale com a nossa equipe
          </BotaoSuporte>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
        O limite é por CNPJ e por mês. O plano define os módulos desta empresa: se você sair de um módulo, os dados dele ficam guardados e voltam
        quando contratar de novo.
      </p>
    </div>
  )
}

function Linha({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-1.5">
      <Check size={13} className="mt-0.5 shrink-0 text-success-600" aria-hidden="true" />
      <span>{children}</span>
    </li>
  )
}
