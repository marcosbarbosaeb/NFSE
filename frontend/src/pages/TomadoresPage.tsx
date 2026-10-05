import { CalendarDays, FilePlus2, Pencil, Plus, Search, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { documentoDoTomador, formatarDocumento } from "../lib/documento"
import { competenciaAtual, formatBRL, formatCompetenciaLonga } from "../lib/format"
import { useModulos } from "../lib/modulos"
import type { ConferenciaTomadores, Tomador, VinculoResumo } from "../lib/types"

// Aba Tomadores — revista a pedido do Marcos (28/09/2026):
// 1) coluna "Dia" editável (o dia do mês de gerar a nota — vira o evento
//    "Dia de gerar a nota" no Calendário), lista ordenada por esse dia e
//    acompanhamento do que já foi gerado no mês;
// 2) "ativo": desmarcar não some com o tomador, só manda ele pro fim da
//    lista, com outra cor;
// 3) "excluir": aí sim ele some (se já tiver nota, ela continua guardada).

type Aba = "meus" | "todos"

/** Dá pra emitir nota pra ele? Tem CNPJ, ou é de fora do Brasil com país + NIF.
 * Quem não tem nada disso nasceu "só controle" (um recebimento lançado no
 * financeiro, por exemplo) e ainda precisa dizer quem é. */
function identificado(v: VinculoResumo): boolean {
  return Boolean(v.tomador_cnpj) || Boolean(v.tomador_pais && v.tomador_nif)
}

function ordenar(lista: VinculoResumo[]): VinculoResumo[] {
  return [...lista].sort((a, b) => {
    const ia = a.ativo === false ? 1 : 0
    const ib = b.ativo === false ? 1 : 0
    if (ia !== ib) return ia - ib
    const da = a.dia_limite_emissao ?? 99
    const db = b.dia_limite_emissao ?? 99
    if (da !== db) return da - db
    return a.apelido.localeCompare(b.apelido, "pt-BR")
  })
}

type Situacao = "gerada" | "atrasada" | "hoje" | "pendente" | "sem_dia" | "inativo"

function situacao(v: VinculoResumo, competencia: string): Situacao {
  if (v.emissao_id) return "gerada"
  if (v.ativo === false || v.sem_nota) return "inativo"
  if (v.dia_limite_emissao == null) return "sem_dia"
  const atual = competenciaAtual()
  if (competencia < atual) return "atrasada"
  if (competencia > atual) return "pendente"
  const hoje = new Date().getDate()
  if (hoje > v.dia_limite_emissao) return "atrasada"
  if (hoje === v.dia_limite_emissao) return "hoje"
  return "pendente"
}

function BadgeSituacao({ v, competencia }: { v: VinculoResumo; competencia: string }) {
  const s = situacao(v, competencia)
  switch (s) {
    case "gerada":
      return (
        <Link to={(v.emissao_quantidade ?? 1) > 1 ? `/app/nfse` : `/app/nfse/${v.emissao_id}`} title="Abrir a nota">
          <Badge variant="success">
            {(v.emissao_quantidade ?? 1) > 1 ? `${v.emissao_quantidade} notas` : v.emissao_estado === "confirmado" ? "Emitida" : "Gerada"}
            {v.emissao_valor != null && <span className="font-normal">· {formatBRL(v.emissao_valor)}</span>}
          </Badge>
        </Link>
      )
    case "atrasada":
      return <Badge variant="danger">Não gerada</Badge>
    case "hoje":
      return <Badge variant="warning">Gerar hoje</Badge>
    case "pendente":
      return <Badge variant="info">Dia {v.dia_limite_emissao}</Badge>
    case "sem_dia":
      return <Badge variant="neutral">Sem dia definido</Badge>
    default:
      return <span className="text-xs text-slate-400">—</span>
  }
}

function Interruptor({ ligado, onChange, rotulo }: { ligado: boolean; onChange: (v: boolean) => void; rotulo: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      aria-label={rotulo}
      title={ligado ? "Ativo — clique para desativar" : "Inativo — clique para ativar"}
      onClick={() => onChange(!ligado)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
        ligado ? "bg-success-600" : "bg-slate-300 dark:bg-slate-600"
      }`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${ligado ? "translate-x-4" : "translate-x-0.5"}`} />
    </button>
  )
}

function CampoDia({ valor, onSalvar, desabilitado }: { valor: number | null; onSalvar: (dia: number | null) => void; desabilitado?: boolean }) {
  const [texto, setTexto] = useState(valor?.toString() ?? "")
  useEffect(() => setTexto(valor?.toString() ?? ""), [valor])

  function salvar() {
    const limpo = texto.trim()
    const novo = limpo === "" ? null : Math.min(31, Math.max(1, Number(limpo) || 1))
    if (novo !== valor) onSalvar(novo)
    setTexto(novo?.toString() ?? "")
  }

  return (
    <input
      type="number"
      inputMode="numeric"
      min={1}
      max={31}
      placeholder="—"
      value={texto}
      disabled={desabilitado}
      onChange={(e) => setTexto(e.target.value)}
      onBlur={salvar}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      title="Dia do mês de gerar a nota — aparece no Calendário"
      className="w-14 rounded-md border border-slate-200 bg-white px-2 py-1 text-center text-sm font-semibold text-slate-800 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
    />
  )
}

export function TomadoresPage() {
  const navigate = useNavigate()
  // Clientes "só controle" (sem nota) são fontes de receita do financeiro:
  // só aparecem aqui pra quem tem aquele módulo.
  const { financeiro } = useModulos()
  const [aba, setAba] = useState<Aba>("meus")
  const [busca, setBusca] = useState("")
  const [competencia, setCompetencia] = useState(competenciaAtual())
  const [vinculos, setVinculos] = useState<VinculoResumo[] | null>(null)
  const [tomadores, setTomadores] = useState<Tomador[] | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null)
  const [excluindo, setExcluindo] = useState<VinculoResumo | null>(null)
  // Conferência (05/10/2026): quantos pontos a Ana achou no cadastro de cada
  // tomador ativo — uma chamada só pra lista toda.
  const [conferencia, setConferencia] = useState<ConferenciaTomadores>({})
  useEffect(() => {
    if (aba !== "meus") return
    let cancelado = false
    api
      .get<ConferenciaTomadores>("/conferencia/tomadores")
      .then((c) => !cancelado && setConferencia(c))
      .catch(() => {
        // é só um selo a mais: sem ele a lista continua funcionando
      })
    return () => {
      cancelado = true
    }
  }, [aba])

  useEffect(() => {
    let cancelado = false
    setCarregando(true)
    const carregar =
      aba === "meus"
        ? api.get<VinculoResumo[]>(`/vinculos?todos=true&competencia=${competencia}`).then((v) => !cancelado && setVinculos(financeiro ? v : v.filter((x) => !x.sem_nota)))
        : api.get<Tomador[]>("/tomadores?apenas_meus=false").then((t) => !cancelado && setTomadores(t))
    carregar
      .catch((err) => !cancelado && setAviso({ tipo: "erro", texto: err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão." }))
      .finally(() => !cancelado && setCarregando(false))
    return () => {
      cancelado = true
    }
  }, [aba, competencia])

  async function atualizar(v: VinculoResumo, mudancas: Partial<VinculoResumo>) {
    const anterior = vinculos
    setVinculos((lista) => ordenar((lista ?? []).map((x) => (x.id === v.id ? { ...x, ...mudancas } : x))))
    try {
      await api.patch(`/vinculos/${v.id}`, mudancas)
    } catch (err) {
      setVinculos(anterior)
      setAviso({ tipo: "erro", texto: err instanceof ApiError ? formatarErro(err.detail) : "Não foi possível salvar." })
    }
  }

  async function confirmarExclusao() {
    if (!excluindo) return
    try {
      const resp = await api.delete<{ resultado: string; mensagem: string }>(`/vinculos/${excluindo.id}`)
      setVinculos((lista) => (lista ?? []).filter((x) => x.id !== excluindo.id))
      setAviso({ tipo: "ok", texto: resp.mensagem })
    } catch (err) {
      setAviso({ tipo: "erro", texto: err instanceof ApiError ? formatarErro(err.detail) : "Não foi possível excluir." })
    } finally {
      setExcluindo(null)
    }
  }

  const vinculosFiltrados = useMemo(() => {
    if (!vinculos) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return vinculos
    const digitos = termo.replace(/\D/g, "")
    return vinculos.filter(
      (v) =>
        v.apelido.toLowerCase().includes(termo) ||
        v.tomador_razao_social.toLowerCase().includes(termo) ||
        (digitos !== "" && v.tomador_cnpj.includes(digitos)) ||
        (v.tomador_nif ?? "").toLowerCase().includes(termo)
    )
  }, [vinculos, busca])

  const tomadoresFiltrados = useMemo(() => {
    if (!tomadores) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return tomadores
    const digitos = termo.replace(/\D/g, "")
    return tomadores.filter((t) => t.razao_social.toLowerCase().includes(termo) || (digitos !== "" && t.cnpj.includes(digitos)))
  }, [tomadores, busca])

  const resumo = useMemo(() => {
    // "Só controle" (sem_nota) não entra na conta de notas a gerar.
    const ativos = (vinculos ?? []).filter((v) => v.ativo !== false && !v.sem_nota)
    const gerados = ativos.filter((v) => v.emissao_id).length
    const atrasados = ativos.filter((v) => situacao(v, competencia) === "atrasada").length
    return { total: ativos.length, gerados, atrasados, faltam: ativos.length - gerados }
  }, [vinculos, competencia])

  const pct = resumo.total ? Math.round((resumo.gerados / resumo.total) * 100) : 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Tomadores</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Quem você fatura, em que dia do mês, e o que já foi gerado.</p>
        </div>
        <Link to="/app/tomadores/novo" data-tour="tomadores-adicionar">
          <Button variant="accent">
            <Plus size={16} /> Adicionar tomador
          </Button>
        </Link>
      </div>

      {aviso && (
        <div
          className={`flex items-start justify-between gap-3 rounded-lg px-4 py-3 text-sm ${
            aviso.tipo === "ok" ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300" : "bg-danger-50 text-danger-700"
          }`}
        >
          <span>{aviso.texto}</span>
          <button type="button" onClick={() => setAviso(null)} className="text-xs font-medium underline">
            fechar
          </button>
        </div>
      )}

      {aba === "meus" && vinculos && (
        <Card className="p-5" data-tour="tomadores-progresso">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm text-slate-500 dark:text-slate-400">Notas de {formatCompetenciaLonga(competencia)}</p>
              <p className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                {resumo.gerados} de {resumo.total} gerada{resumo.total === 1 ? "" : "s"}
                {resumo.atrasados > 0 && (
                  <span className="ml-2 text-sm font-medium text-danger-600">· {resumo.atrasados} passou do dia</span>
                )}
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <CalendarDays size={16} />
              <input
                type="month"
                value={competencia}
                onChange={(e) => e.target.value && setCompetencia(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div className="h-full rounded-full bg-gradient-to-r from-accent-400 to-primary-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </Card>
      )}

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex rounded-lg bg-slate-100 p-1 text-sm dark:bg-slate-700">
            {(["meus", "todos"] as Aba[]).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAba(a)}
                className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                  aba === a ? "bg-white text-primary-700 shadow-sm dark:bg-slate-800" : "text-slate-500 dark:text-slate-400"
                }`}
              >
                {a === "meus" ? "Meus tomadores" : "Todos os tomadores"}
              </button>
            ))}
          </div>
          <div className="relative w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por nome ou CNPJ..."
              className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
        </div>

        {carregando && <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

        {!carregando && aba === "meus" && (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 pr-3 font-medium" data-tour="tomadores-dia">Dia</th>
                  <th className="py-2 pr-3 font-medium">Tomador</th>
                  <th className="py-2 pr-3 font-medium" data-tour="tomadores-situacao">Neste mês</th>
                  <th className="py-2 pr-3 font-medium" data-tour="tomadores-ativo">Ativo</th>
                  <th className="py-2 text-right font-medium">Ações</th>
                </tr>
              </thead>
              <tbody>
                {vinculosFiltrados.map((v) => {
                  const inativo = v.ativo === false
                  return (
                    <tr
                      key={v.id}
                      className={`border-b border-slate-50 last:border-0 dark:border-slate-700/40 ${
                        inativo ? "bg-slate-50/80 text-slate-400 dark:bg-slate-900/40" : "hover:bg-slate-50 dark:hover:bg-slate-700/40"
                      }`}
                    >
                      <td className="py-2.5 pr-3">
                        <CampoDia valor={v.dia_limite_emissao ?? null} onSalvar={(dia) => atualizar(v, { dia_limite_emissao: dia })} />
                      </td>
                      <td className="py-2.5 pr-3">
                        <Link
                          to={`/app/tomadores/${v.id}`}
                          className={`font-medium hover:underline ${inativo ? "text-slate-500 dark:text-slate-400" : "text-primary-700 dark:text-primary-300"}`}
                        >
                          {v.apelido}
                        </Link>
                        {inativo && <span className="ml-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">inativo</span>}
                        {v.sem_nota &&
                          (identificado(v) ? (
                            <Link
                              to={`/app/tomadores/${v.id}`}
                              className="ml-2 align-middle"
                              title="Ainda falta configurar a nota deste tomador (código do serviço e descrição). Clique pra configurar — eu preencho com base na última nota dele."
                            >
                              <Badge variant="warning">Falta configurar a nota</Badge>
                            </Link>
                          ) : (
                            <span
                              className="ml-2 align-middle"
                              title="Você só controla o que este cliente paga — não emite nota pra ele por aqui. Se quiser emitir, clique em “Emitir nota pra este cliente”."
                            >
                              <Badge>Sem nota</Badge>
                            </span>
                          ))}
                        {!inativo && (conferencia[v.id]?.erros ?? 0) > 0 ? (
                          <Link
                            to={`/app/tomadores/${v.id}`}
                            className="ml-2 align-middle"
                            title="Achei dados errados no cadastro deste tomador: a nota sairia errada. Clique pra ver e corrigir."
                          >
                            <Badge variant="danger">{conferencia[v.id].erros} a corrigir</Badge>
                          </Link>
                        ) : !inativo && (conferencia[v.id]?.avisos ?? 0) > 0 ? (
                          <Link
                            to={`/app/tomadores/${v.id}`}
                            className="ml-2 align-middle"
                            title="Achei algo diferente no cadastro deste tomador. Clique pra conferir."
                          >
                            <Badge variant="warning">{conferencia[v.id].avisos} a conferir</Badge>
                          </Link>
                        ) : null}
                        <p className="text-xs text-slate-400 dark:text-slate-500">
                          {v.tomador_razao_social}
                          {documentoDoTomador({ cnpj: v.tomador_cnpj, nif: v.tomador_nif, pais: v.tomador_pais }) &&
                            ` · ${documentoDoTomador({ cnpj: v.tomador_cnpj, nif: v.tomador_nif, pais: v.tomador_pais })}`}
                        </p>
                      </td>
                      <td className="py-2.5 pr-3">
                        <BadgeSituacao v={v} competencia={competencia} />
                      </td>
                      <td className="py-2.5 pr-3">
                        <Interruptor ligado={!inativo} rotulo={`Ativo: ${v.apelido}`} onChange={(ligado) => atualizar(v, { ativo: ligado })} />
                      </td>
                      <td className="py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {v.sem_nota && identificado(v) && (
                            <Link
                              to={`/app/tomadores/${v.id}?emitir=1`}
                              className="inline-flex items-center gap-1 rounded-md bg-accent-50 px-2 py-1 text-xs font-semibold text-accent-700 hover:bg-accent-100 dark:bg-accent-900/30 dark:text-accent-200"
                              title="Configurar a nota deste tomador"
                            >
                              Configurar
                            </Link>
                          )}
                          {v.sem_nota && !identificado(v) && !inativo && (
                            <Link
                              to={`/app/tomadores/${v.id}?emitir=1`}
                              className="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-accent-50 px-2 py-1 text-xs font-semibold text-accent-700 hover:bg-accent-100 dark:bg-accent-900/30 dark:text-accent-200"
                              title="Hoje você só controla o que ele te paga. Clique pra me contar quem ele é (CNPJ, ou empresa de fora do Brasil) e passar a gerar nota pra ele."
                            >
                              <FilePlus2 size={14} /> Emitir nota pra este cliente
                            </Link>
                          )}
                          {!v.emissao_id && !inativo && !v.sem_nota && (
                            <button
                              type="button"
                              onClick={() => navigate(`/app/nfse?gerar=${v.id}&competencia=${competencia}`)}
                              className="inline-flex items-center gap-1 rounded-md bg-accent-50 px-2 py-1 text-xs font-semibold text-accent-700 hover:bg-accent-100 dark:bg-accent-900/30 dark:text-accent-200"
                              title="Gerar a nota deste mês"
                            >
                              <FilePlus2 size={14} /> Gerar
                            </button>
                          )}
                          <Link
                            to={`/app/tomadores/${v.id}`}
                            className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                            title="Editar"
                          >
                            <Pencil size={15} />
                          </Link>
                          <button
                            type="button"
                            onClick={() => setExcluindo(v)}
                            className="rounded-md p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
                            title="Excluir"
                            data-tour="tomadores-excluir"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {vinculosFiltrados.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-slate-400 dark:text-slate-500">
                      {busca ? "Nenhum tomador encontrado." : "Você ainda não tem tomadores. Clique em “Adicionar tomador” pra começar."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {!carregando && aba === "todos" && (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700/60 dark:text-slate-500">
                  <th className="py-2 font-medium">Razão social</th>
                  <th className="py-2 font-medium">CNPJ</th>
                  <th className="py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {tomadoresFiltrados.map((t) => (
                  <tr key={t.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:border-slate-700/40 dark:hover:bg-slate-700/50">
                    <td className="py-3 font-medium text-slate-800 dark:text-slate-200">{t.razao_social}</td>
                    <td className="py-3 text-slate-500 dark:text-slate-400">{t.cnpj ? formatarDocumento(t.cnpj) : "—"}</td>
                    <td className="py-3 text-right">
                      <Link to={`/app/tomadores/novo?tomador_id=${t.id}`} className="text-sm font-medium text-primary-600 hover:text-primary-700">
                        Usar este tomador
                      </Link>
                    </td>
                  </tr>
                ))}
                {tomadoresFiltrados.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 dark:text-slate-500">
                      Nenhum tomador no catálogo ainda.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {excluindo && (
        <Modal titulo="Excluir tomador" onClose={() => setExcluindo(null)}>
          <div className="flex flex-col gap-4 text-sm text-slate-600 dark:text-slate-300">
            <p>
              Excluir <strong>{excluindo.apelido}</strong> da sua lista? Ele some daqui e do calendário.
            </p>
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:bg-slate-900/40 dark:text-slate-400">
              As notas já geradas pra ele continuam guardadas na aba NFS-e. Se você só quer parar de faturar por um tempo, é
              melhor desmarcar “Ativo”.
            </p>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setExcluindo(null)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" onClick={confirmarExclusao}>
                <Trash2 size={15} /> Excluir
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
