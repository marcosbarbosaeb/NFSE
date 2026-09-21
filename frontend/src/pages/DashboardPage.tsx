import {
  AlertTriangle,
  ArrowRight,
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
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { MiniBarChart } from "../components/ui/MiniBarChart"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../lib/format"
import type { DashboardResumo } from "../lib/types"

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

function badgePagamento(recebido: boolean) {
  return recebido ? <Badge variant="success">Recebida</Badge> : <Badge variant="warning">Pendente</Badge>
}

export function DashboardPage() {
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [resumo, setResumo] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

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
  }, [competencia])

  const pctEmitidas = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.emitidas / resumo.total_vinculos) * 100) : 0
  const pctAguardando = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.aguardando / resumo.total_vinculos) * 100) : 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Bom dia! 👋</h1>
          <p className="text-sm text-slate-500">Aqui está o resumo das suas notas deste mês.</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm">
          <button
            type="button"
            onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))}
            className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100"
          >
            ‹
          </button>
          <span className="min-w-[9rem] text-center font-medium text-slate-700">{formatCompetenciaLonga(competencia)}</span>
          <button
            type="button"
            onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
            className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100"
          >
            ›
          </button>
        </div>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {carregando && !resumo && <p className="text-sm text-slate-400">Carregando...</p>}

      {resumo && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={<FileText size={18} />}
              iconClassName="bg-primary-50 text-primary-600"
              label="Notas deste mês"
              value={resumo.total_vinculos}
              sublabel="fornecedores ativos"
            />
            <StatCard
              icon={<CheckCircle2 size={18} />}
              iconClassName="bg-success-50 text-success-600"
              label="Emitidas"
              value={resumo.emitidas}
              sublabel={`${pctEmitidas}% do total`}
            />
            <StatCard
              icon={<Clock size={18} />}
              iconClassName="bg-warning-50 text-warning-600"
              label="Aguardando emissão"
              value={resumo.aguardando}
              sublabel={`${pctAguardando}% do total`}
            />
            <StatCard
              icon={<Wallet size={18} />}
              iconClassName="bg-accent-50 text-accent-600"
              label="A receber"
              value={formatBRL(resumo.a_receber)}
              sublabel={`${resumo.pagamentos_pendentes} pagamento(s) pendente(s)`}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="p-5 xl:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800">Emissões deste mês</h2>
                <div className="flex items-center gap-3">
                  <Link to="/nfse" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
                    Ver todas <ArrowRight size={14} />
                  </Link>
                  <Link to="/nfse">
                    <Button variant="accent" className="text-sm">
                      <Plus size={15} /> Nova emissão
                    </Button>
                  </Link>
                </div>
              </div>

              {resumo.emissoes.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400">Nenhuma nota emitida nesta competência ainda.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                        <th className="py-2 font-medium">Tomador</th>
                        <th className="py-2 font-medium">Competência</th>
                        <th className="py-2 font-medium">Valor</th>
                        <th className="py-2 font-medium">NFS-e</th>
                        <th className="py-2 font-medium">Envio</th>
                        <th className="py-2 font-medium">Pagamento</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resumo.emissoes.map((linha) => (
                        <tr key={linha.emissao_id} className="border-b border-slate-50 last:border-0">
                          <td className="py-3">
                            <p className="font-medium text-slate-800">{linha.apelido}</p>
                            <p className="text-xs text-slate-400">{linha.tomador_razao_social}</p>
                          </td>
                          <td className="py-3 text-slate-600">{linha.competencia}</td>
                          <td className="py-3 text-slate-600">{formatBRL(linha.valor)}</td>
                          <td className="py-3">{badgeEstadoNfse(linha.estado, linha.estado_label)}</td>
                          <td className="py-3">{badgeEnvio(linha.envio_status)}</td>
                          <td className="py-3">{badgePagamento(linha.pagamento_recebido)}</td>
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
                <h2 className="text-base font-semibold text-slate-800">Precisa da sua atenção</h2>
                {resumo.atencao.length > 0 && <Badge variant="warning">{resumo.atencao.length}</Badge>}
              </div>
              {resumo.atencao.length === 0 ? (
                <p className="text-sm text-slate-400">Tudo em dia por aqui.</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {resumo.atencao.map((item, i) => (
                    <li key={i} className="rounded-lg bg-warning-50 px-3 py-2">
                      <p className="text-sm font-medium text-slate-800">{item.titulo}</p>
                      <p className="text-xs text-slate-500">{item.mensagem}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800">Recebimentos</h2>
                <Link to="/recebimentos" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
                  Ver detalhes <ArrowRight size={14} />
                </Link>
              </div>
              <p className="text-2xl font-semibold text-slate-900">{formatBRL(resumo.recebido_no_mes)}</p>
              <p className="mb-4 text-xs text-slate-400">recebidos este mês</p>
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
              <h2 className="mb-3 text-base font-semibold text-slate-800">Atalhos rápidos</h2>
              <div className="flex flex-col divide-y divide-slate-100">
                {[
                  { to: "/nfse", label: "Nova emissão", icon: FileText },
                  { to: "/tomadores", label: "Adicionar tomador", icon: UserPlus },
                  { to: "/recebimentos", label: "Registrar recebimento", icon: Wallet },
                  { to: "/despesas", label: "Registrar despesa", icon: TrendingDown },
                ].map(({ to, label, icon: Icon }) => (
                  <Link key={to} to={to} className="flex items-center justify-between py-2.5 text-sm text-slate-700 hover:text-primary-600">
                    <span className="flex items-center gap-2">
                      <Icon size={16} className="text-slate-400" />
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
