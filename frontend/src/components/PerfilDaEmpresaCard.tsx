import { Sparkles } from "lucide-react"
import { useEffect, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { ESCOLHA_VAZIA, EscolherPerfil, type EscolhaPerfil, escolhaFeita } from "./EscolherPerfil"
import { TituloSecao } from "./PaginaAbas"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"

// Empresa › Emitente: mudar o "como você costuma emitir" (2026.10.7).
export function PerfilDaEmpresaCard() {
  const { recarregarUsuario } = useAuth()
  const [escolha, setEscolha] = useState<EscolhaPerfil | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    api
      .get<{ perfis: string[]; outro: string | null; pulou: boolean }>("/empresa/perfil")
      .then((r) => setEscolha({ perfis: r.perfis, outro: r.outro, pulou: false, buscas_sem_resultado: [] }))
      .catch(() => setEscolha(ESCOLHA_VAZIA))
  }, [])

  async function salvar() {
    if (!escolha) return
    setSalvando(true)
    setMsg(null)
    try {
      await api.put("/empresa/perfil", escolha)
      await recarregarUsuario()
      setMsg({ ok: true, texto: "Pronto, guardei." })
    } catch (err) {
      setMsg({ ok: false, texto: err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão." })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card className="p-5">
      <TituloSecao icone={Sparkles}>Como você costuma emitir suas notas?</TituloSecao>
      <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
        O primeiro marcado é o principal: o atalho dele aparece em destaque na Visão geral.
      </p>
      {escolha ? <EscolherPerfil valor={escolha} onChange={setEscolha} /> : <p className="text-sm text-slate-400">Carregando...</p>}
      {msg && <p className={`mt-3 text-sm ${msg.ok ? "text-success-700 dark:text-success-300" : "text-danger-700"}`}>{msg.texto}</p>}
      <div className="mt-3">
        <Button type="button" variant="outline" disabled={salvando || !escolha || !escolhaFeita(escolha)} onClick={salvar}>
          {salvando ? "Salvando..." : "Salvar"}
        </Button>
      </div>
    </Card>
  )
}
