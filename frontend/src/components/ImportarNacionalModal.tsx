import {
  AlertTriangle,
  CheckCircle2,
  DownloadCloud,
  Eye,
  Loader2,
  MailCheck,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatarDocumento } from "../lib/documento"
import { formatBRL, formatCompetenciaAbrev } from "../lib/format"
import type { AcaoImportacao, GrupoImportacao, PreviaNacional, RegraImportacao, ResultadoNacional, VinculoResumo } from "../lib/types"
import { Badge } from "./ui/Badge"
import { Button } from "./ui/Button"
import { Modal } from "./ui/Modal"

// "Você consegue importar do Emissor Nacional?" (28/09/2026) — lê com o
// certificado da empresa, no ADN, as NFS-e que ela EMITIU (por qualquer
// emissor), agrupa por tomador e a pessoa decide pra onde vai cada grupo:
// tomador já cadastrado, notas avulsas de um marketplace (Shopee), tomador
// novo ou não importar. Ver backend/app/services/importar_adn.py.

type Fase = "carregando" | "intro" | "buscando" | "revisao" | "importando" | "resultado"

interface Regra {
  acao: AcaoImportacao
  vinculo_id: string | null
}

interface Erro {
  mensagem: string
  certificado?: boolean
}

const SELECT =
  "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

function padrao(g: GrupoImportacao): Regra {
  if ((g.sugestao === "vinculo" || g.sugestao === "avulsa") && g.vinculo_id) return { acao: g.sugestao, vinculo_id: g.vinculo_id }
  return { acao: "novo", vinculo_id: null }
}

function valorSelect(r: Regra): string {
  if (r.acao === "vinculo" || r.acao === "avulsa") return `${r.acao}:${r.vinculo_id ?? ""}`
  return r.acao
}

function regraDoSelect(valor: string): Regra {
  const [acao, id] = valor.split(":") as [AcaoImportacao, string | undefined]
  return { acao, vinculo_id: id || null }
}

function documentoLegivel(g: GrupoImportacao): string {
  if (g.documento === "sem-documento") return "Sem documento"
  if (g.tipo === "NIF") return `NIF ${g.documento} (exterior)`
  return formatarDocumento(g.documento)
}

function competenciaCurta(c: string): string {
  return `${formatCompetenciaAbrev(c).toLowerCase()}/${c.slice(0, 4)}`
}

function faixaCompetencias(lista: string[]): string {
  const validas = lista.filter((c) => /^\d{4}-\d{2}$/.test(c)).sort()
  if (validas.length === 0) return "—"
  const [primeira, ultima] = [validas[0], validas[validas.length - 1]]
  return primeira === ultima ? competenciaCurta(primeira) : `${competenciaCurta(primeira)} – ${competenciaCurta(ultima)}`
}

function mensagemDe(err: unknown): Erro {
  if (err instanceof ApiError) {
    const mensagem = formatarErro(err.detail)
    return { mensagem, certificado: (err.status === 409 || err.status === 502) && /certificado/i.test(mensagem) }
  }
  return { mensagem: "Falha de conexão. Confira a internet e tente de novo." }
}

const semCadastro = (g: GrupoImportacao) => g.sugestao === "novo"
const pessoaOuExterior = (g: GrupoImportacao) => g.tipo !== "CNPJ"

export function ImportarNacionalModal({ onClose, onConcluido }: { onClose: () => void; onConcluido: () => void }) {
  const [fase, setFase] = useState<Fase>("carregando")
  const [previa, setPrevia] = useState<PreviaNacional | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [regras, setRegras] = useState<Record<string, Regra>>({})
  const [erro, setErro] = useState<Erro | null>(null)
  const [parando, setParando] = useState(false)
  const [resultado, setResultado] = useState<ResultadoNacional | null>(null)

  // Filtros e ação em massa da revisão.
  const [busca, setBusca] = useState("")
  const [soSemCadastro, setSoSemCadastro] = useState(false)
  const [escopoMassa, setEscopoMassa] = useState<"sem_cadastro" | "pessoas">("sem_cadastro")
  const [destinoEscolhido, setDestinoMassa] = useState("")

  const montado = useRef(true)
  const parar = useRef(false)
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
      parar.current = true
    }
  }, [])

  // Grupos novos que chegam durante a leitura ganham a sugestão; o que a
  // pessoa já mudou fica como está.
  const receber = useCallback((p: PreviaNacional) => {
    setPrevia(p)
    setRegras((atual) => {
      const nova = { ...atual }
      p.grupos.forEach((g) => {
        if (!(g.documento in nova)) nova[g.documento] = padrao(g)
      })
      return nova
    })
  }, [])

  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos?todos=true").then((v) => montado.current && setVinculos(v)).catch(() => {})
    api
      .get<PreviaNacional>("/importar/nacional")
      .then((p) => {
        if (!montado.current) return
        receber(p)
        setFase(p.grupos.length > 0 ? "revisao" : "intro")
      })
      .catch(() => montado.current && setFase("intro"))
  }, [receber])

  const vinculosOrdenados = useMemo(
    () => [...vinculos].sort((a, b) => a.apelido.localeCompare(b.apelido, "pt-BR")),
    [vinculos],
  )
  const apelidoPorId = useMemo(() => new Map(vinculos.map((v) => [v.id, v.apelido])), [vinculos])

  // Marketplace provável pra ação em massa: o que a Ana mais sugeriu como
  // "avulsa"; senão o tomador com relatório em planilha (Shopee).
  const marketplacePadrao = useMemo(() => {
    const contagem = new Map<string, number>()
    previa?.grupos.forEach((g) => g.sugestao === "avulsa" && g.vinculo_id && contagem.set(g.vinculo_id, (contagem.get(g.vinculo_id) ?? 0) + 1))
    const maisUsado = [...contagem.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
    return maisUsado ?? vinculos.find((v) => v.metodo_captura_valor === "csv")?.id ?? ""
  }, [previa, vinculos])
  const destinoMassa = destinoEscolhido || (marketplacePadrao ? `avulsa:${marketplacePadrao}` : "")

  async function buscar(modo: "continuar" | "recomecar" | "desde_inicio") {
    parar.current = false
    setParando(false)
    setErro(null)
    setFase("buscando")
    let corpo: Record<string, boolean> = modo === "desde_inicio" ? { desde_inicio: true } : modo === "recomecar" ? { recomecar: true } : {}
    if (modo !== "continuar") setRegras({})
    let ultima: PreviaNacional | null = null
    try {
      for (;;) {
        const p = await api.post<PreviaNacional>("/importar/nacional/buscar", corpo)
        corpo = {}
        if (!montado.current) return
        receber(p)
        ultima = p
        if (p.terminou || parar.current) break
      }
      setFase("revisao")
    } catch (err) {
      if (!montado.current) return
      setErro(mensagemDe(err))
      setFase((ultima ?? previa)?.grupos.length ? "revisao" : "intro")
    } finally {
      if (montado.current) setParando(false)
    }
  }

  const grupos = useMemo(() => previa?.grupos ?? [], [previa])

  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase()
    const digitos = termo.replace(/\D/g, "")
    return grupos.filter((g) => {
      if (soSemCadastro && !semCadastro(g)) return false
      if (!termo) return true
      return (
        g.nome.toLowerCase().includes(termo) ||
        (digitos.length > 0 && g.documento.includes(digitos)) ||
        (g.intermediario ?? "").toLowerCase().includes(termo) ||
        (g.descricao_exemplo ?? "").toLowerCase().includes(termo)
      )
    })
  }, [grupos, busca, soSemCadastro])

  const alvoMassa = useMemo(
    () => visiveis.filter((g) => semCadastro(g) && (escopoMassa === "sem_cadastro" || pessoaOuExterior(g))),
    [visiveis, escopoMassa],
  )

  function aplicarEmMassa() {
    if (!destinoMassa || alvoMassa.length === 0) return
    const regra = regraDoSelect(destinoMassa)
    setRegras((atual) => {
      const nova = { ...atual }
      alvoMassa.forEach((g) => (nova[g.documento] = regra))
      return nova
    })
  }

  // Mesmo CNPJ com mais de um tomador aqui (ex.: AWIN e AWIN Rchlo).
  const irmaosPorCnpj = useMemo(() => {
    const mapa = new Map<string, string[]>()
    vinculos.forEach((v) => v.tomador_cnpj && mapa.set(v.tomador_cnpj, [...(mapa.get(v.tomador_cnpj) ?? []), v.apelido]))
    return mapa
  }, [vinculos])

  const totais = useMemo(() => {
    let notas = 0
    let valor = 0
    let canceladas = 0
    let novos = 0
    let ignorados = 0
    grupos.forEach((g) => {
      const r = regras[g.documento] ?? padrao(g)
      if (r.acao === "ignorar") {
        ignorados += 1
        return
      }
      notas += g.quantidade
      valor += g.total
      canceladas += g.canceladas
      if (r.acao === "novo") novos += 1
    })
    return { notas, valor, canceladas, novos, ignorados }
  }, [grupos, regras])

  const semDestino = grupos.filter((g) => {
    const r = regras[g.documento] ?? padrao(g)
    return (r.acao === "vinculo" || r.acao === "avulsa") && !r.vinculo_id
  })

  async function importar() {
    setErro(null)
    setFase("importando")
    const mapeamento: RegraImportacao[] = grupos.map((g) => {
      const r = regras[g.documento] ?? padrao(g)
      return { documento: g.documento, acao: r.acao, vinculo_id: r.acao === "vinculo" || r.acao === "avulsa" ? r.vinculo_id : null }
    })
    try {
      const res = await api.post<ResultadoNacional>("/importar/nacional", { mapeamento })
      if (!montado.current) return
      setResultado(res)
      setFase("resultado")
    } catch (err) {
      if (!montado.current) return
      const e = mensagemDe(err)
      setErro(e)
      // 409 sem ser de certificado = a prévia expirou no servidor: ler de novo.
      setFase(err instanceof ApiError && err.status === 409 && !e.certificado ? "intro" : "revisao")
    }
  }

  function fechar() {
    parar.current = true
    if (resultado) onConcluido()
    onClose()
  }

  return (
    <Modal titulo="Importar do Emissor Nacional" onClose={fechar} largura="max-w-4xl">
      {erro && (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <p>{erro.mensagem}</p>
            {erro.certificado && (
              <Link to="/app/empresa?aba=certificado" className="mt-1 inline-block font-semibold underline">
                Carregar o certificado
              </Link>
            )}
          </div>
        </div>
      )}

      {fase === "carregando" && (
        <p className="flex items-center justify-center gap-2 py-10 text-sm text-slate-400 dark:text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Carregando...
        </p>
      )}

      {fase === "intro" && <Intro previa={previa} onBuscar={buscar} temErro={Boolean(erro)} onClose={fechar} />}

      {fase === "buscando" && (
        <div className="flex flex-col items-center gap-4 py-8 text-center" aria-live="polite">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300">
            <DownloadCloud size={22} className="animate-pulse" />
          </div>
          <div>
            <p className="font-medium text-slate-800 dark:text-slate-100">
              {parando ? "Parando depois deste pedaço..." : "Lendo as notas no Emissor Nacional..."}
            </p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              NSU {(previa?.nsu ?? 0).toLocaleString("pt-BR")} · {previa?.total_notas ?? 0} nota{previa?.total_notas === 1 ? "" : "s"}{" "}
              encontrada{previa?.total_notas === 1 ? "" : "s"}
              {previa && previa.grupos.length > 0 && ` · ${previa.grupos.length} tomador${previa.grupos.length === 1 ? "" : "es"}`}
            </p>
          </div>
          <div className="h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div className="h-full w-1/3 animate-[importar-barra_1.4s_ease-in-out_infinite] rounded-full motion-reduce:animate-none bg-gradient-to-r from-accent-400 to-primary-600" />
          </div>
          <style>{"@keyframes importar-barra{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}"}</style>
          <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
            Pode levar alguns minutos se a empresa emite muitas notas. Dá pra parar e revisar o que já foi lido.
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={parando}
            onClick={() => {
              parar.current = true
              setParando(true)
            }}
          >
            <Square size={14} /> Parar
          </Button>
        </div>
      )}

      {fase === "importando" && (
        <p className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500 dark:text-slate-400" aria-live="polite">
          <Loader2 size={16} className="animate-spin" /> Importando {totais.notas} nota{totais.notas === 1 ? "" : "s"}...
        </p>
      )}

      {fase === "resultado" && resultado && <Resultado resultado={resultado} onFechar={fechar} />}

      {fase === "revisao" && previa && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
            <span>
              <strong className="text-slate-900 dark:text-slate-100">{previa.total_notas}</strong> nota{previa.total_notas === 1 ? "" : "s"} nova
              {previa.total_notas === 1 ? "" : "s"} de <strong className="text-slate-900 dark:text-slate-100">{grupos.length}</strong> tomador
              {grupos.length === 1 ? "" : "es"}
            </span>
            {previa.ja_importadas > 0 && <span className="text-slate-400 dark:text-slate-500">· {previa.ja_importadas} já estavam aqui</span>}
            {previa.recebidas > 0 && (
              <span className="text-slate-400 dark:text-slate-500" title="Notas de serviços que a empresa comprou — não entram">
                · {previa.recebidas} recebida{previa.recebidas === 1 ? "" : "s"} (de fora)
              </span>
            )}
            <span className="ml-auto flex flex-wrap gap-2">
              {previa.terminou ? (
                <Button type="button" variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => buscar("recomecar")}>
                  <RotateCcw size={13} /> Ler de novo
                </Button>
              ) : (
                <Button type="button" variant="outline" className="px-2.5 py-1 text-xs" onClick={() => buscar("continuar")}>
                  <DownloadCloud size={13} /> Continuar lendo
                </Button>
              )}
            </span>
          </div>

          {!previa.terminou && (
            <p className="rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
              A leitura parou no NSU {previa.nsu.toLocaleString("pt-BR")} — pode faltar nota. Dá pra importar o que já veio e continuar
              depois.
            </p>
          )}

          {grupos.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <CheckCircle2 size={28} className="text-success-600" aria-hidden />
              <p className="font-medium text-slate-800 dark:text-slate-100">Nenhuma nota nova pra importar.</p>
              <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
                Tudo o que a empresa emitiu no Emissor Nacional desde a última importação já está aqui.
              </p>
              <Button type="button" variant="ghost" onClick={() => buscar("desde_inicio")}>
                <RotateCcw size={15} /> Buscar desde o início
              </Button>
            </div>
          ) : (
            <>
              {/* Filtros */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative min-w-0 flex-1 basis-56">
                  <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
                  <input
                    value={busca}
                    onChange={(e) => setBusca(e.target.value)}
                    placeholder="Buscar nome, CPF/CNPJ, descrição..."
                    aria-label="Buscar tomador na importação"
                    className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={soSemCadastro}
                    onChange={(e) => setSoSemCadastro(e.target.checked)}
                    className="h-4 w-4 accent-primary-600"
                  />
                  Só os sem tomador cadastrado ({grupos.filter(semCadastro).length})
                </label>
              </div>

              {/* Ação em massa — pensada pras dezenas de vendedores da Shopee. */}
              {grupos.some(semCadastro) && (
                <div className="flex flex-wrap items-end gap-2 rounded-xl border border-primary-100 bg-primary-50/60 px-3 py-3 dark:border-primary-900/40 dark:bg-primary-900/20">
                  <label className="flex min-w-0 flex-1 basis-48 flex-col gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
                    Aplicar a
                    <select value={escopoMassa} onChange={(e) => setEscopoMassa(e.target.value as "sem_cadastro" | "pessoas")} className={SELECT}>
                      <option value="sem_cadastro">Todos os sem cadastro{busca || soSemCadastro ? " (visíveis)" : ""}</option>
                      <option value="pessoas">Só CPF/exterior sem cadastro{busca || soSemCadastro ? " (visíveis)" : ""}</option>
                    </select>
                  </label>
                  <label className="flex min-w-0 flex-1 basis-56 flex-col gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
                    Destino
                    <select value={destinoMassa} onChange={(e) => setDestinoMassa(e.target.value)} className={SELECT}>
                      <option value="" disabled>
                        Escolha...
                      </option>
                      {vinculosOrdenados.length > 0 && (
                        <optgroup label="Como notas avulsas de">
                          {vinculosOrdenados.map((v) => (
                            <option key={v.id} value={`avulsa:${v.id}`}>
                              Avulsas de {v.apelido}
                            </option>
                          ))}
                        </optgroup>
                      )}
                      <option value="novo">Criar tomador novo pra cada um</option>
                      <option value="ignorar">Não importar</option>
                    </select>
                  </label>
                  <Button type="button" variant="outline" className="bg-white py-1.5 dark:bg-slate-800" disabled={!destinoMassa || alvoMassa.length === 0} onClick={aplicarEmMassa}>
                    Aplicar a {alvoMassa.length}
                  </Button>
                </div>
              )}

              {/* Grupos — linhas de tabela no computador, cartões no celular. */}
              <div className="-mx-5 border-y border-slate-100 dark:border-slate-700/60">
                <div className="hidden grid-cols-[minmax(0,1fr)_9.5rem_15rem] gap-4 bg-slate-50 px-5 py-2 text-xs font-medium uppercase tracking-wide text-slate-400 md:grid dark:bg-slate-900/40 dark:text-slate-500">
                  <span>Tomador na nota</span>
                  <span>Notas</span>
                  <span>Importar para</span>
                </div>
                <ul className="max-h-[52vh] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-700/60">
                  {visiveis.map((g) => (
                    <LinhaGrupo
                      key={g.documento}
                      grupo={g}
                      regra={regras[g.documento] ?? padrao(g)}
                      vinculos={vinculosOrdenados}
                      apelidoPorId={apelidoPorId}
                      irmaos={irmaosPorCnpj.get(g.documento)}
                      onChange={(r) => setRegras((atual) => ({ ...atual, [g.documento]: r }))}
                    />
                  ))}
                  {visiveis.length === 0 && (
                    <li className="px-5 py-8 text-center text-sm text-slate-400 dark:text-slate-500">Nenhum tomador com esse filtro.</li>
                  )}
                </ul>
              </div>

              {/* Totais + confirmar */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-slate-600 dark:text-slate-300" aria-live="polite">
                  <p>
                    Vão entrar <strong className="text-slate-900 dark:text-slate-100">{totais.notas}</strong> nota{totais.notas === 1 ? "" : "s"} ·{" "}
                    <strong className="text-slate-900 dark:text-slate-100">{formatBRL(totais.valor)}</strong>
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {[
                      totais.novos > 0 && `${totais.novos} tomador${totais.novos === 1 ? "" : "es"} novo${totais.novos === 1 ? "" : "s"}`,
                      totais.canceladas > 0 && `${totais.canceladas} cancelada${totais.canceladas === 1 ? "" : "s"} (entram como canceladas)`,
                      totais.ignorados > 0 && `${totais.ignorados} tomador${totais.ignorados === 1 ? "" : "es"} de fora`,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "Entram como já entregues ao tomador — nada é enviado."}
                  </p>
                  {semDestino.length > 0 && (
                    <p className="text-xs text-danger-600 dark:text-danger-300">Escolha o tomador de destino de {semDestino[0].nome}.</p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="ghost" onClick={fechar}>
                    Cancelar
                  </Button>
                  <Button type="button" variant="accent" disabled={totais.notas === 0 || semDestino.length > 0} onClick={importar}>
                    <DownloadCloud size={16} /> Importar {totais.notas} nota{totais.notas === 1 ? "" : "s"}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </Modal>
  )
}

function Intro({
  previa,
  onBuscar,
  temErro,
  onClose,
}: {
  previa: PreviaNacional | null
  onBuscar: (modo: "continuar" | "recomecar" | "desde_inicio") => void
  temErro: boolean
  onClose: () => void
}) {
  const itens = [
    {
      Icone: ShieldCheck,
      texto: "A Ana usa o certificado digital da empresa pra ler, no Emissor Nacional, as NFS-e que ela emitiu — pelo portal ou por outro sistema.",
    },
    { Icone: Eye, texto: "É só leitura: nada é enviado à prefeitura nem aos tomadores." },
    {
      Icone: Sparkles,
      texto: "Antes de gravar, você revisa pra qual tomador vai cada grupo de notas (a Ana já sugere).",
    },
    { Icone: MailCheck, texto: "As notas importadas entram como já entregues ao tomador — não viram pendência de envio." },
  ]
  return (
    <div className="flex flex-col gap-5">
      <ul className="flex flex-col gap-3">
        {itens.map(({ Icone, texto }) => (
          <li key={texto} className="flex items-start gap-3 text-sm text-slate-600 dark:text-slate-300">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300">
              <Icone size={16} aria-hidden />
            </span>
            <span className="pt-1.5">{texto}</span>
          </li>
        ))}
      </ul>
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:bg-slate-900/40 dark:text-slate-400">
        Precisa do certificado A1 carregado em Empresa › Certificado.
        {previa && previa.nsu > 0 && ` A leitura continua de onde parou da última vez (NSU ${previa.nsu.toLocaleString("pt-BR")}).`}
      </p>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button type="button" variant="ghost" onClick={() => onBuscar("desde_inicio")} title="Relê tudo desde a primeira nota — use se faltou alguma">
          <RotateCcw size={15} /> Buscar desde o início
        </Button>
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="button" variant="accent" onClick={() => onBuscar(previa?.terminou ? "recomecar" : "continuar")}>
            <DownloadCloud size={16} /> {temErro ? "Tentar de novo" : "Buscar notas"}
          </Button>
        </div>
      </div>
    </div>
  )
}

function LinhaGrupo({
  grupo: g,
  regra,
  vinculos,
  apelidoPorId,
  irmaos,
  onChange,
}: {
  grupo: GrupoImportacao
  regra: Regra
  vinculos: VinculoResumo[]
  apelidoPorId: Map<string, string>
  irmaos?: string[]
  onChange: (r: Regra) => void
}) {
  const valor = valorSelect(regra)
  const sugerida = valorSelect(padrao(g)) === valor
  const desconhecido = (regra.acao === "vinculo" || regra.acao === "avulsa") && regra.vinculo_id && !apelidoPorId.has(regra.vinculo_id)

  let dica: string | null = null
  if (regra.acao === "novo") {
    dica =
      g.tipo === "CNPJ"
        ? "Cadastra o tomador com o código e a descrição das notas."
        : "Cria um tomador só de controle (a Ana não gera nota pra ele)."
  } else if (regra.acao === "vinculo" && irmaos && irmaos.length > 1) {
    dica = `Mesmo CNPJ em ${irmaos.join(", ")}: cada nota vai pro da descrição mais parecida.`
  } else if (regra.acao === "avulsa") {
    dica = "Cada nota fica como avulsa, com o vendedor como tomador."
  }

  return (
    <li className="grid grid-cols-1 gap-2 px-5 py-3 md:grid-cols-[minmax(0,1fr)_9.5rem_15rem] md:gap-4">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-slate-800 dark:text-slate-100">{g.nome}</span>
          {g.canceladas > 0 && <Badge>{g.canceladas} cancelada{g.canceladas === 1 ? "" : "s"}</Badge>}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {documentoLegivel(g)}
          {g.intermediario && <span className="text-slate-400 dark:text-slate-500"> · via {g.intermediario}</span>}
        </p>
        {g.descricao_exemplo && (
          <p className="mt-0.5 truncate text-xs italic text-slate-400 dark:text-slate-500" title={g.descricao_exemplo}>
            “{g.descricao_exemplo}”
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-2 text-sm md:flex-col md:gap-0">
        <span className="font-semibold text-slate-800 dark:text-slate-100">{formatBRL(g.total)}</span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {g.quantidade} nota{g.quantidade === 1 ? "" : "s"} · {faixaCompetencias(g.competencias)}
        </span>
      </div>
      <div className="min-w-0">
        <select
          value={valor}
          onChange={(e) => onChange(regraDoSelect(e.target.value))}
          aria-label={`Importar as notas de ${g.nome} para`}
          className={`${SELECT} ${regra.acao === "ignorar" ? "text-slate-400 dark:text-slate-500" : ""}`}
        >
          {vinculos.length > 0 && (
            <optgroup label="Para o tomador cadastrado">
              {vinculos.map((v) => (
                <option key={v.id} value={`vinculo:${v.id}`}>
                  {v.apelido}
                </option>
              ))}
            </optgroup>
          )}
          {vinculos.length > 0 && (
            <optgroup label="Como notas avulsas de">
              {vinculos.map((v) => (
                <option key={v.id} value={`avulsa:${v.id}`}>
                  Avulsas de {v.apelido}
                </option>
              ))}
            </optgroup>
          )}
          {desconhecido && <option value={valor}>Tomador cadastrado</option>}
          <option value="novo">Criar tomador novo</option>
          <option value="ignorar">Não importar</option>
        </select>
        {(dica || sugerida) && (
          <p className="mt-1 text-[11px] leading-snug text-slate-400 dark:text-slate-500">
            {sugerida && regra.acao !== "novo" && (
              <span className="mr-1 inline-flex items-center gap-0.5 font-medium text-accent-700 dark:text-accent-300">
                <Sparkles size={11} aria-hidden /> Sugestão da Ana.
              </span>
            )}
            {dica}
          </p>
        )}
      </div>
    </li>
  )
}

function Resultado({ resultado, onFechar }: { resultado: ResultadoNacional; onFechar: () => void }) {
  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <div className="flex items-start gap-3">
        <CheckCircle2 size={24} className="mt-0.5 shrink-0 text-success-600" aria-hidden />
        <div>
          <p className="font-medium text-slate-800 dark:text-slate-100">
            {resultado.importadas} nota{resultado.importadas === 1 ? "" : "s"} importada{resultado.importadas === 1 ? "" : "s"}
            {resultado.vinculos_criados > 0 &&
              ` · ${resultado.vinculos_criados} tomador${resultado.vinculos_criados === 1 ? "" : "es"} criado${resultado.vinculos_criados === 1 ? "" : "s"}`}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Elas já aparecem na lista de NFS-e, como entregues ao tomador. Tomadores novos sem nota recente entram como inativos.
          </p>
        </div>
      </div>
      {resultado.puladas.length > 0 && (
        <div>
          <p className="mb-1.5 text-sm font-medium text-warning-700 dark:text-warning-300">
            {resultado.puladas.length} nota{resultado.puladas.length === 1 ? "" : "s"} ficou de fora:
          </p>
          <ul className="max-h-60 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-100 text-xs dark:divide-slate-700/60 dark:border-slate-700/60">
            {resultado.puladas.map((p, i) => (
              <li key={`${p.chave}-${i}`} className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:gap-3">
                <span className="shrink-0 font-mono text-slate-400 dark:text-slate-500" title={p.chave ?? undefined}>
                  {p.chave ? `…${p.chave.slice(-10)}` : "—"}
                </span>
                <span className="text-slate-600 dark:text-slate-300">{p.motivo}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex justify-end">
        <Button type="button" variant="accent" onClick={onFechar}>
          Fechar
        </Button>
      </div>
    </div>
  )
}
