import {
  EyeOff,
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileText,
  Plus,
  TrendingDown,
  TrendingUp,
  UserPlus,
  Wallet,
} from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { type NotaParaAcoes, SeloAssinatura, SeloPrefeitura, SeloTomador } from "../components/AcoesNota"
import { BaixaPagamento } from "../components/BaixaPagamento"
import { Badge } from "../components/ui/Badge"
import { Card } from "../components/ui/Card"
import { MiniBarChart } from "../components/ui/MiniBarChart"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../lib/format"
import type { DashboardResumo, EmissaoResumoLinha, Proximos } from "../lib/types"


function formatDataCurta(iso: string): string {
  const [ano, mes, dia] = iso.split("-").map(Number)
  return new Date(ano, mes - 1, dia).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })
}

function badgeEstadoNfse(estado: string, label: string) {
  if (["confirmado", "assinado", "submetido", "montado"].includes(estado)) return <Badge variant="success">{label}</Badge>
  if (estado === "erro") return <Badge variant="danger">{label}</Badge>
  return <Badge variant="neutral">{label}</Badge>
}

function badgeEnvio(status: string | null) {
  if (status === "enviado") return <Badge variant="success">Enviada</Badge>
  if (status === "falha") return <Badge variant="danger">Falha</Badge>
  if (status === "pendente") return <Badge variant="warning">Pendente</Badge>
  return <Badge variant="neutral">Não enviado</Badge>
}


function notaDaLinha(l: EmissaoResumoLinha): NotaParaAcoes {
  return { id: l.emissao_id, estado: l.estado, envio_status: l.envio_status, tem_pdf: l.tem_pdf, tem_email: l.tem_email, homologacao: l.homologacao, envio_forma: l.envio_forma, vinculo_id: l.vinculo_id }
}

const COR_PENDENCIA: Record<string, string> = {
  erro: "bg-danger-600",
  prefeitura: "bg-warning-600",
  assinar: "bg-warning-600",
  enviar_tomador: "bg-primary-600",
  nota_recebimento: "bg-accent-600",
  gerar: "bg-accent-600",
  receber: "bg-success-600",
}

export function DashboardPage() {
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [resumo, setResumo] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

  const [proximos, setProximos] = useState<Proximos | null>(null)

  // "Ignorar este aviso" — atraso consciente (ex.: nota que sai depois do pagamento).
  function ignorarPendencia(chave: string) {
    setProximos((p) =>
      p ? { ...p, pendencias: p.pendencias.filter((x) => x.chave !== chave), total_pendencias: Math.max(0, p.total_pendencias - 1) } : p,
    )
    api.post("/painel/pendencias/ignorar", { chave }).catch(() => setRecarga((n) => n + 1))
  }
  const [recarga, setRecarga] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelado = false
    setCarregando(true)
    setErro(null)
    api
      .get<DashboardResumo>(`/painel/resumo-mes?competencia=${competencia}`)
      .then((dados) => {
        if (!cancelado) setResumo(dados)
      })
      .catch((err) => {
        if (!cancelado) setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
      })
      .finally(() => {
        if (!cancelado) setCarregando(false)
      })
    return () => {
      cancelado = true
    }
  }, [competencia, recarga])

  // "Próximos eventos não está aparecendo, pode aparecer além de somente
  // eventos" (28/09/2026): o que tem pra fazer agora + agenda de 30 dias.
  useEffect(() => {
    let cancelado = false
    api
      .get<Proximos>("/painel/proximos")
      .then((dados) => {
        if (!cancelado) setProximos(dados)
      })
      .catch(() => {
        if (!cancelado) setProximos({ pendencias: [], total_pendencias: 0, agenda: [] })
      })
    return () => {
      cancelado = true
    }
  }, [recarga])

  const pctEmitidas = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.emitidas / resumo.total_vinculos) * 100) : 0
  const pctAguardando = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.aguardando / resumo.total_vinculos) * 100) : 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Bom dia! 👋</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Aqui está o resumo das suas notas deste mês.</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800">
          <button
            type="button"
            onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))}
            className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            ‹
          </button>
          <span className="min-w-[9rem] text-center font-medium text-slate-700 dark:text-slate-300">{formatCompetenciaLonga(competencia)}</span>
          <button
            type="button"
            onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
            className="rounded px-2 py-0.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            ›
          </button>
        </div>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {carregando && !resumo && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {resumo && (
        <>
          {/* "Ligar a visão geral com as abas" (28/09/2026): cada número leva
              pra tela onde ele é resolvido. */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Link to="/app/tomadores" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<FileText size={18} />}
                iconClassName="bg-primary-50 text-primary-600"
                label="Notas deste mês"
                value={resumo.total_vinculos}
                sublabel="tomadores ativos"
              />
            </Link>
            <Link to="/app/nfse" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<CheckCircle2 size={18} />}
                iconClassName="bg-success-50 text-success-600"
                label="Emitidas"
                value={resumo.emitidas}
                sublabel={`${pctEmitidas}% do mês`}
              />
            </Link>
            <Link to="/app/tomadores" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<Clock size={18} />}
                iconClassName="bg-warning-50 text-warning-600"
                label="Aguardando emissão"
                value={resumo.aguardando}
                sublabel={`${pctAguardando}% do mês · gerar`}
              />
            </Link>
            <Link to="/app/financeiro#a-receber" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<Wallet size={18} />}
                iconClassName="bg-accent-50 text-accent-600"
                label="Notas a receber"
                value={formatBRL(resumo.a_receber_total ?? resumo.a_receber)}
                sublabel={`${resumo.notas_a_receber ?? resumo.pagamentos_pendentes} nota(s) em aberto · todos os meses`}
              />
            </Link>
            <Link to="/app/financeiro" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<TrendingUp size={18} />}
                iconClassName="bg-success-50 text-success-600"
                label="Notas recebidas"
                value={formatBRL(resumo.recebido_total ?? 0)}
                sublabel={`${resumo.notas_recebidas ?? 0} nota(s) pagas · total`}
              />
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="p-5 xl:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Emissões deste mês</h2>
                <div className="flex items-center gap-3">
                  <Link to="/app/nfse" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
                    Ver todas <ArrowRight size={14} />
                  </Link>
                  <Link
                    to="/app/nfse?nova=1"
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600"
                  >
                    <Plus size={15} /> Nova emissão
                  </Link>
                </div>
              </div>

              {resumo.emissoes.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma nota emitida nesta competência ainda.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-slate-700/60 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                        <th className="py-2 font-medium">Tomador</th>
                        <th className="py-2 font-medium">Valor</th>
                        <th className="py-2 font-medium">Assinatura</th>
                        <th className="py-2 font-medium">Prefeitura</th>
                        <th className="py-2 font-medium">Fornecedor</th>
                        <th className="py-2 font-medium">Pagamento</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resumo.emissoes.map((linha) => (
                        <tr
                          key={linha.emissao_id}
                          onClick={() =>
                            navigate(
                              linha.vendedores
                                ? "/app/nfse?aba=vendedores"
                                : (linha.quantidade ?? 1) > 1
                                  ? "/app/nfse"
                                  : `/app/nfse/${linha.emissao_id}`,
                            )
                          }
                          className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:border-slate-700/40 dark:hover:bg-slate-700/40"
                        >
                          <td className="py-3">
                            <p className="font-medium text-slate-800 dark:text-slate-200">{linha.apelido}</p>
                            <p className="text-xs text-slate-400 dark:text-slate-500">{linha.tomador_razao_social}</p>
                          </td>
                          <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(linha.valor)}</td>
                          {(linha.quantidade ?? 1) > 1 ? (
                            <>
                              <td className="py-3" colSpan={2}>
                                {badgeEstadoNfse(linha.estado, linha.estado_label)}
                              </td>
                              <td className="py-3">{badgeEnvio(linha.envio_status)}</td>
                            </>
                          ) : (
                            <>
                              <td className="py-3">
                                <SeloAssinatura nota={notaDaLinha(linha)} onMudou={() => setRecarga((n) => n + 1)} />
                              </td>
                              <td className="py-3">
                                <SeloPrefeitura nota={notaDaLinha(linha)} onMudou={() => setRecarga((n) => n + 1)} />
                              </td>
                              <td className="py-3">
                                <SeloTomador nota={notaDaLinha(linha)} onMudou={() => setRecarga((n) => n + 1)} />
                              </td>
                            </>
                          )}
                          <td className="py-3">
                            {linha.vendedores ? (
                              <Badge variant="neutral">Na nota da Shopee</Badge>
                            ) : (
                              <BaixaPagamento
                                emissaoId={linha.emissao_id}
                                vinculoId={linha.vinculo_id}
                                competencia={linha.competencia}
                                valor={linha.valor}
                                recebido={linha.pagamento_recebido}
                                onMudou={() => setRecarga((n) => n + 1)}
                              />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card className="p-5">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle size={16} className="text-warning-600" />
                <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Precisa da sua atenção</h2>
                {resumo.atencao.length > 0 && <Badge variant="warning">{resumo.atencao.length}</Badge>}
              </div>
              {resumo.atencao.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">Tudo em dia por aqui.</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {resumo.atencao.map((item, i) => (
                    <li key={i} className="rounded-lg bg-warning-50 px-3 py-2">
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{item.titulo}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.mensagem}</p>
                      {item.link && (
                        <Link
                          to={item.link}
                          className="mt-1.5 inline-flex items-center gap-1 text-xs font-semibold text-primary-600 hover:text-primary-700"
                        >
                          {item.link_label ?? "Resolver"} <ArrowRight size={12} />
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Próximos passos</h2>
                <Link to="/app/calendario" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
                  Ver agenda <ArrowRight size={14} />
                </Link>
              </div>
              {proximos === null ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
              ) : proximos.pendencias.length === 0 && proximos.agenda.length === 0 ? (
                <p className="flex items-center gap-2 text-sm text-slate-400 dark:text-slate-500">
                  <CalendarDays size={16} /> Nada pendente nem na agenda dos próximos 30 dias.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  {proximos.pendencias.length > 0 && (
                    <ul className="flex flex-col gap-1.5">
                      {proximos.pendencias.map((p, i) => (
                        <li key={`p${i}`} className="group relative">
                          <Link
                            to={p.link}
                            className={`-mx-2 flex items-start gap-2.5 rounded-lg px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-700/40 ${p.chave ? "pr-9" : ""}`}
                          >
                            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${COR_PENDENCIA[p.tipo] ?? "bg-slate-400"}`} />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{p.titulo}</p>
                              <p className="text-xs text-slate-400 dark:text-slate-500">
                                {[p.competencia ? formatCompetenciaLonga(p.competencia) : null, p.valor != null ? formatBRL(p.valor) : null]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </p>
                            </div>
                            <span className="shrink-0 text-xs font-semibold text-primary-600">{p.acao} →</span>
                          </Link>
                          {p.chave && (
                            <button
                              type="button"
                              onClick={() => ignorarPendencia(p.chave!)}
                              title="Ignorar este aviso (atraso consciente)"
                              aria-label={`Ignorar o aviso: ${p.titulo}`}
                              className="absolute right-0 top-1 rounded p-1 text-slate-300 opacity-60 hover:bg-slate-100 hover:text-slate-500 focus-visible:opacity-100 group-hover:opacity-100 dark:text-slate-500 dark:hover:bg-slate-700"
                            >
                              <EyeOff className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </li>
                      ))}
                      {proximos.total_pendencias > proximos.pendencias.length && (
                        <li className="text-xs text-slate-400">+ {proximos.total_pendencias - proximos.pendencias.length} outras pendências</li>
                      )}
                    </ul>
                  )}
                  {proximos.agenda.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Agenda</p>
                      <ul className="flex flex-col gap-2">
                        {proximos.agenda.map((ev, i) => (
                          <li
                            key={`a${i}`}
                            onClick={() => navigate("/app/calendario")}
                            className="-mx-2 flex cursor-pointer items-start gap-2.5 rounded-lg px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-700/40"
                          >
                            <span className="mt-0.5 w-12 shrink-0 text-xs font-semibold text-slate-500">{formatDataCurta(ev.data)}</span>
                            <div className="min-w-0">
                              <p className="truncate text-sm text-slate-700 dark:text-slate-200">{ev.detalhe ?? ev.titulo}</p>
                              {ev.valor != null && <p className="text-xs text-slate-400">{formatBRL(ev.valor)}</p>}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Card>

            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Recebimentos</h2>
                <Link to="/app/financeiro" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
                  Ver detalhes <ArrowRight size={14} />
                </Link>
              </div>
              <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{formatBRL(resumo.recebido_no_mes)}</p>
              <p className="mb-4 text-xs text-slate-400 dark:text-slate-500">recebidos este mês</p>
              {resumo.delta_recebimentos_pct !== null && (
                <p
                  className={`mb-3 flex items-center gap-1 text-xs font-medium ${
                    resumo.delta_recebimentos_pct >= 0 ? "text-success-600" : "text-danger-600"
                  }`}
                >
                  {resumo.delta_recebimentos_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {Math.abs(Math.round(resumo.delta_recebimentos_pct))}% vs. mês anterior
                </p>
              )}
              <MiniBarChart dados={resumo.serie_recebimentos} />
            </Card>

            <Card className="p-5">
              <h2 className="mb-3 text-base font-semibold text-slate-800 dark:text-slate-200">Atalhos rápidos</h2>
              <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-700">
                {[
                  { to: "/app/nfse?nova=1", label: "Nova emissão", icon: FileText },
                  { to: "/app/tomadores/novo", label: "Adicionar tomador", icon: UserPlus },
                  { to: "/app/financeiro?novo=recebimento", label: "Registrar recebimento", icon: Wallet },
                  { to: "/app/financeiro?novo=despesa", label: "Registrar despesa", icon: TrendingDown },
                  { to: "/app/calendario", label: "Ver calendário", icon: CalendarDays },
                ].map(({ to, label, icon: Icon }) => (
                  <Link key={to} to={to} className="flex items-center justify-between py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:text-primary-600">
                    <span className="flex items-center gap-2">
                      <Icon size={16} className="text-slate-400 dark:text-slate-500" />
                      {label}
                    </span>
                    <ArrowRight size={14} className="text-slate-300" />
                  </Link>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
