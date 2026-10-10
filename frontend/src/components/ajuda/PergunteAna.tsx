import { MessageCircleQuestion } from "lucide-react"
import { type FormEvent, useState } from "react"
import { api } from "../../lib/api"
import type { RespostaPergunteAna } from "../../lib/types"
import { telaDeOrigem } from "../../lib/uso"
import { Button } from "../ui/Button"

/** "Pergunte à Ana" (2026.10.7): a IA do Claude responde só com o guia da
 * Ana, que fica no servidor. Desde as observações de teste (10/10/2026) mora
 * dentro do "Fale com o suporte", depois da busca nas perguntas: a pessoa
 * procura primeiro e, se não achar, pergunta à Ana; se ainda precisar, fala
 * com a equipe (`aoPrecisarDaEquipe`). */
export function PergunteAna({
  perguntaInicial = "",
  restantesIniciais,
  limite,
  aoPrecisarDaEquipe,
}: {
  perguntaInicial?: string
  restantesIniciais: number | null
  limite: number | null
  aoPrecisarDaEquipe: (pergunta: string, resposta: string | null) => void
}) {
  const [pergunta, setPergunta] = useState(perguntaInicial)
  const [enviando, setEnviando] = useState(false)
  const [resposta, setResposta] = useState<RespostaPergunteAna | null>(null)
  const [perguntaFeita, setPerguntaFeita] = useState("")
  const [restantes, setRestantes] = useState<number | null>(restantesIniciais)
  const semPerguntas = restantes !== null && restantes <= 0
  const respondeu = resposta && (resposta.situacao === "ok" || resposta.situacao === "nao_sei" || resposta.situacao === "contador") && resposta.texto

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const texto = pergunta.trim()
    if (!texto || enviando || semPerguntas) return
    setEnviando(true)
    setResposta(null)
    try {
      const r = await api.post<RespostaPergunteAna>("/ajuda/perguntar", { pergunta: texto, tela: telaDeOrigem() })
      setResposta(r)
      setPerguntaFeita(texto)
      if (typeof r.restantes === "number") setRestantes(r.restantes)
      if (r.situacao === "ok" || r.situacao === "nao_sei" || r.situacao === "contador") setPergunta("")
    } catch {
      setResposta({ situacao: "falha", texto: null, restantes })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={enviar} className="flex flex-col gap-2">
        <label htmlFor="pergunte-ana" className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Escreva a sua dúvida do seu jeito
        </label>
        <textarea
          id="pergunte-ana"
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value.slice(0, 600))}
          rows={2}
          maxLength={600}
          disabled={semPerguntas}
          placeholder="Ex.: como eu cancelo uma nota?"
          className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 sm:text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {restantes !== null && limite ? `Você ainda pode fazer ${restantes} de ${limite} perguntas hoje.` : ""}
          </span>
          <Button type="submit" variant="accent" disabled={enviando || semPerguntas || !pergunta.trim()}>
            <MessageCircleQuestion size={16} aria-hidden="true" /> {enviando ? "Pensando..." : "Perguntar à Ana"}
          </Button>
        </div>
      </form>

      <div role="status" aria-live="polite">
        {semPerguntas && !resposta && (
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
            Por hoje acabaram as suas perguntas. Amanhã tem mais — e a equipe continua aqui.
          </p>
        )}
        {respondeu && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40">
            {perguntaFeita && <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">Você perguntou: “{perguntaFeita}”</p>}
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-slate-200">{resposta.texto}</p>
            <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">Resposta escrita por IA: pode errar. Na dúvida, fale com a equipe.</p>
          </div>
        )}
        {resposta && resposta.situacao === "limite" && (
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
            Por hoje acabaram as suas perguntas. Amanhã tem mais — e a equipe continua aqui.
          </p>
        )}
        {resposta && (resposta.situacao === "falha" || resposta.situacao === "desligada") && (
          <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
            Não consegui responder agora — a sua pergunta não foi contada. Tente de novo ou fale com a equipe.
          </p>
        )}
      </div>

      <div className="flex justify-end border-t border-slate-100 pt-3 dark:border-slate-700/60">
        <Button
          type="button"
          variant={respondeu ? "outline" : "ghost"}
          onClick={() => aoPrecisarDaEquipe(perguntaFeita || pergunta.trim(), respondeu ? resposta.texto : null)}
        >
          {respondeu ? "Não resolveu? Falar com a equipe" : "Falar direto com a equipe"}
        </Button>
      </div>
    </div>
  )
}
