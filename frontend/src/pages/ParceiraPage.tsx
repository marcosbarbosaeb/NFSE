import { HandCoins, PauseCircle, Users, Wallet } from "lucide-react"
import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { AnaAvatar } from "../components/brand/Marca"
import { Badge } from "../components/ui/Badge"
import { BotaoCopiar } from "../components/ui/BotaoCopiar"
import { Card } from "../components/ui/Card"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import { dataBR, formatPct, situacaoDoIndicado } from "../lib/parceiras"
import type { ParceiroResumo } from "../lib/types"

// Painel da parceira de indicação (06/10/2026) — página PÚBLICA, aberta pelo
// link secreto /parceira/<token>. A parceira não é cliente e não tem login:
// nada aqui pode depender de sessão (só GET /publico/parceira/{token}).

const classeTh = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const classeTd = "px-3 py-2.5 text-slate-700 dark:text-slate-200"

export function ParceiraPage() {
  const { token = "" } = useParams()
  const [dados, setDados] = useState<ParceiroResumo | null>(null)
  const [erro, setErro] = useState<{ texto: string; linkInvalido: boolean } | null>(null)

  useEffect(() => {
    let vivo = true
    api
      .get<ParceiroResumo>(`/publico/parceira/${encodeURIComponent(token)}`)
      .then((d) => {
        if (vivo) setDados(d)
      })
      .catch((err) => {
        if (!vivo) return
        if (err instanceof ApiError) setErro({ texto: formatarErro(err.detail), linkInvalido: err.status === 404 })
        else setErro({ texto: "Não consegui carregar agora. Confira a internet e tente de novo.", linkInvalido: false })
      })
    return () => {
      vivo = false
    }
  }, [token])

  // O endereço é secreto: não deve aparecer em busca nem vazar no "referer".
  useEffect(() => {
    const titulo = document.title
    document.title = "Suas indicações — Agente Ana"
    const metas = [
      { name: "robots", content: "noindex, nofollow" },
      { name: "referrer", content: "no-referrer" },
    ].map((m) => {
      const el = document.createElement("meta")
      el.name = m.name
      el.content = m.content
      document.head.appendChild(el)
      return el
    })
    return () => {
      document.title = titulo
      metas.forEach((el) => el.remove())
    }
  }, [])

  return (
    <div className="min-h-screen bg-canvas px-4 py-8 dark:bg-canvas-dark sm:py-12">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <header className="flex items-center gap-3">
          <AnaAvatar size={52} />
          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              <span className="font-normal opacity-80">Agente</span> <span className="text-accent-500">Ana</span>
              <span className="ml-2 font-normal text-slate-400 dark:text-slate-500">· Parceiras</span>
            </p>
            <h1 className="break-words text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {dados ? `Olá, ${dados.nome}` : erro ? "Painel da parceira" : "Olá!"}
            </h1>
          </div>
        </header>

        {!dados && !erro && (
          <p role="status" className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
            Carregando suas indicações...
          </p>
        )}

        {erro && (
          <Card className="p-6 text-center">
            <p className="text-base font-semibold text-slate-800 dark:text-slate-200">
              {erro.linkInvalido ? "Este link não funciona mais" : "Não deu pra abrir o painel"}
            </p>
            <p role="alert" className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {erro.texto}
            </p>
            {!erro.linkInvalido && (
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="mt-4 text-sm font-medium text-primary-700 underline dark:text-primary-300"
              >
                Tentar de novo
              </button>
            )}
          </Card>
        )}

        {dados && <Painel dados={dados} />}

        <footer className="border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {dados && (
            <p>
              <strong className="text-slate-700 dark:text-slate-200">Guarde este endereço:</strong> é por ele que você acompanha
              suas indicações. Não compartilhe.
            </p>
          )}
          <p className={dados ? "mt-1" : ""}>Ficou com dúvida? Fale com quem te convidou pra ser parceira.</p>
        </footer>
      </div>
    </div>
  )
}

function Painel({ dados }: { dados: ParceiroResumo }) {
  return (
    <>
      {!dados.ativo && (
        <div role="status" className="flex items-start gap-3 rounded-2xl border border-warning-300 bg-warning-50 p-4 dark:border-warning-900/60 dark:bg-warning-900/20">
          <PauseCircle size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-warning-600 dark:text-warning-300" />
          <p className="text-sm text-warning-700 dark:text-warning-300">
            <strong>Seu link de indicação está pausado.</strong> Enquanto estiver assim, novos cadastros por ele não contam
            pra você. Fale com quem te convidou pra saber mais.
          </p>
        </div>
      )}

      <Card className="p-5">
        <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Seu link de indicação</h2>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            readOnly
            aria-label="Seu link de indicação"
            value={dados.link}
            onFocus={(e) => e.target.select()}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
          />
          <BotaoCopiar texto={dados.link} rotulo="Copiar link" variant="accent" className="shrink-0" />
        </div>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
          Você recebe <strong>{formatPct(dados.comissao_pct)}</strong> de cada mensalidade paga por quem assinar pelo seu link,
          enquanto a assinatura estiver ativa.
        </p>
        {dados.desconto_1_mes_pct > 0 && (
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Quem assinar pelo seu link ganha <strong>{formatPct(dados.desconto_1_mes_pct)}</strong> de desconto na primeira
            mensalidade.
          </p>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<Users size={18} />}
          iconClassName="bg-success-50 text-success-600 dark:bg-success-900/40 dark:text-success-300"
          label="Indicados com assinatura ativa"
          value={dados.indicados_ativos}
          sublabel={`de ${dados.indicados_total} que se cadastraram`}
        />
        <StatCard
          icon={<Wallet size={18} />}
          iconClassName="bg-primary-50 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300"
          label="Comissão acumulada"
          value={formatBRL(dados.total_comissao)}
          sublabel="desde o começo"
        />
        <StatCard
          icon={<HandCoins size={18} />}
          iconClassName="bg-accent-50 text-accent-600 dark:bg-accent-900/40 dark:text-accent-300"
          label="A receber"
          value={formatBRL(dados.a_receber)}
          sublabel="ainda não repassado"
        />
      </div>

      <Card className="p-5">
        <h2 className="mb-3 text-base font-semibold text-slate-800 dark:text-slate-200">Quem veio pelo seu link</h2>
        {dados.indicados.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
            Ninguém ainda — mande seu link pra quem emite nota fiscal todo mês.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {dados.indicados.map((i, n) => {
              const situacao = situacaoDoIndicado(i.status)
              return (
                <li key={n} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2.5 text-sm">
                  <span className="text-slate-700 dark:text-slate-200">
                    {i.nome}
                    <span className="ml-2 text-xs text-slate-400 dark:text-slate-500">desde {dataBR(i.desde)}</span>
                  </span>
                  <Badge variant={situacao.variante}>{situacao.rotulo}</Badge>
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="mb-3 text-base font-semibold text-slate-800 dark:text-slate-200">Suas comissões, mês a mês</h2>
        {dados.meses.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
            Ainda não há comissão — ela aparece aqui quando um indicado pagar a primeira mensalidade.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[460px] text-sm">
              <thead>
                <tr>
                  <th className={classeTh}>Mês</th>
                  <th className={`${classeTh} text-right`}>Mensalidades pagas</th>
                  <th className={`${classeTh} text-right`}>Comissão</th>
                  <th className={classeTh}>Situação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                {dados.meses.map((m) => (
                  <tr key={m.competencia}>
                    <td className={`${classeTd} whitespace-nowrap`}>{formatCompetenciaLonga(m.competencia)}</td>
                    <td className={`${classeTd} text-right`}>{m.pagamentos}</td>
                    <td className={`${classeTd} whitespace-nowrap text-right font-medium`}>{formatBRL(m.comissao)}</td>
                    <td className={classeTd}>
                      {m.a_pagar > 0 ? (
                        <Badge variant="warning">
                          {m.pago_em ? `A receber: ${formatBRL(m.a_pagar)}` : "A receber"}
                        </Badge>
                      ) : m.pago_em ? (
                        <span className="whitespace-nowrap text-success-700 dark:text-success-300">Repassado em {dataBR(m.pago_em)}</span>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
