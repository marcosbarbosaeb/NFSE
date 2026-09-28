import { FileCode2, FileDown } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import type { FormaEnvio } from "../lib/types"
import { EnvioNota, envioLiberado } from "./EnvioNota"
import { Badge } from "./ui/Badge"

// Pedido do Marcos (28/09/2026): "na aba NFS-e, além do estado, vamos deixar
// a opção assinar, enviar para a prefeitura, enviar para o vendedor e o
// pagamento que já está. Traga isso para a visão geral também; gostei dessa
// opção de passar o mouse em cima do pagamento e mudar a opção, coloque isso
// nas demais." Cada etapa é um selo: parado mostra o estado, com o mouse em
// cima mostra a ação, e o clique abre uma confirmação (mesmo jeito do
// BaixaPagamento).

type Variante = "success" | "warning" | "danger" | "neutral" | "info"

export interface NotaParaAcoes {
  id: string
  estado: string
  envio_status?: string | null
  tem_pdf?: boolean
  tem_email?: boolean
  homologacao?: boolean
  avulsa?: boolean
  /** Como o tomador recebe a nota (null = e-mail). */
  envio_forma?: FormaEnvio | null
  /** Tomador da nota — pro atalho "cadastrar o link do portal". */
  vinculo_id?: string | null
}

/** Selo com confirmação em popover (position:fixed — tabelas com overflow cortariam um popover comum). */
export function SeloAcao({
  rotulo,
  variante,
  rotuloHover,
  titulo,
  desabilitado,
  larguraPainel = 272,
  alturaPainel = 260,
  onAbrir,
  children,
}: {
  rotulo: ReactNode
  variante: Variante
  rotuloHover?: ReactNode
  titulo?: string
  desabilitado?: boolean
  larguraPainel?: number
  /** Altura esperada do painel — decide se abre pra baixo ou pra cima (ele rola se não couber). */
  alturaPainel?: number
  onAbrir?: () => void
  children?: (fechar: () => void) => ReactNode
}) {
  const [aberto, setAberto] = useState(false)
  const [pos, setPos] = useState<{ top?: number; bottom?: number; left: number; largura: number; alturaMax: number } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setAberto(false)
    // Rolar a página fecha (o painel é fixo e ficaria solto) — menos quando
    // a pessoa está digitando nele: no celular o teclado rola a tela.
    const fechar = (e: Event) => {
      // Rolar dentro do próprio painel (ele tem barra de rolagem) não fecha.
      if (e.target instanceof Node && ref.current?.contains(e.target)) return
      if (ref.current?.contains(document.activeElement)) return
      setAberto(false)
    }
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false)
    document.addEventListener("mousedown", fora)
    document.addEventListener("keydown", esc)
    window.addEventListener("scroll", fechar, true)
    return () => {
      document.removeEventListener("mousedown", fora)
      document.removeEventListener("keydown", esc)
      window.removeEventListener("scroll", fechar, true)
    }
  }, [aberto])

  if (desabilitado || !children) {
    return (
      <span title={titulo} className="inline-flex">
        <Badge variant={variante}>{rotulo}</Badge>
      </span>
    )
  }

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        title={titulo}
        onClick={(e) => {
          e.stopPropagation()
          const r = e.currentTarget.getBoundingClientRect()
          const largura = Math.min(larguraPainel, window.innerWidth - 16)
          const left = Math.max(8, Math.min(r.left, window.innerWidth - largura - 8))
          const abaixo = window.innerHeight - r.bottom - 16
          const acima = r.top - 16
          // Abre pra baixo se couber (ou se embaixo tem mais espaço); senão pra cima, colado no selo.
          setPos(
            abaixo >= alturaPainel || abaixo >= acima
              ? { top: r.bottom + 8, left, largura, alturaMax: Math.max(160, abaixo) }
              : { bottom: window.innerHeight - r.top + 8, left, largura, alturaMax: Math.max(160, acima) },
          )
          if (!aberto) onAbrir?.()
          setAberto((a) => !a)
        }}
        className="rounded-full focus:outline-none focus:ring-2 focus:ring-primary-300"
      >
        {rotuloHover ? (
          <span className="group inline-flex">
            <span className="group-hover:hidden">
              <Badge variant={variante}>{rotulo}</Badge>
            </span>
            <span className="hidden group-hover:inline-flex">
              <Badge variant="info">{rotuloHover}</Badge>
            </span>
          </span>
        ) : (
          <Badge variant={variante}>{rotulo}</Badge>
        )}
      </button>
      {aberto && pos && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{ top: pos.top, bottom: pos.bottom, left: pos.left, width: pos.largura, maxHeight: pos.alturaMax }}
          className="fixed z-50 overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white p-3 text-left text-sm shadow-xl dark:border-slate-700 dark:bg-slate-800"
        >
          {children(() => setAberto(false))}
        </div>
      )}
    </div>
  )
}

function Confirmar({
  texto,
  botao,
  onConfirmar,
  fechar,
  children,
  perigo,
}: {
  texto?: ReactNode
  botao: string
  onConfirmar: () => Promise<void>
  fechar: () => void
  children?: ReactNode
  perigo?: boolean
}) {
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  return (
    <div className="flex flex-col gap-2">
      {texto && <p className="text-slate-600 dark:text-slate-300">{texto}</p>}
      {children}
      {erro && <p className="text-xs text-danger-600">{erro}</p>}
      <div className="mt-1 flex justify-end gap-2">
        <button type="button" onClick={fechar} className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700">
          Cancelar
        </button>
        <button
          type="button"
          disabled={enviando}
          onClick={async () => {
            setEnviando(true)
            setErro(null)
            try {
              await onConfirmar()
              fechar()
            } catch (err) {
              setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
            } finally {
              setEnviando(false)
            }
          }}
          className={`rounded-md px-3 py-1 text-xs font-semibold text-white disabled:opacity-50 ${
            perigo ? "bg-danger-600 hover:bg-danger-700" : "bg-primary-600 hover:bg-primary-700"
          }`}
        >
          {enviando ? "..." : botao}
        </button>
      </div>
    </div>
  )
}

export function SeloAssinatura({ nota, onMudou }: { nota: NotaParaAcoes; onMudou: () => void }) {
  if (nota.estado === "montado") {
    return (
      <SeloAcao rotulo="A assinar" rotuloHover="Assinar" variante="warning" titulo="Gerada — clique pra assinar com o certificado">
        {(fechar) => (
          <Confirmar
            texto="Assinar esta nota com o seu certificado digital? Depois de assinada ela fica pronta pra ir à prefeitura."
            botao="Assinar"
            fechar={fechar}
            onConfirmar={async () => {
              await api.post(`/dps/${nota.id}/assinar`, {})
              onMudou()
            }}
          />
        )}
      </SeloAcao>
    )
  }
  if (["assinado", "submetido", "confirmado", "erro"].includes(nota.estado)) return <SeloAcao rotulo="Assinada ✓" variante="success" desabilitado />
  if (nota.estado === "cancelada" || nota.estado === "substituida") return <SeloAcao rotulo="—" variante="neutral" desabilitado />
  return <SeloAcao rotulo="Rascunho" variante="neutral" desabilitado />
}

export function SeloPrefeitura({ nota, onMudou }: { nota: NotaParaAcoes; onMudou: () => void }) {
  const [resultado, setResultado] = useState<string | null>(null)
  if (nota.estado === "assinado" || nota.estado === "erro") {
    const erro = nota.estado === "erro"
    return (
      <SeloAcao
        rotulo={erro ? "Recusada" : "A enviar"}
        rotuloHover={erro ? "Tentar de novo" : "Enviar"}
        variante={erro ? "danger" : "warning"}
        titulo={erro ? "A prefeitura recusou — clique pra tentar de novo" : "Assinada — clique pra enviar à prefeitura"}
      >
        {(fechar) => (
          <Confirmar
            texto={
              <>
                {erro ? "Enviar de novo à prefeitura" : "Enviar esta nota à prefeitura"}
                {nota.homologacao ? " (ambiente de teste)" : ""}? {erro && "Se o erro foi nos dados, corrija antes na página da nota."}
              </>
            }
            botao="Enviar à prefeitura"
            fechar={fechar}
            onConfirmar={async () => {
              const r = await api.post<{ estado: string; erro_detalhe?: string | null }>(`/dps/${nota.id}/submeter`, {})
              setResultado(r.estado === "confirmado" ? "Autorizada!" : null)
              onMudou()
              // Recusa da prefeitura volta com 200 + estado "erro": mostra o motivo.
              if (r.estado === "erro") throw new ApiError(400, r.erro_detalhe ?? "A prefeitura recusou a nota.")
            }}
          />
        )}
      </SeloAcao>
    )
  }
  if (nota.estado === "submetido") return <SeloAcao rotulo="Aguardando" variante="info" desabilitado titulo="Enviada, esperando a resposta da prefeitura" />
  if (nota.estado === "confirmado") return <SeloAcao rotulo={resultado ?? "Autorizada ✓"} variante="success" desabilitado />
  if (nota.estado === "montado") return <SeloAcao rotulo="—" variante="neutral" desabilitado titulo="Assine a nota primeiro" />
  return <SeloAcao rotulo="—" variante="neutral" desabilitado />
}

export function SeloTomador({ nota, onMudou }: { nota: NotaParaAcoes; onMudou: () => void }) {
  const liberado = envioLiberado(nota)
  const enviada = nota.envio_status === "enviado"
  const falhou = nota.envio_status === "falha"

  if (nota.estado === "cancelada" || nota.estado === "substituida") return <SeloAcao rotulo="—" variante="neutral" desabilitado />
  if (!liberado && !enviada) {
    return <SeloAcao rotulo="—" variante="neutral" desabilitado titulo="Dá pra enviar depois que a prefeitura autorizar a nota" />
  }

  // E-mail não é obrigatório (29/09/2026): sem e-mail o painel abre no WhatsApp.
  const forma = nota.avulsa ? "email" : nota.envio_forma ?? (nota.tem_email === false ? "whatsapp" : "email")
  let rotulo: string
  let rotuloHover: string
  let variante: Variante
  let titulo: string
  if (enviada) {
    ;[rotulo, rotuloHover, variante, titulo] = ["Enviada ✓", "Reenviar", "success", "Já enviada — clique pra reenviar (e-mail, WhatsApp...)"]
  } else if (falhou) {
    ;[rotulo, rotuloHover, variante, titulo] = ["Falhou", "Tentar de novo", "danger", "O último envio falhou — clique pra tentar de novo"]
  } else if (forma === "nenhum") {
    ;[rotulo, rotuloHover, variante, titulo] = ["Não precisa", "Enviar", "neutral", "Este tomador não precisa receber a nota — clique se quiser mandar mesmo assim"]
  } else if (forma === "portal") {
    ;[rotulo, rotuloHover, variante, titulo] = ["Enviar no portal", "Abrir", "warning", "Este tomador recebe pelo sistema dele — baixe a nota e marque como enviada"]
  } else {
    const porZap = forma === "whatsapp"
    ;[rotulo, rotuloHover, variante, titulo] = [
      "A enviar",
      "Enviar",
      "warning",
      porZap ? "Clique pra mandar a nota pelo WhatsApp (ou e-mail)" : "Clique pra mandar a nota por e-mail (ou WhatsApp)",
    ]
  }

  return (
    <SeloAcao rotulo={rotulo} rotuloHover={rotuloHover} variante={variante} titulo={titulo} larguraPainel={380} alturaPainel={460}>
      {(fechar) => (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Enviar a nota</p>
            <button
              type="button"
              onClick={fechar}
              aria-label="Fechar"
              className="rounded-md px-1.5 text-lg leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
            >
              ×
            </button>
          </div>
          <EnvioNota nota={nota} onMudou={onMudou} onConcluido={fechar} modo="popover" />
        </div>
      )}
    </SeloAcao>
  )
}

/** Baixar PDF (oficial, depois de autorizada) e XML. */
export function DownloadsNota({ nota }: { nota: NotaParaAcoes }) {
  const temXml = !["rascunho"].includes(nota.estado)
  const classe = "inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:border-primary-300 hover:text-primary-600 dark:border-slate-600 dark:text-slate-400"
  const desligado = "inline-flex h-7 w-7 cursor-not-allowed items-center justify-center rounded-md border border-slate-100 text-slate-300 dark:border-slate-700 dark:text-slate-600"
  return (
    <span className="inline-flex gap-1" onClick={(e) => e.stopPropagation()}>
      {nota.tem_pdf ? (
        <a href={`/api/dps/${nota.id}/pdf`} download className={classe} title="Baixar PDF">
          <FileDown size={14} />
        </a>
      ) : (
        <span className={desligado} title="O PDF oficial sai depois que a prefeitura autoriza a nota">
          <FileDown size={14} />
        </span>
      )}
      {temXml ? (
        <a href={`/api/dps/${nota.id}/download`} download className={classe} title="Baixar XML">
          <FileCode2 size={14} />
        </a>
      ) : (
        <span className={desligado} title="Sem XML ainda">
          <FileCode2 size={14} />
        </span>
      )}
    </span>
  )
}
