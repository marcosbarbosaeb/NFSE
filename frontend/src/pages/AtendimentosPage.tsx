import { ArrowRight, BarChart3, BriefcaseBusiness, Building2, CalendarCheck, Check, Gift, ListChecks, Loader2, MailPlus } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { FichaDaEmpresa } from "../components/contador/FichaDaEmpresa"
import { GestaoDaCarteira } from "../components/contador/GestaoDaCarteira"
import { FaixaDaCarteira, FilaDeTarefas, ListaDaCarteira, QuadroDeFechamento, tarefasDe } from "../components/contador/PainelContador"
import { CaixaBusca } from "../components/ui/CaixaBusca"
import { nomeEmpresa } from "../components/TrocaEmpresa"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { PERMISSOES_PADRAO } from "../lib/contador"
import { formatarDocumento } from "../lib/documento"
import type { Atendimentos, ClienteAtendido, ConviteContador, PermissaoContador, PermissaoInfo } from "../lib/types"

// Contador (06/10/2026): as empresas que este login atende. O cliente convida
// pelo e-mail em Empresa › Contador e escolhe o que o contador pode fazer;
// aqui o contador aceita e abre cada empresa (a troca recarrega o painel).

const erroDe = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

const ABAS = [
  { id: "hoje", rotulo: "Hoje", Icone: ListChecks },
  { id: "fechamento", rotulo: "Fechamento do mês", Icone: CalendarCheck },
  { id: "empresas", rotulo: "Empresas", Icone: Building2 },
  // 2026.10.7: os números de cada cliente e o cadastro de cliente novo.
  { id: "gestao", rotulo: "Gestão", Icone: BarChart3 },
] as const
type IdAba = (typeof ABAS)[number]["id"]

export function AtendimentosPage() {
  const { usuario, recarregarUsuario } = useAuth()
  const [dados, setDados] = useState<Atendimentos | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [fazendo, setFazendo] = useState<string | null>(null)
  const [saindo, setSaindo] = useState<ClienteAtendido | null>(null)

  const carregar = useCallback(() => {
    api
      .get<Atendimentos>("/contador/atendimentos")
      .then((d) => {
        setDados(d)
        setErro(null)
      })
      .catch((err) => setErro(erroDe(err)))
  }, [])
  useEffect(carregar, [carregar])

  const catalogo = dados?.permissoes?.length ? dados.permissoes : PERMISSOES_PADRAO

  async function responder(c: ConviteContador, aceitar: boolean) {
    setFazendo(c.id)
    setErro(null)
    try {
      await api.post(`/contador/convites/${c.id}/${aceitar ? "aceitar" : "recusar"}`)
      await recarregarUsuario()
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(null)
    }
  }

  // Painel de pendências (07/10/2026): "o contador poder ter uma aba de gestão
  // com a pendência de cada empresa, sem entrar em cada uma". Quem tem mais
  // o que fazer vem primeiro; o filtro esconde quem está em dia.
  const [soPendentes, setSoPendentes] = useState(false)
  const [busca, setBusca] = useState("")
  const clientes = useMemo(() => {
    const peso = (c: ClienteAtendido) =>
      (c.alertas ?? []).filter((x) => x.nivel === "critico").length * 1000 + (c.alertas ?? []).length * 100 + (c.total_pendencias ?? 0)
    const lista = [...(dados?.clientes ?? [])].sort((a, b) => peso(b) - peso(a))
    const termo = busca.trim().toLowerCase()
    return lista
      .filter((c) => !soPendentes || (c.total_pendencias ?? 0) > 0 || (c.alertas ?? []).length > 0)
      .filter((c) => !termo || `${c.empresa} ${c.nome_fantasia ?? ""} ${c.cnpj}`.toLowerCase().includes(termo) || c.cnpj.includes(termo.replace(/\D/g, "") || "#"))
  }, [dados, soPendentes, busca])
  // 08/10/2026 — painel próprio: a aba e a empresa aberta ficam na URL (dá
  // pra voltar com o botão do navegador e mandar o link).
  const [params, setParams] = useSearchParams()
  const aba = (ABAS.find((a) => a.id === params.get("aba"))?.id ?? "hoje") as IdAba
  const ficha = (dados?.clientes ?? []).find((c) => c.id === params.get("empresa")) ?? null
  const posicao = ficha ? (dados?.clientes ?? []).findIndex((c) => c.id === ficha.id) : -1
  const mudarAba = (id: IdAba) => setParams(id === "hoje" ? {} : { aba: id })
  const verEmpresa = (id: string | null) => {
    setParams(id ? { empresa: id } : aba === "hoje" ? {} : { aba })
    window.scrollTo({ top: 0 })
  }
  const tarefas = useMemo(() => tarefasDe(dados?.clientes ?? []), [dados])
  const urgentes = tarefas.filter((t) => t.peso <= 1).length

  /** Abre a empresa já na tela onde a pendência se resolve. */
  async function abrir(c: ClienteAtendido, destino = "/app") {
    // A pasta do mês o contador vê na ficha da empresa, sem entrar nela.
    if (destino === "/app/pasta") {
      setParams({ empresa: c.id })
      window.setTimeout(() => document.getElementById("pasta")?.scrollIntoView({ behavior: "smooth", block: "start" }), 150)
      return
    }
    setFazendo(c.id)
    setErro(null)
    try {
      await api.post(`/empresas/${c.prestador_id}/ativar`)
      window.location.assign(destino)
    } catch (err) {
      setErro(erroDe(err))
      setFazendo(null)
    }
  }

  async function sair(c: ClienteAtendido) {
    setFazendo(c.id)
    setErro(null)
    try {
      await api.delete(`/contador/atendimentos/${c.id}`)
      // Se estava dentro dela, o painel inteiro volta pra empresa do contador.
      if (c.prestador_id === dados?.ativa) window.location.assign("/app/atendimentos")
      else {
        setSaindo(null)
        verEmpresa(null)
        await recarregarUsuario()
        carregar()
      }
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(null)
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
          <BriefcaseBusiness size={24} className="text-primary-600 dark:text-primary-400" aria-hidden="true" /> Painel do contador
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          As empresas dos seus clientes num lugar só: o que fazer hoje, o fechamento do mês e os números de cada uma — sem precisar entrar em nenhuma.
        </p>
      </header>

      {erro && (
        <p role="alert" className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
          {erro}
        </p>
      )}

      {dados === null && !erro && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {dados && dados.convites.length > 0 && (
        <section className="flex flex-col gap-3" aria-label="Convites esperando resposta">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Convites esperando a sua resposta</h2>
          {dados.convites.map((c) => (
            <Card key={c.id} className="border-primary-300 p-5 dark:border-primary-700">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
                    <MailPlus size={18} className="shrink-0 text-primary-600 dark:text-primary-400" aria-hidden="true" />
                    <span className="truncate">{c.empresa}</span>
                  </p>
                  <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                    CNPJ {formatarDocumento(c.cnpj)}
                    {c.convidado_por && <> · convite de {c.convidado_por}</>}
                  </p>
                  <Permissoes catalogo={catalogo} marcadas={c.permissoes} />
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button type="button" variant="ghost" disabled={fazendo !== null} onClick={() => responder(c, false)}>
                    Recusar
                  </Button>
                  <Button type="button" variant="accent" disabled={fazendo !== null} onClick={() => responder(c, true)}>
                    {fazendo === c.id ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Aceitar
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </section>
      )}

      {dados && dados.clientes.length > 0 && (
        <>
          {/* Trocar de empresa sem sair do painel. */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1 basis-64 sm:max-w-sm" data-tour="contador-busca">
              <CaixaBusca
                valor={ficha?.id ?? ""}
                opcoes={dados.clientes.map((c) => ({ id: c.id, rotulo: `${nomeEmpresa({ nome_fantasia: c.nome_fantasia, razao_social: c.empresa })} · ${formatarDocumento(c.cnpj)}` }))}
                onEscolher={(id) => verEmpresa(id)}
                placeholder="Ver uma empresa (nome ou CNPJ)..."
                ariaLabel="Escolher a empresa pra ver no painel"
              />
            </div>
            {ficha && (
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {posicao + 1} de {dados.clientes.length}
                <button type="button" className="ml-2 font-medium text-primary-700 hover:underline dark:text-primary-300" onClick={() => verEmpresa(dados.clientes[(posicao + 1) % dados.clientes.length].id)}>
                  próxima →
                </button>
              </span>
            )}
          </div>

          {ficha ? (
            <FichaDaEmpresa cliente={ficha} ativa={dados.ativa} fazendo={fazendo !== null} aoVoltar={() => verEmpresa(null)} aoAbrir={(c, link) => abrir(c, link)} aoSair={setSaindo} />
          ) : (
            <>
              {dados.resumo && <FaixaDaCarteira resumo={dados.resumo} />}

              <div role="tablist" aria-label="Partes do painel" data-tour="contador-abas" className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-700">
                {ABAS.map((a) => {
                  const n = a.id === "hoje" ? tarefas.length : a.id === "empresas" ? dados.clientes.length : null
                  return (
                    <button
                      key={a.id}
                      type="button"
                      role="tab"
                      aria-selected={aba === a.id}
                      onClick={() => mudarAba(a.id)}
                      className={`-mb-px inline-flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium ${
                        aba === a.id
                          ? "border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300"
                          : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
                      }`}
                    >
                      <a.Icone size={16} aria-hidden /> {a.rotulo}
                      {n !== null && (
                        <span className={`rounded-full px-1.5 text-xs tabular-nums ${a.id === "hoje" && urgentes > 0 ? "bg-danger-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"}`}>
                          {n}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>

              {aba === "hoje" && (
                <Card className="p-5" data-painel="hoje">
                  <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                      {tarefas.length === 0 ? "Tudo em dia" : urgentes > 0 ? `${urgentes} ${urgentes === 1 ? "coisa urgente" : "coisas urgentes"} e mais ${tarefas.length - urgentes} pra fazer` : `${tarefas.length} ${tarefas.length === 1 ? "coisa" : "coisas"} pra fazer`}
                    </h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Das suas empresas, do mais urgente pro menos. “Resolver” abre a empresa já na tela certa.</p>
                  </div>
                  <FilaDeTarefas tarefas={tarefas} desligado={fazendo !== null} aoResolver={(c, link) => abrir(c, link)} aoVerEmpresa={(c) => verEmpresa(c.id)} />
                </Card>
              )}

              {aba === "gestao" && (
                <GestaoDaCarteira clientes={dados.clientes} resumo={dados.resumo} aoAtualizar={carregar} aoVerEmpresa={(c) => verEmpresa(c.id)} />
              )}

              {aba === "fechamento" && <QuadroDeFechamento clientes={dados.clientes} desligado={fazendo !== null} aoAbrir={(c, link) => abrir(c, link)} aoVerEmpresa={(c) => verEmpresa(c.id)} />}

              {aba === "empresas" && (
                <section className="flex flex-col gap-3" aria-label="Empresas atendidas">
                  <div className="flex flex-wrap items-center gap-3">
                    {dados.clientes.length > 3 && (
                      <input
                        type="search"
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                        placeholder="Filtrar por nome ou CNPJ"
                        aria-label="Filtrar por nome ou CNPJ"
                        className="w-56 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                      />
                    )}
                    {dados.clientes.length > 1 && (
                      <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                        <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500" checked={soPendentes} onChange={(e) => setSoPendentes(e.target.checked)} />
                        Só com algo pra fazer
                      </label>
                    )}
                  </div>
                  {clientes.length === 0 ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">Nenhuma empresa com esse filtro.</p>
                  ) : (
                    <ListaDaCarteira clientes={clientes} ativa={dados.ativa} aoVerEmpresa={(c) => verEmpresa(c.id)} />
                  )}
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    Faturamento = soma das notas autorizadas que passaram pela Ana (geradas aqui ou importadas do Emissor Nacional). Receita que não virou
                    NFS-e por aqui não entra: é um indicador, não o RBT12 oficial. Limites: MEI R$ 81 mil e Simples R$ 4,8 milhões por ano.
                  </p>
                </section>
              )}
            </>
          )}
        </>
      )}

      {dados?.bonificacao && (
        <Card className="p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
                <Gift size={18} className="shrink-0 text-accent-500" aria-hidden="true" /> Sua bonificação: {dados.bonificacao.pct}% de cada mensalidade
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                Você recebe {dados.bonificacao.pct}% do que cada cliente que você atende paga de assinatura, todo mês, enquanto atender a
                empresa. {dados.bonificacao.clientes_pagando === 0
                  ? "Ainda nenhum cliente seu está pagando."
                  : `${dados.bonificacao.clientes_pagando} de ${dados.bonificacao.clientes} ${dados.bonificacao.clientes === 1 ? "cliente está" : "clientes estão"} pagando.`}
                {dados.bonificacao.a_receber > 0 && (
                  <>
                    {" "}
                    <strong>A receber: {dados.bonificacao.a_receber.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}.</strong>
                  </>
                )}
              </p>
            </div>
            <Link
              to={dados.bonificacao.painel}
              target="_blank"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              Ver extrato <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </Card>
      )}

      {dados && dados.clientes.length === 0 && dados.convites.length === 0 && (
        <Card className="p-6">
          <p className="text-base font-semibold text-slate-900 dark:text-slate-100">Você ainda não atende nenhuma empresa por aqui.</p>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-600 dark:text-slate-300">
            <li>
              Peça ao seu cliente pra abrir <strong>Empresa › Contador</strong> na conta dele e convidar o seu e-mail:{" "}
              <strong className="break-all">{usuario?.email}</strong>.
            </li>
            <li>Ele marca o que você pode fazer: só ver, gerar notas, enviar, cuidar dos tomadores, do financeiro...</li>
            <li>O convite aparece aqui. Você aceita e a empresa dele entra na sua lista — e no seletor de empresas, lá no topo do menu.</li>
          </ol>
          <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">Ou cadastre você mesmo a empresa do cliente: eu mando o convite para o dono criar o acesso dele.</p>
        </Card>
      )}
      {dados && dados.clientes.length === 0 && usuario?.so_contador && (
        <GestaoDaCarteira clientes={[]} resumo={dados.resumo} aoAtualizar={carregar} aoVerEmpresa={() => undefined} />
      )}

      {saindo && (
        <Modal titulo="Deixar de atender esta empresa?" onClose={() => setSaindo(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Você perde o acesso a <strong>{saindo.empresa}</strong> na hora. Nada da empresa é apagado. Pra voltar, o cliente precisa te
              convidar de novo.
            </p>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="ghost" onClick={() => setSaindo(null)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" disabled={fazendo !== null} onClick={() => sair(saindo)}>
                Deixar de atender
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Permissoes({ catalogo, marcadas }: { catalogo: PermissaoInfo[]; marcadas: PermissaoContador[] }) {
  return (
    <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="O que você pode fazer">
      <li>
        <Badge variant="neutral">Ver notas e financeiro</Badge>
      </li>
      {catalogo
        .filter((p) => marcadas.includes(p.id))
        .map((p) => (
          <li key={p.id} title={p.descricao}>
            <Badge variant="success">{p.nome}</Badge>
          </li>
        ))}
    </ul>
  )
}
