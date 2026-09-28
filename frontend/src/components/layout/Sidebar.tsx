import { Building2, CalendarDays, FileText, Gift, Home, UserRound, Users, Wallet } from "lucide-react"
import { Link, NavLink, useLocation } from "react-router-dom"
import { BotaoSuporte } from "../SuporteModal"
import { TrocaEmpresa } from "../TrocaEmpresa"
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
  // "Configurações" virou "Empresa" (dados do CNPJ ativo) + "Minha conta"
  // (no pé da barra e no menu do usuário) — 29/09/2026.
  { to: "/app/empresa", label: "Empresa", icon: Building2 },
]

const classeItem = (ativo: boolean) =>
  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 ${
    ativo ? "bg-primary-600 text-white" : "text-slate-300 hover:bg-brand-800 hover:text-white"
  }`

// Celular (revisão de 28/09/2026): abaixo de "lg" a barra vira uma gaveta
// que abre pelo botão de menu do topo e fecha ao escolher uma tela.
export function Sidebar({ aberto = false, onFechar }: { aberto?: boolean; onFechar?: () => void }) {
  const { pathname, search } = useLocation()
  const naConta = pathname.replace(/\/+$/, "") === "/app/conta"
  const naIndicacao = naConta && new URLSearchParams(search).get("aba") === "indique"
  return (
    <>
      {aberto && <div className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden" onClick={onFechar} aria-hidden="true" />}
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col justify-between overflow-y-auto bg-brand-900 px-4 py-6 text-slate-300 transition-transform lg:sticky lg:top-0 lg:z-auto lg:translate-x-0 lg:self-start ${
        aberto ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div>
        <div className="mb-5 flex items-center gap-2 px-2">
          <Marca escuro subtitulo="Emissor de notas" />
        </div>

        <div className="mb-5">
          <TrocaEmpresa />
        </div>

        <nav className="flex flex-col gap-1" data-tour="menu">
          {ITENS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onFechar}
              className={({ isActive }) => classeItem(isActive)}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-6 flex flex-col gap-3">
        <div className="border-t border-brand-800 pt-3">
          <Link to="/app/conta" onClick={onFechar} aria-current={naConta && !naIndicacao ? "page" : undefined} className={classeItem(naConta && !naIndicacao)}>
            <UserRound size={18} aria-hidden="true" />
            Minha conta
          </Link>
          <Link
            to="/app/conta?aba=indique"
            onClick={onFechar}
            aria-current={naIndicacao ? "page" : undefined}
            className={`mt-1 flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 ${
              naIndicacao ? "bg-brand-800 text-accent-200" : "text-accent-300 hover:bg-brand-800 hover:text-accent-200"
            }`}
          >
            <Gift size={15} aria-hidden="true" />
            Indique e ganhe desconto
          </Link>
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
      </div>
    </aside>
    </>
  )
}
