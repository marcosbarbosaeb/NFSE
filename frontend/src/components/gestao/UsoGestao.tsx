import { Activity, AlertTriangle, Lightbulb, MousePointerClick, PanelsTopLeft } from "lucide-react"
import { useEffect, useState } from "react"
import { api } from "../../lib/api"
import { erroDe, numero, plural } from "../../lib/gestao"
import { TituloSecao } from "../PaginaAbas"
import { Card } from "../ui/Card"
import { StatCard } from "../ui/StatCard"

// Gestão › Uso (08/10/2026): "você conseguiria rastrear a atividade do usuário
// na plataforma, de forma futura sugerir melhorias?". Telas abertas, ações
// feitas, erros e o caminho da conta nova até a primeira nota — só nomes e
// contagens (backend/app/services/uso.py).

interface Linha {
  titulo: string
  vezes: number
  pessoas: number
}
interface UsoDaPlataforma {
  dias: number
  eventos: number
  pessoas: number
  telas: (Linha & { nome: string })[]
  acoes: Linha[]
  erros: (Linha & { nome: string; status: string; ultima: string | null })[]
  telas_sem_visita: { nome: string; titulo: string }[]
  funil: { etapa: string; contas: number }[]
  sugestoes: { tipo: string; titulo: string; texto: string }[]
}

const PERIODOS = [7, 30, 90]
const th = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const td = "px-3 py-2 text-sm text-slate-700 dark:text-slate-200"

function Tabela({ linhas, vazio, extra }: { linhas: Linha[]; vazio: string; extra?: (l: Linha) => string }) {
  const [tudo, setTudo] = useState(false)
  if (linhas.length === 0) return <p className="py-4 text-sm text-slate-400 dark:text-slate-500">{vazio}</p>
  const maior = Math.max(...linhas.map((l) => l.vezes))
  const visiveis = tudo ? linhas : linhas.slice(0, 8)
  return (
    <>
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-100 dark:border-slate-700">
            <th scope="col" className={th}>O quê</th>
            <th scope="col" className={`${th} text-right`}>Vezes</th>
            <th scope="col" className={`${th} text-right`}>Pessoas</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
          {visiveis.map((l, i) => (
            <tr key={`${l.titulo}-${i}`}>
              <td className={td}>
                <span className="block">
                  {l.titulo}
                  {extra && <span className="ml-1.5 text-xs text-slate-400 dark:text-slate-500">{extra(l)}</span>}
                </span>
                <span className="mt-1 block h-1 rounded-full bg-slate-100 dark:bg-slate-700" aria-hidden="true">
                  <span className="block h-full rounded-full bg-primary-500 dark:bg-primary-400" style={{ width: `${Math.max(2, (l.vezes / maior) * 100)}%` }} />
                </span>
              </td>
              <td className={`${td} text-right tabular-nums`}>{numero(l.vezes)}</td>
              <td className={`${td} text-right tabular-nums`}>{numero(l.pessoas)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {linhas.length > 8 && (
        <button type="button" onClick={() => setTudo((v) => !v)} className="mt-2 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300">
          {tudo ? "Mostrar menos" : `Ver as ${linhas.length}`}
        </button>
      )}
    </>
  )
}

export function UsoGestao() {
  const [dias, setDias] = useState(30)
  const [dados, setDados] = useState<UsoDaPlataforma | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  useEffect(() => {
    let vivo = true
    setErro(null)
    api
      .get<UsoDaPlataforma>(`/gestao/uso?dias=${dias}`)
      .then((d) => vivo && setDados(d))
      .catch((e) => vivo && setErro(erroDe(e)))
    return () => {
      vivo = false
    }
  }, [dias])

  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>
  if (!dados) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
  const topo = dados.funil[0]?.contas ?? 0

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          O que as pessoas abrem e fazem no painel, e onde travam. Só o nome da tela ou da ação — nunca o conteúdo. Simulações não contam.
        </p>
        <div className="flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-700" role="group" aria-label="Período">
          {PERIODOS.map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={p === dias}
              onClick={() => setDias(p)}
              className={`rounded-md px-3 py-1 text-sm font-medium ${p === dias ? "bg-primary-600 text-white" : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"}`}
            >
              {p} dias
            </button>
          ))}
        </div>
      </div>

      {dados.sugestoes.length > 0 && (
        <Card className="border-primary-200 bg-primary-50/50 p-5 dark:border-primary-800 dark:bg-primary-900/20">
          <TituloSecao icone={Lightbulb}>Onde olhar primeiro</TituloSecao>
          <ul className="mt-2 flex flex-col gap-3">
            {dados.sugestoes.map((s, i) => (
              <li key={i}>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{s.titulo}</p>
                <p className="text-sm text-slate-600 dark:text-slate-300">{s.texto}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard icon={<Activity size={18} />} label="Registros de uso" value={numero(dados.eventos)} sublabel={`nos últimos ${dados.dias} dias`} />
        <StatCard icon={<MousePointerClick size={18} />} label="Pessoas usando" value={numero(dados.pessoas)} sublabel="logins diferentes" />
        <StatCard
          icon={<AlertTriangle size={18} />}
          iconClassName={dados.erros.length ? "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300" : undefined}
          label="Ações recusadas"
          value={numero(dados.erros.reduce((n, e) => n + e.vezes, 0))}
          sublabel={dados.erros.length ? plural(dados.erros.length, "tipo de erro", "tipos de erro") : "nenhum erro no período"}
        />
      </div>

      <Card className="p-5">
        <TituloSecao>Da conta criada até a primeira nota</TituloSecao>
        <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">Contas reais com o módulo de notas, desde sempre. Cada linha mostra quantas chegaram até ali.</p>
        <ol className="flex flex-col gap-2">
          {dados.funil.map((e, i) => {
            const pct = topo ? Math.round((e.contas / topo) * 100) : 0
            const perdeu = i > 0 ? dados.funil[i - 1].contas - e.contas : 0
            return (
              <li key={e.etapa} className="grid grid-cols-[minmax(0,12rem)_minmax(0,1fr)_auto] items-center gap-3 text-sm">
                <span className="truncate text-slate-700 dark:text-slate-200">{e.etapa}</span>
                <span className="h-2.5 rounded-full bg-slate-100 dark:bg-slate-700" aria-hidden="true">
                  <span className="block h-full rounded-full bg-primary-500 dark:bg-primary-400" style={{ width: `${Math.max(1.5, pct)}%` }} />
                </span>
                <span className="whitespace-nowrap tabular-nums text-slate-600 dark:text-slate-300">
                  <strong className="font-semibold text-slate-900 dark:text-slate-100">{numero(e.contas)}</strong> · {pct}%
                  {perdeu > 0 && <span className="ml-1.5 text-xs text-warning-700 dark:text-warning-300">−{perdeu}</span>}
                </span>
              </li>
            )
          })}
        </ol>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <TituloSecao icone={PanelsTopLeft}>Telas mais abertas</TituloSecao>
          <Tabela linhas={dados.telas} vazio="Nenhuma tela registrada ainda neste período." />
          {dados.telas_sem_visita.length > 0 && dados.eventos > 0 && (
            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Ninguém abriu: {dados.telas_sem_visita.map((t) => t.titulo).join(", ")}.</p>
          )}
        </Card>
        <Card className="p-5">
          <TituloSecao icone={MousePointerClick}>O que mais fazem</TituloSecao>
          <Tabela linhas={dados.acoes} vazio="Nenhuma ação registrada ainda neste período." />
        </Card>
      </div>

      <Card className="p-5">
        <TituloSecao icone={AlertTriangle}>Onde aparece erro</TituloSecao>
        <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">
          Ações que o sistema recusou. Muita recusa na mesma ação costuma ser tela que não deixa claro o que falta. (409 = já existe ou falta algo; 422 = campo
          inválido; 402 = sem acesso; 5xx = falha nossa.)
        </p>
        <Tabela linhas={dados.erros} vazio="Nenhuma ação recusada neste período." extra={(l) => `código ${(l as UsoDaPlataforma["erros"][number]).status || "?"}`} />
      </Card>
    </>
  )
}
