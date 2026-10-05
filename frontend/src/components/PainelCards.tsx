import { ArrowDown, ArrowUp, Check, ChevronDown, Columns2, Eye, EyeOff, GripVertical, Move, RectangleHorizontal, RotateCcw } from "lucide-react"
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react"
import { api } from "../lib/api"

/** Cards de uma tela que a pessoa organiza do jeito dela (05/10/2026): cada
 * um abre e fecha, e em "Editar disposição" ela arruma a tela VENDO os
 * blocos — "seria bom conseguir mexer vendo os blocos para entender como
 * ficará a disposição". Os cards continuam no lugar, com o conteúdo de
 * verdade (só que parado e cortado na altura, pra caberem vários na tela), e
 * cada um ganha uma barra pra arrastar, subir/descer, trocar a largura,
 * recolher e esconder. A escolha fica na conta (e no navegador, pra abrir
 * sem piscar). */

export interface SecaoCard {
  id: string
  titulo: string
  /** Texto curto ao lado do título (um total, uma contagem). */
  resumo?: ReactNode
  conteudo: ReactNode
  /** Âncora pra links (#a-receber). */
  ancora?: string
  /** Não aparece (ex.: card que só existe quando há algo a mostrar). */
  oculto?: boolean
  /** Ocupa meia largura em tela grande (dois cards lado a lado) — é o
   * padrão do card; a pessoa pode trocar em "Editar disposição". */
  meia?: boolean
  /** Rótulo do grupo na edição (ex.: "Notas", "Financeiro"). */
  grupo?: string
}

type Largura = "meia" | "inteira"

/** O que fica salvo por tela (`usuario.preferencias[tela]`). `larguras` entrou
 * depois: layout salvo sem ela continua valendo (cada card na largura padrão). */
interface Disposicao {
  ordem: string[]
  fechados: string[]
  /** Composição: cards que a pessoa tirou da tela. */
  ocultos: string[]
  /** Largura escolhida pela pessoa, só dos cards em que ela mexeu. */
  larguras: Record<string, Largura>
}

function normalizar(d: unknown): Disposicao | null {
  const o = d as Partial<Disposicao> | null
  if (!o || !Array.isArray(o.ordem) || !Array.isArray(o.fechados)) return null
  const larguras: Record<string, Largura> = {}
  if (o.larguras && typeof o.larguras === "object" && !Array.isArray(o.larguras)) {
    for (const [id, l] of Object.entries(o.larguras)) if (l === "meia" || l === "inteira") larguras[id] = l
  }
  return { ordem: o.ordem, fechados: o.fechados, ocultos: Array.isArray(o.ocultos) ? o.ocultos : [], larguras }
}

const chaveLocal = (tela: string) => `ana:disposicao:${tela}`

function lerLocal(tela: string): Disposicao | null {
  try {
    const bruto = localStorage.getItem(chaveLocal(tela))
    return normalizar(bruto ? JSON.parse(bruto) : null)
  } catch {
    return null
  }
}

interface Arrasto {
  id: string
  x: number
  y: number
  /** Onde o bloco cai se soltar agora. */
  alvo: string | null
  depois: boolean
  /** O alvo está ao lado de outro (a marca de destino fica em pé). */
  lateral: boolean
}

// (sem o `display`: o botão de largura só aparece em tela grande)
const BOTAO_BARRA_BASE =
  "h-8 min-w-8 shrink-0 items-center justify-center gap-1 rounded-md px-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary-500 disabled:pointer-events-none disabled:opacity-30 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white"
const BOTAO_BARRA = `inline-flex ${BOTAO_BARRA_BASE}`

/** Barra que acompanha a rolagem. (`position: sticky` não serve aqui: o
 * <main> do app tem `overflow`, então nada gruda no topo da janela.) */
function BarraFixa({ children }: { children: ReactNode }) {
  const marcador = useRef<HTMLDivElement>(null)
  const barra = useRef<HTMLDivElement>(null)
  const [presa, setPresa] = useState<{ left: number; width: number } | null>(null)
  const [altura, setAltura] = useState(0)

  useLayoutEffect(() => {
    const medir = () => {
      const r = marcador.current?.getBoundingClientRect()
      if (!r) return
      setAltura(barra.current?.offsetHeight ?? 0)
      setPresa(r.top < 8 ? { left: r.left, width: r.width } : null)
    }
    medir()
    window.addEventListener("scroll", medir, { passive: true, capture: true })
    window.addEventListener("resize", medir)
    return () => {
      window.removeEventListener("scroll", medir, { capture: true })
      window.removeEventListener("resize", medir)
    }
  }, [])

  return (
    <div ref={marcador} className="xl:col-span-2" style={{ minHeight: altura || undefined }}>
      <div
        ref={barra}
        className={`z-40 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-900 dark:border-primary-800 dark:bg-[#1b2452] dark:text-primary-100 ${presa ? "fixed shadow-lg shadow-slate-900/10" : ""}`}
        style={presa ? { top: 8, left: presa.left, width: presa.width } : undefined}
      >
        {children}
      </div>
    </div>
  )
}

/** O conteúdo do card em modo de edição: aparece de verdade, mas parado
 * (não clica, não foca) e cortado na altura, com um esmaecido embaixo
 * quando tem mais do que cabe. */
function Previa({ ativa, children }: { ativa: boolean; children: ReactNode }) {
  const caixa = useRef<HTMLDivElement>(null)
  const [cortado, setCortado] = useState(false)
  useEffect(() => {
    const el = caixa.current
    if (!ativa || !el) {
      setCortado(false)
      return
    }
    const medir = () => setCortado(el.scrollHeight > el.clientHeight + 4)
    medir()
    if (typeof ResizeObserver === "undefined") return
    const observador = new ResizeObserver(medir)
    observador.observe(el)
    if (el.firstElementChild) observador.observe(el.firstElementChild)
    return () => observador.disconnect()
  }, [ativa])
  return (
    <div
      ref={caixa}
      inert={ativa}
      aria-hidden={ativa || undefined}
      className={ativa ? "pointer-events-none relative max-h-40 select-none overflow-hidden opacity-90 sm:max-h-52" : "min-w-0"}
    >
      <div className="min-w-0">{children}</div>
      {ativa && cortado && (
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-b from-transparent to-slate-100 dark:to-[#141a2e]" />
      )}
    </div>
  )
}

export function PainelCards({
  tela,
  secoes,
  editando,
  fechadosDePadrao = [],
  abrir,
  permitirOcultar = false,
  onConcluir,
}: {
  /** Deixa a pessoa escolher quais cards aparecem (composição da tela). */
  permitirOcultar?: boolean
  tela: "financeiro" | "visao_geral"
  secoes: SecaoCard[]
  editando: boolean
  fechadosDePadrao?: string[]
  /** Id de um card que precisa estar aberto agora (veio de um link). */
  abrir?: string | null
  /** Botão "Concluir" da barra de edição. */
  onConcluir?: () => void
}) {
  const padrao = (): Disposicao => ({ ordem: [], fechados: fechadosDePadrao, ocultos: [], larguras: {} })
  const [disposicao, setDisposicao] = useState<Disposicao>(() => lerLocal(tela) ?? padrao())
  const [arrasto, setArrasto] = useState<Arrasto | null>(null)
  const [aviso, setAviso] = useState("")
  /** Bloco que acabou de voltar pra tela (pisca a borda um instante). */
  const [recemMostrado, setRecemMostrado] = useState<string | null>(null)
  const salvar = useRef<number | undefined>(undefined)
  const blocos = useRef(new Map<string, HTMLElement>())
  const grade = useRef<HTMLDivElement>(null)
  /** Depois de mexer pelo teclado/botão, o foco volta pro mesmo controle. */
  const refocar = useRef<{ id: string; qual: "alca" | "subir" | "descer" } | null>(null)
  const ultimoPonteiro = useRef({ x: 0, y: 0 })

  useEffect(() => {
    let vivo = true
    api
      .get<Record<string, unknown>>("/conta/preferencias")
      .then((p) => {
        const d = normalizar(p?.[tela])
        if (vivo && d) setDisposicao(d)
      })
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [tela])

  function mudar(nova: Disposicao) {
    setDisposicao(nova)
    try {
      localStorage.setItem(chaveLocal(tela), JSON.stringify(nova))
    } catch {
      // navegador sem armazenamento: vale só nesta visita
    }
    window.clearTimeout(salvar.current)
    salvar.current = window.setTimeout(() => {
      api
        .put("/conta/preferencias", { tela, ordem: nova.ordem, fechados: nova.fechados, ocultos: nova.ocultos, larguras: nova.larguras })
        .catch(() => undefined)
    }, 600)
  }

  const visiveis = secoes.filter((s) => !s.oculto)
  // Ordem escolhida primeiro. Card novo (que a pessoa ainda não ordenou) entra
  // logo depois do vizinho que vem antes dele no padrão — não lá no fim da tela.
  const posicoes = new Map<string, number>()
  let anterior = -1
  secoes.forEach((s) => {
    const i = disposicao.ordem.indexOf(s.id)
    anterior = i === -1 ? anterior + 0.001 : i
    posicoes.set(s.id, anterior)
  })
  const posicao = (id: string) => posicoes.get(id) ?? 0
  const ordenadas = [...visiveis].sort((a, b) => posicao(a.id) - posicao(b.id))
  const ids = ordenadas.map((s) => s.id)
  const naTela = ordenadas.filter((s) => !disposicao.ocultos.includes(s.id))
  const escondidas = ordenadas.filter((s) => disposicao.ocultos.includes(s.id))
  const idsNaTela = naTela.map((s) => s.id)
  const ehMeia = (s: SecaoCard) => (disposicao.larguras[s.id] ? disposicao.larguras[s.id] === "meia" : !!s.meia)
  const titulo = (id: string) => secoes.find((s) => s.id === id)?.titulo ?? ""

  // Link pra um card fechado: abre.
  useEffect(() => {
    if (abrir && (disposicao.fechados.includes(abrir) || disposicao.ocultos.includes(abrir)))
      mudar({ ...disposicao, fechados: disposicao.fechados.filter((f) => f !== abrir), ocultos: disposicao.ocultos.filter((f) => f !== abrir) })
  }, [abrir]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!editando) {
      setArrasto(null)
      setAviso("")
    }
  }, [editando])

  // Mexeu pelo teclado: o foco continua no controle do mesmo bloco.
  useEffect(() => {
    const alvo = refocar.current
    if (!alvo) return
    refocar.current = null
    const bloco = blocos.current.get(alvo.id)
    const botao = bloco?.querySelector<HTMLButtonElement>(`[data-controle="${alvo.qual}"]`)
    ;(botao && !botao.disabled ? botao : bloco?.querySelector<HTMLButtonElement>('[data-controle="alca"]'))?.focus({ preventScroll: true })
    bloco?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  })

  function alternar(id: string) {
    const fechados = disposicao.fechados.includes(id) ? disposicao.fechados.filter((f) => f !== id) : [...disposicao.fechados, id]
    mudar({ ...disposicao, fechados })
  }

  function esconder(id: string) {
    mudar({ ...disposicao, ocultos: [...disposicao.ocultos.filter((f) => f !== id), id] })
    setAviso(`${titulo(id)} saiu da tela. Está em “Blocos escondidos”, no fim da página.`)
  }

  function mostrar(id: string) {
    mudar({ ...disposicao, ocultos: disposicao.ocultos.filter((f) => f !== id) })
    setAviso(`${titulo(id)} voltou pra tela.`)
    setRecemMostrado(id)
    window.setTimeout(() => {
      blocos.current.get(id)?.scrollIntoView({ block: "center", behavior: "smooth" })
    }, 60)
    window.setTimeout(() => setRecemMostrado((r) => (r === id ? null : r)), 1800)
  }

  function trocarLargura(s: SecaoCard) {
    const nova: Largura = ehMeia(s) ? "inteira" : "meia"
    const larguras = { ...disposicao.larguras }
    // Voltou pra largura padrão do card: não precisa guardar nada.
    if ((nova === "meia") === !!s.meia) delete larguras[s.id]
    else larguras[s.id] = nova
    mudar({ ...disposicao, larguras })
    setAviso(`${s.titulo} agora ocupa ${nova === "meia" ? "meia largura" : "a largura inteira"}.`)
  }

  /** Põe `id` antes/depois de `alvo` (na ordem completa, que inclui os escondidos). */
  function moverPara(id: string, alvo: string, depois: boolean) {
    if (id === alvo) return
    const nova = ids.filter((x) => x !== id)
    const i = nova.indexOf(alvo)
    if (i === -1) return
    nova.splice(depois ? i + 1 : i, 0, id)
    if (nova.join("|") === ids.join("|")) return
    mudar({ ...disposicao, ordem: nova })
    const lugar = nova.filter((x) => !disposicao.ocultos.includes(x)).indexOf(id) + 1
    setAviso(`${titulo(id)} agora é o ${lugar}º de ${idsNaTela.length} blocos.`)
  }

  function passo(id: string, sentido: -1 | 1, qual: "alca" | "subir" | "descer") {
    const i = idsNaTela.indexOf(id)
    const vizinho = idsNaTela[i + sentido]
    if (i === -1 || !vizinho) return
    refocar.current = { id, qual }
    moverPara(id, vizinho, sentido === 1)
  }

  function voltarAoPadrao() {
    if (!window.confirm("Voltar ao padrão? Os blocos voltam pra ordem e pra largura originais, e os escondidos aparecem de novo.")) return
    mudar(padrao())
    setAviso("A tela voltou ao padrão.")
  }

  // --- Arrastar (mouse, dedo ou caneta: tudo pelo mesmo evento de ponteiro) ---

  function acharAlvo(id: string, x: number, y: number): Pick<Arrasto, "alvo" | "depois" | "lateral"> {
    const larguraGrade = grade.current?.getBoundingClientRect().width ?? 0
    let melhor: { id: string; r: DOMRect; d: number } | null = null
    for (const outro of idsNaTela) {
      if (outro === id) continue
      const r = blocos.current.get(outro)?.getBoundingClientRect()
      if (!r) continue
      const dx = Math.max(r.left - x, 0, x - r.right)
      const dy = Math.max(r.top - y, 0, y - r.bottom)
      const d = Math.hypot(dx, dy)
      if (!melhor || d < melhor.d) melhor = { id: outro, r, d }
    }
    if (!melhor) return { alvo: null, depois: false, lateral: false }
    const { r } = melhor
    // Bloco de meia largura tem vizinho ao lado: decide pela esquerda/direita.
    const lateral = r.width < larguraGrade * 0.75
    const depois = lateral ? x > r.left + r.width / 2 : y > r.top + r.height / 2
    return { alvo: melhor.id, depois, lateral }
  }

  function iniciarArrasto(e: React.PointerEvent<HTMLButtonElement>, id: string) {
    if (e.pointerType === "mouse" && e.button !== 0) return
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    ultimoPonteiro.current = { x: e.clientX, y: e.clientY }
    setArrasto({ id, x: e.clientX, y: e.clientY, alvo: null, depois: false, lateral: false })
  }

  function moverArrasto(e: React.PointerEvent) {
    if (!arrasto) return
    ultimoPonteiro.current = { x: e.clientX, y: e.clientY }
    setArrasto({ id: arrasto.id, x: e.clientX, y: e.clientY, ...acharAlvo(arrasto.id, e.clientX, e.clientY) })
  }

  function soltarArrasto() {
    if (!arrasto) return
    const { id, alvo, depois } = arrasto
    setArrasto(null)
    if (alvo) moverPara(id, alvo, depois)
  }

  const arrastando = arrasto?.id ?? null
  // Perto da borda da janela, a página rola sozinha; Esc desiste.
  useEffect(() => {
    if (!arrastando) return
    let quadro = 0
    const rolar = () => {
      const { x, y } = ultimoPonteiro.current
      const margem = 90
      const passoRolagem = y < margem ? -Math.ceil((margem - y) / 6) : y > window.innerHeight - margem ? Math.ceil((y - (window.innerHeight - margem)) / 6) : 0
      if (passoRolagem) {
        const antes = window.scrollY
        window.scrollBy(0, passoRolagem)
        if (window.scrollY !== antes) setArrasto((a) => (a ? { ...a, ...acharAlvo(a.id, x, y) } : a))
      }
      quadro = requestAnimationFrame(rolar)
    }
    quadro = requestAnimationFrame(rolar)
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setArrasto(null)
    }
    window.addEventListener("keydown", esc)
    return () => {
      cancelAnimationFrame(quadro)
      window.removeEventListener("keydown", esc)
    }
  }, [arrastando]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={grade} className={`grid grid-cols-1 xl:grid-cols-2 ${editando ? "gap-4" : "gap-6"} ${arrasto ? "cursor-grabbing select-none" : ""}`}>
      {editando && (
        <BarraFixa>
          <Move size={16} className="shrink-0" aria-hidden />
          <p className="min-w-0 flex-1 basis-48">
            <strong className="font-semibold">Arraste os blocos pra organizar</strong>
            <span className="text-primary-800/80 dark:text-primary-200/80">
              {" "}
              — pegue pelos pontinhos ou use as setas. Fica salvo na sua conta.
            </span>
          </p>
          <span className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={voltarAoPadrao}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-primary-800 hover:bg-primary-100 dark:text-primary-100 dark:hover:bg-primary-800/60"
            >
              <RotateCcw size={14} aria-hidden /> Voltar ao padrão
            </button>
            {onConcluir && (
              <button
                type="button"
                onClick={onConcluir}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
              >
                <Check size={15} aria-hidden /> Concluir
              </button>
            )}
          </span>
        </BarraFixa>
      )}

      {naTela.map((s, i) => {
        const fechado = disposicao.fechados.includes(s.id)
        const meia = ehMeia(s)
        const alvoAqui = arrasto?.alvo === s.id ? arrasto : null
        return (
          <section
            key={s.id}
            id={s.ancora}
            ref={(el) => {
              if (el) blocos.current.set(s.id, el)
              else blocos.current.delete(s.id)
            }}
            aria-label={editando ? `Bloco ${s.titulo}` : undefined}
            className={`relative min-w-0 scroll-mt-20 ${meia ? "" : "xl:col-span-2"} ${
              editando
                ? `rounded-2xl border bg-slate-100 p-1.5 transition-[opacity,box-shadow] dark:bg-[#141a2e] ${
                    arrastando === s.id
                      ? "border-primary-500 opacity-40"
                      : recemMostrado === s.id
                        ? "border-primary-500 ring-2 ring-primary-300 dark:ring-primary-600"
                        : "border-slate-300 dark:border-slate-600"
                  }`
                : ""
            }`}
          >
            {editando ? (
              <div className="mb-1.5 flex items-center gap-0.5 rounded-xl border border-slate-200 bg-white py-1 pl-1 pr-1.5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <button
                  type="button"
                  data-controle="alca"
                  aria-label={`Mover ${s.titulo}: arraste, ou use as setas do teclado`}
                  title="Arraste pra mudar de lugar"
                  onPointerDown={(e) => iniciarArrasto(e, s.id)}
                  onPointerMove={moverArrasto}
                  onPointerUp={soltarArrasto}
                  onPointerCancel={() => setArrasto(null)}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                      e.preventDefault()
                      passo(s.id, -1, "alca")
                    } else if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                      e.preventDefault()
                      passo(s.id, 1, "alca")
                    }
                  }}
                  className={`${BOTAO_BARRA} touch-none ${arrasto ? "cursor-grabbing" : "cursor-grab"}`}
                >
                  <GripVertical size={18} aria-hidden />
                </button>
                <span className="min-w-0 flex-1 truncate px-1 text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {s.titulo}
                  {s.grupo && <span className="ml-2 hidden text-xs sm:inline font-normal text-slate-400 dark:text-slate-500">{s.grupo}</span>}
                </span>
                {/* A largura só muda alguma coisa onde cabem dois lado a lado (tela grande). */}
                <button
                  type="button"
                  onClick={() => trocarLargura(s)}
                  aria-label={`${s.titulo}: ${meia ? "deixar na largura inteira" : "deixar em meia largura"}`}
                  title={meia ? "Ocupar a largura inteira" : "Ocupar meia largura (dois lado a lado)"}
                  className={`${BOTAO_BARRA_BASE} hidden xl:inline-flex`}
                >
                  {meia ? <RectangleHorizontal size={15} aria-hidden /> : <Columns2 size={15} aria-hidden />}
                  <span>{meia ? "Alargar" : "Meia largura"}</span>
                </button>
                <button
                  type="button"
                  data-controle="subir"
                  onClick={() => passo(s.id, -1, "subir")}
                  disabled={i === 0}
                  aria-label={`Subir ${s.titulo}`}
                  title="Subir"
                  className={BOTAO_BARRA}
                >
                  <ArrowUp size={16} aria-hidden />
                </button>
                <button
                  type="button"
                  data-controle="descer"
                  onClick={() => passo(s.id, 1, "descer")}
                  disabled={i === naTela.length - 1}
                  aria-label={`Descer ${s.titulo}`}
                  title="Descer"
                  className={BOTAO_BARRA}
                >
                  <ArrowDown size={16} aria-hidden />
                </button>
                <button
                  type="button"
                  onClick={() => alternar(s.id)}
                  aria-expanded={!fechado}
                  aria-label={`${fechado ? "Abrir" : "Recolher"} ${s.titulo}`}
                  title={fechado ? "Abrir (mostrar o conteúdo)" : "Recolher (deixar só o título)"}
                  className={BOTAO_BARRA}
                >
                  <ChevronDown size={16} className={`transition-transform ${fechado ? "-rotate-90" : ""}`} aria-hidden />
                </button>
                {permitirOcultar && (
                  <button type="button" onClick={() => esconder(s.id)} aria-label={`Esconder ${s.titulo}`} title="Esconder (tirar da tela)" className={BOTAO_BARRA}>
                    <EyeOff size={16} aria-hidden />
                  </button>
                )}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => alternar(s.id)}
                aria-expanded={!fechado}
                className={`group flex w-full items-center gap-2 text-left ${fechado ? "rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700/60" : "mb-2 px-1"}`}
              >
                <ChevronDown
                  className={`h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:text-slate-600 ${fechado ? "-rotate-90" : ""}`}
                  aria-hidden
                />
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{s.titulo}</span>
                {s.resumo != null && <span className="ml-auto text-sm tabular-nums text-slate-500 dark:text-slate-400">{s.resumo}</span>}
              </button>
            )}

            <Previa ativa={editando}>{!fechado && s.conteudo}</Previa>
            {editando && fechado && (
              <p className="px-2 pb-1 text-xs text-slate-500 dark:text-slate-400">Recolhido: na tela aparece só o título. A setinha abre de novo.</p>
            )}

            {/* Onde o bloco arrastado vai cair. */}
            {alvoAqui && (
              <div
                aria-hidden
                className={`pointer-events-none absolute z-20 rounded-full bg-primary-500 shadow-[0_0_0_3px] shadow-primary-500/25 dark:bg-primary-400 ${
                  alvoAqui.lateral
                    ? `inset-y-0 w-1 ${alvoAqui.depois ? "-right-[10px]" : "-left-[10px]"}`
                    : `inset-x-0 h-1 ${alvoAqui.depois ? "-bottom-[10px]" : "-top-[10px]"}`
                }`}
              />
            )}
          </section>
        )
      })}

      {editando && permitirOcultar && (
        <section aria-label="Blocos escondidos" className="rounded-2xl border border-dashed border-slate-300 px-4 py-3 xl:col-span-2 dark:border-slate-600">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Blocos escondidos</h2>
          {escondidas.length === 0 ? (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Nenhum. Pra tirar um bloco da tela, use o olho riscado <EyeOff size={12} className="inline align-[-1px]" aria-hidden /> na barra dele — ele vem pra cá e
              você traz de volta quando quiser.
            </p>
          ) : (
            <>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Toque num bloco pra ele voltar pra tela, no lugar em que estava.</p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {escondidas.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => mostrar(s.id)}
                      aria-label={`Mostrar de novo: ${s.titulo}`}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-slate-300 bg-white py-1.5 pl-2.5 pr-3 text-sm font-medium text-slate-700 shadow-sm hover:border-primary-400 hover:bg-primary-50 hover:text-primary-800 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-primary-500 dark:hover:bg-primary-900/40 dark:hover:text-white"
                    >
                      <Eye size={14} className="shrink-0" aria-hidden />
                      <span className="truncate">{s.titulo}</span>
                      {s.grupo && <span className="shrink-0 text-xs font-normal text-slate-400 dark:text-slate-500">{s.grupo}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {/* O bloco que está sendo arrastado, pequeno, junto do dedo/mouse. */}
      {arrasto && (
        <div
          aria-hidden
          className="pointer-events-none fixed z-50 flex max-w-[240px] items-center gap-1.5 rounded-lg border border-primary-400 bg-white px-2.5 py-1.5 text-sm font-semibold text-slate-800 shadow-xl dark:border-primary-500 dark:bg-slate-800 dark:text-slate-100"
          style={{ left: arrasto.x + 10, top: arrasto.y + 10 }}
        >
          <GripVertical size={15} className="shrink-0 text-primary-500" />
          <span className="truncate">{titulo(arrasto.id)}</span>
        </div>
      )}
      {editando && (
        <p className="sr-only" role="status" aria-live="polite">
          {aviso}
        </p>
      )}
    </div>
  )
}
