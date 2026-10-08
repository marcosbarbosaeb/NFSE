import { CheckCircle2, Send } from "lucide-react"
import { useState } from "react"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import { ehContador } from "../lib/contador"
import { mensagemDeErro } from "../lib/excluir"

/** Fase sem cobrança (08/10/2026): "podem começar direto no teste e, depois
 * desse período, me permita autorizar o uso". Quando o teste acaba, a pessoa
 * pede a liberação aqui — um clique — e a administração autoriza na Gestão.
 * `claro`: sobre a faixa vermelha do topo (botão branco). */
export function PedirLiberacao({ claro = false, aoPedir }: { claro?: boolean; aoPedir?: () => void }) {
  const { usuario, recarregarUsuario } = useAuth()
  const [pedindo, setPedindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const pedida = usuario?.acesso?.liberacao_pedida_em
  if (!usuario || ehContador(usuario)) return null

  async function pedir() {
    setPedindo(true)
    setErro(null)
    try {
      await api.post("/assinatura/pedir-liberacao", {})
      await recarregarUsuario()
      aoPedir?.()
    } catch (err) {
      setErro(mensagemDeErro(err))
    } finally {
      setPedindo(false)
    }
  }

  if (pedida) {
    return (
      <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${claro ? "text-white" : "text-success-700 dark:text-success-300"}`}>
        <CheckCircle2 size={15} aria-hidden="true" />
        Liberação pedida em {new Date(pedida).toLocaleDateString("pt-BR")}. A equipe te chama no WhatsApp.
      </span>
    )
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => void pedir()}
        disabled={pedindo}
        className={
          claro
            ? "inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-0.5 text-xs font-semibold text-danger-700 hover:bg-white/90 disabled:opacity-70"
            : "inline-flex items-center gap-1.5 rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-60"
        }
      >
        <Send size={claro ? 13 : 15} aria-hidden="true" /> {pedindo ? "Pedindo..." : "Pedir liberação"}
      </button>
      {erro && <span className={`text-xs ${claro ? "text-white" : "text-danger-600"}`}>{erro}</span>}
    </span>
  )
}
