import { AlertTriangle, ArrowLeft, CheckCircle2, Clock, FileCheck2, FileUp, Landmark, Minus } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { ConciliacaoExtrato } from "../components/financeiro/ConciliacaoExtrato"
import { ConciliacaoNotas, type FiltroNotas, ehFiltroNotas } from "../components/financeiro/ConciliacaoNotas"
import { ImportarExtratoModal } from "../components/financeiro/ImportarExtratoModal"
import { ImportacoesFeitas } from "../components/ImportacoesFeitas"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { api } from "../lib/api"
import { NOMES_MESES } from "../lib/financeiro"
import type { FechamentoDoMes, ResumoConciliacao, VinculoResumo } from "../lib/types"

/** Conciliação (05/10/2026) — pedido do Marcos: "existem duas conciliações
 * que devem ser feitas. Uma é na importação do extrato. E a segunda, mais
 * importante, é se as notas geradas foram pagas. Isso é importante de
 * aparecer de forma bem clara nesse ambiente de conciliação."
 *
 * A tela tem as duas partes, com nome e estado próprios, a das notas
 * primeiro:
 *   1. "As notas foram pagas?"            (?parte=notas)   components/financeiro/ConciliacaoNotas
 *   2. "O extrato está todo classificado?" (?parte=extrato) components/financeiro/ConciliacaoExtrato
 * e, juntando as duas, o "Fechamento do mês". Outras telas ligam direto na
 * parte certa pelo endereço (?parte=..., e ?filtro=atrasadas etc. na 1). */

type Parte = "notas" | "extrato"

const nomeDoMes = (competencia: string) => NOMES_MESES[Number(competencia.slice(5)) - 1]
const plural = (n: number, um: string, varios: string) => `${n.toLocaleString("pt-BR")} ${n === 1 ? um : varios}`

function Fechamento({ mes, comNotas, onIr }: { mes: FechamentoDoMes; comNotas: boolean; onIr: (parte: Parte) => void }) {
  const ESTADOS = {
    fechado: { rotulo: "Fechado", cor: "text-success-700 dark:text-success-300", fundo: "border-success-100 bg-success-50/60 dark:border-success-900/40 dark:bg-success-900/20", Icone: CheckCircle2 },
    aguardando: { rotulo: "Aguardando pagamento", cor: "text-primary-700 dark:text-primary-300", fundo: "border-primary-100 bg-primary-50/60 dark:border-primary-900/40 dark:bg-primary-900/20", Icone: Clock },
    pendente: { rotulo: "Falta conferir", cor: "text-warning-700 dark:text-warning-300", fundo: "border-warning-100 bg-warning-50/70 dark:border-warning-900/40 dark:bg-warning-900/20", Icone: AlertTriangle },
    vazio: { rotulo: "Nada lançado", cor: "text-slate-500 dark:text-slate-400", fundo: "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60", Icone: Minus },
  } as const
  const e = ESTADOS[mes.estado]
  // As notas em lote (Shopee + vendedores) contam como uma só — senão centenas
  // de notinhas escondem as poucas que a pessoa precisa acompanhar.
  const emLote = mes.notas_em_lote ? ` · o lote de ${mes.notas_em_lote.toLocaleString("pt-BR")} vendedores conta como 1` : ""
  const notas =
    (mes.notas === 0
      ? "nenhuma nota"
      : mes.notas_pagas === mes.notas
        ? `${plural(mes.notas, "nota paga", "notas pagas")}${mes.diferencas > 0 ? ` · ${mes.diferencas} com diferença` : ""}`
        : `${mes.notas_pagas} de ${plural(mes.notas, "nota paga", "notas pagas")}${mes.notas_atrasadas > 0 ? ` · ${plural(mes.notas_atrasadas, "atrasada", "atrasadas")}` : ""}`) + emLote
  const extrato =
    mes.extrato_linhas === 0
      ? "nenhum extrato importado"
      : mes.extrato_pendentes === 0
        ? `${plural(mes.extrato_linhas, "linha classificada", "linhas classificadas")}`
        : `${plural(mes.extrato_pendentes, "linha", "linhas")} sem classificar`
  const linha = (rotulo: string, texto: string, ok: boolean, parte: Parte) => (
    <button type="button" onClick={() => onIr(parte)} className="flex w-full items-baseline gap-1.5 text-left text-xs hover:underline">
      <span className={`h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full ${ok ? "bg-success-600" : "bg-warning-600"}`} aria-hidden />
      <span className="text-slate-500 dark:text-slate-400">{rotulo}:</span>
      <span className="text-slate-700 dark:text-slate-200">{texto}</span>
    </button>
  )
  return (
    <div className={`min-w-[15.5rem] shrink-0 rounded-xl border px-3.5 py-3 sm:min-w-0 sm:flex-1 sm:shrink sm:basis-56 ${e.fundo}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          {nomeDoMes(mes.competencia)}
          {mes.em_andamento && <span className="block text-[11px] font-normal leading-tight text-slate-500 dark:text-slate-400">mês em andamento</span>}
        </p>
        <span className={`inline-flex items-center gap-1 text-xs font-semibold ${e.cor}`}>
          <e.Icone size={14} aria-hidden /> {e.rotulo}
        </span>
      </div>
      <div className="mt-1.5 flex flex-col gap-0.5">
        {comNotas && linha("Notas", notas, mes.notas_atrasadas === 0 && mes.diferencas === 0, "notas")}
        {linha("Extrato", extrato, mes.extrato_pendentes === 0, "extrato")}
      </div>
    </div>
  )
}

export function ConciliacaoPage() {
  const [params, setParams] = useSearchParams()
  const [resumo, setResumo] = useState<ResumoConciliacao | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [importando, setImportando] = useState(false)
  const [recarga, setRecarga] = useState(0)

  const carregarResumo = () =>
    api
      .get<ResumoConciliacao>("/conciliacao/resumo")
      .then((r) => {
        setResumo(r)
        // o selo do menu acompanha (components/layout/Sidebar.tsx)
        window.dispatchEvent(new CustomEvent("agenteana:conciliacao", { detail: { notas: r.notas.aplica ? r.notas.pendencias : 0, extrato: r.extrato.pendentes } }))
      })
      .catch(() => undefined)
  const carregarVinculos = () => api.get<VinculoResumo[]>("/vinculos").then(setVinculos).catch(() => undefined)

  useEffect(() => {
    void carregarResumo()
    void carregarVinculos()
  }, [])

  // A parte aberta mora no endereço (?parte=notas | extrato), pra outras telas
  // ligarem direto. Sem nada no endereço: as notas — a mais importante — ou o
  // extrato quando a empresa não tem nota nenhuma pra conferir.
  const pedida = params.get("parte")
  const semNotas = resumo !== null && !resumo.notas.aplica
  const parte: Parte = pedida === "extrato" || pedida === "notas" ? pedida : semNotas ? "extrato" : "notas"
  const filtroInicial = ehFiltroNotas(params.get("filtro")) ? (params.get("filtro") as FiltroNotas) : undefined

  function irPara(nova: Parte) {
    setParams(nova === "notas" ? { parte: "notas" } : { parte: "extrato" }, { replace: true })
  }

  const estadoNotas = resumo?.notas
  const estadoExtrato = resumo?.extrato

  const aba = (qual: Parte, numero: number, Icone: typeof FileCheck2, titulo: string, explicacao: string, estado: { ok: boolean; texto: string; neutro?: boolean } | null) => {
    const ativa = parte === qual
    return (
      <button
        type="button"
        role="tab"
        id={`aba-${qual}`}
        aria-selected={ativa}
        aria-controls={`parte-${qual}`}
        onClick={() => irPara(qual)}
        className={`flex flex-1 basis-72 items-start gap-3 rounded-2xl border-2 px-4 py-3.5 text-left transition-colors ${
          ativa
            ? "border-primary-600 bg-white shadow-sm dark:border-primary-400 dark:bg-slate-800"
            : "border-slate-200 bg-white/60 hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-800/50 dark:hover:border-slate-600"
        }`}
      >
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${ativa ? "bg-primary-600 text-white" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300"}`}
          aria-hidden
        >
          <Icone size={18} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {numero}ª conciliação{numero === 1 ? " · a mais importante" : ""}
          </span>
          <span className="block text-base font-semibold text-slate-900 dark:text-slate-100">{titulo}</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">{explicacao}</span>
          {estado && (
            <span
              className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                estado.neutro
                  ? "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                  : estado.ok
                    ? "bg-success-50 text-success-700 dark:bg-success-900/40 dark:text-success-300"
                    : "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300"
              }`}
            >
              {estado.neutro ? <Minus size={13} aria-hidden /> : estado.ok ? <CheckCircle2 size={13} aria-hidden /> : <AlertTriangle size={13} aria-hidden />}
              {estado.texto}
            </span>
          )}
        </span>
      </button>
    )
  }

  const textoNotas = !estadoNotas
    ? null
    : !estadoNotas.aplica
      ? { ok: true, neutro: true, texto: "Sem notas pra conferir (só o Financeiro)" }
      : estadoNotas.ok
        ? { ok: true, texto: estadoNotas.no_prazo > 0 ? `Tudo conferido · ${plural(estadoNotas.no_prazo, "nota", "notas")} ainda no prazo` : "Tudo conferido" }
        : { ok: false, texto: plural(estadoNotas.pendencias, "pendência", "pendências") }
  const textoExtrato = !estadoExtrato
    ? null
    : estadoExtrato.linhas === 0
      ? { ok: true, neutro: true, texto: "Nenhum extrato importado" }
      : estadoExtrato.ok
        ? { ok: true, texto: "Tudo conferido" }
        : { ok: false, texto: plural(estadoExtrato.pendentes, "pendência", "pendências") }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/app/financeiro" className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-primary-600">
            <ArrowLeft size={14} /> Financeiro
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Conciliação</h1>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            <strong className="font-semibold text-slate-700 dark:text-slate-200">1. As notas foram pagas?</strong> Eu confiro cada nota que você
            emitiu com o dinheiro que entrou.
            <br />
            <strong className="font-semibold text-slate-700 dark:text-slate-200">2. O extrato está todo classificado?</strong> Cada linha do
            banco vira um recebimento ou uma despesa.
          </p>
        </div>
        <Button variant="accent" onClick={() => setImportando(true)}>
          <FileUp size={16} /> Importar extrato
        </Button>
      </div>

      {/* Fechamento do mês: as duas conciliações juntas */}
      {resumo && (
        <Card className="p-4">
          <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Fechamento do mês</h2>
            <p className="hidden text-xs text-slate-500 sm:block dark:text-slate-400">
              O mês fecha quando {semNotas ? "todas as linhas do extrato dele estão classificadas" : "as notas dele estão pagas e o extrato dele está todo classificado"}.
            </p>
          </div>
          {/* do mais antigo pro atual, da esquerda pra direita; no celular rola pro lado */}
          <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
            {resumo.fechamentos.map((mes) => (
              <Fechamento key={mes.competencia} mes={mes} comNotas={!semNotas} onIr={irPara} />
            ))}
          </div>
        </Card>
      )}

      <div role="tablist" aria-label="As duas conciliações" className="flex flex-wrap gap-3">
        {aba("notas", 1, FileCheck2, "As notas foram pagas?", "Notas emitidas × dinheiro que entrou, por tomador.", textoNotas)}
        {aba("extrato", 2, Landmark, "O extrato do banco está todo classificado?", "Linhas do extrato × recebimentos e despesas.", textoExtrato)}
      </div>

      <div role="tabpanel" id={`parte-${parte}`} aria-labelledby={`aba-${parte}`}>
        {!pedida && resumo === null ? (
          <p className="py-10 text-center text-sm text-slate-400">Carregando...</p>
        ) : parte === "notas" ? (
          <ConciliacaoNotas
            recarga={recarga}
            filtroInicial={filtroInicial}
            onMudou={() => void carregarResumo()}
            onImportar={() => setImportando(true)}
          />
        ) : (
          <ConciliacaoExtrato
            resumo={resumo?.extrato ?? null}
            recarga={recarga}
            vinculos={vinculos}
            onVinculosMudaram={carregarVinculos}
            onMudou={() => void carregarResumo()}
            onImportar={() => setImportando(true)}
          />
        )}
      </div>

      <ImportacoesFeitas
        origem="financeiro"
        recarga={recarga}
        onDesfeito={() => {
          setRecarga((n) => n + 1)
          void carregarResumo()
        }}
      />

      {importando && (
        <ImportarExtratoModal
          vinculos={vinculos}
          onClose={() => setImportando(false)}
          onImportado={() => {
            setRecarga((n) => n + 1)
            void carregarResumo()
            void carregarVinculos()
          }}
        />
      )}
    </div>
  )
}
