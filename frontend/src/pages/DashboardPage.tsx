import {
  ArrowLeftRight,
  ArrowRight,
  LayoutDashboard,
  Wallet,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileText,
  Plus,
  StickyNote,
  TrendingDown,
  TrendingUp,
  UserPlus,

} from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { type NotaParaAcoes, SeloAssinatura, SeloPrefeitura, SeloTomador } from "../components/AcoesNota"
import { PrimeirosPassos } from "../components/PrimeirosPassos"
import { AnotacaoCard, EscolherFormatoAnotacao, anotacaoApareceEm, useAnotacoes } from "../components/financeiro/Anotacoes"
import { ContasDoMesPainel } from "../components/financeiro/ContasDoMesPainel"
import { GraficoEntrouSaiu, GraficoFaturamentoMes, GraficoTomadores } from "../components/graficos/Paineis"
import { PainelCards, type SecaoCard } from "../components/PainelCards"
import { ProximosPassos } from "../components/ProximosPassos"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { StatCard } from "../components/ui/StatCard"
import { AlturaLimitada, useVerMais } from "../components/ui/VerMais"
import { ApiError, api, formatarErro } from "../lib/api"
import { competenciaAtual, deslocarCompetencia, formatBRL, formatCompetenciaLonga } from "../lib/format"
import { useModulos } from "../lib/modulos"
import type { DashboardResumo, EmissaoResumoLinha, Proximos, ResumoFinanceiro } from "../lib/types"


function badgeEstadoNfse(estado: string, label: string) {
  if (["confirmado", "assinado", "submetido", "montado"].includes(estado)) return <Badge variant="success">{label}</Badge>
  if (estado === "erro") return <Badge variant="danger">{label}</Badge>
  return <Badge variant="neutral">{label}</Badge>
}

function badgeEnvio(status: string | null, linha?: EmissaoResumoLinha) {
  // Linha que junta as notas dos vendedores: mostra a conta.
  if (linha?.vendedores && linha.a_enviar) {
    const n = linha.enviadas ?? 0
    if (status === "enviado") return <Badge variant="success">Enviadas ({n})</Badge>
    if (status === "parcial") return <Badge variant="warning">{n} de {linha.a_enviar} enviadas</Badge>
  }
  if (status === "enviado") return <Badge variant="success">Enviada</Badge>
  if (status === "falha") return <Badge variant="danger">Falha</Badge>
  if (status === "pendente") return <Badge variant="warning">Pendente</Badge>
  return <Badge variant="neutral">Não enviado</Badge>
}


/** Linha que junta as notas dos vendedores: "Assinadas (464)" quando todas
 * estão, senão "120 de 464 assinadas". */
function badgeDoGrupo(feitas: number, total: number, todas: string, parte: string) {
  if (total > 0 && feitas >= total) return <Badge variant="success">{todas} ({total})</Badge>
  if (feitas === 0) return <Badge variant="neutral">Nenhuma {parte.replace(/s$/, "")}</Badge>
  return <Badge variant="warning">{feitas} de {total} {parte}</Badge>
}

function notaDaLinha(l: EmissaoResumoLinha): NotaParaAcoes {
  return { id: l.emissao_id, estado: l.estado, envio_status: l.envio_status, tem_pdf: l.tem_pdf, tem_email: l.tem_email, homologacao: l.homologacao, envio_forma: l.envio_forma, vinculo_id: l.vinculo_id, erro_detalhe: l.erro_detalhe, erro_corrigivel: l.erro_corrigivel }
}

/** Visão geral (05/10/2026): é da empresa, não de um módulo. Junta os
 * cards dos módulos que estão ligados, e a pessoa escolhe quais aparecem e
 * em que ordem ("Editar disposição") — fica salvo na conta dela. */
export function DashboardPage() {
  const modulos = useModulos()
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [resumo, setResumo] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(modulos.emissor)
  const [editando, setEditando] = useState(false)

  const [proximos, setProximos] = useState<Proximos | null>(null)
  // Financeiro: resultado do ano da competência escolhida + extrato sem classificar.
  const [financeiro, setFinanceiro] = useState<ResumoFinanceiro | null>(null)
  const [pendentesExtrato, setPendentesExtrato] = useState(0)
  // Nenhum card cresce sem limite (05/10/2026): acima disso, "ver mais".
  const emissoesDoMes = useVerMais(resumo?.emissoes ?? [], 6)
  const atencao = useVerMais(resumo?.atencao ?? [], 4)

  // "Ignorar este aviso" — atraso consciente (ex.: nota que sai depois do pagamento).
  // Some da tela na hora (inclusive de dentro de um grupo "Gerar 8 notas") e
  // recarrega: o grupo muda de tamanho e o "Precisa da sua atenção" também
  // deixa de cobrar essa nota.
  function ignorarPendencia(chave: string) {
    setProximos((p) => {
      if (!p) return p
      const pendencias = p.pendencias
        .filter((x) => x.chave !== chave)
        .map((x) => (x.itens ? { ...x, itens: x.itens.filter((i) => i.chave !== chave) } : x))
        .filter((x) => !x.itens || x.itens.length > 0)
      return { ...p, pendencias, total_pendencias: Math.max(0, p.total_pendencias - (p.pendencias.length - pendencias.length)) }
    })
    api
      .post("/painel/pendencias/ignorar", { chave })
      .catch(() => undefined)
      .finally(() => setRecarga((n) => n + 1))
  }
  const [recarga, setRecarga] = useState(0)
  const navigate = useNavigate()

  // "Na visão geral, falta a opção de criar anotação" (05/10/2026): as mesmas
  // anotações do Financeiro, só as que a pessoa quer ver aqui. A nota criada
  // aqui nasce aqui. Empresa sem o Financeiro vê todas (é a única tela delas).
  const { anotacoes: todasAnotacoes, erro: erroAnotacao, criar: criarAnotacao, atualizar: atualizarAnotacao, apagar: apagarAnotacao } = useAnotacoes(true, "visao_geral")
  const anotacoes = todasAnotacoes.filter((n) => anotacaoApareceEm(n, "visao_geral", modulos.financeiro))
  const [anotacaoNova, setAnotacaoNova] = useState<string | null>(null)
  const [escolhendoFormatoAnotacao, setEscolhendoFormatoAnotacao] = useState(false)

  useEffect(() => {
    if (!modulos.emissor) return
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
  }, [competencia, recarga, modulos.emissor])

  // "Próximos eventos não está aparecendo, pode aparecer além de somente
  // eventos" (28/09/2026): o que tem pra fazer agora + agenda de 30 dias.
  useEffect(() => {
    if (!modulos.emissor) return
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
  }, [recarga, modulos.emissor])

  const anoDaCompetencia = competencia.slice(0, 4)
  useEffect(() => {
    if (!modulos.financeiro) return
    let cancelado = false
    api
      .get<ResumoFinanceiro>(`/financeiro/resumo?ano=${anoDaCompetencia}`)
      .then((dados) => {
        if (!cancelado) setFinanceiro(dados)
      })
      .catch(() => undefined)
    api
      .get<{ pendentes: number }>("/conciliacao/contagem")
      .then((r) => {
        if (!cancelado) setPendentesExtrato(r.pendentes)
      })
      .catch(() => undefined)
    return () => {
      cancelado = true
    }
  }, [anoDaCompetencia, recarga, modulos.financeiro])

  const pctEmitidas = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.emitidas / resumo.total_vinculos) * 100) : 0
  const pctAguardando = resumo && resumo.total_vinculos > 0 ? Math.round((resumo.aguardando / resumo.total_vinculos) * 100) : 0
  const mesIndice = Number(competencia.slice(5, 7)) - 1
  const fin = financeiro?.ano === anoDaCompetencia ? financeiro : null
  const doisModulos = modulos.emissor && modulos.financeiro

  const atalhos = [
    ...(modulos.emissor
      ? [
          { to: "/app/nfse?nova=1", label: "Nova emissão", icon: FileText },
          { to: "/app/tomadores/novo", label: "Adicionar tomador", icon: UserPlus },
          { to: "/app/calendario", label: "Ver calendário", icon: CalendarDays },
        ]
      : []),
    ...(modulos.financeiro
      ? [
          { to: "/app/financeiro?novo=recebimento", label: "Registrar recebimento", icon: Wallet },
          { to: "/app/financeiro/conciliacao", label: "Conciliar o extrato", icon: ArrowLeftRight },
        ]
      : []),
  ]

  const secoes: SecaoCard[] = [
    ...(modulos.emissor && resumo
      ? ([
          {
            id: "notas_resumo",
            titulo: "Notas do mês",
            grupo: "Notas",
            conteudo: (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
            <Link to="/app/nfse" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
              <StatCard
                icon={<TrendingUp size={18} />}
                iconClassName="bg-accent-50 text-accent-600"
                label="Faturado no mês"
                value={formatBRL(resumo.faturado_no_mes)}
                sublabel="valor das notas do mês"
              />
            </Link>
          </div>
            ),
          },
          {
            id: "notas_emissoes",
            titulo: "Emissões deste mês",
            grupo: "Notas",
            resumo: `${resumo.emissoes.length} ${resumo.emissoes.length === 1 ? "nota" : "notas"}`,
            conteudo: (
            <Card className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <span />
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
                      </tr>
                    </thead>
                    <tbody>
                      {emissoesDoMes.visiveis.map((linha) => (
                        <tr
                          key={linha.emissao_id}
                          onClick={() =>
                            navigate(
                              linha.vendedores
                                ? "/app/nfse/lote"
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
                          {linha.vendedores && linha.total_grupo != null ? (
                            <>
                              <td className="py-3">{badgeDoGrupo(linha.assinadas ?? 0, linha.total_grupo, "Assinadas", "assinadas")}</td>
                              <td className="py-3">
                                <span className="inline-flex flex-col items-start gap-1">
                                  {badgeDoGrupo(linha.autorizadas ?? 0, linha.total_grupo, "Autorizadas", "autorizadas")}
                                  {(linha.recusadas ?? 0) > 0 && <Badge variant="danger">{linha.recusadas} recusada{linha.recusadas === 1 ? "" : "s"}</Badge>}
                                </span>
                              </td>
                              <td className="py-3">{badgeEnvio(linha.envio_status, linha)}</td>
                            </>
                          ) : (linha.quantidade ?? 1) > 1 ? (
                            <>
                              <td className="py-3" colSpan={2}>
                                {badgeEstadoNfse(linha.estado, linha.estado_label)}
                              </td>
                              <td className="py-3">{badgeEnvio(linha.envio_status, linha)}</td>
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {emissoesDoMes.botao}
                </div>
              )}
            </Card>
            ),
          },
          {
            id: "notas_atencao",
            titulo: "Precisa da sua atenção",
            grupo: "Notas",
            meia: true,
            resumo: resumo.atencao.length > 0 ? <Badge variant="warning">{resumo.atencao.length}</Badge> : "tudo em dia",
            conteudo: (
            <Card className="p-5">
              {resumo.atencao.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">Tudo em dia por aqui.</p>
              ) : (
                <>
                <ul className="flex flex-col gap-3">
                  {atencao.visiveis.map((item, i) => (
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
                {atencao.botao}
                </>
              )}
            </Card>
            ),
          },
          {
            id: "notas_proximos",
            titulo: "Próximos passos",
            grupo: "Notas",
            meia: true,
            conteudo: <ProximosPassos proximos={proximos} onIgnorar={ignorarPendencia} />,
          },
          // Gráficos (05/10/2026). O "Faturamento" já existia com 6 barrinhas:
          // continua o mesmo card (mesmo id, fica onde a pessoa deixou), agora
          // com 12 meses, a média e o mês atual em destaque.
          {
            id: "notas_faturamento",
            titulo: "Faturamento por mês",
            grupo: "Notas",
            meia: true,
            resumo: formatBRL(resumo.faturado_no_mes),
            conteudo: <GraficoFaturamentoMes competencia={competencia} versao={recarga} resumo={resumo} />,
          },
          {
            id: "notas_tomadores",
            titulo: "Quem mais te paga",
            grupo: "Notas",
            meia: true,
            conteudo: <GraficoTomadores competencia={competencia} versao={recarga} />,
          },
        ] satisfies SecaoCard[])
      : []),
    ...(modulos.financeiro
      ? ([
          {
            id: "fin_mes",
            titulo: "Dinheiro do mês",
            grupo: "Financeiro",
            resumo: fin ? `lucro ${formatBRL(fin.lucro[mesIndice] ?? 0)}` : undefined,
            conteudo: (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Link to="/app/financeiro" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
                  <StatCard
                    icon={<TrendingUp size={18} />}
                    iconClassName="bg-success-50 text-success-600"
                    label="Recebido no mês"
                    value={fin ? formatBRL(fin.recebido[mesIndice] ?? 0) : "…"}
                    sublabel={formatCompetenciaLonga(competencia)}
                  />
                </Link>
                <Link to="/app/financeiro" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
                  <StatCard
                    icon={<TrendingDown size={18} />}
                    iconClassName="bg-danger-50 text-danger-600"
                    label="Despesas do mês"
                    value={fin ? formatBRL(fin.despesas[mesIndice] ?? 0) : "…"}
                    sublabel="sem as retiradas"
                  />
                </Link>
                <Link to="/app/financeiro" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
                  <StatCard
                    icon={<Wallet size={18} />}
                    iconClassName="bg-primary-50 text-primary-600"
                    label="Lucro do mês"
                    value={fin ? formatBRL(fin.lucro[mesIndice] ?? 0) : "…"}
                    sublabel="recebido − despesas"
                  />
                </Link>
                {modulos.emissor ? (
                  <Link to="/app/financeiro#a-receber" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
                    <StatCard
                      icon={<Clock size={18} />}
                      iconClassName="bg-warning-50 text-warning-600"
                      label="A receber"
                      value={fin ? formatBRL(fin.totais.a_receber) : "…"}
                      sublabel="notas ainda não pagas"
                    />
                  </Link>
                ) : (
                  <Link to="/app/financeiro" className="rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
                    <StatCard
                      icon={<Clock size={18} />}
                      iconClassName="bg-warning-50 text-warning-600"
                      label="Saldo a distribuir"
                      value={fin ? formatBRL(fin.saldo_a_distribuir[mesIndice] ?? 0) : "…"}
                      sublabel="acumulado no ano"
                    />
                  </Link>
                )}
              </div>
            ),
          },
          {
            id: "fin_grafico",
            titulo: "Entrou × saiu por mês",
            grupo: "Financeiro",
            conteudo: (
              <GraficoEntrouSaiu
                resumo={fin}
                mes={competencia.slice(5, 7)}
                onSelecionarMes={(m) => m && setCompetencia(`${anoDaCompetencia}-${m}`)}
                rotuloEixo={modulos.emissor ? "pelo mês da nota" : "pelo mês de referência"}
                sempreUmMes
              />
            ),
          },
          {
            id: "fin_conciliacao",
            titulo: "Extrato sem classificar",
            grupo: "Financeiro",
            oculto: pendentesExtrato === 0,
            resumo: <Badge variant="warning">{pendentesExtrato}</Badge>,
            conteudo: (
              <Card className="flex flex-wrap items-center justify-between gap-3 p-5 text-sm text-slate-600 dark:text-slate-300">
                <p>
                  <strong>{pendentesExtrato}</strong>{" "}
                  {pendentesExtrato === 1 ? "lançamento do extrato está" : "lançamentos do extrato estão"} esperando você dizer de quem é
                  (ou de que conta é).
                </p>
                <Link to="/app/financeiro/conciliacao" className="inline-flex items-center gap-1 font-semibold text-primary-600 hover:text-primary-700">
                  Abrir a Conciliação <ArrowRight size={14} />
                </Link>
              </Card>
            ),
          },
          {
            id: "fin_contas",
            titulo: "Contas do mês",
            grupo: "Financeiro",
            meia: true,
            conteudo: (
              <AlturaLimitada altura={360}>
              <ContasDoMesPainel
                parte="contas"
                competencia={competencia}
                onCompetencia={setCompetencia}
                versao={recarga}
                onMudou={() => setRecarga((n) => n + 1)}
                semTitulo
              />
              </AlturaLimitada>
            ),
          },
          {
            id: "fin_rotina",
            titulo: "Rotina de fechamento",
            grupo: "Financeiro",
            meia: true,
            conteudo: (
              <AlturaLimitada altura={360}>
              <ContasDoMesPainel
                parte="rotina"
                competencia={competencia}
                onCompetencia={setCompetencia}
                versao={recarga}
                onMudou={() => undefined}
                semTitulo
              />
              </AlturaLimitada>
            ),
          },
        ] satisfies SecaoCard[])
      : []),
    // Anotações: uma por card, como no Financeiro.
    ...anotacoes.map(
      (nota): SecaoCard => ({
        id: `nota:${nota.id}`,
        ancora: `nota-${nota.id}`,
        titulo: nota.titulo,
        grupo: "anotação",
        meia: true,
        conteudo: (
          <AlturaLimitada key={nota.id} altura={340}>
          <AnotacaoCard
            nota={nota}
            nova={nota.id === anotacaoNova}
            tela="visao_geral"
            podeTrocarTela={modulos.financeiro}
            onMudou={(m) => atualizarAnotacao(nota.id, m)}
            onApagar={() => apagarAnotacao(nota.id)}
          />
          </AlturaLimitada>
        ),
      }),
    ),
    {
      id: "atalhos",
      titulo: "Atalhos rápidos",
      meia: true,
      oculto: atalhos.length === 0,
      conteudo: (
        <Card className="p-5">
          <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-700">
            {atalhos.map(({ to, label, icon: Icon }) => (
              <Link key={to} to={to} className="flex items-center justify-between py-2.5 text-sm text-slate-700 hover:text-primary-600 dark:text-slate-300">
                <span className="flex items-center gap-2">
                  <Icon size={16} className="text-slate-400 dark:text-slate-500" />
                  {label}
                </span>
                <ArrowRight size={14} className="text-slate-300" />
              </Link>
            ))}
          </div>
        </Card>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Visão geral</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {doisModulos ? "Suas notas e o seu dinheiro" : modulos.financeiro ? "O seu dinheiro" : "Suas notas"} em{" "}
            {formatCompetenciaLonga(competencia).toLowerCase()}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => setEditando((e) => !e)} aria-pressed={editando} data-tour="visao-disposicao">
            <LayoutDashboard size={16} /> {editando ? "Concluir" : "Editar disposição"}
          </Button>
          <Button
            variant="ghost"
            title="Crie uma anotação pra deixar registrado o que quiser (um lembrete, uma lista, um controle)"
            onClick={() => setEscolhendoFormatoAnotacao(true)}
          >
            <StickyNote size={16} /> Nova anotação
          </Button>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800">
            <button
              type="button"
              aria-label="Mês anterior"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))}
              className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              ‹
            </button>
            <span className="min-w-[9rem] text-center font-medium text-slate-700 dark:text-slate-300">{formatCompetenciaLonga(competencia)}</span>
            <button
              type="button"
              aria-label="Próximo mês"
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
              className="rounded px-2 py-0.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              ›
            </button>
          </div>
        </div>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {carregando && !resumo && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}
      {erroAnotacao && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroAnotacao}</p>}

      {/* Empresa ainda sem tomador nem nota: começa trazendo do Emissor Nacional. */}
      {/* Conta nova: certificado, dados da empresa e tomadores — nessa ordem. */}
      {modulos.emissor && <PrimeirosPassos />}

      <PainelCards tela="visao_geral" secoes={secoes} editando={editando} permitirOcultar onConcluir={() => setEditando(false)} />

      {escolhendoFormatoAnotacao && (
        <EscolherFormatoAnotacao
          onClose={() => setEscolhendoFormatoAnotacao(false)}
          onEscolher={async (formato) => {
            setEscolhendoFormatoAnotacao(false)
            const nova = await criarAnotacao("Nova anotação", formato)
            if (!nova) return
            setAnotacaoNova(nova.id)
            // Espera o card existir na tela e leva a pessoa até ele.
            window.setTimeout(() => document.getElementById(`nota-${nova.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 150)
          }}
        />
      )}
    </div>
  )
}
