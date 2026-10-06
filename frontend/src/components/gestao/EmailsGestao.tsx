import { Layers, Mail, MailWarning, Trophy } from "lucide-react"
import { formatCompetenciaLonga } from "../../lib/format"
import { nomeDaConta, numero, plural } from "../../lib/gestao"
import type { PainelGestao } from "../../lib/types"
import { TituloSecao } from "../PaginaAbas"
import { Card } from "../ui/Card"
import { StatCard } from "../ui/StatCard"
import { useVerMais } from "../ui/VerMais"

// Gestão › E-mails (06/10/2026): quanto da cota de envio o mês já gastou e
// quem mais envia. Contam os e-mails de nota das contas reais.

/** E-mails por mês incluídos no plano de envio contratado. */
const COTA_MENSAL = 50_000

const classeTh = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const classeTd = "px-3 py-2.5 text-slate-700 dark:text-slate-200"

export function EmailsGestao({ painel }: { painel: PainelGestao }) {
  const r = painel.resumo
  const mes = formatCompetenciaLonga(painel.competencia).toLowerCase()
  const ranking = painel.contas
    .filter((c) => !c.demo && (c.emails_mes > 0 || c.emails_falha_mes > 0))
    .sort((a, b) => b.emails_mes - a.emails_mes || b.emails_falha_mes - a.emails_falha_mes)
  const { visiveis, botao } = useVerMais(ranking, 10)

  const usado = (r.emails_mes / COTA_MENSAL) * 100
  const pct = usado.toLocaleString("pt-BR", { maximumFractionDigits: usado < 10 ? 1 : 0 })
  const corBarra = usado >= 100 ? "bg-danger-600 dark:bg-danger-400" : usado >= 80 ? "bg-warning-600 dark:bg-warning-400" : "bg-primary-500 dark:bg-primary-400"
  const deLote = r.emails_mes > 0 ? Math.round((r.emails_lote_mes / r.emails_mes) * 100) : 0

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard icon={<Mail size={18} />} label="E-mails enviados no mês" value={numero(r.emails_mes)} sublabel={`em ${mes}`} />
        <StatCard
          icon={<Layers size={18} />}
          label="Foram de lote"
          value={numero(r.emails_lote_mes)}
          sublabel={r.emails_mes > 0 ? `${deLote}% do que saiu no mês` : "nada enviado ainda"}
        />
        <StatCard
          icon={<MailWarning size={18} />}
          iconClassName={
            r.emails_falha_mes > 0
              ? "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300"
              : "bg-success-50 text-success-600 dark:bg-success-900/40 dark:text-success-300"
          }
          label="Falhas no mês"
          value={numero(r.emails_falha_mes)}
          sublabel={r.emails_falha_mes > 0 ? "e-mails que não foram entregues" : "nenhum e-mail voltou"}
        />
      </div>

      <Card className="p-5">
        <TituloSecao icone={Mail}>Cota do plano de e-mail</TituloSecao>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p className="text-sm text-slate-700 dark:text-slate-200">
            <strong className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{pct}%</strong> usado
          </p>
          <p className="text-sm tabular-nums text-slate-500 dark:text-slate-400">
            {numero(r.emails_mes)} de {numero(COTA_MENSAL)}
          </p>
        </div>
        <div
          role="progressbar"
          aria-label="Quanto da cota de e-mails do mês já foi usado"
          aria-valuemin={0}
          aria-valuemax={COTA_MENSAL}
          aria-valuenow={Math.min(r.emails_mes, COTA_MENSAL)}
          aria-valuetext={`${pct}% — ${numero(r.emails_mes)} de ${numero(COTA_MENSAL)} e-mails`}
          className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"
        >
          <div className={`h-full rounded-full transition-[width] duration-300 ${corBarra}`} style={{ width: `${Math.min(100, r.emails_mes > 0 ? Math.max(1, usado) : 0)}%` }} />
        </div>
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          O plano de e-mail contratado inclui {numero(COTA_MENSAL)} envios por mês.
          {usado >= 100
            ? " A cota do mês acabou: os lotes ficam aguardando e voltam sozinhos quando ela renovar."
            : usado >= 80
              ? " Está perto do limite — se acabar, os lotes ficam aguardando e voltam sozinhos quando a cota renovar."
              : ` Ainda cabem ${numero(Math.max(0, COTA_MENSAL - r.emails_mes))} neste mês.`}{" "}
          Aqui entram só os e-mails de nota (avulsos e de lote); os de cadastro e de código de acesso não estão nesta conta.
        </p>
      </Card>

      <Card className="p-5">
        <TituloSecao icone={Trophy}>Quem mais enviou no mês</TituloSecao>
        {ranking.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Nenhuma conta enviou e-mail em {mes} ainda.</p>
        ) : (
          <>
            <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">{plural(ranking.length, "conta enviou", "contas enviaram")} e-mail neste mês.</p>
            <div className="-mx-2 overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700">
                    <th scope="col" className={classeTh}>Empresa</th>
                    <th scope="col" className={`${classeTh} text-right`}>No mês</th>
                    <th scope="col" className={`${classeTh} text-right`}>De lote</th>
                    <th scope="col" className={`${classeTh} text-right`}>Falhas</th>
                    <th scope="col" className={`${classeTh} text-right`}>Desde o começo</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {visiveis.map((c, i) => (
                    <tr key={c.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700/60">
                      <th scope="row" className={`${classeTd} text-left font-normal`}>
                        <span className="mr-2 text-xs text-slate-400 dark:text-slate-500">{i + 1}º</span>
                        <span className="font-medium text-slate-800 dark:text-slate-100">{nomeDaConta(c)}</span>
                      </th>
                      <td className={`${classeTd} text-right font-semibold`}>{numero(c.emails_mes)}</td>
                      <td className={`${classeTd} text-right`}>{numero(c.emails_lote_mes)}</td>
                      <td className={`${classeTd} text-right ${c.emails_falha_mes > 0 ? "text-warning-700 dark:text-warning-300" : ""}`}>{numero(c.emails_falha_mes)}</td>
                      <td className={`${classeTd} text-right`}>{numero(c.emails_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {botao}
          </>
        )}
      </Card>
    </>
  )
}
