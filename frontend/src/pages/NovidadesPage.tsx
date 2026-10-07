import { ArrowRight, Sparkles } from "lucide-react"
import { useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Card } from "../components/ui/Card"
import { type PerfilNovidade, useNovidades } from "../lib/novidades"

// Novidades (08/10/2026): o que mudou em cada versão, pra quem usa — "listar
// o que mudou até para informarmos aos usuários". Cada pessoa vê o que é do
// perfil dela (empresa, contador ou os dois).

const ETIQUETA: Record<PerfilNovidade, { texto: string; variante: "neutral" | "info" | "success" } | null> = {
  todos: null,
  empresa: { texto: "pra sua empresa", variante: "info" },
  contador: { texto: "pra contadores", variante: "success" },
}

function dataPorExtenso(iso: string): string {
  const d = new Date(`${iso}T12:00:00`)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" })
}

export function NovidadesPage() {
  const { dados, marcarVistas } = useNovidades()
  // Guarda quais eram novas ao abrir: a etiqueta "nova" fica até sair da tela.
  const marcou = useRef(false)
  useEffect(() => {
    if (dados && dados.novas > 0 && !marcou.current) {
      marcou.current = true
      marcarVistas()
    }
  }, [dados, marcarVistas])

  // Só mostra as duas etiquetas de perfil pra quem recebe os dois tipos.
  const perfis = new Set((dados?.versoes ?? []).flatMap((v) => v.itens.map((i) => i.perfil)))
  const doisPerfis = perfis.has("empresa") && perfis.has("contador")

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
          <Sparkles size={22} className="text-accent-500" aria-hidden="true" /> Novidades
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          O que mudou em cada atualização da Agente Ana{dados ? <> · você está na versão <strong className="tabular-nums">{dados.versao}</strong></> : null}.
        </p>
      </header>

      {dados === null && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {dados?.versoes.map((v) => (
        <Card key={v.versao} className="p-5">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">Versão {v.versao}</h2>
            <span className="text-sm text-slate-500 dark:text-slate-400">{dataPorExtenso(v.data)}</span>
            {v.nova && <Badge variant="warning">nova</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{v.resumo}</p>
          <ul className="mt-4 flex flex-col gap-4">
            {v.itens.map((i) => {
              const etiqueta = doisPerfis ? ETIQUETA[i.perfil] : null
              return (
                <li key={i.titulo} className="border-l-2 border-primary-200 pl-3 dark:border-primary-800">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                    {i.titulo}
                    {etiqueta && <Badge variant={etiqueta.variante}>{etiqueta.texto}</Badge>}
                  </p>
                  <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{i.texto}</p>
                  {i.link && (
                    <Link to={i.link} className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300">
                      Ver <ArrowRight size={14} aria-hidden="true" />
                    </Link>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      ))}
    </div>
  )
}
