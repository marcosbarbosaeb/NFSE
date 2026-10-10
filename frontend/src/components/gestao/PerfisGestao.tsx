import { SearchX, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"
import { api } from "../../lib/api"
import { erroDe, numero } from "../../lib/gestao"
import { TituloSecao } from "../PaginaAbas"
import { Card } from "../ui/Card"

// Gestão › Perfis (2026.10.7): quantas empresas em cada jeito de emitir, quem
// pulou, quem ainda não respondeu, e a lista de demanda pros próximos perfis
// ("Não me encontrei" e buscas sem resultado, agrupadas por texto parecido).

interface Grupo {
  texto: string
  vezes: number
  variacoes: string[]
}
interface ResumoPerfis {
  perfis: { id: string; titulo: string; principal: number; marcado: number }[]
  pularam: number
  sem_resposta: number
  nao_me_encontrei: Grupo[]
  buscas_sem_resultado: Grupo[]
}

function ListaGrupos({ grupos, vazio }: { grupos: Grupo[]; vazio: string }) {
  if (grupos.length === 0) return <p className="text-sm text-slate-400 dark:text-slate-500">{vazio}</p>
  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
      {grupos.slice(0, 100).map((g) => (
        <li key={g.texto} className="flex items-start justify-between gap-3 py-2 text-sm">
          <span className="min-w-0 text-slate-700 dark:text-slate-200">
            {g.texto}
            {g.variacoes.length > 1 && <span className="block text-xs text-slate-400 dark:text-slate-500">também: {g.variacoes.slice(1).join(", ")}</span>}
          </span>
          <span className="tabular-nums text-slate-500 dark:text-slate-400">{numero(g.vezes)}</span>
        </li>
      ))}
    </ul>
  )
}

export function PerfisGestao() {
  const [dados, setDados] = useState<ResumoPerfis | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  useEffect(() => {
    api.get<ResumoPerfis>("/gestao/perfis").then(setDados).catch((e) => setErro(erroDe(e)))
  }, [])
  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
  if (!dados) return <p className="text-sm text-slate-400">Carregando...</p>
  return (
    <>
      <Card className="p-5">
        <TituloSecao icone={Sparkles}>Como as empresas emitem</TituloSecao>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400 dark:border-slate-700 dark:text-slate-500">
              <th scope="col" className="py-2">Perfil</th>
              <th scope="col" className="py-2 text-right">Principal</th>
              <th scope="col" className="py-2 text-right">Marcado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {dados.perfis.map((p) => (
              <tr key={p.id}>
                <td className="py-2 text-slate-700 dark:text-slate-200">{p.titulo}</td>
                <td className="py-2 text-right tabular-nums">{numero(p.principal)}</td>
                <td className="py-2 text-right tabular-nums">{numero(p.marcado)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          {numero(dados.pularam)} pularam a pergunta · {numero(dados.sem_resposta)} ainda não responderam.
        </p>
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <TituloSecao icone={Sparkles}>“Não me encontrei”</TituloSecao>
          <ListaGrupos grupos={dados.nao_me_encontrei} vazio="Ninguém escreveu ainda." />
        </Card>
        <Card className="p-5">
          <TituloSecao icone={SearchX}>Profissões buscadas sem resultado</TituloSecao>
          <ListaGrupos grupos={dados.buscas_sem_resultado} vazio="Nenhuma busca sem resultado ainda." />
        </Card>
      </div>
    </>
  )
}
