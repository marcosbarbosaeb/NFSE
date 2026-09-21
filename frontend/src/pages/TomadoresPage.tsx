import { Plus, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { api } from "../lib/api"
import type { Tomador, VinculoResumo } from "../lib/types"

type Aba = "meus" | "todos"

export function TomadoresPage() {
  const [aba, setAba] = useState<Aba>("meus")
  const [busca, setBusca] = useState("")
  const [vinculos, setVinculos] = useState<VinculoResumo[] | null>(null)
  const [tomadores, setTomadores] = useState<Tomador[] | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    let cancelado = false
    setCarregando(true)
    const carregar =
      aba === "meus"
        ? api.get<VinculoResumo[]>("/vinculos").then((v) => !cancelado && setVinculos(v))
        : api.get<Tomador[]>("/tomadores?apenas_meus=false").then((t) => !cancelado && setTomadores(t))
    carregar.finally(() => !cancelado && setCarregando(false))
    return () => {
      cancelado = true
    }
  }, [aba])

  const vinculosFiltrados = useMemo(() => {
    if (!vinculos) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return vinculos
    return vinculos.filter(
      (v) => v.apelido.toLowerCase().includes(termo) || v.tomador_razao_social.toLowerCase().includes(termo)
    )
  }, [vinculos, busca])

  const tomadoresFiltrados = useMemo(() => {
    if (!tomadores) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return tomadores
    return tomadores.filter((t) => t.razao_social.toLowerCase().includes(termo) || t.cnpj.includes(termo))
  }, [tomadores, busca])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Tomadores</h1>
          <p className="text-sm text-slate-500">Gerencie seus tomadores e as regras de emissão de cada um.</p>
        </div>
        <Link to="/tomadores/novo">
          <Button variant="accent">
            <Plus size={16} /> Adicionar tomador
          </Button>
        </Link>
      </div>

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex rounded-lg bg-slate-100 p-1 text-sm">
            <button
              type="button"
              onClick={() => setAba("meus")}
              className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                aba === "meus" ? "bg-white text-primary-700 shadow-sm" : "text-slate-500"
              }`}
            >
              Meus tomadores
            </button>
            <button
              type="button"
              onClick={() => setAba("todos")}
              className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                aba === "todos" ? "bg-white text-primary-700 shadow-sm" : "text-slate-500"
              }`}
            >
              Todos os tomadores
            </button>
          </div>
          <div className="relative w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por nome ou CNPJ..."
              className="w-full rounded-lg border border-slate-200 py-1.5 pl-9 pr-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>

        {carregando && <p className="py-8 text-center text-sm text-slate-400">Carregando...</p>}

        {!carregando && aba === "meus" && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 font-medium">Apelido</th>
                <th className="py-2 font-medium">Tomador</th>
                <th className="py-2 font-medium">CNPJ</th>
                <th className="py-2 font-medium">Série</th>
                <th className="py-2 font-medium">Revisão</th>
              </tr>
            </thead>
            <tbody>
              {vinculosFiltrados.map((v) => (
                <tr key={v.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                  <td className="py-3">
                    <Link to={`/tomadores/${v.id}`} className="font-medium text-primary-700 hover:underline">
                      {v.apelido}
                    </Link>
                  </td>
                  <td className="py-3 text-slate-600">{v.tomador_razao_social}</td>
                  <td className="py-3 text-slate-500">{v.tomador_cnpj}</td>
                  <td className="py-3 text-slate-500">{v.serie}</td>
                  <td className="py-3">
                    {v.requer_revisao ? <Badge variant="warning">Obrigatória</Badge> : <Badge variant="neutral">Não</Badge>}
                  </td>
                </tr>
              ))}
              {vinculosFiltrados.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    Nenhum tomador ativo ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {!carregando && aba === "todos" && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 font-medium">Razão social</th>
                <th className="py-2 font-medium">CNPJ</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {tomadoresFiltrados.map((t) => (
                <tr key={t.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                  <td className="py-3 font-medium text-slate-800">{t.razao_social}</td>
                  <td className="py-3 text-slate-500">{t.cnpj}</td>
                  <td className="py-3 text-right">
                    <Link to={`/tomadores/novo?tomador_id=${t.id}`} className="text-sm font-medium text-primary-600 hover:text-primary-700">
                      Usar este tomador
                    </Link>
                  </td>
                </tr>
              ))}
              {tomadoresFiltrados.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-slate-400">
                    Nenhum tomador no catálogo ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
