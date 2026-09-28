import { FileCode2, FileDown } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import type { FormaEnvio, PreviaEmail } from "../lib/types"
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
}

/** Selo com confirmação em popover (position:fixed — tabelas com overflow cortariam um popover comum). */
export function SeloAcao({
  rotulo,
  variante,
  rotuloHover,
  titulo,
  desabilitado,
  larguraPainel = 272,
  onAbrir,
  children,
}: {
  rotulo: ReactNode
  variante: Variante
  rotuloHover?: ReactNode
  titulo?: string
  desabilitado?: boolean
  larguraPainel?: number
  onAbrir?: () => void
  children?: (fechar: () => void) => ReactNode
}) {
  const [aberto, setAberto] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setAberto(false)
    // Rolar a página fecha (o painel é fixo e ficaria solto) — menos quando
    // a pessoa está digitando nele: no celular o teclado rola a tela.
    const fechar = () => {
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
          const top = r.bottom + 8 + 260 > window.innerHeight ? Math.max(8, r.top - 268) : r.bottom + 8
          setPos({ top, left: Math.max(8, Math.min(r.left, window.innerWidth - larguraPainel - 8)) })
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
          style={{ top: pos.top, left: pos.left, width: larguraPainel }}
          className="fixed z-50 rounded-xl border border-slate-200 bg-white p-3 text-left text-sm shadow-xl dark:border-slate-700 dark:bg-slate-800"
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
  const [previa, setPrevia] = useState<PreviaEmail | null>(null)
  const [erroPrevia, setErroPrevia] = useState<string | null>(null)
  // Destinatário e cópia editáveis na hora (valem só pra este envio).
  const [para, setPara] = useState("")
  const [copia, setCopia] = useState("")
  const liberado = nota.estado === "confirmado" || (nota.homologacao && ["montado", "assinado", "submetido"].includes(nota.estado))
  const enviada = nota.envio_status === "enviado"

  if (nota.estado === "cancelada" || nota.estado === "substituida") return <SeloAcao rotulo="—" variante="neutral" desabilitado />
  if (!nota.tem_email) {
    return <SeloAcao rotulo="Sem e-mail" variante="neutral" desabilitado titulo="Cadastre o e-mail deste tomador (Tomadores › editar) pra enviar direto" />
  }
  if (!liberado && !enviada) {
    return <SeloAcao rotulo="—" variante="neutral" desabilitado titulo="Dá pra enviar depois que a prefeitura autorizar a nota" />
  }

  return (
    <SeloAcao
      rotulo={enviada ? "Enviada ✓" : nota.envio_status === "falha" ? "Falhou" : "A enviar"}
      rotuloHover={enviada ? "Reenviar" : "Enviar"}
      variante={enviada ? "success" : nota.envio_status === "falha" ? "danger" : "warning"}
      titulo={enviada ? "Já enviada — clique pra reenviar" : "Clique pra mandar a nota por e-mail"}
      larguraPainel={320}
      onAbrir={() => {
        setPrevia(null)
        setErroPrevia(null)
        api
          .get<PreviaEmail>(`/dps/${nota.id}/email-previa`)
          .then((p) => {
            setPrevia(p)
            setPara(p.destinos.join(", "))
            setCopia(p.copia.join(", "))
          })
          .catch((err) => setErroPrevia(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      }}
    >
      {(fechar) => (
        <Confirmar
          botao={enviada ? "Reenviar" : "Enviar e-mail"}
          fechar={fechar}
          onConfirmar={async () => {
            const lista = (t: string) => t.split(/[,;\s]+/).map((e) => e.trim()).filter(Boolean)
            if (lista(para).length === 0) throw new ApiError(400, "Informe pelo menos um destinatário.")
            const envio = await api.post<{ status: string; erro: string | null }>(`/dps/${nota.id}/enviar-email`, {
              para: lista(para),
              copia: lista(copia),
            })
            if (envio.status === "falha") throw new ApiError(400, envio.erro ?? "O envio falhou.")
            onMudou()
          }}
        >
          {erroPrevia && <p className="text-xs text-danger-600">{erroPrevia}</p>}
          {!previa && !erroPrevia && <p className="text-xs text-slate-400">Carregando o e-mail...</p>}
          {previa && (
            <div className="flex flex-col gap-1.5 text-xs text-slate-600 dark:text-slate-300">
              <label className="flex flex-col gap-0.5">
                <span className="text-slate-400">Para</span>
                <input
                  value={para}
                  readOnly={nota.avulsa && nota.estado === "confirmado"}
                  title={nota.avulsa ? "Nota da Shopee: vai pro e-mail do vendedor que veio no relatório" : undefined}
                  onChange={(e) => setPara(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-slate-400">Cópia</span>
                <input
                  value={copia}
                  onChange={(e) => setCopia(e.target.value)}
                  placeholder="opcional"
                  className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <p>
                <span className="text-slate-400">Assunto:</span> {previa.assunto}
              </p>
              <p>
                <span className="text-slate-400">Anexos:</span> {previa.arquivos.join(", ")}
              </p>
              {previa.motivo_desabilitado && previa.destinos.length > 0 && <p className="text-danger-600">{previa.motivo_desabilitado}</p>}
            </div>
          )}
        </Confirmar>
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
