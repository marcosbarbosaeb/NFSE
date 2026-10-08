import {
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Download,
  FileText,
  Landmark,
  Loader2,
  MinusCircle,
  Pencil,
  Plus,
  Send,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, api, formatarErro } from "../../lib/api"
import { competenciaAtual, deslocarCompetencia, formatCompetenciaLonga } from "../../lib/format"
import type { ArquivoPasta, ItemPasta, MensagemPasta, PastaDoMes as Pasta } from "../../lib/types"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"

/** Pasta do mês (08/10/2026): "o contador e o cliente se falarem e trocarem
 * arquivos — organizando o que o contador precisa mensalmente", com "tipo um
 * chat" pra deixar algo escrito. A mesma tela serve aos dois lados:
 *   - empresa: `base="/pasta"` (tela Pasta do mês);
 *   - contador pelo painel dele: `base="/contador/atendimentos/<id>/pasta"`.
 * Quem é quem vem do servidor (`papel`), nunca daqui. */

const ESTADO: Record<ItemPasta["situacao"], { rotulo: string; Icone: typeof Circle; cor: string }> = {
  pendente: { rotulo: "Falta enviar", Icone: Circle, cor: "text-warning-700 dark:text-warning-300" },
  entregue: { rotulo: "Enviado", Icone: CheckCircle2, cor: "text-primary-700 dark:text-primary-300" },
  nao_tem: { rotulo: "Não teve neste mês", Icone: MinusCircle, cor: "text-slate-500 dark:text-slate-400" },
  conferido: { rotulo: "Conferido pelo contador", Icone: CheckCircle2, cor: "text-success-700 dark:text-success-300" },
}

function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`
}

function quando(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function erroDe(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

export function PastaDoMes({ base, competenciaInicial, onNovidadesVistas }: { base: string; competenciaInicial?: string; onNovidadesVistas?: () => void }) {
  const [competencia, setCompetencia] = useState(competenciaInicial ?? deslocarCompetencia(competenciaAtual(), -1))
  const [dados, setDados] = useState<Pasta | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState<string | null>(null)

  const carregar = useCallback(
    () =>
      api
        .get<Pasta>(`${base}?competencia=${competencia}`)
        .then((d) => {
          setDados(d)
          setErro(null)
          return d
        })
        .catch((err) => {
          setErro(erroDe(err))
          return null
        }),
    [base, competencia],
  )

  useEffect(() => {
    void carregar().then((d) => {
      // abriu a pasta: o que o outro lado mandou já foi visto
      if (d && (d.novidades.mensagens > 0 || d.novidades.arquivos > 0)) {
        api.post(`${base}/lido`, {}).then(() => {
          onNovidadesVistas?.()
          window.dispatchEvent(new Event("agenteana:pasta-lida"))
        }).catch(() => undefined)
      }
    })
    // atualiza sozinho enquanto a tela está aberta (a conversa)
    const t = window.setInterval(() => void carregar(), 30000)
    return () => window.clearInterval(t)
  }, [carregar, base, onNovidadesVistas])

  async function agir(chave: string, acao: () => Promise<unknown>) {
    setOcupado(chave)
    setErro(null)
    try {
      await acao()
      await carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setOcupado(null)
    }
  }

  function enviarArquivos(arquivos: FileList | null, pedidoId: string | null) {
    if (!arquivos || arquivos.length === 0) return
    void agir(`enviar:${pedidoId ?? "avulso"}`, async () => {
      for (const arquivo of Array.from(arquivos)) {
        const form = new FormData()
        form.append("competencia", competencia)
        if (pedidoId) form.append("pedido_id", pedidoId)
        form.append("arquivo", arquivo)
        await api.postForm(`${base}/arquivos`, form)
      }
    })
  }

  const papel = dados?.papel
  const ehContador = papel === "contador"
  const mes = dados?.mes

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {ehContador ? "O que eu preciso deste cliente" : "O que o contador precisa"}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {mes ? (mes.resumo.itens === 0 ? "Nenhum item na lista ainda." : `${mes.resumo.prontos} de ${mes.resumo.itens} prontos`) : " "}
            </p>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-1 py-1 text-sm dark:border-slate-700 dark:bg-slate-800">
            <button type="button" aria-label="Mês anterior" onClick={() => setCompetencia((c) => deslocarCompetencia(c, -1))} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700">
              <ChevronLeft size={16} />
            </button>
            <span className="min-w-[8.5rem] text-center font-medium text-slate-700 dark:text-slate-200">{formatCompetenciaLonga(competencia)}</span>
            <button
              type="button"
              aria-label="Próximo mês"
              disabled={competencia >= competenciaAtual()}
              onClick={() => setCompetencia((c) => deslocarCompetencia(c, 1))}
              className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-700"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {mes && mes.resumo.itens > 0 && (
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700" aria-hidden>
            <div className="h-full rounded-full bg-success-600 transition-[width]" style={{ width: `${(mes.resumo.prontos / mes.resumo.itens) * 100}%` }} />
          </div>
        )}

        {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}

        {!dados ? (
          <p className="py-8 text-center text-sm text-slate-400">Carregando...</p>
        ) : (
          <>
            {mes!.itens.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 p-5 text-center dark:border-slate-600">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  {ehContador
                    ? "Monte a lista do que você precisa todo mês — ela vale pros próximos meses também."
                    : "Aqui fica a lista do que o seu contador precisa todo mês. Ele pode montar, ou você começa com a lista mais comum:"}
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{dados.sugestoes.map((s) => s.titulo).join(" · ")}</p>
                <Button variant="outline" className="mt-3" disabled={ocupado !== null} onClick={() => agir("sugestoes", () => api.post(`${base}/pedidos/sugestoes`, {}))}>
                  Usar esta lista
                </Button>
              </div>
            )}

            <ul className="flex flex-col gap-3">
              {mes!.itens.map((item) => (
                <ItemDaPasta
                  key={item.id}
                  item={item}
                  base={base}
                  competencia={competencia}
                  ehContador={ehContador}
                  ocupado={ocupado}
                  onAgir={agir}
                  onEnviar={(lista) => enviarArquivos(lista, item.id)}
                />
              ))}
            </ul>

            <NovoPedido base={base} ocupado={ocupado} onAgir={agir} />

            <div className="border-t border-slate-100 pt-4 dark:border-slate-700/60">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Outros arquivos de {formatCompetenciaLonga(competencia).toLowerCase()}</h3>
                <BotaoEnviar rotulo="Enviar outro arquivo" ocupado={ocupado === "enviar:avulso"} desabilitado={ocupado !== null} onEscolher={(l) => enviarArquivos(l, null)} />
              </div>
              {mes!.avulsos.length === 0 ? (
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Nada além da lista.</p>
              ) : (
                <ListaArquivos arquivos={mes!.avulsos} base={base} ocupado={ocupado} onAgir={agir} />
              )}
              <p className="mt-2 text-[11px] text-slate-400 dark:text-slate-500">
                PDF, imagem, planilha, XML, OFX, documento ou ZIP · até {tamanho(mes!.limite_arquivo)} por arquivo.
              </p>
            </div>
          </>
        )}
      </Card>

      <Conversa
        base={base}
        competencia={competencia}
        mensagens={dados?.mensagens ?? null}
        papel={papel}
        temContador={dados?.tem_contador ?? true}
        onEnviado={() => void carregar()}
      />
    </div>
  )
}

function BotaoEnviar({ rotulo, ocupado, desabilitado, onEscolher }: { rotulo: string; ocupado: boolean; desabilitado: boolean; onEscolher: (l: FileList | null) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input ref={ref} type="file" multiple className="hidden" onChange={(e) => { onEscolher(e.target.files); e.target.value = "" }} />
      <Button variant="outline" className="!px-3 !py-1.5 text-xs" disabled={desabilitado} onClick={() => ref.current?.click()}>
        {ocupado ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />} {rotulo}
      </Button>
    </>
  )
}

function ListaArquivos({ arquivos, base, ocupado, onAgir }: { arquivos: ArquivoPasta[]; base: string; ocupado: string | null; onAgir: (c: string, a: () => Promise<unknown>) => void }) {
  return (
    <ul className="mt-2 flex flex-col gap-1">
      {arquivos.map((a) => (
        <li key={a.id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-2.5 py-1.5 text-sm dark:bg-slate-900/40">
          <FileText size={14} className="shrink-0 text-slate-400" aria-hidden />
          <span className="min-w-0 flex-1">
            <a href={`/api${base}/arquivos/${a.id}`} className="block truncate font-medium text-primary-700 hover:underline dark:text-primary-300" title={`Baixar ${a.nome}`}>
              {a.nome}
            </a>
            <span className="block truncate text-xs text-slate-400 dark:text-slate-500">
              {tamanho(a.tamanho)} · enviado por {a.papel === "contador" ? "contador" : (a.enviado_por ?? "empresa")} · {quando(a.criado_em)}
            </span>
          </span>
          <a href={`/api${base}/arquivos/${a.id}`} aria-label={`Baixar ${a.nome}`} className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700">
            <Download size={14} />
          </a>
          <button
            type="button"
            aria-label={`Apagar ${a.nome}`}
            disabled={ocupado !== null}
            onClick={() => {
              if (window.confirm(`Apagar “${a.nome}” da pasta?`)) onAgir(`apagar:${a.id}`, () => api.delete(`${base}/arquivos/${a.id}`))
            }}
            className="shrink-0 rounded p-1 text-slate-400 hover:bg-danger-50 hover:text-danger-600 disabled:opacity-40 dark:hover:bg-danger-900/30"
          >
            <Trash2 size={14} />
          </button>
        </li>
      ))}
    </ul>
  )
}

function ItemDaPasta({
  item,
  base,
  competencia,
  ehContador,
  ocupado,
  onAgir,
  onEnviar,
}: {
  item: ItemPasta
  base: string
  competencia: string
  ehContador: boolean
  ocupado: string | null
  onAgir: (c: string, a: () => Promise<unknown>) => void
  onEnviar: (l: FileList | null) => void
}) {
  const [editando, setEditando] = useState(false)
  const [titulo, setTitulo] = useState(item.titulo)
  const [descricao, setDescricao] = useState(item.descricao ?? "")
  const estado = ESTADO[item.situacao]
  const marcar = (situacao: string | null) =>
    onAgir(`marcar:${item.id}`, () => api.post(`${base}/marcar`, { pedido_id: item.id, competencia, situacao }))

  return (
    <li className="rounded-xl border border-slate-200 p-3.5 dark:border-slate-700">
      <div className="flex items-start gap-3">
        <estado.Icone size={20} className={`mt-0.5 shrink-0 ${estado.cor}`} aria-hidden />
        <div className="min-w-0 flex-1">
          {editando ? (
            <form
              className="flex flex-col gap-2"
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                onAgir(`editar:${item.id}`, () => api.patch(`${base}/pedidos/${item.id}`, { titulo, descricao }))
                setEditando(false)
              }}
            >
              <input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={120} className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" aria-label="O que precisa" />
              <input value={descricao} onChange={(e) => setDescricao(e.target.value)} maxLength={300} placeholder="Detalhe (opcional)" className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" aria-label="Detalhe" />
              <div className="flex gap-2">
                <Button type="submit" className="!px-3 !py-1 text-xs">Salvar</Button>
                <Button type="button" variant="ghost" className="!px-3 !py-1 text-xs" onClick={() => setEditando(false)}>Cancelar</Button>
              </div>
            </form>
          ) : (
            <>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-medium text-slate-800 dark:text-slate-100">{item.titulo}</p>
                <span className={`text-xs font-semibold ${estado.cor}`}>{estado.rotulo}</span>
              </div>
              {item.descricao && <p className="text-xs text-slate-500 dark:text-slate-400">{item.descricao}</p>}
              {item.tipo === "extrato" && (
                <p className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                  <Landmark size={12} aria-hidden />
                  {item.extrato_linhas
                    ? `Extrato importado no Financeiro: ${item.extrato_linhas} ${item.extrato_linhas === 1 ? "linha" : "linhas"} deste mês — conta como enviado.`
                    : <>Se você importar o extrato em <Link to="/app/financeiro/conciliacao" className="underline">Conciliação</Link>, ele conta aqui sozinho.</>}
                </p>
              )}
            </>
          )}
          {item.arquivos.length > 0 && <ListaArquivos arquivos={item.arquivos} base={base} ocupado={ocupado} onAgir={onAgir} />}
          {!editando && (
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <BotaoEnviar rotulo="Enviar arquivo" ocupado={ocupado === `enviar:${item.id}`} desabilitado={ocupado !== null} onEscolher={onEnviar} />
              {!ehContador && item.situacao === "pendente" && (
                <Button variant="ghost" className="!px-2.5 !py-1.5 text-xs" disabled={ocupado !== null} onClick={() => marcar("nao_tem")}>
                  Não teve neste mês
                </Button>
              )}
              {!ehContador && item.situacao === "nao_tem" && (
                <Button variant="ghost" className="!px-2.5 !py-1.5 text-xs" disabled={ocupado !== null} onClick={() => marcar(null)}>
                  Desfazer “não teve”
                </Button>
              )}
              {ehContador && item.situacao !== "conferido" && (
                <Button variant="ghost" className="!px-2.5 !py-1.5 text-xs" disabled={ocupado !== null} onClick={() => marcar("conferido")}>
                  <Check size={13} /> Marcar como conferido
                </Button>
              )}
              {ehContador && item.situacao === "conferido" && (
                <Button variant="ghost" className="!px-2.5 !py-1.5 text-xs" disabled={ocupado !== null} onClick={() => marcar(null)}>
                  Desfazer conferido
                </Button>
              )}
              <span className="ml-auto flex gap-1">
                <button type="button" aria-label={`Editar “${item.titulo}”`} onClick={() => setEditando(true)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700">
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  aria-label={`Tirar “${item.titulo}” da lista`}
                  onClick={() => {
                    if (window.confirm(`Tirar “${item.titulo}” da lista dos próximos meses? O que já foi enviado continua guardado.`))
                      onAgir(`tirar:${item.id}`, () => api.delete(`${base}/pedidos/${item.id}`))
                  }}
                  className="rounded p-1 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
                >
                  <X size={14} />
                </button>
              </span>
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

function NovoPedido({ base, ocupado, onAgir }: { base: string; ocupado: string | null; onAgir: (c: string, a: () => Promise<unknown>) => void }) {
  const [aberto, setAberto] = useState(false)
  const [titulo, setTitulo] = useState("")
  const [descricao, setDescricao] = useState("")
  if (!aberto) {
    return (
      <button type="button" onClick={() => setAberto(true)} className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-primary-700 hover:underline dark:text-primary-300">
        <Plus size={15} /> Adicionar item à lista
      </button>
    )
  }
  return (
    <form
      className="flex flex-col gap-2 rounded-xl border border-slate-200 p-3 dark:border-slate-700"
      onSubmit={(e) => {
        e.preventDefault()
        if (titulo.trim().length < 2) return
        onAgir("novo", () => api.post(`${base}/pedidos`, { titulo, descricao: descricao || null }))
        setTitulo("")
        setDescricao("")
        setAberto(false)
      }}
    >
      <input autoFocus value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={120} placeholder="O que precisa todo mês (ex.: Folha de pagamento)" aria-label="O que precisa todo mês" className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" />
      <input value={descricao} onChange={(e) => setDescricao(e.target.value)} maxLength={300} placeholder="Detalhe (opcional)" aria-label="Detalhe" className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" />
      <div className="flex gap-2">
        <Button type="submit" className="!px-3 !py-1.5 text-xs" disabled={ocupado !== null || titulo.trim().length < 2}>Adicionar</Button>
        <Button type="button" variant="ghost" className="!px-3 !py-1.5 text-xs" onClick={() => setAberto(false)}>Cancelar</Button>
      </div>
      <p className="text-[11px] text-slate-400 dark:text-slate-500">Vale pra este mês e pros próximos.</p>
    </form>
  )
}

function Conversa({
  base,
  competencia,
  mensagens,
  papel,
  temContador,
  onEnviado,
}: {
  base: string
  competencia: string
  mensagens: MensagemPasta[] | null
  papel?: "empresa" | "contador"
  temContador: boolean
  onEnviado: () => void
}) {
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const fim = useRef<HTMLDivElement>(null)
  const quantas = mensagens?.length ?? 0
  useEffect(() => {
    fim.current?.scrollIntoView({ block: "nearest" })
  }, [quantas])

  async function enviar() {
    const t = texto.trim()
    if (!t) return
    setEnviando(true)
    setErro(null)
    try {
      await api.post(`${base}/mensagens`, { texto: t, competencia })
      setTexto("")
      onEnviado()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }
  function teclas(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      void enviar()
    }
  }

  return (
    <Card className="flex max-h-[42rem] min-h-[22rem] flex-col p-0">
      <div className="border-b border-slate-100 px-5 py-3.5 dark:border-slate-700/60">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Conversa {papel === "contador" ? "com a empresa" : "com o contador"}</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400">Fica tudo escrito aqui, junto dos arquivos.</p>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {mensagens === null ? (
          <p className="py-6 text-center text-sm text-slate-400">Carregando...</p>
        ) : mensagens.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
            {temContador ? "Nenhuma mensagem ainda. Escreva o que quiser deixar combinado." : "Convide o seu contador em Empresa › Contador pra conversar por aqui."}
          </p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {mensagens.map((m) => {
              const minha = m.papel === papel
              return (
                <li key={m.id} className={`flex flex-col ${minha ? "items-end" : "items-start"}`}>
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm ${
                      minha ? "rounded-br-md bg-primary-600 text-white" : "rounded-bl-md bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-100"
                    }`}
                  >
                    {m.texto}
                  </div>
                  <span className="mt-0.5 text-[11px] text-slate-400 dark:text-slate-500">
                    {minha ? "Você" : m.autor_nome} · {quando(m.criado_em)}
                    {m.competencia && ` · ${formatCompetenciaLonga(m.competencia).toLowerCase()}`}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
        <div ref={fim} />
      </div>
      <form
        className="border-t border-slate-100 p-3 dark:border-slate-700/60"
        onSubmit={(e) => {
          e.preventDefault()
          void enviar()
        }}
      >
        {erro && <p className="mb-2 text-xs text-danger-600">{erro}</p>}
        <div className="flex items-end gap-2">
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={teclas}
            rows={2}
            maxLength={4000}
            placeholder="Escreva uma mensagem (Enter envia, Shift+Enter pula linha)"
            aria-label="Mensagem"
            className="min-h-[2.75rem] flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          />
          <Button type="submit" disabled={enviando || !texto.trim()} aria-label="Enviar mensagem" className="!px-3">
            {enviando ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </Button>
        </div>
      </form>
    </Card>
  )
}
