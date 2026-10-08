import { CalendarPlus, Check, Copy, RefreshCw } from "lucide-react"
import { useEffect, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { Button } from "../ui/Button"

/** Link de assinatura do calendário (08/10/2026): a pessoa cola uma vez no
 * Google Agenda (ou Outlook/Apple) e os prazos, previsões e lembretes da Ana
 * aparecem lá e se atualizam sozinhos. Fica em Empresa › Integrações e no
 * Calendário. Backend: app/services/agenda_ics.py. */
export function AgendaAssinatura({ compacto = false }: { compacto?: boolean }) {
  const [url, setUrl] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)
  const [trocando, setTrocando] = useState(false)

  useEffect(() => {
    api
      .get<{ url: string }>("/calendario/assinatura")
      .then((r) => setUrl(r.url))
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Não consegui buscar o link agora."))
  }, [])

  async function copiar() {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      // sem permissão de área de transferência: seleciona pra pessoa copiar
      ;(document.getElementById("link-agenda") as HTMLInputElement | null)?.select()
    }
    setCopiado(true)
    window.setTimeout(() => setCopiado(false), 2500)
  }

  async function trocar() {
    if (!window.confirm("Gerar um link novo? O link antigo para de funcionar e você vai precisar colar o novo na sua agenda.")) return
    setTrocando(true)
    try {
      setUrl((await api.post<{ url: string }>("/calendario/assinatura/novo", {})).url)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Não consegui trocar o link agora.")
    } finally {
      setTrocando(false)
    }
  }

  const webcal = url ? url.replace(/^https?:\/\//, "webcal://") : null
  const noGoogle = webcal ? `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(webcal)}` : null

  return (
    <div className="flex flex-col gap-3">
      {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="link-agenda"
          readOnly
          value={url ?? "Carregando..."}
          onFocus={(e) => e.target.select()}
          aria-label="Link da sua agenda"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
        />
        <Button variant="outline" onClick={copiar} disabled={!url}>
          {copiado ? <Check size={15} /> : <Copy size={15} />} {copiado ? "Copiado" : "Copiar link"}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {noGoogle && (
          <a
            href={noGoogle}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            <CalendarPlus size={15} /> Adicionar no Google Agenda
          </a>
        )}
        {webcal && (
          <a href={webcal} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-primary-700 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-900/30">
            Outlook ou Apple
          </a>
        )}
      </div>
      {!compacto && (
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-300">
          <li>
            Clique em <strong>Adicionar no Google Agenda</strong> e confirme. Se não abrir, no Google Agenda vá em <strong>Outras agendas › + › Do URL</strong> e cole o link.
          </li>
          <li>Pronto: os dias de gerar nota, as previsões de recebimento e os seus lembretes aparecem lá.</li>
          <li>Mudou algo aqui? O Google atualiza sozinho, mas demora algumas horas (é o tempo dele, não dá pra apressar).</li>
        </ol>
      )}
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Quem tiver este link vê os eventos da sua agenda (sem entrar no painel). Se ele cair em mãos erradas,{" "}
        <button type="button" onClick={trocar} disabled={trocando || !url} className="inline-flex items-center gap-1 font-medium text-primary-700 underline disabled:opacity-50 dark:text-primary-300">
          <RefreshCw size={12} /> gere um link novo
        </button>
        .
      </p>
    </div>
  )
}
