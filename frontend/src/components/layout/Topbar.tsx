import { Bell, ChevronDown, LogOut, Search } from "lucide-react"
import { useState } from "react"
import { useAuth } from "../../lib/auth"

function iniciais(email: string): string {
  const nome = email.split("@")[0].replace(/[._-]+/g, " ")
  const partes = nome.trim().split(" ").filter(Boolean)
  const letras = partes.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "")
  return letras.join("") || "?"
}

export function Topbar() {
  const { usuario, logout } = useAuth()
  const [menuAberto, setMenuAberto] = useState(false)

  return (
    <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-4">
      <div className="relative w-full max-w-md">
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Pesquisar tomadores, notas, documentos..."
          disabled
          className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-500 placeholder:text-slate-400"
          title="Busca ainda não implementada"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          className="rounded-full p-2 text-slate-500 hover:bg-slate-100"
          title="Notificações (ainda não implementado)"
          disabled
        >
          <Bell size={18} />
        </button>

        {usuario && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuAberto((v) => !v)}
              className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-900 text-xs font-semibold text-white">
                {iniciais(usuario.email)}
              </div>
              <div className="text-left leading-tight">
                <p className="text-sm font-medium text-slate-800">{usuario.email}</p>
                <p className="text-xs text-slate-400">Prestador(a) de serviços</p>
              </div>
              <ChevronDown size={16} className="text-slate-400" />
            </button>
            {menuAberto && (
              <div className="absolute right-0 z-10 mt-2 w-44 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                <button
                  type="button"
                  onClick={() => logout()}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
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
