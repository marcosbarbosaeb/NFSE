import { CalendarDays, FileText, Home, Lightbulb, Settings, TrendingDown, Users, Wallet } from "lucide-react"
import { NavLink } from "react-router-dom"

// "Calendário" não faz parte das telas originais do NotaFácil (mockup) — foi
// pedido à parte pelo usuário (previsão de recebimento + prazo de emissão
// por tomador), então entra como item novo na navegação.
const ITENS = [
  { to: "/", label: "Visão geral", icon: Home, end: true },
  { to: "/nfse", label: "NFS-e", icon: FileText },
  { to: "/tomadores", label: "Tomadores", icon: Users },
  { to: "/calendario", label: "Calendário", icon: CalendarDays },
  { to: "/recebimentos", label: "Recebimentos", icon: Wallet },
  { to: "/despesas", label: "Despesas", icon: TrendingDown },
  { to: "/configuracoes", label: "Configurações", icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col justify-between bg-brand-900 px-4 py-6 text-slate-300">
      <div>
        <div className="mb-8 flex items-center gap-2 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white">
            <FileText size={18} />
          </div>
          <div className="leading-tight">
            <p className="text-base font-semibold text-white">
              Nota<span className="text-primary-400">Fácil</span>
            </p>
            <p className="text-[11px] text-slate-400">NFS-e sem complicação</p>
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {ITENS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-primary-600 text-white" : "text-slate-300 hover:bg-brand-800 hover:text-white"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="rounded-xl bg-brand-800/70 p-4 text-slate-300">
        <Lightbulb size={18} className="mb-2 text-primary-400" />
        <p className="text-sm font-medium text-white">Cadastre uma vez. Use todos os meses.</p>
        <p className="mt-1 text-xs text-slate-400">
          Automatize suas emissões e foque no que realmente importa.
        </p>
      </div>
    </aside>
  )
}
