import { useState } from "react"
import { api, formatarErro, ApiError } from "../lib/api"
import { useAuth } from "../lib/auth"
import { ESCOLHA_VAZIA, EscolherPerfil, type EscolhaPerfil, escolhaFeita } from "./EscolherPerfil"
import { Button } from "./ui/Button"
import { Modal } from "./ui/Modal"

// Perfis (2026.10.7): contas que já existiam (e empresas novas que ainda não
// responderam) veem a pergunta UMA vez ao entrar, com a opção de pular.
// Só o dono; nunca na conta de contador nem na simulação (o servidor decide:
// `usuario.perguntar_perfil`).

export function PerguntaPerfil() {
  const { usuario, recarregarUsuario } = useAuth()
  const [escolha, setEscolha] = useState<EscolhaPerfil>(ESCOLHA_VAZIA)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [fechado, setFechado] = useState(false)
  if (!usuario?.perguntar_perfil || fechado) return null

  async function salvar(pulou: boolean) {
    setSalvando(true)
    setErro(null)
    try {
      await api.put("/empresa/perfil", pulou ? { ...escolha, perfis: [], outro: null, pulou: true } : escolha)
      setFechado(true)
      await recarregarUsuario()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal titulo="Como você costuma emitir suas notas?" onClose={() => salvar(true)} largura="max-w-2xl">
      <div className="flex flex-col gap-4 p-5">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Me conta pra eu deixar à mão o que você mais usa. Pode marcar mais de um — o primeiro que você marcar é o principal. Dá pra mudar
          depois em Empresa.
        </p>
        <EscolherPerfil valor={escolha} onChange={setEscolha} />
        {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" disabled={salvando} onClick={() => salvar(true)}>
            Pular
          </Button>
          <Button type="button" variant="accent" disabled={salvando || !escolhaFeita(escolha)} onClick={() => salvar(false)}>
            {salvando ? "Salvando..." : "Pronto"}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
