import { ChevronDown, HandCoins, Handshake, Pencil, Plus, RefreshCw, Users } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import { dataBR, formatPct, situacaoDoIndicado } from "../lib/parceiras"
import type { ParceiroAdmin } from "../lib/types"
import { Badge } from "./ui/Badge"
import { BotaoCopiar } from "./ui/BotaoCopiar"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"
import { Field } from "./ui/Field"
import { Modal } from "./ui/Modal"
import { StatCard } from "./ui/StatCard"

// Parceiras de indicação (06/10/2026) — área da administração da plataforma
// (Minha conta › Parceiras). A parceira recebe uma % do que cada indicado
// paga; o repasse é feito por fora (Pix) e aqui só se controla.
// Backend: app/services/parceiros.py.

function erroDe(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

const classeErro = "rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300"
const classeTh = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const classeTd = "px-3 py-2.5 text-slate-700 dark:text-slate-200"

export function ParceirasAdmin() {
  const [lista, setLista] = useState<ParceiroAdmin[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  /** "nova" = cadastro; uma parceira = edição. */
  const [formulario, setFormulario] = useState<"nova" | ParceiroAdmin | null>(null)
  const [abertas, setAbertas] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    api
      .get<ParceiroAdmin[]>("/parceiros")
      .then(setLista)
      .catch((err) => setErro(erroDe(err)))
  }, [])

  function guardar(p: ParceiroAdmin) {
    setLista((atual) => {
      if (!atual) return [p]
      return atual.some((x) => x.id === p.id) ? atual.map((x) => (x.id === p.id ? p : x)) : [...atual, p]
    })
  }

  function alternar(id: string) {
    setAbertas((atual) => {
      const novo = new Set(atual)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  const indicadosAtivos = (lista ?? []).reduce((soma, p) => soma + p.indicados_ativos, 0)
  const aRepassar = (lista ?? []).reduce((soma, p) => soma + p.a_receber, 0)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Parceiras indicam a Ana e recebem uma parte de cada mensalidade paga por quem assinou pelo link delas, enquanto a
          assinatura estiver ativa. O repasse é feito por fora (Pix) — aqui você só acompanha quanto deve e marca o que já pagou.
        </p>
        <Button type="button" className="shrink-0" onClick={() => setFormulario("nova")}>
          <Plus size={16} aria-hidden="true" /> Nova parceira
        </Button>
      </div>

      {erro && <p className={classeErro}>{erro}</p>}
      {!lista && !erro && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {lista && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              icon={<Handshake size={18} />}
              iconClassName="bg-primary-50 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300"
              label="Parceiras"
              value={lista.length}
              sublabel={`${lista.filter((p) => p.ativo).length} com o link ativo`}
            />
            <StatCard
              icon={<Users size={18} />}
              iconClassName="bg-success-50 text-success-600 dark:bg-success-900/40 dark:text-success-300"
              label="Indicados com assinatura ativa"
              value={indicadosAtivos}
            />
            <StatCard
              icon={<HandCoins size={18} />}
              iconClassName="bg-accent-50 text-accent-600 dark:bg-accent-900/40 dark:text-accent-300"
              label="Total a repassar"
              value={formatBRL(aRepassar)}
            />
          </div>

          {lista.length === 0 ? (
            <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300">
                <Handshake size={22} aria-hidden="true" />
              </div>
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200">Nenhuma parceira ainda</p>
              <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
                Cadastre a primeira (uma contadora, por exemplo). Ela recebe um link pra divulgar e outro, secreto, pra
                acompanhar as indicações — não precisa ter conta na Ana.
              </p>
              <Button type="button" onClick={() => setFormulario("nova")}>
                <Plus size={16} aria-hidden="true" /> Cadastrar a primeira parceira
              </Button>
            </Card>
          ) : (
            <div className="flex flex-col gap-4">
              {lista.map((p) => (
                <CartaoParceira
                  key={p.id}
                  parceira={p}
                  aberta={abertas.has(p.id)}
                  onAlternar={() => alternar(p.id)}
                  onEditar={() => setFormulario(p)}
                  onAtualizada={guardar}
                />
              ))}
            </div>
          )}
        </>
      )}

      {formulario && (
        <FormularioParceira
          parceira={formulario === "nova" ? null : formulario}
          onFechar={() => setFormulario(null)}
          onSalva={(p) => {
            guardar(p)
            setFormulario(null)
          }}
        />
      )}
    </div>
  )
}

// --- uma parceira -----------------------------------------------------------

function CartaoParceira({
  parceira: p,
  aberta,
  onAlternar,
  onEditar,
  onAtualizada,
}: {
  parceira: ParceiroAdmin
  aberta: boolean
  onAlternar: () => void
  onEditar: () => void
  onAtualizada: (p: ParceiroAdmin) => void
}) {
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [confirmandoTroca, setConfirmandoTroca] = useState(false)
  const [linkTrocado, setLinkTrocado] = useState(false)

  async function executar(chave: string, acao: () => Promise<ParceiroAdmin>): Promise<boolean> {
    setErro(null)
    setOcupado(chave)
    try {
      onAtualizada(await acao())
      return true
    } catch (err) {
      setErro(erroDe(err))
      return false
    } finally {
      setOcupado(null)
    }
  }

  const alternarAtivo = () => executar("ativo", () => api.patch<ParceiroAdmin>(`/parceiros/${p.id}`, { ativo: !p.ativo }))

  async function trocarLink() {
    const ok = await executar("link", () => api.post<ParceiroAdmin>(`/parceiros/${p.id}/novo-link`))
    if (ok) {
      setConfirmandoTroca(false)
      setLinkTrocado(true)
    }
  }

  const marcar = (competencia: string, pago: boolean) =>
    executar(`mes-${competencia}`, async () => {
      const resposta = await api.post<{ marcadas: number; parceiro: ParceiroAdmin }>(`/parceiros/${p.id}/pagar`, { competencia, pago })
      return resposta.parceiro
    })

  const idDetalhes = `parceira-${p.id}`

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="break-words text-base font-semibold text-slate-900 dark:text-slate-100">{p.nome}</h3>
              <Badge variant={p.ativo ? "success" : "neutral"}>{p.ativo ? "Ativa" : "Desativada"}</Badge>
            </div>
            <p className="break-all text-sm text-slate-500 dark:text-slate-400">{p.email || "Sem e-mail cadastrado"}</p>
          </div>
          <div className="text-left sm:text-right">
            <p className="text-xs text-slate-400 dark:text-slate-500">A repassar</p>
            <p className={`text-xl font-semibold ${p.a_receber > 0 ? "text-accent-600 dark:text-accent-300" : "text-slate-900 dark:text-slate-100"}`}>
              {formatBRL(p.a_receber)}
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Dado rotulo="Comissão" valor={formatPct(p.comissao_pct)} />
          <Dado rotulo="Desconto na 1ª mensalidade" valor={p.desconto_1_mes_pct > 0 ? formatPct(p.desconto_1_mes_pct) : "Sem desconto"} />
          <Dado rotulo="Indicados ativos / total" valor={`${p.indicados_ativos} / ${p.indicados_total}`} />
          <Dado rotulo="Comissão acumulada" valor={formatBRL(p.total_comissao)} />
        </dl>

        {!p.ativo && (
          <p className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600 dark:bg-slate-700/60 dark:text-slate-300">
            Desativada: o link de indicação não registra novos cadastros. Quem ela já trouxe continua gerando comissão — pra
            encerrar de vez, edite e ponha a comissão em 0%.
          </p>
        )}

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <BotaoCopiar texto={p.link} rotulo="Copiar link de indicação" />
          <BotaoCopiar texto={p.painel} rotulo="Copiar link do painel" />
          <Button type="button" variant="outline" onClick={onEditar}>
            <Pencil size={16} aria-hidden="true" /> Editar
          </Button>
          <Button type="button" variant="outline" disabled={ocupado !== null} onClick={alternarAtivo}>
            {ocupado === "ativo" ? "Salvando..." : p.ativo ? "Desativar" : "Reativar"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={ocupado !== null}
            onClick={() => {
              setLinkTrocado(false)
              setConfirmandoTroca(true)
            }}
          >
            <RefreshCw size={16} aria-hidden="true" /> Trocar link do painel
          </Button>
        </div>

        {confirmandoTroca && (
          <div role="alert" className="rounded-lg border border-warning-300 bg-warning-50 p-4 dark:border-warning-900/60 dark:bg-warning-900/20">
            <p className="text-sm font-medium text-warning-700 dark:text-warning-300">Trocar o link do painel de {p.nome}?</p>
            <p className="mt-1 text-sm text-warning-700 dark:text-warning-300">
              O link antigo para de funcionar na hora. Depois de trocar, copie o link novo e mande pra ela — sem ele, ela
              não consegue mais acompanhar as indicações. O link de indicação (o que ela divulga) continua o mesmo.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="danger" disabled={ocupado !== null} onClick={trocarLink}>
                {ocupado === "link" ? "Trocando..." : "Sim, trocar o link"}
              </Button>
              <Button type="button" variant="outline" disabled={ocupado === "link"} onClick={() => setConfirmandoTroca(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        )}

        {linkTrocado && (
          <div role="status" className="flex flex-col gap-2 rounded-lg bg-success-50 p-4 dark:bg-success-900/20 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-success-700 dark:text-success-300">
              Link trocado. O antigo não abre mais — mande o novo pra {p.nome}.
            </p>
            <BotaoCopiar texto={p.painel} rotulo="Copiar link novo" className="shrink-0" />
          </div>
        )}

        {erro && <p role="alert" className={classeErro}>{erro}</p>}

        <button
          type="button"
          onClick={onAlternar}
          aria-expanded={aberta}
          aria-controls={idDetalhes}
          className="flex items-center gap-1.5 self-start rounded-lg text-sm font-medium text-primary-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-primary-300"
        >
          <ChevronDown size={16} aria-hidden="true" className={`transition-transform ${aberta ? "rotate-180" : ""}`} />
          {aberta ? "Esconder indicados e meses" : "Ver indicados e meses"}
        </button>

        {aberta && (
          <div id={idDetalhes} className="flex flex-col gap-5 border-t border-slate-100 pt-4 dark:border-slate-700/60">
            <section>
              <h4 className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">Quem veio pelo link dela</h4>
              {p.indicados.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">Ninguém se cadastrou pelo link dela ainda.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[420px] text-sm">
                    <thead>
                      <tr>
                        <th className={classeTh}>Nome</th>
                        <th className={classeTh}>Situação</th>
                        <th className={classeTh}>Desde</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                      {p.indicados.map((i, n) => {
                        const situacao = situacaoDoIndicado(i.status)
                        return (
                          <tr key={n}>
                            <td className={classeTd}>{i.nome}</td>
                            <td className={classeTd}>
                              <Badge variant={situacao.variante}>{situacao.rotulo}</Badge>
                            </td>
                            <td className={`${classeTd} whitespace-nowrap`}>{dataBR(i.desde)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section>
              <h4 className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">Mês a mês</h4>
              {p.meses.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">
                  Nenhuma mensalidade paga pelos indicados ainda — a comissão aparece aqui quando o primeiro pagamento entrar.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead>
                      <tr>
                        <th className={classeTh}>Mês</th>
                        <th className={`${classeTh} text-right`}>Mensalidades pagas</th>
                        <th className={`${classeTh} text-right`}>Base</th>
                        <th className={`${classeTh} text-right`}>Comissão</th>
                        <th className={classeTh}>Repasse</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                      {p.meses.map((m) => {
                        const salvando = ocupado === `mes-${m.competencia}`
                        return (
                          <tr key={m.competencia}>
                            <td className={`${classeTd} whitespace-nowrap`}>{formatCompetenciaLonga(m.competencia)}</td>
                            <td className={`${classeTd} text-right`}>{m.pagamentos}</td>
                            <td className={`${classeTd} whitespace-nowrap text-right`}>{formatBRL(m.base)}</td>
                            <td className={`${classeTd} whitespace-nowrap text-right font-medium`}>{formatBRL(m.comissao)}</td>
                            <td className={classeTd}>
                              {m.a_pagar > 0 ? (
                                <div className="flex flex-col items-start gap-1">
                                  <Button
                                    type="button"
                                    variant="outline"
                                    className="whitespace-nowrap px-3 py-1.5"
                                    disabled={ocupado !== null}
                                    onClick={() => marcar(m.competencia, true)}
                                  >
                                    {salvando ? "Salvando..." : "Marcar como repassado"}
                                  </Button>
                                  {m.pago_em && (
                                    <span className="text-xs text-slate-400 dark:text-slate-500">
                                      Falta {formatBRL(m.a_pagar)} — o resto foi repassado em {dataBR(m.pago_em)}
                                    </span>
                                  )}
                                </div>
                              ) : m.pago_em ? (
                                <span className="whitespace-nowrap text-success-700 dark:text-success-300">
                                  Repassado em {dataBR(m.pago_em)}
                                  <button
                                    type="button"
                                    disabled={ocupado !== null}
                                    onClick={() => marcar(m.competencia, false)}
                                    className="ml-2 text-xs text-slate-400 underline hover:text-slate-600 disabled:opacity-50 dark:text-slate-500 dark:hover:text-slate-300"
                                  >
                                    {salvando ? "desfazendo..." : "desfazer"}
                                  </button>
                                </span>
                              ) : (
                                <span className="text-slate-400 dark:text-slate-500">Nada a repassar</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </Card>
  )
}

function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-400 dark:text-slate-500">{rotulo}</dt>
      <dd className="font-medium text-slate-800 dark:text-slate-200">{valor}</dd>
    </div>
  )
}

// --- cadastro / edição --------------------------------------------------------

/** "12,5" / "12.5" / "12" -> número; vazio ou texto estranho -> null. */
function lerPercentual(texto: string): number | null {
  const limpo = texto.trim().replace("%", "").replace(",", ".")
  if (!/^\d+(\.\d+)?$/.test(limpo)) return null
  return Number(limpo)
}

function FormularioParceira({
  parceira,
  onFechar,
  onSalva,
}: {
  parceira: ParceiroAdmin | null
  onFechar: () => void
  onSalva: (p: ParceiroAdmin) => void
}) {
  const [nome, setNome] = useState(parceira?.nome ?? "")
  const [email, setEmail] = useState(parceira?.email ?? "")
  const [comissao, setComissao] = useState(parceira ? String(parceira.comissao_pct).replace(".", ",") : "")
  const [desconto, setDesconto] = useState(parceira ? String(parceira.desconto_1_mes_pct) : "0")
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    const nomeLimpo = nome.trim()
    const emailLimpo = email.trim()
    const comissaoPct = lerPercentual(comissao)
    const descontoPct = desconto.trim() === "" ? 0 : lerPercentual(desconto)

    if (nomeLimpo.length < 2) return setErro("Escreva o nome da parceira.")
    if (emailLimpo && !/^\S+@\S+\.\S+$/.test(emailLimpo)) return setErro("Confira o e-mail — parece incompleto.")
    if (comissaoPct === null || comissaoPct > 100) return setErro("Comissão: informe um número entre 0 e 100.")
    if (descontoPct === null || descontoPct > 100) return setErro("Desconto: informe um número entre 0 e 100.")
    if (!Number.isInteger(descontoPct)) return setErro("Desconto: use um número inteiro, sem vírgula (ex.: 20).")

    const dados = { nome: nomeLimpo, email: emailLimpo || null, comissao_pct: comissaoPct, desconto_1_mes_pct: descontoPct }
    setErro(null)
    setSalvando(true)
    try {
      onSalva(parceira ? await api.patch<ParceiroAdmin>(`/parceiros/${parceira.id}`, dados) : await api.post<ParceiroAdmin>("/parceiros", dados))
    } catch (err) {
      setErro(erroDe(err))
      setSalvando(false)
    }
  }

  return (
    <Modal titulo={parceira ? "Editar parceira" : "Nova parceira"} onClose={onFechar}>
      <form onSubmit={salvar} noValidate className="flex flex-col gap-4">
        <Field label="Nome" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={120} required autoComplete="off" />
        <Field
          label="E-mail (opcional)"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={200}
          autoComplete="off"
          hint="Só pra você ter o contato dela — a Ana não manda e-mail pra parceira."
        />
        <Field
          label="Comissão (% de cada mensalidade paga)"
          inputMode="decimal"
          value={comissao}
          onChange={(e) => setComissao(e.target.value)}
          placeholder="Ex.: 20"
          autoComplete="off"
          hint={parceira ? "Se mudar, vale só pras mensalidades pagas daqui pra frente." : "De 0 a 100. Pode ter vírgula (ex.: 12,5)."}
        />
        <Field
          label="Desconto do indicado na 1ª mensalidade (%)"
          inputMode="numeric"
          value={desconto}
          onChange={(e) => setDesconto(e.target.value)}
          placeholder="0"
          autoComplete="off"
          hint="De 0 a 100, número inteiro. Deixe 0 pra não dar desconto."
        />
        {erro && <p role="alert" className={classeErro}>{erro}</p>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onFechar} disabled={salvando}>
            Cancelar
          </Button>
          <Button type="submit" disabled={salvando}>
            {salvando ? "Salvando..." : parceira ? "Salvar" : "Cadastrar parceira"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
