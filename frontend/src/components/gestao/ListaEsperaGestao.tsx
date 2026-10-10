import { MapPin, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { api } from "../../lib/api"
import { erroDe, numero } from "../../lib/gestao"
import { formatarDocumento } from "../../lib/documento"
import { TituloSecao } from "../PaginaAbas"
import { Card } from "../ui/Card"

// Gestão › Lista de espera (2026.10.7): quem não pôde criar conta porque a
// cidade ainda não usa o Emissor Nacional ou porque o regime não é atendido.
// Agrupado por cidade e por motivo. Quando a cidade entra na lista da
// Receita, a pessoa recebe um e-mail sozinha.

interface ListaEspera {
  total: number
  por_motivo: { cidade_fora: number; regime: number }
  por_cidade: { cidade: string; cod_municipio: string | null; pessoas: number; ja_no_emissor: boolean }[]
  pessoas: {
    id: string
    email: string
    whatsapp: string | null
    cnpj: string
    razao_social: string | null
    cidade: string | null
    motivo: "cidade_fora" | "regime"
    criado_em: string | null
    avisado_em: string | null
  }[]
}

const MOTIVO = { cidade_fora: "Cidade fora do Emissor Nacional", regime: "Regime não atendido" }
const th = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500"
const td = "px-3 py-2 text-sm text-slate-700 dark:text-slate-200"

export function ListaEsperaGestao() {
  const [dados, setDados] = useState<ListaEspera | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  useEffect(() => {
    api.get<ListaEspera>("/gestao/lista-espera").then(setDados).catch((e) => setErro(erroDe(e)))
  }, [])
  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
  if (!dados) return <p className="text-sm text-slate-400">Carregando...</p>
  return (
    <>
      <Card className="p-5">
        <TituloSecao icone={Users}>Lista de espera</TituloSecao>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {numero(dados.total)} pessoa(s): {numero(dados.por_motivo.cidade_fora)} por cidade fora do Emissor Nacional e{" "}
          {numero(dados.por_motivo.regime)} por regime não atendido (Lucro Presumido ou Real).
        </p>
      </Card>
      <Card className="p-5">
        <TituloSecao icone={MapPin}>Por cidade</TituloSecao>
        {dados.por_cidade.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Ninguém esperando por cidade.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {dados.por_cidade.map((c) => (
              <li key={c.cod_municipio ?? c.cidade} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-700 dark:text-slate-200">
                  {c.cidade}
                  {c.ja_no_emissor && <span className="ml-2 text-xs text-success-700 dark:text-success-300">já entrou — o aviso sai sozinho</span>}
                </span>
                <span className="tabular-nums text-slate-500 dark:text-slate-400">{numero(c.pessoas)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card className="overflow-x-auto p-5">
        <TituloSecao icone={Users}>Pessoas</TituloSecao>
        {dados.pessoas.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Ninguém na lista ainda.</p>
        ) : (
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700">
                <th scope="col" className={th}>Empresa</th>
                <th scope="col" className={th}>Contato</th>
                <th scope="col" className={th}>Motivo</th>
                <th scope="col" className={th}>Desde</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {dados.pessoas.map((p) => (
                <tr key={p.id}>
                  <td className={td}>
                    <span className="block">{p.razao_social ?? "—"}</span>
                    <span className="block text-xs text-slate-400 dark:text-slate-500">{formatarDocumento(p.cnpj)} · {p.cidade ?? "cidade ?"}</span>
                  </td>
                  <td className={td}>
                    <span className="block">{p.email}</span>
                    {p.whatsapp && <span className="block text-xs text-slate-400 dark:text-slate-500">{p.whatsapp}</span>}
                  </td>
                  <td className={td}>
                    {MOTIVO[p.motivo]}
                    {p.avisado_em && <span className="block text-xs text-success-700 dark:text-success-300">avisado(a)</span>}
                  </td>
                  <td className={td}>{p.criado_em ? new Date(p.criado_em).toLocaleDateString("pt-BR") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
