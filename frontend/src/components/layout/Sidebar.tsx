import { CalendarDays, FileText, Gift, Home, Settings, Users, Wallet } from "lucide-react"
import { NavLink } from "react-router-dom"
import { BotaoSuporte } from "../SuporteModal"
import { AnaAvatar, Marca } from "../brand/Marca"

// "Calendário" não faz parte das telas originais do emissor (mockup) — foi
// pedido à parte pelo usuário (previsão de recebimento + prazo de emissão
// por tomador), então entra como item novo na navegação.
const ITENS = [
  { to: "/app", label: "Visão geral", icon: Home, end: true },
  { to: "/app/nfse", label: "NFS-e", icon: FileText },
  { to: "/app/tomadores", label: "Tomadores", icon: Users },
  { to: "/app/calendario", label: "Calendário", icon: CalendarDays },
  { to: "/app/financeiro", label: "Financeiro", icon: Wallet },
  { to: "/app/indique", label: "Indique e ganhe", icon: Gift },
  { to: "/app/configuracoes", label: "Configurações", icon: Settings },
]

// Celular (revisão de 28/09/2026): abaixo de "lg" a barra vira uma gaveta
// que abre pelo botão de menu do topo e fecha ao escolher uma tela.
export function Sidebar({ aberto = false, onFechar }: { aberto?: boolean; onFechar?: () => void }) {
  return (
    <>
      {aberto && <div className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden" onClick={onFechar} aria-hidden="true" />}
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col justify-between overflow-y-auto bg-brand-900 px-4 py-6 text-slate-300 transition-transform lg:sticky lg:top-0 lg:z-auto lg:translate-x-0 lg:self-start ${
        aberto ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div>
        <div className="mb-8 flex items-center gap-2 px-2">
          <Marca escuro subtitulo="Emissor de notas" />
        </div>

        <nav className="flex flex-col gap-1" data-tour="menu">
          {ITENS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onFechar}
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
        <div className="mb-2 flex items-center gap-2">
          <AnaAvatar size={28} />
          <p className="text-sm font-medium text-white">Deixa comigo.</p>
        </div>
        <p className="text-xs text-slate-400">
          Cadastre cada fornecedor uma vez — todo mês eu preparo a nota e você só confere.
        </p>
        <BotaoSuporte logado className="mt-3 inline-block text-left text-xs font-medium text-accent-300 hover:text-accent-200">
          Precisa de ajuda? Fale com o suporte
        </BotaoSuporte>
      </div>
    </aside>
    </>
  )
}
