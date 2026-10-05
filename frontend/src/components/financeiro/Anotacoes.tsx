import { AlignLeft, Check, ListChecks, Pencil, Plus, Settings2, Table2, Trash2, X } from "lucide-react"
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react"
import { api } from "../../lib/api"
import { formatData, mensagemErro } from "../../lib/financeiro"
import { formatBRL, parseBRL } from "../../lib/format"
import { CampoMoeda, formatarMoedaCampo } from "../ui/CampoMoeda"
import { Card } from "../ui/Card"
import { Modal } from "../ui/Modal"

/** Anotações (05/10/2026): abas/notas que a pessoa cria pra deixar
 * registrado o que quiser — "controle de recarga de telefone", um lembrete,
 * uma lista. Cada uma vira um card (dá pra recolher e reordenar em "Editar
 * disposição", como os outros). Tudo salva sozinho.
 *
 * São da empresa, não de um módulo: aparecem no Financeiro e/ou na Visão
 * geral (`telas`). A nota nasce na tela em que foi criada e a pessoa troca
 * no próprio card ("Aparece em").
 *
 * Cada anotação tem um formato:
 * - "texto": bloco de notas livre (coluna `texto`);
 * - "lista": itens com tique — `dados = { itens: [{ texto, feito }] }`;
 * - "tabela": controle com colunas (texto, valor em R$ ou data) e total —
 *   `dados = { colunas: [{ nome, tipo }], linhas: [[...]] }`. Valor é número
 *   (ou null), data é "AAAA-MM-DD" (ou ""). */

export type FormatoAnotacao = "texto" | "lista" | "tabela"
export type TipoColunaAnotacao = "texto" | "valor" | "data"

export interface ItemAnotacao {
  texto: string
  feito: boolean
}

export interface ColunaAnotacao {
  nome: string
  tipo: TipoColunaAnotacao
}

export type CelulaAnotacao = string | number | null

export interface DadosLista {
  itens: ItemAnotacao[]
}

export interface DadosTabela {
  colunas: ColunaAnotacao[]
  linhas: CelulaAnotacao[][]
}

export type TelaAnotacao = "financeiro" | "visao_geral"

export interface Anotacao {
  id: string
  titulo: string
  texto: string
  formato?: FormatoAnotacao
  dados?: DadosLista | DadosTabela | null
  /** Em que telas a nota aparece (nota antiga: só no Financeiro). */
  telas?: TelaAnotacao[]
  atualizado_em?: string
}

const NOME_TELA: Record<TelaAnotacao, string> = { financeiro: "Financeiro", visao_geral: "Visão geral" }

/** A nota aparece nesta tela? Empresa sem o Financeiro só tem a Visão
 * geral: lá aparecem todas (senão uma nota "do Financeiro" ficaria perdida). */
export function anotacaoApareceEm(nota: Anotacao, tela: TelaAnotacao, temFinanceiro: boolean): boolean {
  if (tela === "visao_geral" && !temFinanceiro) return true
  return (nota.telas?.length ? nota.telas : ["financeiro"]).includes(tela)
}

// Os mesmos limites que o servidor confere.
const MAX_TEXTO = 20000
const MAX_ITENS = 200
const MAX_COLUNAS = 8
const MAX_LINHAS = 300
const MAX_TEXTO_ITEM = 500
const MAX_NOME_COLUNA = 40

const FORMATOS: { id: FormatoAnotacao; nome: string; descricao: string; icone: ReactNode }[] = [
  { id: "texto", nome: "Texto", descricao: "Escreva livremente, como num bloco de notas.", icone: <AlignLeft size={18} /> },
  { id: "lista", nome: "Lista", descricao: "Itens pra ir marcando conforme você faz.", icone: <ListChecks size={18} /> },
  { id: "tabela", nome: "Tabela", descricao: "Controle com colunas, datas e valores somados no fim.", icone: <Table2 size={18} /> },
]

const TIPOS_COLUNA: { id: TipoColunaAnotacao; nome: string }[] = [
  { id: "texto", nome: "Texto" },
  { id: "valor", nome: "Valor (R$)" },
  { id: "data", nome: "Data" },
]

/** Tabela que nasce pronta pra um controle simples (ex.: recarga de telefone). */
function tabelaPadrao(): DadosTabela {
  return {
    colunas: [
      { nome: "Data", tipo: "data" },
      { nome: "Valor", tipo: "valor" },
      { nome: "Observação", tipo: "texto" },
    ],
    linhas: [["", null, ""]],
  }
}

function celulaVazia(tipo: TipoColunaAnotacao): CelulaAnotacao {
  return tipo === "valor" ? null : ""
}

function celulaTemConteudo(celula: CelulaAnotacao): boolean {
  return typeof celula === "number" || (typeof celula === "string" && celula.trim() !== "")
}

function itensDe(dados: unknown): ItemAnotacao[] {
  const itens = (dados as DadosLista | null | undefined)?.itens
  if (!Array.isArray(itens)) return []
  return itens.map((i) => ({ texto: String(i?.texto ?? ""), feito: i?.feito === true }))
}

function tabelaDe(dados: unknown): DadosTabela {
  const d = dados as Partial<DadosTabela> | null | undefined
  const colunas: ColunaAnotacao[] = Array.isArray(d?.colunas) && d.colunas.length > 0 ? d.colunas : [{ nome: "Anotação", tipo: "texto" }]
  const linhas = Array.isArray(d?.linhas) ? d.linhas.map((l) => colunas.map((c, i) => (Array.isArray(l) ? (l[i] ?? celulaVazia(c.tipo)) : celulaVazia(c.tipo)))) : []
  return { colunas, linhas }
}

/** Como a célula aparece escrita (na conversão pra texto/lista). */
function textoDaCelula(tipo: TipoColunaAnotacao, celula: CelulaAnotacao): string {
  if (tipo === "valor") return typeof celula === "number" ? formatBRL(celula) : ""
  if (tipo === "data") return typeof celula === "string" ? formatData(celula) : ""
  return String(celula ?? "").trim()
}

// --- Datas: a pessoa digita e vê dd/mm/aaaa; o que guarda é AAAA-MM-DD ---

function mascaraData(digitos: string): string {
  if (digitos.length <= 2) return digitos
  if (digitos.length <= 4) return `${digitos.slice(0, 2)}/${digitos.slice(2)}`
  return `${digitos.slice(0, 2)}/${digitos.slice(2, 4)}/${digitos.slice(4)}`
}

/** "05102026" → "2026-10-05" (null se a data não existe). */
function isoDeDigitos(digitos: string): string | null {
  if (digitos.length !== 8) return null
  const dia = Number(digitos.slice(0, 2))
  const mes = Number(digitos.slice(2, 4))
  const ano = Number(digitos.slice(4))
  const d = new Date(ano, mes - 1, dia)
  if (ano < 1900 || ano > 2200 || d.getFullYear() !== ano || d.getMonth() !== mes - 1 || d.getDate() !== dia) return null
  return `${digitos.slice(4)}-${digitos.slice(2, 4)}-${digitos.slice(0, 2)}`
}

/** Completa o que faltou: "0510" vira deste ano, "051026" vira 2026. */
function completarData(digitos: string): string {
  if (digitos.length === 4) return digitos + String(new Date().getFullYear())
  if (digitos.length === 6) return `${digitos.slice(0, 4)}20${digitos.slice(4)}`
  return digitos
}

// --- Mudar de formato sem perder o que já estava escrito ---

interface Conteudo {
  formato: FormatoAnotacao
  texto: string
  dados: DadosLista | DadosTabela | null
}

const MARCA_FEITO = "✓ "

/** O conteúdo da nota como linhas soltas — o meio do caminho de toda conversão. */
function linhasDoConteudo(c: Conteudo): ItemAnotacao[] {
  if (c.formato === "lista") {
    return itensDe(c.dados)
      .map((i) => ({ texto: i.texto.trim(), feito: i.feito }))
      .filter((i) => i.texto)
  }
  const brutas =
    c.formato === "tabela"
      ? (() => {
          const t = tabelaDe(c.dados)
          return t.linhas.map((linha) =>
            t.colunas
              .map((coluna, i) => textoDaCelula(coluna.tipo, linha[i]))
              .filter(Boolean)
              .join(" · "),
          )
        })()
      : c.texto.split("\n")
  return brutas
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => (l.startsWith(MARCA_FEITO) && l.length > MARCA_FEITO.length ? { texto: l.slice(MARCA_FEITO.length).trim(), feito: true } : { texto: l, feito: false }))
}

function converterConteudo(c: Conteudo, para: FormatoAnotacao): { texto: string; dados: Conteudo["dados"] } | { erro: string } {
  const linhas = linhasDoConteudo(c)
  const escrita = linhas.map((l) => (l.feito ? MARCA_FEITO : "") + l.texto)
  if (para === "texto") {
    const texto = escrita.join("\n")
    if (texto.length > MAX_TEXTO) return { erro: "Esta anotação é grande demais pra virar texto. Apague algumas linhas antes." }
    return { texto, dados: null }
  }
  if (escrita.some((l) => l.length > MAX_TEXTO_ITEM)) {
    return { erro: `Tem uma linha comprida demais pra caber (até ${MAX_TEXTO_ITEM} letras por linha). Encurte ou quebre essa linha antes.` }
  }
  if (para === "lista") {
    if (linhas.length > MAX_ITENS) return { erro: `Esta anotação tem ${linhas.length} linhas e a lista aceita até ${MAX_ITENS}. Apague algumas antes.` }
    return { texto: "", dados: { itens: linhas } }
  }
  if (linhas.length > MAX_LINHAS) return { erro: `Esta anotação tem ${linhas.length} linhas e a tabela aceita até ${MAX_LINHAS}. Apague algumas antes.` }
  if (linhas.length === 0) return { texto: "", dados: tabelaPadrao() }
  return { texto: "", dados: { colunas: [{ nome: "Anotação", tipo: "texto" }], linhas: escrita.map((l) => [l]) } }
}

/** Troca o tipo de uma coluna aproveitando o que der das células. */
function converterCelula(de: TipoColunaAnotacao, para: TipoColunaAnotacao, celula: CelulaAnotacao): CelulaAnotacao {
  if (de === para) return celula
  if (para === "texto") {
    if (de === "valor") return typeof celula === "number" ? formatarMoedaCampo(celula) : ""
    return typeof celula === "string" ? formatData(celula) : ""
  }
  if (de !== "texto" || typeof celula !== "string") return celulaVazia(para)
  if (para === "valor") {
    const n = parseBRL(celula)
    return n == null ? null : Math.round(n * 100) / 100
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(celula.trim())) return celula.trim()
  // "5/10/2026", "05/10" ou "051026": completa zeros e ano antes de conferir.
  const partes = celula.trim().match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2}|\d{4}))?$/)
  const digitos = partes ? partes[1].padStart(2, "0") + partes[2].padStart(2, "0") + (partes[3] ?? "") : celula.replace(/\D/g, "")
  return isoDeDigitos(completarData(digitos)) ?? ""
}

/** `tela`: onde a pessoa está — a nota criada aqui nasce aparecendo aqui. */
export function useAnotacoes(ligado: boolean, tela: TelaAnotacao = "financeiro") {
  const [anotacoes, setAnotacoes] = useState<Anotacao[]>([])
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (!ligado) return
    api.get<Anotacao[]>("/financeiro/anotacoes").then(setAnotacoes).catch(() => undefined)
  }, [ligado])

  const criar = useCallback(async (titulo: string, formato: FormatoAnotacao = "texto") => {
    setErro(null)
    try {
      const nova = await api.post<Anotacao>("/financeiro/anotacoes", {
        titulo,
        formato,
        telas: [tela],
        ...(formato === "tabela" ? { dados: tabelaPadrao() } : {}),
      })
      setAnotacoes((a) => [...a, nova])
      return nova
    } catch (err) {
      setErro(mensagemErro(err))
      return null
    }
  }, [tela])

  const atualizar = useCallback((id: string, mudanca: Partial<Anotacao>) => {
    setAnotacoes((a) => a.map((n) => (n.id === id ? { ...n, ...mudanca } : n)))
  }, [])

  const apagar = useCallback(async (id: string) => {
    setErro(null)
    try {
      await api.delete(`/financeiro/anotacoes/${id}`)
      setAnotacoes((a) => a.filter((n) => n.id !== id))
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }, [])

  return { anotacoes, erro, criar, atualizar, apagar }
}

/** Janela do "Nova anotação": a pessoa escolhe o formato antes de criar. */
export function EscolherFormatoAnotacao({ onEscolher, onClose }: { onEscolher: (formato: FormatoAnotacao) => void; onClose: () => void }) {
  return (
    <Modal titulo="Nova anotação" onClose={onClose} largura="max-w-md">
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">Como você quer anotar?</p>
      <div className="flex flex-col gap-2">
        {FORMATOS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => onEscolher(f.id)}
            className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-left transition-colors hover:border-primary-400 hover:bg-primary-50/60 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:hover:border-primary-500 dark:hover:bg-primary-900/20"
          >
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">
              {f.icone}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">{f.nome}</span>
              <span className="block text-sm text-slate-500 dark:text-slate-400">{f.descricao}</span>
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">Se mudar de ideia, dá pra trocar o formato depois.</p>
    </Modal>
  )
}

const BOTAO_LEVE =
  "inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-50 dark:text-primary-300 dark:hover:bg-primary-900/30"
const BOTAO_APAGAR =
  "shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:text-slate-500 dark:hover:bg-danger-900/30"
const CAMPO_CELULA =
  "block w-full bg-transparent px-2.5 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:bg-primary-50/70 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500 dark:text-slate-100 dark:placeholder:text-slate-600 dark:focus:bg-slate-900"

type Carga = Partial<Pick<Anotacao, "texto" | "formato" | "dados" | "telas">>

export function AnotacaoCard({
  nota,
  onMudou,
  onApagar,
  nova = false,
  tela = "financeiro",
  podeTrocarTela = false,
}: {
  /** Acabou de ser criada: já abre pedindo o nome. */
  nova?: boolean
  /** A tela em que este card está sendo mostrado. */
  tela?: TelaAnotacao
  /** A empresa tem as duas telas (Financeiro e Visão geral): mostra o "Aparece em". */
  podeTrocarTela?: boolean
  nota: Anotacao
  onMudou: (mudanca: Partial<Anotacao>) => void
  onApagar: () => void
}) {
  const [conteudo, setConteudo] = useState<Conteudo>({ formato: nota.formato ?? "texto", texto: nota.texto ?? "", dados: nota.dados ?? null })
  const [titulo, setTitulo] = useState(nota.titulo)
  const [renomeando, setRenomeando] = useState(nova)
  const [estado, setEstado] = useState<"salvo" | "salvando" | "erro">("salvo")
  const [aviso, setAviso] = useState<string | null>(null)

  // Salvar sozinho: o que mudou fica em `pendente` e vai pro servidor depois
  // de uma pausa na digitação. Um pedido por vez, na ordem — o que a pessoa
  // digitar enquanto um pedido está no ar vai no próximo. Se falhar, o que
  // não foi salvo continua em `pendente` pra próxima tentativa.
  const pendente = useRef<Carga | null>(null)
  const noAr = useRef(false)
  const espera = useRef<number | undefined>(undefined)
  const avisarPai = useRef(onMudou)
  useEffect(() => {
    avisarPai.current = onMudou
  })

  const enviar = useCallback(function enviarPendente() {
    window.clearTimeout(espera.current)
    if (noAr.current || !pendente.current) return
    const carga = pendente.current
    pendente.current = null
    noAr.current = true
    // A página guarda a versão nova já agora: se o card for recolhido e
    // aberto de novo, volta com o que a pessoa escreveu.
    avisarPai.current(carga)
    api
      .patch<Anotacao>(`/financeiro/anotacoes/${nota.id}`, carga)
      .then(() => {
        noAr.current = false
        if (pendente.current) enviarPendente()
        else setEstado("salvo")
      })
      .catch(() => {
        noAr.current = false
        pendente.current = { ...carga, ...pendente.current }
        setEstado("erro")
      })
  }, [nota.id])

  function salvar(mudanca: Carga, agora = false) {
    pendente.current = { ...pendente.current, ...mudanca }
    setEstado("salvando")
    window.clearTimeout(espera.current)
    if (agora) enviar()
    else espera.current = window.setTimeout(enviar, 700)
  }

  // Recolher o card (ou sair da tela) no meio da pausa não perde o que foi digitado.
  useEffect(() => () => enviar(), [enviar])

  function mudarTexto(texto: string) {
    setConteudo((c) => ({ ...c, texto }))
    salvar({ texto })
  }

  function mudarDados(dados: DadosLista | DadosTabela, agora = false) {
    setConteudo((c) => ({ ...c, dados }))
    salvar({ dados }, agora)
  }

  function mudarFormato(para: FormatoAnotacao) {
    if (para === conteudo.formato) return
    setAviso(null)
    const convertido = converterConteudo(conteudo, para)
    if ("erro" in convertido) {
      setAviso(convertido.erro)
      return
    }
    if (conteudo.formato === "tabela") {
      const t = tabelaDe(conteudo.dados)
      const temAlgo = t.linhas.some((l) => l.some(celulaTemConteudo))
      const destino = para === "lista" ? "um item da lista" : "uma linha de texto"
      if (temAlgo && !window.confirm(`Mudar o formato desfaz a tabela: cada linha vira ${destino} e as colunas e os totais deixam de existir. Continuar?`)) return
    }
    setConteudo({ formato: para, ...convertido })
    salvar({ formato: para, ...convertido }, true)
  }

  const telas: TelaAnotacao[] = nota.telas?.length ? nota.telas : ["financeiro"]
  const ondeAparece = telas.length > 1 ? "duas" : telas[0]

  function mudarTelas(para: string) {
    const novas: TelaAnotacao[] = para === "duas" ? ["financeiro", "visao_geral"] : [para as TelaAnotacao]
    const outra = novas[0]
    // Sai desta tela: avisa antes, pra pessoa não achar que a nota sumiu.
    if (!novas.includes(tela) && !window.confirm(`A anotação "${nota.titulo}" sai desta tela e passa a aparecer só em ${NOME_TELA[outra]}. Continuar?`)) return
    onMudou({ telas: novas })
    salvar({ telas: novas }, true)
  }

  async function salvarTitulo() {
    const novo = titulo.trim()
    setRenomeando(false)
    if (!novo || novo === nota.titulo) {
      setTitulo(nota.titulo)
      return
    }
    try {
      await api.patch(`/financeiro/anotacoes/${nota.id}`, { titulo: novo })
      onMudou({ titulo: novo })
    } catch {
      setTitulo(nota.titulo)
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        {renomeando ? (
          <form
            className="flex min-w-[10rem] flex-1 items-center gap-1.5"
            onSubmit={(e) => {
              e.preventDefault()
              void salvarTitulo()
            }}
          >
            <input
              autoFocus
              value={titulo}
              maxLength={80}
              onChange={(e) => setTitulo(e.target.value)}
              // Já vem selecionado: é só digitar o nome por cima.
              onFocus={(e) => e.currentTarget.select()}
              onBlur={() => void salvarTitulo()}
              aria-label="Nome da anotação"
              className="w-full max-w-sm rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            <button type="submit" aria-label="Salvar nome" className="rounded p-1.5 text-success-600 hover:bg-slate-100 dark:hover:bg-slate-700">
              <Check size={15} />
            </button>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setRenomeando(true)}
            title="Mudar o nome"
            className="flex min-w-[7.5rem] flex-1 items-center gap-1.5 whitespace-nowrap text-left text-xs font-medium text-slate-400 hover:text-primary-600 dark:text-slate-500"
          >
            <Pencil size={13} /> mudar o nome
          </button>
        )}
        <select
          value={conteudo.formato}
          onChange={(e) => mudarFormato(e.target.value as FormatoAnotacao)}
          aria-label={`Formato da anotação ${nota.titulo}`}
          title="Mudar o formato desta anotação"
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs text-slate-600 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300"
        >
          {FORMATOS.map((f) => (
            <option key={f.id} value={f.id}>
              {f.nome}
            </option>
          ))}
        </select>
        {podeTrocarTela && (
          <label className="flex shrink-0 items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
            <span>Aparece em</span>
            <select
              value={ondeAparece}
              onChange={(e) => mudarTelas(e.target.value)}
              aria-label={`Em que tela a anotação ${nota.titulo} aparece`}
              title="Escolha em que tela esta anotação aparece"
              className="rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs text-slate-600 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300"
            >
              <option value="financeiro">{tela === "financeiro" ? "só aqui (Financeiro)" : "só no Financeiro"}</option>
              <option value="visao_geral">{tela === "visao_geral" ? "só aqui (Visão geral)" : "só na Visão geral"}</option>
              <option value="duas">{tela === "financeiro" ? "aqui e na Visão geral" : "aqui e no Financeiro"}</option>
            </select>
          </label>
        )}
        <span className="ml-auto shrink-0 text-xs text-slate-400 dark:text-slate-500" aria-live="polite">
          {estado === "salvando" ? (
            "salvando..."
          ) : estado === "erro" ? (
            <button type="button" onClick={() => { setEstado("salvando"); enviar() }} className="font-medium text-danger-600 underline dark:text-danger-400">
              não salvou — tentar de novo
            </button>
          ) : (
            "salvo"
          )}
        </span>
        <button
          type="button"
          onClick={() => {
            if (window.confirm(`Apagar a anotação "${nota.titulo}"? O que está escrito nela se perde.`)) {
              // Nada pendente deve ir pro servidor depois de apagar.
              window.clearTimeout(espera.current)
              pendente.current = null
              onApagar()
            }
          }}
          aria-label={`Apagar a anotação ${nota.titulo}`}
          title="Apagar"
          className="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
        >
          <Trash2 size={15} />
        </button>
      </div>

      {aviso && (
        <p role="alert" className="mb-2 flex items-start gap-2 rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700 dark:bg-warning-900/40 dark:text-warning-300">
          <span className="flex-1">{aviso}</span>
          <button type="button" onClick={() => setAviso(null)} aria-label="Fechar aviso" className="shrink-0 rounded p-0.5 hover:bg-warning-100 dark:hover:bg-warning-900/60">
            <X size={13} />
          </button>
        </p>
      )}

      {conteudo.formato === "lista" ? (
        <EditorLista titulo={nota.titulo} itens={itensDe(conteudo.dados)} onChange={(itens, agora) => mudarDados({ itens }, agora)} />
      ) : conteudo.formato === "tabela" ? (
        <EditorTabela titulo={nota.titulo} tabela={tabelaDe(conteudo.dados)} onChange={mudarDados} />
      ) : (
        <textarea
          value={conteudo.texto}
          onChange={(e) => mudarTexto(e.target.value)}
          rows={Math.min(14, Math.max(4, conteudo.texto.split("\n").length + 1))}
          maxLength={MAX_TEXTO}
          placeholder="Escreva o que quiser deixar registrado aqui..."
          aria-label={`Texto da anotação ${nota.titulo}`}
          className="w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-800 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      )}
    </Card>
  )
}

// --- Lista: itens com tique; os feitos descem pro fim, riscados ---

function EditorLista({ titulo, itens, onChange }: { titulo: string; itens: ItemAnotacao[]; onChange: (itens: ItemAnotacao[], agora?: boolean) => void }) {
  const [novo, setNovo] = useState("")
  const campoNovo = useRef<HTMLInputElement>(null)
  const feitos = itens.filter((i) => i.feito).length
  const cheia = itens.length >= MAX_ITENS
  // A ordem guardada não muda: só a exibição põe os feitos por último
  // (desmarcar devolve o item pro lugar onde estava).
  const indices = itens.map((_, i) => i)
  const ordem = [...indices.filter((i) => !itens[i].feito), ...indices.filter((i) => itens[i].feito)]

  function adicionar() {
    const texto = novo.trim()
    if (!texto || cheia) return
    onChange([...itens, { texto, feito: false }], true)
    setNovo("")
    campoNovo.current?.focus()
  }

  function linha(i: number) {
    const item = itens[i]
    return (
      <li key={i} className="group flex items-center gap-1">
        <label className="flex shrink-0 cursor-pointer items-center p-2">
          <input
            type="checkbox"
            checked={item.feito}
            onChange={(e) => onChange(itens.map((x, j) => (j === i ? { ...x, feito: e.target.checked } : x)), true)}
            aria-label={`${item.feito ? "Desmarcar" : "Marcar como feito"}: ${item.texto || "item sem texto"}`}
            className="h-[18px] w-[18px] cursor-pointer rounded border-slate-300 accent-primary-600"
          />
        </label>
        <input
          value={item.texto}
          maxLength={MAX_TEXTO_ITEM}
          onChange={(e) => onChange(itens.map((x, j) => (j === i ? { ...x, texto: e.target.value } : x)))}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              campoNovo.current?.focus()
            }
          }}
          aria-label="Texto do item"
          className={`min-w-0 flex-1 rounded-md border border-transparent bg-transparent px-1.5 py-1 text-sm hover:border-slate-200 focus:border-primary-500 focus:bg-white focus:outline-none dark:hover:border-slate-700 dark:focus:bg-slate-900 ${
            item.feito ? "text-slate-400 line-through dark:text-slate-500" : "text-slate-800 dark:text-slate-100"
          }`}
        />
        <button type="button" onClick={() => onChange(itens.filter((_, j) => j !== i), true)} aria-label={`Apagar o item ${item.texto || "sem texto"}`} title="Apagar item" className={BOTAO_APAGAR}>
          <X size={14} />
        </button>
      </li>
    )
  }

  const pendentes = ordem.filter((i) => !itens[i].feito)
  const prontos = ordem.filter((i) => itens[i].feito)

  return (
    <div>
      <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400" aria-live="polite">
        {itens.length === 0 ? "Nenhum item ainda. Escreva o primeiro aqui embaixo." : `${feitos} de ${itens.length} ${feitos === 1 ? "feito" : "feitos"}`}
      </p>
      {pendentes.length > 0 && <ul aria-label={`Itens a fazer de ${titulo}`}>{pendentes.map(linha)}</ul>}
      {cheia ? (
        <p className="my-1 text-xs text-slate-400 dark:text-slate-500">A lista chegou em {MAX_ITENS} itens. Apague algum pra colocar outro.</p>
      ) : (
        <form
          className="my-1 flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault()
            adicionar()
          }}
        >
          <input
            ref={campoNovo}
            value={novo}
            maxLength={MAX_TEXTO_ITEM}
            onChange={(e) => setNovo(e.target.value)}
            placeholder="Novo item..."
            aria-label={`Novo item da lista ${titulo}`}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <button type="submit" disabled={!novo.trim()} className={BOTAO_LEVE}>
            <Plus size={14} /> Adicionar
          </button>
        </form>
      )}
      {prontos.length > 0 && (
        <ul aria-label={`Itens feitos de ${titulo}`} className="mt-1 border-t border-dashed border-slate-200 pt-1 dark:border-slate-700">
          {prontos.map(linha)}
        </ul>
      )}
    </div>
  )
}

// --- Tabela: colunas que a pessoa define, linhas e total dos valores ---

function CampoDataCelula({ valor, onChange, rotulo }: { valor: string; onChange: (iso: string) => void; rotulo: string }) {
  // Enquanto a pessoa digita, vale o rascunho; fora disso, o que está salvo.
  const [rascunho, setRascunho] = useState<string | null>(null)
  const digitos = (rascunho ?? "").replace(/\D/g, "")
  const invalida = rascunho !== null && digitos.length === 8 && isoDeDigitos(digitos) === null
  return (
    <input
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder="dd/mm/aaaa"
      aria-label={rotulo}
      aria-invalid={invalida || undefined}
      title={invalida ? "Essa data não existe" : undefined}
      value={rascunho ?? formatData(valor)}
      onChange={(e) => {
        const bruto = e.target.value
        let d = bruto.replace(/\D/g, "").slice(0, 8)
        // "1/" ou "01/2/": a barra depois de um número só completa com zero.
        if (bruto.endsWith("/") && (d.length === 1 || d.length === 3)) d = `${d.slice(0, -1)}0${d.slice(-1)}`
        setRascunho(mascaraData(d))
        if (d.length === 0) onChange("")
        else {
          const iso = isoDeDigitos(d)
          if (iso) onChange(iso)
        }
      }}
      onBlur={() => {
        // Data pela metade: completa o ano se der; senão volta a última válida.
        const iso = isoDeDigitos(completarData(digitos))
        if (rascunho !== null && iso && iso !== valor) onChange(iso)
        setRascunho(null)
      }}
      className={`${CAMPO_CELULA} min-w-28 tabular-nums ${invalida ? "text-danger-600 ring-2 ring-inset ring-danger-400 dark:text-danger-400" : ""}`}
    />
  )
}

function EditorTabela({ titulo, tabela, onChange }: { titulo: string; tabela: DadosTabela; onChange: (dados: DadosTabela, agora?: boolean) => void }) {
  const { colunas, linhas } = tabela
  const [ajustando, setAjustando] = useState(false)
  const corpo = useRef<HTMLTableSectionElement>(null)
  const focar = useRef<number | null>(null)

  // Linha nova: o cursor já vai pra primeira célula dela.
  useEffect(() => {
    if (focar.current === null) return
    corpo.current?.querySelector<HTMLInputElement>(`[data-linha="${focar.current}"] input`)?.focus()
    focar.current = null
  }, [linhas.length])

  const temValor = colunas.some((c) => c.tipo === "valor")
  const totais = colunas.map((c, i) => (c.tipo === "valor" ? linhas.reduce((s, l) => s + (typeof l[i] === "number" ? (l[i] as number) : 0), 0) : null))
  const colunaDoRotulo = colunas.findIndex((c) => c.tipo !== "valor")

  function mudarCelula(l: number, c: number, valor: CelulaAnotacao) {
    onChange({ colunas, linhas: linhas.map((linha, i) => (i === l ? linha.map((x, j) => (j === c ? valor : x)) : linha)) })
  }

  function adicionarLinha() {
    if (linhas.length >= MAX_LINHAS) return
    focar.current = linhas.length
    onChange({ colunas, linhas: [...linhas, colunas.map((c) => celulaVazia(c.tipo))] }, true)
  }

  function apagarLinha(l: number) {
    if (linhas[l].some(celulaTemConteudo) && !window.confirm(`Apagar a linha ${l + 1}? O que está escrito nela se perde.`)) return
    onChange({ colunas, linhas: linhas.filter((_, i) => i !== l) }, true)
  }

  function adicionarColuna() {
    if (colunas.length >= MAX_COLUNAS) return
    onChange({ colunas: [...colunas, { nome: `Coluna ${colunas.length + 1}`, tipo: "texto" }], linhas: linhas.map((l) => [...l, ""]) }, true)
  }

  function apagarColuna(c: number) {
    if (colunas.length <= 1) return
    const nome = colunas[c].nome || `coluna ${c + 1}`
    if (linhas.some((l) => celulaTemConteudo(l[c])) && !window.confirm(`Apagar a coluna "${nome}"? O que está escrito nela se perde.`)) return
    onChange({ colunas: colunas.filter((_, i) => i !== c), linhas: linhas.map((l) => l.filter((_, i) => i !== c)) }, true)
  }

  function mudarTipo(c: number, tipo: TipoColunaAnotacao) {
    const de = colunas[c].tipo
    if (de === tipo) return
    const novas = linhas.map((l) => l.map((x, i) => (i === c ? converterCelula(de, tipo, x) : x)))
    const perdas = linhas.filter((l, i) => celulaTemConteudo(l[c]) && !celulaTemConteudo(novas[i][c])).length
    if (perdas > 0) {
      const nomeTipo = TIPOS_COLUNA.find((t) => t.id === tipo)?.nome ?? tipo
      const quantas = perdas === 1 ? "1 linha tem algo" : `${perdas} linhas têm algo`
      if (!window.confirm(`${quantas} nesta coluna que não dá pra aproveitar como "${nomeTipo}" e vai ficar em branco. Continuar?`)) return
    }
    onChange({ colunas: colunas.map((x, i) => (i === c ? { ...x, tipo } : x)), linhas: novas }, true)
  }

  const borda = "border-slate-200 dark:border-slate-700"

  return (
    <div>
      {/* Em tela estreita a tabela rola de lado dentro do card. */}
      <div className={`overflow-x-auto rounded-lg border ${borda}`}>
        <table className="w-full border-collapse text-sm" aria-label={`Tabela da anotação ${titulo}`}>
          <thead className="bg-slate-50 dark:bg-slate-900/50">
            <tr>
              {colunas.map((coluna, c) => (
                <th key={c} scope="col" className={`border-b border-r ${borda} p-0 text-left align-top font-normal`}>
                  {ajustando ? (
                    <div className="flex min-w-44 flex-col gap-1 p-1.5">
                      <input
                        value={coluna.nome}
                        maxLength={MAX_NOME_COLUNA}
                        onChange={(e) => onChange({ colunas: colunas.map((x, i) => (i === c ? { ...x, nome: e.target.value } : x)), linhas })}
                        placeholder="Nome da coluna"
                        aria-label={`Nome da coluna ${c + 1}`}
                        className="w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                      />
                      <div className="flex items-center gap-1">
                        <select
                          value={coluna.tipo}
                          onChange={(e) => mudarTipo(c, e.target.value as TipoColunaAnotacao)}
                          aria-label={`O que vai na coluna ${coluna.nome || c + 1}`}
                          className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs text-slate-700 focus:border-primary-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
                        >
                          {TIPOS_COLUNA.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.nome}
                            </option>
                          ))}
                        </select>
                        {colunas.length > 1 && (
                          <button type="button" onClick={() => apagarColuna(c)} aria-label={`Apagar a coluna ${coluna.nome || c + 1}`} title="Apagar coluna" className={BOTAO_APAGAR}>
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <span className={`block whitespace-nowrap px-2.5 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 ${coluna.tipo === "valor" ? "text-right" : ""}`}>
                      {coluna.nome || <span className="font-normal italic text-slate-400 dark:text-slate-500">sem nome</span>}
                    </span>
                  )}
                </th>
              ))}
              <th className={`w-9 border-b ${borda} p-0`}>
                <span className="sr-only">Apagar linha</span>
              </th>
            </tr>
          </thead>
          <tbody ref={corpo}>
            {linhas.length === 0 && (
              <tr>
                <td colSpan={colunas.length + 1} className="px-3 py-4 text-center text-xs text-slate-400 dark:text-slate-500">
                  Nenhuma linha ainda. Toque em "Adicionar linha".
                </td>
              </tr>
            )}
            {linhas.map((linha, l) => (
              <tr key={l} data-linha={l}>
                {colunas.map((coluna, c) => {
                  const rotulo = `${coluna.nome || `Coluna ${c + 1}`}, linha ${l + 1}`
                  const celula = linha[c]
                  return (
                    <td key={c} className={`border-b border-r ${borda} p-0`}>
                      {coluna.tipo === "valor" ? (
                        <CampoMoeda
                          valor={typeof celula === "number" ? celula.toFixed(2) : ""}
                          onChange={(v) => mudarCelula(l, c, v === "" ? null : Number(v))}
                          aria-label={rotulo}
                          className={`${CAMPO_CELULA} min-w-32 text-right tabular-nums`}
                        />
                      ) : coluna.tipo === "data" ? (
                        <CampoDataCelula valor={typeof celula === "string" ? celula : ""} onChange={(iso) => mudarCelula(l, c, iso)} rotulo={rotulo} />
                      ) : (
                        <input
                          value={typeof celula === "string" ? celula : String(celula ?? "")}
                          maxLength={MAX_TEXTO_ITEM}
                          onChange={(e) => mudarCelula(l, c, e.target.value)}
                          aria-label={rotulo}
                          className={`${CAMPO_CELULA} min-w-40`}
                        />
                      )}
                    </td>
                  )
                })}
                <td className={`border-b ${borda} p-0 text-center`}>
                  <button type="button" onClick={() => apagarLinha(l)} aria-label={`Apagar a linha ${l + 1}`} title="Apagar linha" className={BOTAO_APAGAR}>
                    <X size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          {temValor && (
            <tfoot className="bg-slate-50 dark:bg-slate-900/50">
              <tr>
                {colunas.map((coluna, c) => (
                  <td key={c} className={`border-r ${borda} whitespace-nowrap px-2.5 py-2 text-sm ${coluna.tipo === "valor" ? "text-right font-semibold tabular-nums text-slate-900 dark:text-slate-100" : "font-medium text-slate-500 dark:text-slate-400"}`}>
                    {totais[c] !== null ? (
                      <>
                        {colunaDoRotulo === -1 && c === 0 && <span className="mr-2 text-xs font-medium text-slate-500 dark:text-slate-400">Total</span>}
                        <span aria-label={`Total de ${coluna.nome || `coluna ${c + 1}`}`}>{formatBRL(totais[c] as number)}</span>
                      </>
                    ) : c === colunaDoRotulo ? (
                      "Total"
                    ) : null}
                  </td>
                ))}
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1">
        <button type="button" onClick={adicionarLinha} disabled={linhas.length >= MAX_LINHAS} className={BOTAO_LEVE}>
          <Plus size={14} /> Adicionar linha
        </button>
        {ajustando && (
          <button type="button" onClick={adicionarColuna} disabled={colunas.length >= MAX_COLUNAS} className={BOTAO_LEVE}>
            <Plus size={14} /> Nova coluna
          </button>
        )}
        <button type="button" onClick={() => setAjustando((a) => !a)} aria-pressed={ajustando} className={`${BOTAO_LEVE} ml-auto`}>
          {ajustando ? <Check size={14} /> : <Settings2 size={14} />} {ajustando ? "Pronto" : "Ajustar colunas"}
        </button>
      </div>
      {ajustando && (
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Dê um nome pra cada coluna e escolha o que vai nela: texto, valor em dinheiro (soma sozinho no fim) ou data.
          {colunas.length >= MAX_COLUNAS && ` A tabela pode ter até ${MAX_COLUNAS} colunas.`}
        </p>
      )}
      {linhas.length >= MAX_LINHAS && <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">A tabela chegou em {MAX_LINHAS} linhas. Apague alguma pra colocar outra.</p>}
    </div>
  )
}
