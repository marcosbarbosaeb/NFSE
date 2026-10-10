import { BriefcaseBusiness } from "lucide-react"
import { useEffect, useState } from "react"
import { api } from "../../lib/api"
import { erroDe, numero } from "../../lib/gestao"
import { TituloSecao } from "../PaginaAbas"
import { Card } from "../ui/Card"

// Gestão › Contadores (2026.10.7): por contador, clientes na carteira, ativos
// no mês e cadastrados por ele — a base da cobrança por cliente, que ainda não
// está ligada (o modelo está em claude/duvidas-para-o-marcos.md). Só números.
// "Ativo no mês": nota autorizada ou uso da Ana no mês, sem bloqueio
// (backend/app/services/carteira.py).

interface Contadores {
  contadores: { email: string | null; nome: string | null; na_carteira: number; ativos_no_mes: number; cadastrados_pelo_contador: number }[]
  total_ativos: number
}

export function ContadoresGestao() {
  const [dados, setDados] = useState<Contadores | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  useEffect(() => {
    api.get<Contadores>("/gestao/contadores").then(setDados).catch((e) => setErro(erroDe(e)))
  }, [])
  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
  if (!dados) return <p className="py-6 text-center text-sm text-slate-400">Carregando...</p>
  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <TituloSecao icone={BriefcaseBusiness}>Contadores</TituloSecao>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {numero(dados.contadores.length)} contador(es) com clientes; {numero(dados.total_ativos)} cliente(s) ativo(s) neste mês. Ativo = nota autorizada ou uso
          da Ana no mês, sem bloqueio. A cobrança por cliente ainda não está ligada.
        </p>
      </Card>
      <Card className="overflow-hidden">
        {dados.contadores.length === 0 ? (
          <p className="p-5 text-sm text-slate-500 dark:text-slate-400">Nenhum contador atendendo clientes ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Contador</th>
                  <th className="px-3 py-2.5 text-right font-medium">Na carteira</th>
                  <th className="px-3 py-2.5 text-right font-medium">Ativos no mês</th>
                  <th className="px-3 py-2.5 text-right font-medium">Cadastrados por ele</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                {dados.contadores.map((c) => (
                  <tr key={c.email ?? c.nome ?? Math.random()}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800 dark:text-slate-100">{c.nome || c.email}</p>
                      {c.nome && <p className="text-xs text-slate-500 dark:text-slate-400">{c.email}</p>}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">{numero(c.na_carteira)}</td>
                    <td className="px-3 py-3 text-right font-semibold tabular-nums text-slate-900 dark:text-slate-100">{numero(c.ativos_no_mes)}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{numero(c.cadastrados_pelo_contador)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
