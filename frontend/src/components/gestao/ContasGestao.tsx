import { ArrowDown, ArrowUp, Ban, ChevronDown, Download, MessageCircle, Search, Trash2, Unlock } from "lucide-react"
import { Fragment, type ReactNode, useMemo, useState } from "react"
import { formatarDocumento, soDigitos } from "../../lib/documento"
import {
  ASSINATURAS,
  SEM_ASSINATURA,
  ativa30,
  baixarCsv,
  dia,
  diaHora,
  erroDe,
  diasDoTeste,
  haDias,
  nomeDaConta,
  nomeDoModulo,
  nomeDoPlano,
  numero,
  plural,
  semAcesso,
  semCertificado,
  situacaoAssinatura,
} from "../../lib/gestao"
import { api } from "../../lib/api"
import { excluirComConfirmacao } from "../../lib/excluir"
import type { ContaGestao, PainelGestao } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"
import { Modal } from "../ui/Modal"

// Gestão › Contas (06/10/2026): quem tem conta, quem está ativo e quanto usa.
// Só números de uso — o conteúdo das notas e do financeiro não chega aqui.

type Filtro = "todas" | "ativas" | "sem-acesso" | "nao-confirmou" | "sem-certificado" | "teste" | "sem-assinatura" | "liberadas" | "bloqueadas" | "contadores" | "pediram" | "fora"
const FILTROS: { id: Filtro; rotulo: string; vale: (c: ContaGestao) => boolean }[] = [
  { id: "todas", rotulo: "Todas", vale: () => true },
  { id: "ativas", rotulo: "Ativas 30 dias", vale: ativa30 },
  { id: "sem-acesso", rotulo: "Sem acesso", vale: semAcesso },
  { id: "nao-confirmou", rotulo: "E-mail não confirmado", vale: (c) => !c.email_confirmado },
  { id: "sem-certificado", rotulo: "Sem certificado", vale: semCertificado },
  { id: "teste", rotulo: "Contas de teste", vale: (c) => c.modo_teste },
  // Quem o bloqueio trava (teste vencido, cancelada) e quem você liberou na mão.
  { id: "sem-assinatura", rotulo: "Aguardando sua autorização", vale: (c) => !c.demo && c.acesso?.liberado === false && c.acesso?.motivo !== "bloqueada" },
  { id: "pediram", rotulo: "Pediram liberação", vale: (c) => Boolean(c.liberacao_pedida_em) },
  { id: "contadores", rotulo: "Contas de contador", vale: (c) => c.so_contador === true },
  // 2026.10.7: contas que já existiam em cidade ou regime que a Ana não atende (continuam funcionando)
  { id: "fora", rotulo: "Fora do atendimento", vale: (c) => Boolean(c.fora_do_atendimento) },
  { id: "liberadas", rotulo: "Liberadas por você", vale: (c) => c.acesso?.motivo === "liberacao" },
  { id: "bloqueadas", rotulo: "Bloqueadas por você", vale: (c) => c.acesso?.motivo === "bloqueada" },
]

type Campo = "criada_em" | "ultimo_acesso" | "notas" | "emails"
const ORDENS: { id: Campo; rotulo: string }[] = [
  { id: "criada_em", rotulo: "Data de criação" },
  { id: "ultimo_acesso", rotulo: "Último acesso" },
  { id: "notas", rotulo: "Notas no mês" },
  { id: "emails", rotulo: "E-mails no mês" },
]

const notasDoMes = (c: ContaGestao) => c.notas_mes + c.notas_lote_mes

function valorDe(c: ContaGestao, campo: Campo): number | null {
  if (campo === "notas") return notasDoMes(c)
  if (campo === "emails") return c.emails_mes
  const iso = campo === "criada_em" ? c.criada_em : c.ultimo_acesso
  const t = iso ? new Date(iso).getTime() : NaN
  return Number.isNaN(t) ? null : t
}

const sem = (texto: string) =>
  texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()

const POR_VEZ = 25
const classeTh = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const classeTd = "px-3 py-3 align-top text-slate-700 dark:text-slate-200"
const classeCampo =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function ContasGestao({ painel, aoMudar }: { painel: PainelGestao; aoMudar?: () => void }) {
  const [busca, setBusca] = useState("")
  const [filtro, setFiltro] = useState<Filtro>("todas")
  const [assinatura, setAssinatura] = useState("")
  const [comSimulacoes, setComSimulacoes] = useState(false)
  const [ordem, setOrdem] = useState<{ campo: Campo; desc: boolean }>({ campo: "criada_em", desc: true })
  const [limite, setLimite] = useState(POR_VEZ)
  const [abertas, setAbertas] = useState<Set<string>>(() => new Set())

  const simulacoes = painel.resumo.contas_simulacao
  const base = useMemo(() => painel.contas.filter((c) => comSimulacoes || !c.demo), [painel.contas, comSimulacoes])

  const lista = useMemo(() => {
    const termo = sem(busca.trim())
    const digitos = soDigitos(busca)
    const vale = FILTROS.find((f) => f.id === filtro)?.vale ?? (() => true)
    const filtradas = base.filter((c) => {
      if (!vale(c)) return false
      if (assinatura && (c.assinatura ?? SEM_ASSINATURA) !== assinatura) return false
      if (!termo) return true
      if (sem(c.razao_social ?? "").includes(termo)) return true
      if (digitos.length >= 3 && soDigitos(c.cnpj).includes(digitos)) return true
      if (digitos.length >= 4 && soDigitos(c.telefone ?? "").includes(digitos)) return true
      return c.logins.some((l) => sem(l.email).includes(termo) || sem(l.nome ?? "").includes(termo))
    })
    const sinal = ordem.desc ? -1 : 1
    return [...filtradas].sort((a, b) => {
      const va = valorDe(a, ordem.campo)
      const vb = valorDe(b, ordem.campo)
      // Sem data (nunca entrou) vai sempre pro fim, em qualquer sentido.
      if (va === null || vb === null) return va === vb ? 0 : va === null ? 1 : -1
      return (va - vb) * sinal
    })
  }, [base, busca, filtro, assinatura, ordem])

  const visiveis = lista.slice(0, limite)

  /** Qualquer mudança de filtro volta pro começo da lista. */
  function mudar<T>(guardar: (v: T) => void) {
    return (valor: T) => {
      guardar(valor)
      setLimite(POR_VEZ)
    }
  }

  function ordenarPor(campo: Campo) {
    setOrdem((atual) => (atual.campo === campo ? { campo, desc: !atual.desc } : { campo, desc: true }))
    setLimite(POR_VEZ)
  }

  function alternar(id: string) {
    setAbertas((atual) => {
      const novo = new Set(atual)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  function baixar() {
    const simNao = (v: boolean) => (v ? "sim" : "não")
    baixarCsv(`contas-agente-ana-${painel.competencia}.csv`, [
      [
        "Empresa", "CNPJ", "Telefone", "E-mail principal", "Outros logins", "E-mail confirmado", "Assinatura", "Plano", "Módulos",
        "Criada em", "Último acesso", "Dias sem acesso", "Certificado", "Tomadores",
        "Notas no mês (uma a uma)", "Notas no mês (lote)", "Notas no total", "Notas importadas",
        "E-mails no mês", "E-mails de lote no mês", "Falhas de e-mail no mês", "E-mails no total",
        "Conta de teste", "Simulação", "Veio por",
      ],
      ...lista.map((c) => [
        c.razao_social ?? "", formatarDocumento(c.cnpj), telefoneLegivel(c.telefone), c.logins[0]?.email ?? "", c.logins.slice(1).map((l) => l.email).join(", "),
        simNao(c.email_confirmado), situacaoAssinatura(c.assinatura).rotulo, nomeDoPlano(c.plano), c.modulos.map(nomeDoModulo).join(" + "),
        c.criada_em ? dia(c.criada_em) : "", c.ultimo_acesso ? diaHora(c.ultimo_acesso) : "", c.dias_sem_acesso ?? "", ROTULO_CERTIFICADO[c.certificado] ?? c.certificado, c.tomadores,
        c.notas_mes, c.notas_lote_mes, c.notas_total, c.notas_importadas,
        c.emails_mes, c.emails_lote_mes, c.emails_falha_mes, c.emails_total,
        simNao(c.modo_teste), simNao(c.demo), c.veio_por ?? "",
      ]),
    ])
  }

  const setaDe = (campo: Campo) =>
    ordem.campo !== campo ? null : ordem.desc ? <ArrowDown size={12} aria-hidden="true" /> : <ArrowUp size={12} aria-hidden="true" />
  const cabecalhoOrdenavel = (campo: Campo, rotulo: string, direita = false) => (
    <th scope="col" className={`${classeTh} ${direita ? "text-right" : ""}`} aria-sort={ordem.campo === campo ? (ordem.desc ? "descending" : "ascending") : undefined}>
      <button
        type="button"
        onClick={() => ordenarPor(campo)}
        className="inline-flex items-center gap-1 rounded uppercase tracking-wide hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:hover:text-slate-200"
      >
        {rotulo} {setaDe(campo)}
      </button>
    </th>
  )

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Buscar por nome, CNPJ, e-mail ou telefone</span>
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={busca}
              onChange={(e) => mudar(setBusca)(e.target.value)}
              placeholder="Buscar por nome, CNPJ, e-mail ou telefone"
              className={`${classeCampo} w-full pl-9`}
            />
          </label>
          <Button type="button" variant="outline" className="shrink-0" disabled={lista.length === 0} onClick={baixar}>
            <Download size={15} aria-hidden="true" /> Baixar lista (.csv)
          </Button>
        </div>

        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0" role="group" aria-label="Filtrar contas">
          {FILTROS.map((f) => {
            const ativo = filtro === f.id
            return (
              <button
                key={f.id}
                type="button"
                aria-pressed={ativo}
                onClick={() => mudar(setFiltro)(f.id)}
                className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                  ativo
                    ? "border-primary-500 bg-primary-50 text-primary-700 dark:border-primary-400 dark:bg-primary-900/40 dark:text-primary-300"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                }`}
              >
                {f.rotulo} <span className="tabular-nums opacity-70">{numero(base.filter(f.vale).length)}</span>
              </button>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <label className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
            Assinatura
            <select value={assinatura} onChange={(e) => mudar(setAssinatura)(e.target.value)} className={`${classeCampo} py-1.5`}>
              <option value="">Todas</option>
              {ASSINATURAS.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.rotulo}
                </option>
              ))}
            </select>
          </label>
          <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
            <label className="flex items-center gap-2">
              Ordenar por
              <select
                value={ordem.campo}
                onChange={(e) => {
                  setOrdem({ campo: e.target.value as Campo, desc: true })
                  setLimite(POR_VEZ)
                }}
                className={`${classeCampo} py-1.5`}
              >
                {ORDENS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.rotulo}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => ordenarPor(ordem.campo)}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              {ordem.desc ? <ArrowDown size={13} aria-hidden="true" /> : <ArrowUp size={13} aria-hidden="true" />}
              {ordem.campo === "criada_em" || ordem.campo === "ultimo_acesso"
                ? ordem.desc
                  ? "mais recentes primeiro"
                  : "mais antigas primeiro"
                : ordem.desc
                  ? "maiores primeiro"
                  : "menores primeiro"}
            </button>
          </span>
          {simulacoes > 0 && (
            <label className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={comSimulacoes}
                onChange={(e) => mudar(setComSimulacoes)(e.target.checked)}
                className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
              />
              mostrar simulações ({numero(simulacoes)})
            </label>
          )}
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400" role="status">
          {lista.length === base.length ? plural(lista.length, "conta", "contas") : `${numero(lista.length)} de ${plural(base.length, "conta", "contas")}`}
          {" · toque numa conta pra ver os detalhes"}
        </p>
      </div>

      {lista.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma conta com esses filtros.</p>
      ) : (
        <>
          {/* Computador: tabela. */}
          <div className="mt-3 hidden overflow-x-auto lg:block">
            <table className="w-full min-w-[880px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th scope="col" className={classeTh}>Empresa</th>
                  <th scope="col" className={classeTh}>Login</th>
                  <th scope="col" className={classeTh}>Assinatura</th>
                  <th scope="col" className={classeTh}>Módulos</th>
                  {cabecalhoOrdenavel("ultimo_acesso", "Último acesso")}
                  {cabecalhoOrdenavel("notas", "Notas no mês", true)}
                  {cabecalhoOrdenavel("emails", "E-mails no mês", true)}
                  <th scope="col" className={`${classeTh} text-right`}>Tomadores</th>
                </tr>
              </thead>
              <tbody>
                {visiveis.map((c) => {
                  const aberta = abertas.has(c.id)
                  return (
                    <Fragment key={c.id}>
                      <tr
                        onClick={() => alternar(c.id)}
                        className={`cursor-pointer border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700/60 dark:hover:bg-slate-700/30 ${aberta ? "bg-slate-50 dark:bg-slate-700/30" : ""}`}
                      >
                        <td className={classeTd}>
                          <div className="flex items-start gap-2">
                            <button
                              type="button"
                              aria-expanded={aberta}
                              aria-label={`${aberta ? "Esconder" : "Ver"} detalhes de ${nomeDaConta(c)}`}
                              onClick={(e) => {
                                e.stopPropagation()
                                alternar(c.id)
                              }}
                              className="mt-0.5 shrink-0 rounded text-slate-400 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:hover:text-slate-200"
                            >
                              <ChevronDown size={16} className={`transition-transform ${aberta ? "rotate-180" : ""}`} aria-hidden="true" />
                            </button>
                            <Empresa conta={c} />
                          </div>
                        </td>
                        <td className={classeTd}><Login conta={c} /></td>
                        <td className={classeTd}><Assinatura conta={c} /></td>
                        <td className={classeTd}><Modulos conta={c} /></td>
                        <td className={`${classeTd} whitespace-nowrap`}><Acesso conta={c} /></td>
                        <td className={`${classeTd} text-right tabular-nums`}><Notas conta={c} /></td>
                        <td className={`${classeTd} text-right tabular-nums`}><Emails conta={c} /></td>
                        <td className={`${classeTd} text-right tabular-nums`}>{numero(c.tomadores)}</td>
                      </tr>
                      {aberta && (
                        <tr className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-700/60 dark:bg-slate-900/30">
                          <td colSpan={8} className="px-3 py-4 sm:px-9">
                            <Detalhes conta={c} aoMudar={aoMudar} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Celular e tablet: um cartão por conta. */}
          <ul className="mt-3 flex flex-col gap-3 lg:hidden">
            {visiveis.map((c) => {
              const aberta = abertas.has(c.id)
              return (
                <li key={c.id} className="rounded-xl border border-slate-200 dark:border-slate-700">
                  <button
                    type="button"
                    aria-expanded={aberta}
                    onClick={() => alternar(c.id)}
                    className="flex w-full flex-col gap-2.5 rounded-xl p-3.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                  >
                    <span className="flex w-full items-start justify-between gap-2">
                      <Empresa conta={c} />
                      <ChevronDown size={16} className={`mt-0.5 shrink-0 text-slate-400 transition-transform ${aberta ? "rotate-180" : ""}`} aria-hidden="true" />
                    </span>
                    <Login conta={c} />
                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <Assinatura conta={c} emLinha />
                      <Modulos conta={c} />
                    </span>
                    <span className="grid w-full grid-cols-2 gap-x-3 gap-y-2 text-sm sm:grid-cols-4">
                      <Mini rotulo="Último acesso"><Acesso conta={c} /></Mini>
                      <Mini rotulo="Notas no mês"><Notas conta={c} /></Mini>
                      <Mini rotulo="E-mails no mês"><Emails conta={c} /></Mini>
                      <Mini rotulo="Tomadores">{numero(c.tomadores)}</Mini>
                    </span>
                  </button>
                  {aberta && (
                    <div className="border-t border-slate-200 p-3.5 dark:border-slate-700">
                      <Detalhes conta={c} aoMudar={aoMudar} />
                    </div>
                  )}
                </li>
              )
            })}
          </ul>

          {lista.length > limite && (
            <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
              <Button type="button" variant="outline" onClick={() => setLimite((n) => n + POR_VEZ)}>
                Ver mais {Math.min(POR_VEZ, lista.length - limite)}
              </Button>
              <span className="text-xs text-slate-400 dark:text-slate-500">
                mostrando {numero(visiveis.length)} de {numero(lista.length)}
              </span>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

// --- Células (a tabela e os cartões do celular mostram a mesma coisa) -------

const classeSub = "block text-xs text-slate-400 dark:text-slate-500"

/** 92999990000 -> (92) 99999-0000 */
function telefoneLegivel(telefone: string | null | undefined): string {
  const d = soDigitos(telefone ?? "")
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return telefone ?? ""
}

function Empresa({ conta: c }: { conta: ContaGestao }) {
  return (
    <span className="block min-w-0">
      <span className="block break-words font-medium text-slate-800 dark:text-slate-100">{nomeDaConta(c)}</span>
      <span className={`${classeSub} tabular-nums`}>
        {c.so_contador ? "sem CNPJ" : formatarDocumento(c.cnpj) || "sem CNPJ"}
        {c.criada_em && ` · desde ${dia(c.criada_em)}`}
      </span>
      {c.telefone && (
        <a
          href={`https://wa.me/${soDigitos(c.telefone).length <= 11 ? "55" : ""}${soDigitos(c.telefone)}`}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          title="Abrir conversa no WhatsApp"
          className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium tabular-nums text-primary-700 hover:underline dark:text-primary-300"
        >
          <MessageCircle size={12} aria-hidden="true" /> {telefoneLegivel(c.telefone)}
          {c.telefone_origem === "empresa" && <span className="font-normal text-slate-400 dark:text-slate-500" title="Telefone do cadastro da empresa (Receita) — pode ser o do contador">· da empresa</span>}
        </a>
      )}
      {(c.modo_teste || c.demo || c.so_contador || c.fora_do_atendimento) && (
        <span className="mt-1 flex flex-wrap gap-1">
          {c.fora_do_atendimento && (
            <Badge variant="warning">{c.fora_do_atendimento === "regime" ? "regime não atendido" : "cidade fora do Emissor Nacional"}</Badge>
          )}
          {c.so_contador && <Badge variant="info">conta de contador</Badge>}
          {c.modo_teste && <Badge variant="warning">teste</Badge>}
          {c.demo && <Badge variant="neutral">simulação</Badge>}
        </span>
      )}
    </span>
  )
}

function Login({ conta: c }: { conta: ContaGestao }) {
  const principal = c.logins[0]
  if (!principal) return <span className="text-slate-400 dark:text-slate-500">sem login</span>
  return (
    <span className="block min-w-0">
      <span className="block break-all text-slate-700 dark:text-slate-200">
        {principal.email}
        {c.logins.length > 1 && (
          <span className="ml-1.5 whitespace-nowrap text-xs text-slate-400 dark:text-slate-500" title={c.logins.slice(1).map((l) => l.email).join(", ")}>
            +{c.logins.length - 1}
          </span>
        )}
      </span>
      {!c.email_confirmado && (
        <span className="mt-1 block">
          <Badge variant="warning">não confirmou</Badge>
        </span>
      )}
    </span>
  )
}

function Assinatura({ conta: c, emLinha = false }: { conta: ContaGestao; emLinha?: boolean }) {
  const s = situacaoAssinatura(c.assinatura)
  const teste = diasDoTeste(c)
  const plano = nomeDoPlano(c.plano)
  const liberada = c.acesso?.motivo === "liberacao"
  const extra = [
    plano,
    liberada ? "" : teste === null ? "" : teste <= 0 ? "teste vencido" : `teste até ${dia(c.trial_termina_em)}`,
    liberada ? (c.acesso.ate ? `até ${dia(c.acesso.ate)}` : "sem prazo") : "",
  ].filter(Boolean).join(" · ")
  return (
    <span className={emLinha ? "inline-flex flex-wrap items-center gap-x-2 gap-y-1" : "block"}>
      {c.acesso?.motivo === "bloqueada" ? (
        <Badge variant="danger">Bloqueada por você</Badge>
      ) : c.so_contador ? (
        <Badge variant="neutral">Não se aplica</Badge>
      ) : liberada ? (
        <Badge variant="success">Liberada por você</Badge>
      ) : (
        <Badge variant={teste !== null && teste <= 0 ? "danger" : s.variante}>{s.rotulo}</Badge>
      )}
      {c.liberacao_pedida_em && (
        <span className={emLinha ? "" : "mt-1 block"}>
          <Badge variant="warning">pediu liberação em {dia(c.liberacao_pedida_em)}</Badge>
        </span>
      )}
      {extra && <span className={emLinha ? "text-xs text-slate-400 dark:text-slate-500" : `${classeSub} mt-1`}>{extra}</span>}
    </span>
  )
}

// Liberar o uso de uma empresa sem assinatura (06/10/2026): amiga testando,
// parceira, cortesia. Por um prazo ou sem prazo; dá pra tirar depois.
const PRAZOS = [
  { rotulo: "30 dias", dias: 30 },
  { rotulo: "90 dias", dias: 90 },
  { rotulo: "1 ano", dias: 365 },
]

function LiberarAcesso({ conta: c, aoMudar }: { conta: ContaGestao; aoMudar?: () => void }) {
  const [obs, setObs] = useState(c.liberado_obs ?? "")
  const [fazendo, setFazendo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const a = c.acesso
  const liberada = a?.motivo === "liberacao"
  const bloqueada = a?.motivo === "bloqueada"
  // Quem paga ou é cortesia não precisa de liberação.
  const precisa = !a || !["assinatura", "cortesia", "pagamento_pendente", "bloqueada"].includes(a.motivo)

  async function pedir(acao: () => Promise<unknown>) {
    setFazendo(true)
    setErro(null)
    try {
      await acao()
      aoMudar?.()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(false)
    }
  }
  const liberar = (corpo: { dias?: number; sempre?: boolean }) =>
    pedir(() => api.post(`/gestao/contas/${c.id}/liberar`, { ...corpo, obs: obs.trim() || null }))

  if (c.demo || c.so_contador) return null
  return (
    <div className="max-w-2xl rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Aceitar a conta (liberar o uso sem assinatura)</p>
      <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
        {bloqueada && "Esta conta está bloqueada por você. Desbloqueie abaixo pra ela voltar a valer."}
        {!precisa && !bloqueada && "Esta conta já tem acesso (paga ou é cortesia). Não precisa liberar."}
        {precisa && liberada && (a.ate ? `Liberada por você até ${dia(a.ate)}.` : "Liberada por você, sem prazo.")}
        {precisa && !liberada && a?.motivo === "teste" && `Em teste grátis até ${dia(a.ate)}. Você pode liberar por mais tempo.`}
        {precisa && !liberada && a && !a.liberado && (c.liberacao_pedida_em
          ? `O teste acabou e a pessoa pediu a liberação em ${dia(c.liberacao_pedida_em)}. Escolha por quanto tempo autorizar.`
          : "Sem acesso: o teste acabou ou a assinatura foi encerrada. Com o bloqueio ligado, ela só consulta até você autorizar.")}
      </p>
      {precisa && (
        <>
          <label className="mt-3 block">
            <span className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Anotação (só você vê)</span>
            <input
              value={obs}
              maxLength={200}
              onChange={(e) => setObs(e.target.value)}
              placeholder="Ex.: amiga testando, parceira, combinado até dezembro"
              className={`${classeCampo} w-full`}
            />
          </label>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">Liberar por:</span>
            {PRAZOS.map((p) => (
              <Button key={p.dias} type="button" variant="outline" className="!px-3 !py-1.5" disabled={fazendo} onClick={() => liberar({ dias: p.dias })}>
                {p.rotulo}
              </Button>
            ))}
            <Button type="button" variant="outline" className="!px-3 !py-1.5" disabled={fazendo} onClick={() => liberar({ sempre: true })}>
              Sem prazo
            </Button>
            {liberada && (
              <Button type="button" variant="ghost" className="!px-3 !py-1.5 !text-danger-600" disabled={fazendo} onClick={() => pedir(() => api.delete(`/gestao/contas/${c.id}/liberar`))}>
                Tirar a liberação
              </Button>
            )}
          </div>
        </>
      )}
      {erro && <p className="mt-2 text-sm text-danger-700 dark:text-danger-300">{erro}</p>}
    </div>
  )
}

// Gestão manual (08/10/2026): "nessa fase em que o sistema de pagamento não
// está implementado quero poder fazer a gestão de contas manualmente,
// aceitando, bloqueando e excluindo". Aceitar = liberar (acima); aqui ficam
// bloquear (a conta fica só pra consulta) e excluir (não tem volta).
function BloquearOuExcluir({ conta: c, aoMudar }: { conta: ContaGestao; aoMudar?: () => void }) {
  const bloqueada = c.acesso?.motivo === "bloqueada"
  const [obs, setObs] = useState(c.bloqueada_obs ?? "")
  const [fazendo, setFazendo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [excluindo, setExcluindo] = useState(false)
  const [digitado, setDigitado] = useState("")
  const codigo = c.so_contador ? (c.cnpj ?? "") : formatarDocumento(c.cnpj)
  // mesma conta do servidor: só letras e números, sem pontuação
  const limpo = (t: string) => t.replace(/[^a-zA-Z0-9]/g, "").toUpperCase()
  const confere = limpo(digitado) !== "" && limpo(digitado) === limpo(c.cnpj ?? "")

  async function pedir(acao: () => Promise<unknown>) {
    setFazendo(true)
    setErro(null)
    try {
      await acao()
      setExcluindo(false)
      aoMudar?.()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(false)
    }
  }

  if (c.demo) return null
  return (
    <div className="max-w-2xl rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Bloquear ou excluir</p>
      <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
        {bloqueada
          ? `Bloqueada por você${c.bloqueada_em ? ` em ${dia(c.bloqueada_em)}` : ""}: a pessoa entra e consulta, mas não gera nota nem lança nada.`
          : "Bloquear deixa a conta só pra consulta (a pessoa vê um aviso pra falar com o suporte). Vale na hora e passa por cima de teste e liberação."}
      </p>
      {!c.so_contador && (
        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Motivo do bloqueio (só você vê)</span>
          <input
            value={obs}
            maxLength={200}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Ex.: não pagou o combinado, uso indevido"
            disabled={bloqueada}
            className={`${classeCampo} w-full disabled:opacity-70`}
          />
        </label>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {!c.so_contador &&
          (bloqueada ? (
            <Button type="button" variant="outline" className="!px-3 !py-1.5" disabled={fazendo} onClick={() => pedir(() => api.delete(`/gestao/contas/${c.id}/bloquear`))}>
              <Unlock size={15} aria-hidden="true" /> Desbloquear
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              className="!px-3 !py-1.5 !text-danger-600"
              disabled={fazendo}
              onClick={() => pedir(() => api.post(`/gestao/contas/${c.id}/bloquear`, { obs: obs.trim() || null }))}
            >
              <Ban size={15} aria-hidden="true" /> Bloquear a conta
            </Button>
          ))}
        <Button
          type="button"
          variant="ghost"
          className="!px-3 !py-1.5 !text-danger-600"
          disabled={fazendo}
          onClick={() => {
            setErro(null)
            setDigitado("")
            setExcluindo(true)
          }}
        >
          <Trash2 size={15} aria-hidden="true" /> Excluir a conta...
        </Button>
      </div>
      {erro && !excluindo && <p className="mt-2 text-sm text-danger-700 dark:text-danger-300">{erro}</p>}

      {excluindo && (
        <Modal titulo="Excluir esta conta?" onClose={() => !fazendo && setExcluindo(false)}>
          <div className="flex flex-col gap-3 text-sm text-slate-600 dark:text-slate-300">
            <p>
              <strong className="text-slate-900 dark:text-slate-100">{nomeDaConta(c)}</strong> e todo o histórico dela aqui são apagados: tomadores, notas,
              recebimentos, despesas e o certificado. {c.logins.length > 0 && `O login ${c.logins.map((l) => l.email).join(", ")} vai junto (se não tiver outra empresa).`}
            </p>
            <p className="rounded-lg bg-danger-50 px-3 py-2 text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
              Não tem como desfazer. As notas já autorizadas continuam válidas na Receita, mas saem da Ana. Se a ideia é só impedir o uso, prefira bloquear.
            </p>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">
                Pra confirmar, digite {c.so_contador ? "o código da conta" : "o CNPJ"}: <strong className="tabular-nums">{codigo}</strong>
              </span>
              <input value={digitado} onChange={(e) => setDigitado(e.target.value)} className={`${classeCampo} w-full`} autoComplete="off" />
            </label>
            {erro && <p className="text-danger-700 dark:text-danger-300">{erro}</p>}
            <div className="mt-1 flex flex-wrap justify-end gap-2">
              <Button type="button" variant="outline" disabled={fazendo} onClick={() => setExcluindo(false)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" disabled={fazendo || !confere} onClick={() => pedir(() => excluirComConfirmacao(`/gestao/contas/${c.id}`, digitado))}>
                <Trash2 size={15} aria-hidden="true" /> {fazendo ? "Excluindo..." : "Excluir de vez"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Modulos({ conta: c }: { conta: ContaGestao }) {
  if (c.modulos.length === 0) return <span className="text-slate-400 dark:text-slate-500">—</span>
  return <span className="text-sm text-slate-600 dark:text-slate-300">{c.modulos.map(nomeDoModulo).join(" + ")}</span>
}

function Acesso({ conta: c }: { conta: ContaGestao }) {
  if (c.dias_sem_acesso === null) return <span className="text-slate-400 dark:text-slate-500">nunca entrou</span>
  return (
    <span className="block">
      {dia(c.ultimo_acesso)}
      <span className={c.dias_sem_acesso > 30 ? "block text-xs text-warning-700 dark:text-warning-300" : classeSub}>{haDias(c.dias_sem_acesso)}</span>
    </span>
  )
}

function Notas({ conta: c }: { conta: ContaGestao }) {
  const total = notasDoMes(c)
  if (total === 0) return <span className="text-slate-400 dark:text-slate-500">0</span>
  return (
    <span className="block">
      {numero(total)}
      <span className={classeSub}>
        {numero(c.notas_mes)} uma a uma + {numero(c.notas_lote_mes)} lote
      </span>
    </span>
  )
}

function Emails({ conta: c }: { conta: ContaGestao }) {
  if (c.emails_mes === 0 && c.emails_falha_mes === 0) return <span className="text-slate-400 dark:text-slate-500">0</span>
  return (
    <span className="block">
      {numero(c.emails_mes)}
      {c.emails_lote_mes > 0 && <span className={classeSub}>{numero(c.emails_lote_mes)} de lote</span>}
      {c.emails_falha_mes > 0 && <span className="block text-xs text-warning-700 dark:text-warning-300">{plural(c.emails_falha_mes, "falha", "falhas")}</span>}
    </span>
  )
}

function Mini({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <span className="block min-w-0">
      <span className="block text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">{rotulo}</span>
      <span className="block tabular-nums text-slate-700 dark:text-slate-200">{children}</span>
    </span>
  )
}

// --- Detalhes da conta ------------------------------------------------------

const ROTULO_CERTIFICADO: Record<string, string> = { ok: "Válido", falta: "Não enviou", vencido: "Vencido" }

function Item({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">{rotulo}</dt>
      <dd className="text-sm text-slate-700 dark:text-slate-200">{children}</dd>
    </div>
  )
}

function Detalhes({ conta: c, aoMudar }: { conta: ContaGestao; aoMudar?: () => void }) {
  return (
    <div className="flex flex-col gap-4">
      <LiberarAcesso conta={c} aoMudar={aoMudar} />
      <BloquearOuExcluir conta={c} aoMudar={aoMudar} />
      <div>
        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
          {c.logins.length === 1 ? "Login" : `Logins (${c.logins.length})`}
        </p>
        {c.logins.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Nenhum login ligado a esta empresa.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {c.logins.map((l) => (
              <li key={l.email} className="flex flex-col gap-x-3 gap-y-1 text-sm sm:flex-row sm:flex-wrap sm:items-center">
                <span className="min-w-0 break-all text-slate-700 dark:text-slate-200">
                  {l.email}
                  {l.nome && <span className="ml-1.5 text-xs text-slate-400 dark:text-slate-500">{l.nome}</span>}
                </span>
                <span className="flex flex-wrap items-center gap-1.5">
                  {l.confirmado ? <Badge variant="success">e-mail confirmado</Badge> : <Badge variant="warning">não confirmou</Badge>}
                  {!l.ativo && <Badge variant="danger">desativado</Badge>}
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    {l.ultimo_acesso ? `último acesso em ${diaHora(l.ultimo_acesso)}` : "nunca entrou"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 xl:grid-cols-4">
        <Item rotulo="Conta criada em">{dia(c.criada_em)}</Item>
        <Item rotulo="Certificado digital">
          {c.certificado === "ok" ? (
            ROTULO_CERTIFICADO.ok
          ) : (
            <span className="text-warning-700 dark:text-warning-300">{ROTULO_CERTIFICADO[c.certificado] ?? c.certificado}</span>
          )}
        </Item>
        <Item rotulo="Última nota">{c.ultima_nota ? dia(c.ultima_nota) : "nenhuma ainda"}</Item>
        <Item rotulo="Notas no total">
          {numero(c.notas_total)}
          <span className={classeSub}>{numero(c.notas_importadas)} importadas do Emissor Nacional</span>
        </Item>
        <Item rotulo="Financeiro no mês">
          {plural(c.lancamentos_financeiros_mes, "lançamento", "lançamentos")}
          <span className={classeSub}>{plural(c.linhas_extrato_mes, "linha de extrato", "linhas de extrato")}</span>
        </Item>
        <Item rotulo="Lotes no mês">{numero(c.lotes_mes)}</Item>
        <Item rotulo="E-mails no total">{numero(c.emails_total)}</Item>
        <Item rotulo="Anotações">{numero(c.anotacoes)}</Item>
        <Item rotulo="Google Drive">{c.drive ? "Conectado" : "Não conectado"}</Item>
        <Item rotulo="Indicações">
          {c.indicou === 0 ? "não indicou ninguém" : `indicou ${numero(c.indicou)} (${plural(c.indicou_ativos, "ativo", "ativos")})`}
        </Item>
        <Item rotulo="Como chegou">{c.veio_por ?? "por conta própria"}</Item>
        <Item rotulo="Contador">{c.contadores ? plural(c.contadores, "com acesso", "com acesso") : "nenhum"}</Item>
        {c.assinatura === "trial" && c.trial_termina_em && <Item rotulo="Teste termina em">{dia(c.trial_termina_em)}</Item>}
      </dl>
    </div>
  )
}
