import { Bot, Download } from "lucide-react"
import { useState } from "react"
import { ApiError } from "../../lib/api"
import { erroDe } from "../../lib/gestao"
import { TituloSecao } from "../PaginaAbas"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"

// Gestão › Ajuda (IA) (06/10/2026): o guia completo alimenta a IA de ajuda e
// não é público — só a administração baixa (GET /gestao/guia).

const PASSOS = [
  <>Baixe o guia pelo botão abaixo (é um arquivo de texto, <code>.md</code>).</>,
  <>
    Carregue o arquivo numa ferramenta de IA gratuita — por exemplo, um caderno do NotebookLM — e gere o link de
    compartilhamento.
  </>,
  <>
    Cole o link na variável <code>AJUDA_IA_URL</code> do servidor. A partir daí aparece o botão “Perguntar pra IA” na tela de
    Ajuda dos usuários.
  </>,
]

export function AjudaIaGestao() {
  const [baixando, setBaixando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function baixar() {
    setBaixando(true)
    setErro(null)
    try {
      const resp = await fetch("/api/gestao/guia", { credentials: "include" })
      if (!resp.ok) {
        const corpo = await resp.json().catch(() => null)
        throw new ApiError(resp.status, corpo?.detail ?? "Não foi possível baixar o guia.")
      }
      const url = URL.createObjectURL(await resp.blob())
      const a = document.createElement("a")
      a.href = url
      a.download = /filename="([^"]+)"/.exec(resp.headers.get("content-disposition") ?? "")?.[1] ?? "guia-agente-ana.md"
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 2000)
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setBaixando(false)
    }
  }

  return (
    <Card className="p-5">
      <TituloSecao icone={Bot}>Guia da IA de ajuda</TituloSecao>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        O guia completo da Ana é o texto que ensina a IA a responder as dúvidas dos usuários. Ele não fica disponível pra eles:
        só a administração baixa por aqui.
      </p>
      <ol className="mt-4 flex flex-col gap-3">
        {PASSOS.map((passo, i) => (
          <li key={i} className="flex items-start gap-3 text-sm text-slate-700 dark:text-slate-200">
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-50 text-xs font-semibold text-primary-700 dark:bg-primary-900/40 dark:text-primary-300"
            >
              {i + 1}
            </span>
            <span className="min-w-0 [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs dark:[&_code]:bg-slate-700">
              {passo}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button type="button" variant="accent" disabled={baixando} onClick={baixar}>
          <Download size={15} aria-hidden="true" /> {baixando ? "Baixando..." : "Baixar o guia"}
        </Button>
        {erro && (
          <span role="alert" className="text-sm text-danger-700 dark:text-danger-300">
            {erro}
          </span>
        )}
      </div>
      <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
        Sempre que o guia mudar, baixe de novo e atualize o arquivo na ferramenta de IA — o link continua o mesmo.
      </p>
    </Card>
  )
}
