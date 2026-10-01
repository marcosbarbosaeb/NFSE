import {
  CheckCircle2,
  Clock,
  DownloadCloud,
  FileArchive,
  FileSpreadsheet,
  FileText,
  FileUp,
  Landmark,
  Mail,
  PenLine,
  Plus,
  RotateCcw,
  Search,
  Send,
  X,
} from "lucide-react"
import { DownloadsNota, SeloAssinatura, SeloPrefeitura, SeloTomador } from "../components/AcoesNota"
import { BaixaPagamento } from "../components/BaixaPagamento"
import { CampoData } from "../components/CampoData"
import { ImportarNacionalModal } from "../components/ImportarNacionalModal"
import { ConfirmarLoteModal, LotePainel } from "../components/LotePainel"
import { ShopeeModal } from "../components/ShopeeModal"
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { CampoPercentual } from "../components/ui/CampoPercentual"
import { Field, FieldWrap } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import { dataPadraoDaCompetencia, hojeLocal } from "../lib/datas"
import { LOTE_RODANDO } from "../lib/lotes"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import type {
  AcaoLote,
  CriarLoteBody,
  EmissaoListaLinha,
  Lote,
  Emissao,
  GerarDpsRequest,
  ImportacaoCsvResultado,
  OrdemAwin,
  Prestador,
  VerificarDuplicata,
  VinculoResumo,
  RecebimentoSemNota,
} from "../lib/types"

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]
const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

// .zip por ids vai na URL (GET /api/dps/zip?ids=a,b,c) — acima disso a URL
// fica grande demais pro servidor; aí só por mês inteiro.
const MAX_IDS_ZIP = 250

// Painel de lote fechado pela pessoa não volta a aparecer ao recarregar a página.
const CHAVE_LOTES_FECHADOS = "agenteana:lotes-fechados"
function lotesFechados(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_LOTES_FECHADOS) ?? "[]")
  } catch {
    return []
  }
}
function marcarLoteFechado(id: string) {
  try {
    sessionStorage.setItem(CHAVE_LOTES_FECHADOS, JSON.stringify([...lotesFechados(), id].slice(-20)))
  } catch {
    // sem storage (aba privada etc.) — só não lembra
  }
}

interface Confirmacao {
  body: CriarLoteBody
  titulo?: string
  totalSelecionadas?: number
  alvo?: string
  permitirReenviar?: boolean
  aviso?: string
}

const SELECT_FILTRO =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

const ESTADOS: Record<string, { label: string; variant: "success" | "warning" | "danger" | "neutral" }> = {
  rascunho: { label: "Rascunho", variant: "neutral" },
  montado: { label: "Emitida", variant: "success" },
  assinado: { label: "Assinada", variant: "success" },
  submetido: { label: "Submetida", variant: "success" },
  confirmado: { label: "Confirmada", variant: "success" },
  cancelada: { label: "Cancelada", variant: "neutral" },
  substituida: { label: "Substituída", variant: "neutral" },
  erro: { label: "Erro", variant: "danger" },
}

function badgeEstado(estado: string, label: string) {
  const info = ESTADOS[estado]
  return <Badge variant={info?.variant ?? "neutral"}>{label}</Badge>
}

// Marco 16 (item 3, pedido do Marcos: "é importante a pessoa confrontar
// notas emitidas com notas pagas") — mesmo badge do dashboard (só a
// competência corrente), aqui aplicado à lista completa.
function badgePagamento(recebido: boolean) {
  return recebido ? <Badge variant="success">Recebida</Badge> : <Badge variant="warning">Pendente</Badge>
}

export function NfsePage() {
  const [ano, setAno] = useState<string>(String(ANO_ATUAL))
  const [vinculoFiltro, setVinculoFiltro] = useState("")
  // Notas dos vendedores da Shopee numa aba própria (01/10/2026): são
  // centenas de notas pequenas e o pagamento delas vem junto com a nota da
  // Shopee — não se misturam com as demais.
  const [grupo, setGrupo] = useState<"notas" | "vendedores">(() =>
    new URLSearchParams(window.location.search).get("aba") === "vendedores" ? "vendedores" : "notas",
  )
  // Mês da competência (01..12) dentro do ano escolhido — filtro no cliente.
  const [mesFiltro, setMesFiltro] = useState("")
  const [pagamentoFiltro, setPagamentoFiltro] = useState<"" | "recebido" | "pendente">("")
  const [busca, setBusca] = useState("")
  const [emissoes, setEmissoes] = useState<EmissaoListaLinha[] | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // Vindo do botão "Gerar" da aba Tomadores: ?gerar=<vínculo>&competencia=AAAA-MM
  const [modalNova, setModalNova] = useState(Boolean(searchParams.get("gerar") || searchParams.get("nova")))
  const [modalCsv, setModalCsv] = useState(false)
  const [modalNacional, setModalNacional] = useState(false)
  const [shopee, setShopee] = useState<VinculoResumo | null>(null)
  // Marco 16, item 5 — só pra pré-preencher aliq_sn na Nova emissão (ver
  // NovaEmissaoModal abaixo); nunca aplicada sem o usuário poder confirmar.
  const [aliquotaReferencia, setAliquotaReferencia] = useState<number | null>(null)
  const [ambienteTeste, setAmbienteTeste] = useState(false)
  // Ações em lote (29/09/2026): seleção múltipla + "enviar todas".
  const [selecionadas, setSelecionadas] = useState<Set<string>>(() => new Set())
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null)
  const [lote, setLote] = useState<Lote | null>(null)
  const [erroLote, setErroLote] = useState<string | null>(null)
  const [baixandoZip, setBaixandoZip] = useState(false)
  const checkTodas = useRef<HTMLInputElement>(null)

  // Um lote que ainda roda (ou parou no meio) aparece ao abrir a página.
  useEffect(() => {
    api
      .get<Lote[]>("/lotes")
      .then((recentes) => {
        const ultimo = recentes[0]
        if (!ultimo || lotesFechados().includes(ultimo.id)) return
        const recente = !ultimo.criado_em || Date.now() - new Date(ultimo.criado_em).getTime() < 24 * 3600 * 1000
        if (LOTE_RODANDO(ultimo) || (ultimo.status === "interrompido" && recente)) setLote(ultimo)
      })
      .catch(() => {})
  }, [])

  function carregarVinculos() {
    api.get<VinculoResumo[]>("/vinculos").then(setVinculos).catch(() => {})
  }

  useEffect(() => {
    carregarVinculos()
    api
      .get<Prestador>("/prestador")
      .then((p) => {
        setAliquotaReferencia(p.aliquota_atual)
        setAmbienteTeste(p.tp_amb_padrao === "2")
      })
      .catch(() => {})
  }, [])

  // Só a resposta do pedido mais recente vale (trocar ano/fornecedor rápido
  // não deixa uma resposta antiga sobrescrever a nova).
  const pedidoAtual = useRef(0)
  function recarregar() {
    const pedido = ++pedidoAtual.current
    setCarregando(true)
    setErro(null)
    const params = new URLSearchParams()
    if (ano) params.set("ano", ano)
    if (vinculoFiltro) params.set("vinculo_id", vinculoFiltro)
    params.set("grupo", grupo)
    api
      .get<EmissaoListaLinha[]>(`/dps?${params.toString()}`)
      .then((dados) => pedido === pedidoAtual.current && setEmissoes(dados))
      .catch((err) => pedido === pedidoAtual.current && setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => pedido === pedidoAtual.current && setCarregando(false))
  }

  useEffect(recarregar, [ano, vinculoFiltro, grupo])
  const temShopee = vinculos.some((v) => v.metodo_captura_valor === "csv")
  function trocarGrupo(g: "notas" | "vendedores") {
    setGrupo(g)
    setSelecionadas(new Set())
  }

  // Trocar ano/tomador recarrega a lista — a seleção anterior não vale mais.
  function trocarAno(valor: string) {
    setAno(valor)
    setSelecionadas(new Set())
  }
  function trocarVinculo(valor: string) {
    setVinculoFiltro(valor)
    setSelecionadas(new Set())
  }

  const competenciaFiltro = ano && mesFiltro ? `${ano}-${mesFiltro}` : ""
  // "Só controle de recebimento" (sem_nota): tem notas importadas na lista,
  // mas a Ana não gera nota pra ele — fica fora da Nova emissão.
  const emissiveis = useMemo(() => vinculos.filter((v) => !v.sem_nota), [vinculos])
  const vinculoSelecionado = vinculos.find((v) => v.id === vinculoFiltro) ?? null

  // Filtro de pagamento aplicado no cliente (não no servidor, embora
  // /api/dps aceite ?pagamento=...): assim o resumo de confronto abaixo
  // continua mostrando emitidas x pagas lado a lado, mesmo com um dos dois
  // lados selecionado no filtro.
  const filtradas = useMemo(() => {
    if (!emissoes) return []
    const termo = busca.trim().toLowerCase()
    return emissoes.filter((e) => {
      if (competenciaFiltro && e.competencia !== competenciaFiltro) return false
      if (pagamentoFiltro === "recebido" && !e.pagamento_recebido) return false
      if (pagamentoFiltro === "pendente" && e.pagamento_recebido) return false
      if (!termo) return true
      return e.apelido.toLowerCase().includes(termo) || e.tomador_razao_social.toLowerCase().includes(termo)
    })
  }, [emissoes, busca, pagamentoFiltro, competenciaFiltro])

  // Confronto emitidas x pagas (item 3 do Marco 16) — sempre sobre TODAS as
  // emissões ativas do filtro de ano/fornecedor corrente, independente do
  // filtro de pagamento selecionado (senão o resumo ficaria só de um lado).
  const confronto = useMemo(() => {
    const ativas = (emissoes ?? []).filter(
      (e) => e.estado !== "cancelada" && e.estado !== "substituida" && (!competenciaFiltro || e.competencia === competenciaFiltro),
    )
    const recebidas = ativas.filter((e) => e.pagamento_recebido)
    const pendentes = ativas.filter((e) => !e.pagamento_recebido)
    return {
      totalEmitidas: ativas.length,
      totalRecebidas: recebidas.length,
      totalPendentes: pendentes.length,
      valorRecebido: recebidas.reduce((soma, e) => soma + e.valor, 0),
      valorPendente: pendentes.reduce((soma, e) => soma + e.valor, 0),
    }
  }, [emissoes, competenciaFiltro])

  // Envios ao fornecedor no filtro tomador+mês ("757 entregues · 35 falhas",
  // como no MandaNotas). Mesma regra de GET /api/envios/resumo (último
  // status de cada nota, canceladas fora) calculada sobre a lista já
  // carregada — o endpoint só filtra por ano, não por mês.
  const resumoEnvios = useMemo(() => {
    if (!vinculoFiltro || !competenciaFiltro || !emissoes) return null
    const doMes = emissoes.filter(
      (e) => e.vinculo_id === vinculoFiltro && e.competencia === competenciaFiltro && e.estado !== "cancelada",
    )
    const enviados = doMes.filter((e) => e.envio_status === "enviado").length
    const falhas = doMes.filter((e) => e.envio_status === "falha").length
    return { total: doMes.length, enviados, falhas, semEnvio: doMes.length - enviados - falhas }
  }, [emissoes, vinculoFiltro, competenciaFiltro])

  // Só conta (e age sobre) o que está visível: esconder uma nota com a busca
  // tira ela da ação, sem surpresa.
  const selecionadasVisiveis = useMemo(() => filtradas.filter((e) => selecionadas.has(e.id)), [filtradas, selecionadas])
  const todasVisiveisSelecionadas = filtradas.length > 0 && selecionadasVisiveis.length === filtradas.length
  useEffect(() => {
    if (checkTodas.current) {
      checkTodas.current.indeterminate = selecionadasVisiveis.length > 0 && !todasVisiveisSelecionadas
    }
  }, [selecionadasVisiveis.length, todasVisiveisSelecionadas])

  function alternarSelecao(id: string) {
    setSelecionadas((atual) => {
      const nova = new Set(atual)
      if (nova.has(id)) nova.delete(id)
      else nova.add(id)
      return nova
    })
  }

  function alternarTodas() {
    setSelecionadas((atual) => {
      const nova = new Set(atual)
      if (todasVisiveisSelecionadas) filtradas.forEach((e) => nova.delete(e.id))
      else filtradas.forEach((e) => nova.add(e.id))
      return nova
    })
  }

  const loteRodando = lote != null && LOTE_RODANDO(lote)

  function acaoNaSelecao(acao: AcaoLote) {
    setErroLote(null)
    setConfirmacao({
      body: { acao, emissao_ids: selecionadasVisiveis.map((e) => e.id) },
      totalSelecionadas: selecionadasVisiveis.length,
      permitirReenviar: acao === "email" || acao === "email_geral",
      aviso:
        acao === "email_geral"
          ? "Vai pros e-mails gerais configurados em Empresa › E-mails (contador, você mesmo...)."
          : undefined,
    })
  }

  function enviarTodasDoFiltro(soFalhas: boolean) {
    if (!vinculoSelecionado || !competenciaFiltro) return
    setErroLote(null)
    setConfirmacao({
      titulo: soFalhas ? "Reenviar falhas" : "Enviar todas por e-mail",
      body: { acao: "email", vinculo_id: vinculoSelecionado.id, competencia: competenciaFiltro, reenviar: false },
      alvo: `de ${vinculoSelecionado.apelido} em ${formatCompetenciaLonga(competenciaFiltro)}`,
      permitirReenviar: !soFalhas,
      aviso: soFalhas
        ? "Vão de novo as que falharam — e também as que ainda não tinham sido enviadas. As já entregues ficam de fora."
        : undefined,
    })
  }

  async function baixarZip() {
    setErroLote(null)
    const params = new URLSearchParams()
    // Mês inteiro selecionado (sem busca/pagamento escondendo nada): pede por
    // competência — URL curta e o .zip sai com o nome do mês.
    if (competenciaFiltro && todasVisiveisSelecionadas && !busca.trim() && !pagamentoFiltro) {
      params.set("competencia", competenciaFiltro)
      if (vinculoFiltro) params.set("vinculo_id", vinculoFiltro)
    } else if (selecionadasVisiveis.length > MAX_IDS_ZIP) {
      setErroLote(
        `Dá pra baixar até ${MAX_IDS_ZIP} notas por .zip. Filtre por mês e selecione todas pra baixar o mês inteiro de uma vez.`,
      )
      return
    } else {
      params.set("ids", selecionadasVisiveis.map((e) => e.id).join(","))
    }
    setBaixandoZip(true)
    try {
      const resp = await fetch(`/api/dps/zip?${params.toString()}`, { credentials: "include" })
      if (!resp.ok) {
        const corpo = await resp.json().catch(() => null)
        throw new ApiError(resp.status, corpo?.detail ?? "Não foi possível gerar o .zip.")
      }
      const blob = await resp.blob()
      const nome = /filename="([^"]+)"/.exec(resp.headers.get("content-disposition") ?? "")?.[1] ?? "notas.zip"
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = nome
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 2000)
    } catch (err) {
      setErroLote(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão ao baixar o .zip.")
    } finally {
      setBaixandoZip(false)
    }
  }

  return (
    <div className={`flex flex-col gap-6 ${lote ? "pb-56 sm:pb-40" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">NFS-e</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Todas as notas emitidas, por competência.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setModalNacional(true)} title="Trazer as notas já emitidas no Emissor Nacional">
            <DownloadCloud size={16} /> Importar do Emissor Nacional
          </Button>
          {/* CSV só pra quem usa relatório em planilha (Shopee) — ver
              "Como o valor chega" no cadastro do tomador (28/09/2026). */}
          {vinculos.some((v) => v.metodo_captura_valor === "csv") && (
            <Button
              variant="outline"
              onClick={() => setShopee(vinculos.find((v) => v.metodo_captura_valor === "csv") ?? null)}
              data-tour="nfse-csv"
            >
              <FileUp size={16} /> Relatório da Shopee
            </Button>
          )}
          <Button
            variant="accent"
            onClick={() => (emissiveis.length > 0 ? setModalNova(true) : navigate("/app/tomadores/novo"))}
            data-tour="nfse-nova"
            title={emissiveis.length > 0 ? undefined : "Cadastre um tomador primeiro"}
          >
            <Plus size={16} /> Nova emissão
          </Button>
        </div>
      </div>

      {/* Marco 16 (item 3) — confronto notas emitidas x notas pagas, pedido
          do Marcos. Sempre reflete ano/fornecedor selecionados, independente
          do filtro de pagamento abaixo (senão o resumo ficaria só de um lado). */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<FileText size={18} />}
          iconClassName="bg-primary-50 text-primary-600"
          label="Notas emitidas"
          value={confronto.totalEmitidas}
          sublabel={competenciaFiltro ? `em ${formatCompetenciaLonga(competenciaFiltro)}` : ano ? `em ${ano}` : "no período"}
        />
        {grupo === "notas" && (<>
        <StatCard
          icon={<CheckCircle2 size={18} />}
          iconClassName="bg-success-50 text-success-600"
          label="Pagas"
          value={confronto.totalRecebidas}
          sublabel={formatBRL(confronto.valorRecebido)}
        />
        <StatCard
          icon={<Clock size={18} />}
          iconClassName="bg-warning-50 text-warning-600"
          label="Emitidas sem pagamento"
          value={confronto.totalPendentes}
          sublabel={formatBRL(confronto.valorPendente)}
          sublabelClassName="text-warning-600"
        />
        </>)}
        {grupo === "vendedores" && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600 sm:col-span-2 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
            <p className="font-medium text-slate-800 dark:text-slate-100">Pagamento indireto</p>
            <p className="mt-1">
              A Shopee paga a comissão inteira (dela + dos vendedores) junto com a nota da Shopee. Estas notas não têm cobrança própria —
              o recebimento é controlado na nota da Shopee, na aba Notas.
            </p>
          </div>
        )}
      </div>

      <Card className="p-5">
        {(temShopee || grupo === "vendedores") && (
          <div role="tablist" aria-label="Tipo de nota" className="mb-4 flex gap-1 border-b border-slate-200 dark:border-slate-700">
            {([["notas", "Notas"], ["vendedores", "Vendedores Shopee"]] as const).map(([id, rotulo]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={grupo === id}
                onClick={() => trocarGrupo(id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                  grupo === id
                    ? "border-primary-600 text-primary-700 dark:text-primary-300"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                {rotulo}
              </button>
            ))}
          </div>
        )}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <select value={ano} onChange={(e) => trocarAno(e.target.value)} aria-label="Ano" className={SELECT_FILTRO}>
            {ANOS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select value={mesFiltro} onChange={(e) => setMesFiltro(e.target.value)} aria-label="Mês da competência" className={SELECT_FILTRO}>
            <option value="">Todos os meses</option>
            {MESES.map((nome, i) => (
              <option key={nome} value={String(i + 1).padStart(2, "0")}>
                {nome}
              </option>
            ))}
          </select>
          <select value={vinculoFiltro} onChange={(e) => trocarVinculo(e.target.value)} aria-label="Tomador" className={SELECT_FILTRO}>
            <option value="">Todos os tomadores</option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido}
              </option>
            ))}
          </select>
          <select
            value={pagamentoFiltro}
            onChange={(e) => setPagamentoFiltro(e.target.value as "" | "recebido" | "pendente")}
            aria-label="Pagamento"
            className={SELECT_FILTRO}
          >
            <option value="">Pagamento: todos</option>
            <option value="recebido">Só pagas</option>
            <option value="pendente">Só pendentes</option>
          </select>
          <div className="relative ml-auto w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar tomador..."
              aria-label="Buscar tomador"
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 py-1.5 pl-9 pr-3 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
        </div>

        {/* "Enviar todas" (29/09/2026) — tomador + mês filtrados: manda todas
            as notas prontas daquele mês por e-mail, num lote em segundo plano.
            Pensado pra Shopee (uma nota por vendedor, centenas por mês). */}
        {vinculoSelecionado && !competenciaFiltro && (
          <p className="mb-4 flex items-center gap-2 rounded-lg bg-slate-50 px-4 py-2.5 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
            <Send size={15} className="shrink-0 text-primary-500" />
            Escolha um mês pra enviar todas as notas de {vinculoSelecionado.apelido} por e-mail de uma vez.
          </p>
        )}
        {vinculoSelecionado && competenciaFiltro && resumoEnvios && (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-primary-100 bg-primary-50/60 px-4 py-3 dark:border-primary-900/40 dark:bg-primary-900/20">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
                Envios ao fornecedor · {vinculoSelecionado.apelido}, {formatCompetenciaLonga(competenciaFiltro)}
              </p>
              <p className="mt-0.5 flex flex-wrap gap-x-2 text-sm text-slate-600 dark:text-slate-300">
                <span>
                  Entregues <strong className="text-success-700 dark:text-success-300">{resumoEnvios.enviados}</strong>
                </span>
                <span aria-hidden="true">·</span>
                <span>
                  Falhas{" "}
                  <strong className={resumoEnvios.falhas > 0 ? "text-danger-600 dark:text-danger-300" : ""}>{resumoEnvios.falhas}</strong>
                </span>
                <span aria-hidden="true">·</span>
                <span>
                  Sem envio <strong>{resumoEnvios.semEnvio}</strong>
                </span>
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {resumoEnvios.falhas > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  className="px-3 py-1.5"
                  disabled={loteRodando}
                  onClick={() => enviarTodasDoFiltro(true)}
                >
                  <RotateCcw size={15} /> Reenviar falhas ({resumoEnvios.falhas})
                </Button>
              )}
              <Button
                type="button"
                variant="accent"
                className="px-3 py-1.5"
                disabled={loteRodando || resumoEnvios.total === 0}
                title={loteRodando ? "Espere a ação em lote em andamento terminar" : undefined}
                onClick={() => enviarTodasDoFiltro(false)}
              >
                <Send size={15} /> Enviar todas por e-mail
              </Button>
            </div>
          </div>
        )}

        {selecionadasVisiveis.length > 0 && (
          <div
            role="toolbar"
            aria-label="Ações nas notas selecionadas"
            className="sticky top-0 z-20 -mx-5 mb-3 flex flex-wrap items-center gap-2 border-y border-primary-100 bg-primary-50 px-5 py-2.5 dark:border-primary-900/40 dark:bg-slate-900"
          >
            <span className="mr-1 text-sm font-semibold text-primary-800 dark:text-primary-200" aria-live="polite">
              {selecionadasVisiveis.length} selecionada{selecionadasVisiveis.length === 1 ? "" : "s"}
            </span>
            <Button type="button" variant="outline" className="bg-white px-3 py-1.5 dark:bg-slate-800" disabled={loteRodando} onClick={() => acaoNaSelecao("assinar")}>
              <PenLine size={15} /> Assinar
            </Button>
            <Button type="button" variant="outline" className="bg-white px-3 py-1.5 dark:bg-slate-800" disabled={loteRodando} onClick={() => acaoNaSelecao("submeter")}>
              <Landmark size={15} /> Enviar à prefeitura
            </Button>
            <Button type="button" variant="outline" className="bg-white px-3 py-1.5 dark:bg-slate-800" disabled={loteRodando} onClick={() => acaoNaSelecao("email")}>
              <Mail size={15} /> Enviar ao fornecedor por e-mail
            </Button>
            <Button type="button" variant="outline" className="bg-white px-3 py-1.5 dark:bg-slate-800" disabled={loteRodando} onClick={() => acaoNaSelecao("email_geral")}>
              <Send size={15} /> Enviar aos e-mails gerais
            </Button>
            <Button type="button" variant="outline" className="bg-white px-3 py-1.5 dark:bg-slate-800" disabled={baixandoZip} onClick={baixarZip}>
              <FileArchive size={15} /> {baixandoZip ? "Gerando .zip..." : "Baixar XMLs (.zip)"}
            </Button>
            <Button type="button" variant="ghost" className="px-3 py-1.5" onClick={() => setSelecionadas(new Set())}>
              <X size={15} /> Limpar
            </Button>
            {loteRodando && (
              <span className="w-full text-xs text-slate-500 dark:text-slate-400">
                Tem uma ação em lote em andamento — espere terminar (ou cancele) pra começar outra.
              </span>
            )}
          </div>
        )}

        {erroLote && (
          <p role="alert" className="mb-3 flex items-start justify-between gap-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
            {erroLote}
            <button type="button" onClick={() => setErroLote(null)} aria-label="Fechar aviso" className="shrink-0 rounded p-0.5 hover:bg-danger-100">
              <X size={16} />
            </button>
          </p>
        )}
        {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
        {carregando && emissoes === null && <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

        {emissoes !== null && (
          <div className={`-mx-5 overflow-x-auto px-5 transition-opacity ${carregando ? "opacity-60" : ""}`}>
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700/60 text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                <th className="w-10 py-2 pr-2 font-medium">
                  <input
                    ref={checkTodas}
                    type="checkbox"
                    checked={todasVisiveisSelecionadas}
                    onChange={alternarTodas}
                    disabled={filtradas.length === 0}
                    aria-label={todasVisiveisSelecionadas ? "Desmarcar todas as notas visíveis" : "Selecionar todas as notas visíveis"}
                    className="h-4 w-4 cursor-pointer accent-primary-600"
                  />
                </th>
                <th className="py-2 font-medium">Tomador</th>
                <th className="py-2 font-medium">Competência</th>
                <th className="py-2 font-medium">Valor</th>
                <th className="py-2 font-medium">Assinatura</th>
                <th className="py-2 font-medium">Prefeitura</th>
                <th className="py-2 font-medium" title="Envio da nota ao fornecedor (tomador)">Fornecedor</th>
                <th className="py-2 font-medium">Pagamento</th>
                <th className="py-2 font-medium">Arquivos</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((e) => (
                <tr
                  key={e.id}
                  className={`border-b border-slate-50 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-700/50 ${
                    selecionadas.has(e.id) ? "bg-primary-50/50 dark:bg-primary-900/15" : ""
                  }`}
                >
                  <td className="py-3 pr-2 align-top">
                    <input
                      type="checkbox"
                      checked={selecionadas.has(e.id)}
                      onChange={() => alternarSelecao(e.id)}
                      aria-label={`Selecionar nota de ${e.tomador_razao_social || e.apelido}, ${e.competencia}`}
                      className="mt-0.5 h-4 w-4 cursor-pointer accent-primary-600"
                    />
                  </td>
                  <td className="py-3">
                    <Link to={`/app/nfse/${e.id}`} className="font-medium text-primary-700 hover:underline">
                      {e.apelido}
                    </Link>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{e.tomador_razao_social}</p>
                  </td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">
                    {e.competencia}
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      DPS {e.n_dps ?? "—"}
                      {e.homologacao && " · teste"}
                    </p>
                  </td>
                  <td className="py-3 text-slate-600 dark:text-slate-300">{formatBRL(e.valor)}</td>
                  <td className="py-3">
                    {e.estado === "cancelada" || e.estado === "substituida" ? badgeEstado(e.estado, e.estado_label) : <SeloAssinatura nota={e} onMudou={recarregar} />}
                  </td>
                  <td className="py-3">
                    <SeloPrefeitura nota={e} onMudou={recarregar} />
                  </td>
                  <td className="py-3">
                    <SeloTomador nota={e} onMudou={recarregar} />
                  </td>
                  <td className="py-3">
                    {e.avulsa ? (
                      <span title="A Shopee paga junto com a nota dela"><Badge variant="neutral">Na nota da Shopee</Badge></span>
                    ) : e.estado === "cancelada" || e.estado === "substituida" ? (
                      badgePagamento(e.pagamento_recebido)
                    ) : (
                      <BaixaPagamento
                        vinculoId={e.vinculo_id}
                        competencia={e.competencia}
                        valor={e.valor}
                        recebido={e.pagamento_recebido}
                        onMudou={recarregar}
                      />
                    )}
                  </td>
                  <td className="py-3">
                    <DownloadsNota nota={e} />
                  </td>
                </tr>
              ))}
              {filtradas.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400 dark:text-slate-500">
                    Nenhuma nota encontrada.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        )}
      </Card>

      {modalNova && emissiveis.length > 0 && (
        <NovaEmissaoModal
          vinculos={emissiveis}
          aliquotaReferencia={aliquotaReferencia}
          ambienteTeste={ambienteTeste}
          vinculoInicial={searchParams.get("gerar")}
          competenciaInicial={searchParams.get("competencia")}
          valorInicial={searchParams.get("valor")}
          pagamentoId={searchParams.get("pagamento")}
          onClose={() => {
            setModalNova(false)
            if (searchParams.get("gerar") || searchParams.get("nova")) navigate("/app/nfse", { replace: true })
          }}
          onEscolherShopee={(v) => {
            setModalNova(false)
            setShopee(v)
          }}
          onCriada={(emissao) => {
            setModalNova(false)
            if (searchParams.get("gerar")) navigate(`/app/nfse/${emissao.id}`)
            else recarregar()
          }}
        />
      )}
      {shopee && (
        <ShopeeModal
          vinculo={shopee}
          aliquotaReferencia={aliquotaReferencia}
          onClose={() => {
            setShopee(null)
            if (searchParams.get("gerar")) navigate("/app/nfse", { replace: true })
          }}
          onGeradas={recarregar}
          onVerNotas={(comp) => {
            const [anoComp, mesComp] = comp.split("-")
            if (ANOS.map(String).includes(anoComp)) {
              trocarAno(anoComp)
              setMesFiltro(mesComp)
            }
            trocarVinculo(shopee.id)
            trocarGrupo("vendedores")
            setBusca("")
            setPagamentoFiltro("")
            setShopee(null)
            if (searchParams.get("gerar")) navigate("/app/nfse", { replace: true })
          }}
        />
      )}
      {confirmacao && (
        <ConfirmarLoteModal
          {...confirmacao}
          onClose={() => setConfirmacao(null)}
          onCriado={(novo) => {
            setConfirmacao(null)
            setLote(novo)
            if (confirmacao.body.emissao_ids) setSelecionadas(new Set())
          }}
        />
      )}
      {lote && (
        <LotePainel
          lote={lote}
          onMudou={setLote}
          onTerminou={recarregar}
          onFechar={() => {
            marcarLoteFechado(lote.id)
            setLote(null)
          }}
        />
      )}
      {modalNacional && (
        <ImportarNacionalModal
          onClose={() => setModalNacional(false)}
          onConcluido={() => {
            recarregar()
            carregarVinculos()
          }}
        />
      )}
      {modalCsv && (
        <ImportarCsvModal
          onClose={() => setModalCsv(false)}
          onImportado={() => recarregar()}
        />
      )}
    </div>
  )
}

function NovaEmissaoModal({
  vinculos,
  aliquotaReferencia,
  ambienteTeste,
  vinculoInicial,
  competenciaInicial,
  valorInicial,
  pagamentoId,
  onClose,
  onEscolherShopee,
  onCriada,
}: {
  vinculos: VinculoResumo[]
  aliquotaReferencia: number | null
  ambienteTeste?: boolean
  vinculoInicial?: string | null
  competenciaInicial?: string | null
  /** Tomador que paga antes da nota: o aviso já traz o valor que caiu. */
  valorInicial?: string | null
  /** Gerar a nota de um recebimento que chegou sem nota (fica no mês dele). */
  pagamentoId?: string | null
  onClose: () => void
  onEscolherShopee: (vinculo: VinculoResumo) => void
  onCriada: (emissao: Emissao) => void
}) {
  const [vinculoId, setVinculoId] = useState(
    vinculoInicial && vinculos.some((v) => v.id === vinculoInicial) ? vinculoInicial : (vinculos[0]?.id ?? ""),
  )
  // Data de competência (29/09/2026): calendário, padrão hoje. Vindo do
  // atalho "Gerar" de um mês passado (?competencia=AAAA-MM), começa no último
  // dia daquele mês. A competência (AAAA-MM) sai da data escolhida.
  const [dataCompetencia, setDataCompetencia] = useState(() => dataPadraoDaCompetencia(competenciaInicial))
  const dataEfetiva = /^\d{4}-\d{2}-\d{2}$/.test(dataCompetencia) ? dataCompetencia : hojeLocal()
  // Recebimento sem nota (ex.: Mercado Livre paga antes): a nota fica no mês
  // do recebimento pra baterem; a data de competência da nota segue a escolhida.
  const [recebimento, setRecebimento] = useState<RecebimentoSemNota | null>(null)
  const doRecebimento = recebimento && recebimento.vinculo_id === vinculoId ? recebimento : null
  const competencia = doRecebimento ? doRecebimento.competencia : dataEfetiva.slice(0, 7)
  const [valor, setValor] = useState(() => {
    const n = Number(valorInicial)
    return valorInicial && Number.isFinite(n) && n > 0 ? n.toFixed(2) : ""
  })
  useEffect(() => {
    if (!pagamentoId) return
    let vivo = true
    api
      .get<RecebimentoSemNota[]>("/financeiro/recebimentos-sem-nota")
      .then((lista) => {
        const r = lista.find((x) => x.pagamento_id === pagamentoId)
        if (!vivo || !r) return
        setRecebimento(r)
        setVinculoId(r.vinculo_id)
        setValor(r.valor.toFixed(2))
      })
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [pagamentoId])
  const [ordem, setOrdem] = useState("")
  // Pré-preenchida com a alíquota de referência de Configurações, quando
  // existir — sempre editável, nunca aplicada sem a pessoa ver/confirmar
  // (mesma alíquota que o backend também aceita None e não assume nada).
  const [aliqSn, setAliqSn] = useState<number | null>(aliquotaReferencia)
  // A referência pode chegar depois do modal abrir (atalho "Gerar" da aba Tomadores).
  useEffect(() => {
    if (aliquotaReferencia != null) setAliqSn((atual) => atual ?? aliquotaReferencia)
  }, [aliquotaReferencia])
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [duplicata, setDuplicata] = useState<VerificarDuplicata | null>(null)

  const vinculo = vinculos.find((v) => v.id === vinculoId)
  // Shopee (01/10/2026): a nota da própria Shopee (valor que ela informa)
  // sai por aqui; as dos vendedores, pelo relatório.
  const [notaDaShopee, setNotaDaShopee] = useState(false)
  const ehRelatorio = vinculo?.metodo_captura_valor === "csv" && !notaDaShopee
  const precisaOrdem = vinculo?.template_descricao.includes("{ordem}") ?? false
  const mostrarOrdem = precisaOrdem || vinculo?.metodo_captura_valor === "pdf"

  // Aviso proativo de nota duplicada (Marco 16, pedido do Marcos): assim que
  // fornecedor+competência ficam preenchidos, consulta se já existe uma
  // emissão ativa pra essa combinação — ANTES do usuário tentar gerar e
  // tomar um erro só depois de preencher tudo. Não bloqueia o envio (a
  // checagem de verdade continua no backend em POST /api/dps) — é só pra
  // avisar com antecedência.
  useEffect(() => {
    setDuplicata(null)
    if (!vinculoId || !competencia) return
    const controlador = new AbortController()
    const tempo = setTimeout(() => {
      api
        .get<VerificarDuplicata>(
          `/dps/verificar-duplicata?vinculo_id=${vinculoId}&competencia=${competencia}`,
        )
        .then((resp) => {
          if (!controlador.signal.aborted) setDuplicata(resp)
        })
        .catch(() => {
          // silencioso de propósito — é só um aviso a mais; se falhar, o
          // usuário ainda tem a checagem de verdade ao tentar submeter.
        })
    }, 300)
    return () => {
      controlador.abort()
      clearTimeout(tempo)
    }
  }, [vinculoId, competencia])

  // Nota criada mas a assinatura falhou: os botões de gerar somem (gerar de
  // novo daria "já existe") e fica o "Ver a nota".
  const [notaSemAssinar, setNotaSemAssinar] = useState<Emissao | null>(null)
  const acaoRef = useRef<"assinar" | "rascunho">("assinar")

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    // Botão clicado: "Gerar rascunho" ou "Gerar e assinar" (28/09/2026). O
    // Enter aciona o primeiro botão de envio do formulário — "Gerar e
    // assinar" (vem primeiro no código; a ordem na tela é invertida).
    const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null | undefined
    const assinarJunto = (submitter?.value ?? acaoRef.current) === "assinar"
    if (notaSemAssinar) return
    setErro(null)
    setEnviando(true)
    let criada: Emissao | null = null
    try {
      const payload: GerarDpsRequest = {
        vinculo_id: vinculoId,
        competencia,
        data_competencia: dataEfetiva,
        pagamento_id: doRecebimento?.pagamento_id ?? null,
        valor: Number(valor),
        ordem: ordem || null,
        aliq_sn: aliqSn,
      }
      criada = await api.post<Emissao>("/dps", payload)
      if (assinarJunto) {
        // "Gerar e assinar": se a assinatura falhar (sem certificado, p.ex.),
        // a nota fica gerada e a pessoa vê o motivo na página dela.
        try {
          criada = await api.post<Emissao>(`/dps/${criada.id}/assinar`, {})
        } catch (err) {
          setErro(
            `Nota gerada, mas não deu pra assinar: ${err instanceof ApiError ? formatarErro(err.detail) : "falha de conexão"}.`,
          )
          setNotaSemAssinar(criada)
          return
        }
      }
      onCriada(criada)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Nova emissão" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        <FieldWrap label="Tomador">
          <select
            required
            value={vinculoId}
            onChange={(e) => setVinculoId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="" disabled>
              Selecione...
            </option>
            {vinculos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.apelido} — {v.tomador_razao_social}
              </option>
            ))}
          </select>
        </FieldWrap>

        {notaDaShopee && vinculo?.metodo_captura_valor === "csv" && (
          <p className="rounded-lg bg-primary-50/60 px-3 py-2 text-xs text-slate-600 dark:bg-primary-900/20 dark:text-slate-300">
            Nota da Shopee: informe o valor da comissão da Shopee.{" "}
            <button type="button" className="font-semibold text-primary-600 hover:underline" onClick={() => setNotaDaShopee(false)}>
              Gerar as dos vendedores
            </button>
          </p>
        )}
        {ehRelatorio && (
          <div className="rounded-xl border border-primary-100 bg-primary-50/60 p-4 text-sm text-slate-700 dark:border-primary-900/40 dark:bg-primary-900/20 dark:text-slate-200">
            <p>
              <strong>{vinculo.apelido}</strong> usa o relatório mensal em planilha: sai uma nota pra cada vendedor que te pagou
              comissão, direto do arquivo.
            </p>
            <Button type="button" variant="accent" className="mt-3" onClick={() => onEscolherShopee(vinculo)}>
              <FileSpreadsheet size={16} /> Notas dos vendedores (relatório)
            </Button>
            <Button type="button" variant="outline" className="mt-3 ml-2" onClick={() => setNotaDaShopee(true)}>
              Nota da Shopee
            </Button>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              A nota da Shopee leva o valor que a Shopee informa pra ela; o pagamento dela vem junto com o dos vendedores.
            </p>
          </div>
        )}
        {vinculo?.metodo_captura_valor === "pdf" && (
          <LerOrdemAwin
            vinculo={vinculo}
            onLida={(o) => {
              if (o.competencia_sugerida) setDataCompetencia(dataPadraoDaCompetencia(o.competencia_sugerida))
              if (o.valor != null) setValor(o.valor.toFixed(2))
              if (o.numero) setOrdem(o.numero)
            }}
          />
        )}

        {!ehRelatorio && (
          <>
        {doRecebimento && (
          <p className="rounded-lg bg-primary-50 px-4 py-3 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
            Nota do recebimento de {formatBRL(doRecebimento.valor)} em {formatCompetenciaLonga(doRecebimento.competencia)}. Ela fica junto
            desse recebimento no financeiro; a data de competência da nota é a escolhida abaixo.
          </p>
        )}
        <div className="grid grid-cols-1 items-start gap-3 sm:grid-cols-2">
          <CampoData valor={dataCompetencia} onChange={setDataCompetencia} />
          <Field
            label="Valor (R$)"
            required
            type="number"
            step="0.01"
            min="0.01"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </div>

        {duplicata?.existe && (
          <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700">
            Já existe uma nota <strong>{ESTADOS[duplicata.estado ?? ""]?.label.toLowerCase() ?? duplicata.estado}</strong>{" "}
            pra {vinculo?.apelido} nessa competência. Gerar outra vai dar erro — cancele a existente primeiro se for
            substituí-la.
          </p>
        )}

        {mostrarOrdem && (
          <Field
            label="Número da ordem de pagamento"
            required={precisaOrdem}
            value={ordem}
            onChange={(e) => setOrdem(e.target.value)}
            hint={precisaOrdem ? "Vai na descrição do serviço — obrigatório pra esse tomador." : "Opcional."}
          />
        )}

        <CampoPercentual
          label="Alíquota do Simples Nacional (%)"
          valor={aliqSn}
          onChange={setAliqSn}
          hint={aliquotaReferencia != null ? "Pré-preenchida com a referência de Empresa › Alíquotas — confira antes de gerar." : "Opcional."}
        />


          </>
        )}

        {ambienteTeste && !ehRelatorio && (
          <p className="rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700">
            Sua conta está gerando notas de <strong>teste</strong> (homologação). Pra emitir de verdade, desligue em
            Empresa › Notas.
          </p>
        )}

        <div className="flex flex-wrap justify-end gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          {notaSemAssinar ? (
            <Button type="button" variant="accent" onClick={() => onCriada(notaSemAssinar)}>
              Ver a nota
            </Button>
          ) : (
            !ehRelatorio && (
              <div className="flex flex-row-reverse flex-wrap gap-3">
                <Button
                  type="submit"
                  name="acao"
                  value="assinar"
                  variant="accent"
                  disabled={enviando || !vinculoId}
                  onClick={() => (acaoRef.current = "assinar")}
                >
                  {enviando ? "Gerando..." : "Gerar e assinar"}
                </Button>
                <Button
                  type="submit"
                  name="acao"
                  value="rascunho"
                  variant="outline"
                  disabled={enviando || !vinculoId}
                  onClick={() => (acaoRef.current = "rascunho")}
                >
                  Gerar rascunho
                </Button>
              </div>
            )
          )}
        </div>
      </form>
    </Modal>
  )
}

function ImportarCsvModal({ onClose, onImportado }: { onClose: () => void; onImportado: () => void }) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [resultado, setResultado] = useState<ImportacaoCsvResultado | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setErro(null)
    setEnviando(true)
    try {
      const form = new FormData()
      form.append("arquivo", arquivo)
      const resp = await api.postForm<ImportacaoCsvResultado>("/dps/importar-csv", form)
      setResultado(resp)
      if (resp.sucesso > 0) onImportado()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Importar CSV" onClose={onClose} largura="max-w-xl">
      {!resultado ? (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Colunas: <code className="rounded bg-slate-100 dark:bg-slate-700 px-1">apelido, competencia, valor</code> — opcionalmente{" "}
            <code className="rounded bg-slate-100 dark:bg-slate-700 px-1">ordem, aliq_sn</code>. O apelido precisa bater com um fornecedor
            já cadastrado.
          </p>
          <input
            type="file"
            accept=".csv,text/csv"
            required
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={enviando || !arquivo}>
              {enviando ? "Importando..." : "Importar"}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-slate-700 dark:text-slate-300">
            {resultado.sucesso} de {resultado.total} linha(s) importada(s) com sucesso
            {resultado.erro > 0 && `, ${resultado.erro} com erro`}.
          </p>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-700/60">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-900/40 text-slate-400 dark:text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Linha</th>
                  <th className="px-3 py-2 font-medium">Apelido</th>
                  <th className="px-3 py-2 font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody>
                {resultado.linhas.map((l) => (
                  <tr key={l.linha} className="border-t border-slate-100 dark:border-slate-700/60">
                    <td className="px-3 py-2 text-slate-500 dark:text-slate-400">{l.linha}</td>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{l.apelido}</td>
                    <td className="px-3 py-2">
                      {l.ok ? <Badge variant="success">OK — nº DPS {l.n_dps}</Badge> : <Badge variant="danger">{l.mensagem}</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end">
            <Button variant="accent" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}

/** Ordem de pagamento da Awin (28/09/2026): lê o PDF e preenche competência,
 * valor e número da ordem. Nada é gravado até a pessoa gerar a nota. */
function LerOrdemAwin({ vinculo, onLida }: { vinculo: VinculoResumo; onLida: (o: OrdemAwin) => void }) {
  const [lendo, setLendo] = useState(false)
  const [ordem, setOrdemLida] = useState<OrdemAwin | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  async function ler(arquivo: File) {
    setLendo(true)
    setErro(null)
    setOrdemLida(null)
    const dados = new FormData()
    dados.append("arquivo", arquivo)
    dados.append("vinculo_id", vinculo.id)
    try {
      const resp = await fetch("/api/awin/ordem", { method: "POST", body: dados, credentials: "include" })
      const corpo = await resp.json().catch(() => null)
      if (!resp.ok) throw new ApiError(resp.status, corpo?.detail ?? "Não foi possível ler o PDF.")
      setOrdemLida(corpo)
      onLida(corpo)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    } finally {
      setLendo(false)
    }
  }

  return (
    <div className="rounded-xl border border-primary-100 bg-primary-50/60 p-4 text-sm text-slate-700 dark:border-primary-900/40 dark:bg-primary-900/20 dark:text-slate-200">
      <p>
        <strong>{vinculo.apelido}</strong> manda uma ordem de pagamento em PDF. Envie o arquivo que a Ana preenche o
        número da ordem, o valor e a competência.
      </p>
      <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-primary-700 shadow-sm ring-1 ring-primary-200 hover:bg-primary-50 dark:bg-slate-800 dark:text-primary-300 dark:ring-primary-800">
        <FileText size={16} /> {lendo ? "Lendo..." : ordem ? "Trocar PDF" : "Enviar o PDF da ordem"}
        <input
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          disabled={lendo}
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) ler(f)
            e.target.value = ""
          }}
        />
      </label>
      {erro && <p className="mt-2 text-xs text-danger-600">{erro}</p>}
      {ordem && (
        <div className="mt-3 flex flex-col gap-1 text-xs">
          <p className="text-success-700 dark:text-success-300">
            Ordem {ordem.numero ?? "?"} · {ordem.valor != null ? formatBRL(ordem.valor) : "valor não encontrado"}
            {ordem.data && ` · emitida em ${new Date(`${ordem.data}T00:00:00`).toLocaleDateString("pt-BR")}`}
          </p>
          {ordem.ja_usada && (
            <p className="text-warning-700">
              Essa ordem já tem nota ({ordem.ja_usada.apelido}, {ordem.ja_usada.competencia}).{" "}
              <Link to={`/app/nfse/${ordem.ja_usada.emissao_id}`} className="font-semibold underline">
                Ver nota
              </Link>
            </p>
          )}
          {ordem.avisos.map((a) => (
            <p key={a} className="text-warning-700">
              {a}
            </p>
          ))}
          <p className="text-slate-500">Confira a data de competência abaixo antes de gerar.</p>
        </div>
      )}
    </div>
  )
}
