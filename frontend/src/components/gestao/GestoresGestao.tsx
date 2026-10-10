import { ShieldCheck, Trash2, UserPlus } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { api } from "../../lib/api"
import { erroDe } from "../../lib/gestao"
import { TituloSecao } from "../PaginaAbas"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"
import { Field } from "../ui/Field"

// Gestão › Gestores (2026.10.7): quem administra a plataforma. Todo gestor tem
// todas as permissões por enquanto. A variável ADMIN_EMAILS do Railway continua
// valendo junto, como reserva (aparece aqui como "pela variável").

interface Gestor {
  email: string
  nome: string | null
  tem_conta: boolean
  origem: "tabela" | "variavel"
  adicionado_em: string | null
  adicionado_por: string | null
}

export function GestoresGestao() {
  const [lista, setLista] = useState<Gestor[] | null>(null)
  const [email, setEmail] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    api.get<{ gestores: Gestor[] }>("/gestao/gestores").then((r) => setLista(r.gestores)).catch((e) => setErro(erroDe(e)))
  }, [])

  async function adicionar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setOcupado(true)
    try {
      const r = await api.post<{ gestores: Gestor[] }>("/gestao/gestores", { email })
      setLista(r.gestores)
      setEmail("")
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setOcupado(false)
    }
  }

  async function remover(g: Gestor) {
    if (!window.confirm(`Tirar ${g.email} da Gestão?`)) return
    setErro(null)
    try {
      const r = await api.delete<{ gestores: Gestor[] }>(`/gestao/gestores/${encodeURIComponent(g.email)}`)
      setLista(r.gestores)
    } catch (err) {
      setErro(erroDe(err))
    }
  }

  return (
    <Card className="p-5">
      <TituloSecao icone={ShieldCheck}>Gestores</TituloSecao>
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
        Quem entra aqui na Gestão. Todo gestor pode tudo nesta área, mas nunca abre os documentos das empresas dos clientes.
      </p>
      {erro && <p className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
      {!lista ? (
        <p className="text-sm text-slate-400">Carregando...</p>
      ) : (
        <ul className="mb-4 divide-y divide-slate-100 dark:divide-slate-700/60">
          {lista.map((g) => (
            <li key={g.email} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0">
                <span className="block font-medium text-slate-800 dark:text-slate-100">{g.nome ?? g.email}</span>
                <span className="block text-xs text-slate-400 dark:text-slate-500">
                  {g.nome ? `${g.email} · ` : ""}
                  {g.origem === "variavel" ? "pela variável ADMIN_EMAILS" : g.adicionado_por ? `incluído por ${g.adicionado_por}` : "incluído"}
                  {!g.tem_conta && " · ainda sem conta na Ana"}
                </span>
              </span>
              {g.origem === "tabela" && (
                <Button type="button" variant="ghost" onClick={() => remover(g)} aria-label={`Tirar ${g.email} da Gestão`}>
                  <Trash2 size={15} aria-hidden="true" /> Tirar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={adicionar} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Field label="Incluir gestor (e-mail do login)" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <Button type="submit" variant="accent" disabled={ocupado || !email.trim()}>
          <UserPlus size={15} aria-hidden="true" /> Incluir
        </Button>
      </form>
    </Card>
  )
}
