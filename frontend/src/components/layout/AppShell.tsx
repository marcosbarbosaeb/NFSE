import { PerguntaPerfil } from "../PerguntaPerfil"
import { FlaskConical, LogOut, ShieldCheck } from "lucide-react"
import { ehDominioGestao } from "../../lib/dominios"
import { Suspense, useState } from "react"
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../../lib/auth"
import { PasseioNovidades } from "../tour/PasseioNovidades"
import { TourDaPagina } from "../tour/Tour"
import { useModoGravacao } from "../../lib/gravacao"
import { useRegistrarTela } from "../../lib/uso"
import { AvisoSemAssinatura, FaixaAssinatura, FaixaContador, FaixaUsoDoPlano } from "./FaixasAcesso"
import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

// Faixa do ambiente de simulação (ver backend/app/services/demo.py).
function FaixaSimulacao() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()
  const gravacao = useModoGravacao()
  if (!usuario?.demo || gravacao) return null
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

// Conta só de contador (07/10/2026): fora da empresa de um cliente não há
// notas nem financeiro — só estas telas existem pra ela.
const TELAS_DA_CONTA_DE_CONTADOR = ["/app/atendimentos", "/app/conta", "/app/ajuda", "/app/novidades", "/app/gestao"]

// Gestão num endereço próprio (2026.10.7, gestao.agenteana.com.br): só a
// Gestão, sem menu do emissor, faixas, passeios ou perguntas. Qualquer outra
// tela volta pra /app/gestao (o servidor faz o mesmo nos acessos diretos).
function GestaoShell() {
  const { usuario, logout } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  if (!pathname.startsWith("/app/gestao")) return <Navigate to="/app/gestao" replace />
  return (
    <div className="flex min-h-screen flex-col bg-canvas dark:bg-canvas-dark">
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-800 sm:px-6 lg:px-8">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
          <ShieldCheck size={18} className="text-primary-600 dark:text-primary-300" aria-hidden="true" />
          Gestão · Agente Ana
        </p>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-slate-500 dark:text-slate-400 sm:inline">{usuario?.email}</span>
          <button
            type="button"
            onClick={async () => {
              await logout()
              navigate("/entrar")
            }}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            <LogOut size={16} aria-hidden="true" /> Sair
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <Suspense fallback={<p className="py-10 text-center text-sm text-slate-400">Carregando...</p>}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}

export function AppShell() {
  if (ehDominioGestao()) return <GestaoShell />
  return <AppShellDoEmissor />
}

function AppShellDoEmissor() {
  const [menuAberto, setMenuAberto] = useState(false)
  const { usuario } = useAuth()
  const { pathname } = useLocation()
  useModoGravacao() // liga/desliga as dicas antes das telas abrirem
  useRegistrarTela()
  if (usuario?.so_contador && !TELAS_DA_CONTA_DE_CONTADOR.some((t) => pathname === t || pathname.startsWith(t + "/"))) {
    return <Navigate to="/app/atendimentos" replace />
  }
  return (
    <div className="flex min-h-screen bg-canvas dark:bg-canvas-dark">
      <Sidebar aberto={menuAberto} onFechar={() => setMenuAberto(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <FaixaSimulacao />
        <FaixaContaTeste />
        <FaixaContador />
        <FaixaAssinatura />
        <FaixaUsoDoPlano />
        <Topbar onAbrirMenu={() => setMenuAberto(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Suspense fallback={<p className="py-10 text-center text-sm text-slate-400">Carregando...</p>}>
            <Outlet />
          </Suspense>
        </main>
        <TourDaPagina />
        <PasseioNovidades />
        <PerguntaPerfil />
        <AvisoSemAssinatura />
      </div>
    </div>
  )
}
