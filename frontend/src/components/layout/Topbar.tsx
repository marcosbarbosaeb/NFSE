import { Bell, Building2, ChevronDown, CircleHelp, Gift, LogOut, Menu, Search, UserRound } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../../lib/auth"
import { mostrarDicasDaTela } from "../../lib/tutorial"

function iniciais(email: string, nomeCompleto?: string | null): string {
  const nome = nomeCompleto?.trim() || email.split("@")[0].replace(/[._-]+/g, " ")
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  const letras = partes.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "")
  return letras.join("") || "?"
}

export function Topbar({ onAbrirMenu }: { onAbrirMenu?: () => void }) {
  const { usuario, logout } = useAuth()
  const [menuAberto, setMenuAberto] = useState(false)
  const refMenu = useRef<HTMLDivElement>(null)

  // Menu do usuário fecha ao clicar fora ou apertar Esc.
  useEffect(() => {
    if (!menuAberto) return
    const fora = (e: MouseEvent) => refMenu.current && !refMenu.current.contains(e.target as Node) && setMenuAberto(false)
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setMenuAberto(false)
    document.addEventListener("mousedown", fora)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", fora)
      document.removeEventListener("keydown", esc)
    }
  }, [menuAberto])

  return (
    <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-800 sm:px-6 lg:px-8 lg:py-4">
      <button
        type="button"
        onClick={onAbrirMenu}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700 lg:hidden"
        aria-label="Abrir o menu"
      >
        <Menu size={20} />
      </button>
      <div className="relative hidden w-full max-w-md md:block">
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
        <input
          type="text"
          placeholder="Pesquisar tomadores, notas, documentos..."
          disabled
          className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 py-2 pl-9 pr-3 text-sm text-slate-500 dark:text-slate-400 placeholder:text-slate-400"
          title="Busca ainda não implementada"
        />
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <button
          type="button"
          onClick={mostrarDicasDaTela}
          data-tour="ajuda"
          className="rounded-full p-2 text-slate-500 hover:bg-slate-100 hover:text-accent-600 dark:text-slate-400 dark:hover:bg-slate-700"
          title="Ver as dicas desta tela"
          aria-label="Ver as dicas desta tela"
        >
          <CircleHelp size={18} />
        </button>
        <button
          type="button"
          className="rounded-full p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          title="Notificações (ainda não implementado)"
          disabled
        >
          <Bell size={18} />
        </button>

        {usuario && (
          <div className="relative" ref={refMenu}>
            <button
              type="button"
              onClick={() => setMenuAberto((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuAberto}
              className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-900 text-xs font-semibold text-white" aria-hidden="true">
                {usuario.demo ? "V" : iniciais(usuario.email, usuario.nome)}
              </div>
              <div className="hidden max-w-[14rem] text-left leading-tight sm:block">
                <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
                  {usuario.demo ? "Visitante" : usuario.nome?.trim() ? `Olá, ${usuario.nome.trim().split(/\s+/)[0]}` : usuario.email}
                </p>
                <p className="truncate text-xs text-slate-400 dark:text-slate-500">
                  {usuario.demo ? "Conta de simulação" : usuario.nome?.trim() ? usuario.email : "Prestador(a) de serviços"}
                </p>
              </div>
              <span className="sr-only">Menu da conta</span>
              <ChevronDown size={16} className="text-slate-400 dark:text-slate-500" />
            </button>
            {menuAberto && (
              <div className="absolute right-0 z-10 mt-2 w-60 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800">
                <div className="border-b border-slate-100 px-3 pb-2 pt-1.5 dark:border-slate-700 sm:hidden">
                  <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
                    {usuario.demo ? "Visitante" : usuario.nome?.trim() || usuario.email}
                  </p>
                  {!usuario.demo && usuario.nome?.trim() && <p className="truncate text-xs text-slate-400">{usuario.email}</p>}
                </div>
                {[
                  { to: "/app/conta", rotulo: "Minha conta", Icone: UserRound },
                  { to: "/app/empresa", rotulo: "Dados da empresa", Icone: Building2 },
                  { to: "/app/conta?aba=indique", rotulo: "Indique e ganhe", Icone: Gift },
                ].map(({ to, rotulo, Icone }) => (
                  <Link
                    key={to}
                    to={to}
                    onClick={() => setMenuAberto(false)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700/50"
                  >
                    <Icone size={15} aria-hidden="true" />
                    {rotulo}
                  </Link>
                ))}
                <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
                <button
                  type="button"
                  onClick={() => logout()}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                >
                  <LogOut size={15} />
                  Sair
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
