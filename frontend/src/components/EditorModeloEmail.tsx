import { useEffect, useRef, useState } from "react"
import { api } from "../lib/api"
import type { ModeloEmailPadrao } from "../lib/types"

// Modelo do e-mail da nota (28/09/2026): "é importante que os campos dessa
// mensagem sejam configuráveis. Tem tomador que pede que o assunto seja
// específico e precisamos enviar em XML e em PDF." Usado em Configurações
// (padrão da conta) e na ficha do tomador (só pra ele).

export type Anexos = "pdf_xml" | "pdf" | "xml"

export interface ValorModeloEmail {
  assunto: string
  mensagem: string
  anexos: Anexos | ""
  copia?: string
}

const OPCOES_ANEXO: { valor: Anexos; rotulo: string }[] = [
  { valor: "pdf_xml", rotulo: "PDF e XML" },
  { valor: "pdf", rotulo: "Só PDF" },
  { valor: "xml", rotulo: "Só XML" },
]

let cacheModelo: Promise<ModeloEmailPadrao> | null = null
export function carregarModeloPadrao(): Promise<ModeloEmailPadrao> {
  cacheModelo ??= api.get<ModeloEmailPadrao>("/email-modelo")
  return cacheModelo
}

const classeCampo =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function EditorModeloEmail({
  valor,
  onChange,
  herdado,
  mostrarCopia,
}: {
  valor: ValorModeloEmail
  onChange: (v: ValorModeloEmail) => void
  /** O que vale quando o campo fica vazio (padrão da conta ou texto da Ana). */
  herdado?: { assunto?: string | null; mensagem?: string | null; anexos?: Anexos | null; rotulo: string }
  mostrarCopia?: boolean
}) {
  const [modelo, setModelo] = useState<ModeloEmailPadrao | null>(null)
  const [focado, setFocado] = useState<"assunto" | "mensagem">("mensagem")
  const refAssunto = useRef<HTMLInputElement>(null)
  const refMensagem = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    carregarModeloPadrao().then(setModelo).catch(() => {})
  }, [])

  const assuntoBase = herdado?.assunto || modelo?.assunto || ""
  const mensagemBase = herdado?.mensagem || modelo?.mensagem || ""
  const anexosBase: Anexos = herdado?.anexos || "pdf_xml"

  function inserir(codigo: string) {
    const campo = focado === "assunto" ? refAssunto.current : refMensagem.current
    const atual = focado === "assunto" ? valor.assunto : valor.mensagem
    // Campo vazio = começa do texto que está valendo, pra não perder o resto.
    const texto = atual || (focado === "assunto" ? assuntoBase : mensagemBase)
    const ini = atual && campo ? campo.selectionStart ?? texto.length : texto.length
    const fim = atual && campo ? campo.selectionEnd ?? texto.length : texto.length
    const novo = `${texto.slice(0, ini)}{${codigo}}${texto.slice(fim)}`
    onChange({ ...valor, [focado]: novo })
    requestAnimationFrame(() => {
      campo?.focus()
      const pos = ini + codigo.length + 2
      campo?.setSelectionRange(pos, pos)
    })
  }

  const exemplos = Object.fromEntries((modelo?.codigos ?? []).map((c) => [c.codigo, c.exemplo]))
  const trocar = (t: string) => t.replace(/\{(\w+)\}/g, (m, c) => exemplos[c] ?? m)
  const assuntoFinal = valor.assunto || assuntoBase
  const mensagemFinal = valor.mensagem || mensagemBase

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
        Assunto
        <input
          ref={refAssunto}
          value={valor.assunto}
          onFocus={() => setFocado("assunto")}
          onChange={(e) => onChange({ ...valor, assunto: e.target.value })}
          placeholder={assuntoBase}
          maxLength={300}
          className={classeCampo}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
        Mensagem
        <textarea
          ref={refMensagem}
          value={valor.mensagem}
          onFocus={() => setFocado("mensagem")}
          onChange={(e) => onChange({ ...valor, mensagem: e.target.value })}
          placeholder={mensagemBase}
          rows={8}
          maxLength={5000}
          className={`${classeCampo} font-normal`}
        />
      </label>
      {herdado && (
        <p className="-mt-2 text-xs text-slate-400">Em branco = usa {herdado.rotulo}.</p>
      )}

      {modelo && (
        <div>
          <p className="mb-1.5 text-xs text-slate-500 dark:text-slate-400">
            Clique pra colocar no {focado === "assunto" ? "assunto" : "texto"} — vira o dado da nota na hora de enviar:
          </p>
          <div className="flex flex-wrap gap-1.5">
            {modelo.codigos.map((c) => (
              <button
                key={c.codigo}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => inserir(c.codigo)}
                title={`${c.descricao} — ex.: ${c.exemplo}`}
                className="rounded-full border border-primary-200 bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700 hover:bg-primary-100 dark:border-primary-800 dark:bg-primary-900/30 dark:text-primary-300"
              >
                {c.descricao}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={`grid grid-cols-1 gap-4 ${mostrarCopia ? "sm:grid-cols-2" : ""}`}>
        <div className="flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
          Anexos
          <div className="flex gap-2">
            {OPCOES_ANEXO.map((o) => {
              const ativo = (valor.anexos || anexosBase) === o.valor
              return (
                <button
                  key={o.valor}
                  type="button"
                  onClick={() => onChange({ ...valor, anexos: o.valor })}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    ativo ? "border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300" : "border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-300"
                  }`}
                >
                  {o.rotulo}
                </button>
              )
            })}
          </div>
          <span className="text-xs font-normal text-slate-400">O PDF oficial existe depois que a prefeitura autoriza a nota.</span>
        </div>
        {mostrarCopia && (
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
            Com cópia para
            <input
              value={valor.copia ?? ""}
              onChange={(e) => onChange({ ...valor, copia: e.target.value })}
              placeholder="contabilidade@empresa.com, outro@empresa.com"
              maxLength={400}
              className={classeCampo}
            />
          </label>
        )}
      </div>

      {modelo && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-700 dark:bg-slate-900/40">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Como vai chegar (exemplo)</p>
          <p className="font-semibold text-slate-800 dark:text-slate-100">{trocar(assuntoFinal)}</p>
          <p className="mt-2 whitespace-pre-line text-slate-600 dark:text-slate-300">{trocar(mensagemFinal)}</p>
        </div>
      )}
    </div>
  )
}
