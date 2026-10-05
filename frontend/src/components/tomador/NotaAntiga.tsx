import { FileUp, Loader2, Sparkles } from "lucide-react"
import { type DragEvent, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"

/** Cadastro assistido (05/10/2026): a pessoa manda uma nota que já emitiu
 * pra este cliente (PDF ou XML) e o cadastro vem preenchido — tomador,
 * códigos e a descrição, com o que muda todo mês já identificado. */

export interface DadosNotaAntiga {
  tomador: {
    tipo_documento: string | null
    documento: string | null
    razao_social: string | null
    cod_municipio: string | null
    cep: string | null
    logradouro: string | null
    numero: string | null
    complemento: string | null
    bairro: string | null
    email: string | null
  }
  cod_trib_nacional: string | null
  cod_trib_municipal: string | null
  cod_nbs: string | null
  cod_local_prestacao: string | null
  serie: string | null
  descricao_original: string | null
  modelo_sugerido: string
  partes: { trecho: string; rotulo: string }[]
  valor: number | null
  competencia: string | null
}

export function ResumoNotaAntiga({ dados }: { dados: DadosNotaAntiga }) {
  return (
    <div className="rounded-xl border border-success-200 bg-success-50/70 px-4 py-3 text-sm text-slate-700 dark:border-success-900/50 dark:bg-success-900/20 dark:text-slate-200">
      <p className="flex items-center gap-1.5 font-semibold text-success-700 dark:text-success-300">
        <Sparkles size={15} /> Preenchi o cadastro com os dados dessa nota. Confira abaixo.
      </p>
      {dados.descricao_original && (
        <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-300">
          Na nota estava escrito: <em>“{dados.descricao_original}”</em>
        </p>
      )}
      {dados.partes.length > 0 ? (
        <ul className="mt-1.5 flex flex-col gap-0.5 text-xs">
          {dados.partes.map((p) => (
            <li key={p.trecho}>
              <strong>“{p.trecho}”</strong> muda todo mês → {p.rotulo}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
          Não achei nada na descrição que mude todo mês. Se muda (mês, ordem de pagamento), marque em “O que muda todo mês?”.
        </p>
      )}
    </div>
  )
}

export function NotaAntiga({ onLida }: { onLida: (dados: DadosNotaAntiga) => void }) {
  const campo = useRef<HTMLInputElement>(null)
  const [lendo, setLendo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sobre, setSobre] = useState(false)

  async function ler(arquivo: File | undefined | null) {
    if (!arquivo) return
    setErro(null)
    setLendo(true)
    try {
      const form = new FormData()
      form.append("arquivo", arquivo)
      onLida(await api.postForm<DadosNotaAntiga>("/tomadores/ler-nota", form))
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setLendo(false)
      if (campo.current) campo.current.value = ""
    }
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setSobre(false)
    ler(e.dataTransfer.files?.[0])
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setSobre(true)
        }}
        onDragLeave={() => setSobre(false)}
        onDrop={soltar}
        className={`flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors ${
          sobre ? "border-primary-500 bg-primary-50 dark:bg-primary-900/30" : "border-accent-200 bg-accent-50/50 dark:border-accent-900/50 dark:bg-accent-900/10"
        }`}
      >
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Já emitiu nota pra este cliente antes?</p>
        <p className="max-w-md text-xs text-slate-500 dark:text-slate-400">
          Envie uma nota antiga (o PDF ou o XML) e eu preencho o cadastro inteiro — quem é o cliente, o código do serviço e a
          descrição. Você só confere.
        </p>
        <button
          type="button"
          disabled={lendo}
          onClick={() => campo.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-60"
        >
          {lendo ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
          {lendo ? "Lendo a nota..." : "Enviar uma nota antiga"}
        </button>
        <p className="text-[11px] text-slate-400">ou arraste o arquivo pra cá</p>
        <input ref={campo} type="file" accept=".xml,.pdf,application/pdf,text/xml,application/xml" className="hidden" onChange={(e) => ler(e.target.files?.[0])} />
      </div>
      {erro && <p className="mt-2 rounded-lg bg-danger-50 px-3 py-2 text-xs text-danger-700">{erro}</p>}
    </div>
  )
}
