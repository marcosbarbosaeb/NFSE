import { FlaskConical } from "lucide-react"
import { Suspense, useState } from "react"
import { Outlet, useNavigate } from "react-router-dom"
import { useAuth } from "../../lib/auth"
import { TourDaPagina } from "../tour/Tour"
import { AvisoSemAssinatura, FaixaAssinatura, FaixaContador } from "./FaixasAcesso"
import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

// Faixa do ambiente de simulação (ver backend/app/services/demo.py).
function FaixaSimulacao() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()
  if (!usuario?.demo) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-gradient-to-r from-accent-500 to-primary-600 px-4 py-2 text-center text-sm text-white">
      <span className="flex items-center gap-1.5 font-semibold">
        <FlaskConical size={15} /> Modo simulação
      </span>
      <span className="text-white/90">Dados de exemplo — nada é enviado à Receita nem a ninguém. Fique à vontade pra mexer.</span>
      <button
        type="button"
        onClick={async () => {
          await logout()
          navigate("/cadastro")
        }}
        className="rounded-full bg-white/95 px-3 py-0.5 text-xs font-semibold text-accent-700 hover:bg-white"
      >
        Criar minha conta grátis
      </button>
    </div>
  )
}

// Conta de teste (01/10/2026): fluxo de usuário novo, notas só em homologação.
function FaixaContaTeste() {
  const { usuario } = useAuth()
  if (!usuario?.teste || usuario.demo) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-warning-600 px-4 py-2 text-center text-sm text-white">
      <span className="flex items-center gap-1.5 font-semibold">
        <FlaskConical size={15} /> Conta de teste
      </span>
      <span className="text-white/95">
        As notas saem só em homologação (sem valor fiscal) e os e-mails de nota vão só pro seu e-mail.
      </span>
    </div>
  )
}

export function AppShell() {
  const [menuAberto, setMenuAberto] = useState(false)
  return (
    <div className="flex min-h-screen bg-canvas dark:bg-canvas-dark">
      <Sidebar aberto={menuAberto} onFechar={() => setMenuAberto(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <FaixaSimulacao />
        <FaixaContaTeste />
        <FaixaContador />
        <FaixaAssinatura />
        <Topbar onAbrirMenu={() => setMenuAberto(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Suspense fallback={<p className="py-10 text-center text-sm text-slate-400">Carregando...</p>}>
            <Outlet />
          </Suspense>
        </main>
        <TourDaPagina />
        <AvisoSemAssinatura />
      </div>
    </div>
  )
}
