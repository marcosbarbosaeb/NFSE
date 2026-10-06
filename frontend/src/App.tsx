import { lazy, Suspense } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { SoNoEmissor } from "./components/layout/SoNoEmissor"
import { ProtectedRoute } from "./components/layout/ProtectedRoute"
import { SoModulo } from "./components/layout/SoModulo"
import { AuthProvider } from "./lib/auth"
import { ehDominioNotas } from "./lib/dominios"
import { ThemeProvider } from "./lib/theme"
import { CadastroPage } from "./pages/CadastroPage"
import { ConfirmarEmailPage } from "./pages/ConfirmarEmailPage"
import { LandingPage } from "./pages/LandingPage"
import { PrivacidadePage, TermosPage } from "./pages/LegalPage"
import { SimulacaoPage } from "./pages/SimulacaoPage"
import { LoginPage } from "./pages/LoginPage"

// Telas do painel carregadas sob demanda (o site institucional e o login
// não baixam o app inteiro).
const AjudaPage = lazy(() => import("./pages/AjudaPage").then((m) => ({ default: m.AjudaPage })))
const CalendarioPage = lazy(() => import("./pages/CalendarioPage").then((m) => ({ default: m.CalendarioPage })))
const ConfiguracoesPage = lazy(() => import("./pages/ConfiguracoesPage").then((m) => ({ default: m.ConfiguracoesPage })))
const ContaPage = lazy(() => import("./pages/ContaPage").then((m) => ({ default: m.ContaPage })))
const EmpresaPage = lazy(() => import("./pages/EmpresaPage").then((m) => ({ default: m.EmpresaPage })))
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })))
const EmissaoDetalhePage = lazy(() => import("./pages/EmissaoDetalhePage").then((m) => ({ default: m.EmissaoDetalhePage })))
const ClientesFinanceiroPage = lazy(() => import("./pages/ClientesFinanceiroPage").then((m) => ({ default: m.ClientesFinanceiroPage })))
const ConciliacaoPage = lazy(() => import("./pages/ConciliacaoPage").then((m) => ({ default: m.ConciliacaoPage })))
const FinanceiroPage = lazy(() => import("./pages/FinanceiroPage").then((m) => ({ default: m.FinanceiroPage })))
const NfsePage = lazy(() => import("./pages/NfsePage").then((m) => ({ default: m.NfsePage })))
const TomadoresPage = lazy(() => import("./pages/TomadoresPage").then((m) => ({ default: m.TomadoresPage })))
const VinculoFormPage = lazy(() => import("./pages/VinculoFormPage").then((m) => ({ default: m.VinculoFormPage })))
// Painel público da parceira de indicação (06/10/2026): sem login, aberto pelo link secreto.
const ParceiraPage = lazy(() => import("./pages/ParceiraPage").then((m) => ({ default: m.ParceiraPage })))

// Marco 15 (item 6): "/" virou a página de marketing pública (ver
// LandingPage.tsx) — o painel autenticado, que antes vivia na raiz,
// mudou pra debaixo de /app (mesmo domínio, ver pedido do Marcos:
// "seudominio.com/ e o painel em /app"). /entrar, /cadastro e
// /confirmar-email continuam fora de /app de propósito — são portas de
// entrada, não fazem parte da área logada.
export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Routes>
          {/* No subdomínio notas.agenteana.com.br a raiz é o próprio emissor
              (a landing mora em agenteana.com.br) — ver lib/dominios.ts. */}
          <Route path="/" element={ehDominioNotas() ? <Navigate to="/app" replace /> : <LandingPage />} />
          <Route path="/privacidade" element={<PrivacidadePage />} />
          <Route path="/termos" element={<TermosPage />} />
          <Route path="/entrar" element={<SoNoEmissor><LoginPage /></SoNoEmissor>} />
          <Route path="/cadastro" element={<SoNoEmissor><CadastroPage /></SoNoEmissor>} />
          <Route path="/simulacao" element={<SoNoEmissor><SimulacaoPage /></SoNoEmissor>} />
          <Route path="/confirmar-email" element={<SoNoEmissor><ConfirmarEmailPage /></SoNoEmissor>} />
          {/* Fora de /app de propósito: a parceira não tem conta. O Suspense é
              próprio porque esta rota não passa pelo AppShell. */}
          <Route
            path="/parceira/:token"
            element={
              <SoNoEmissor>
                <Suspense fallback={<p className="py-16 text-center text-sm text-slate-400">Carregando...</p>}>
                  <ParceiraPage />
                </Suspense>
              </SoNoEmissor>
            }
          />
          <Route
            path="/app"
            element={
              <SoNoEmissor>
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              </SoNoEmissor>
            }
          >
            {/* Visão geral: da empresa, com os cards dos módulos ligados (05/10/2026). */}
            <Route index element={<DashboardPage />} />
            <Route path="nfse" element={<SoModulo modulo="emissor"><NfsePage /></SoModulo>} />
            <Route path="nfse/lote" element={<SoModulo modulo="emissor"><NfsePage modo="lote" /></SoModulo>} />
            <Route path="nfse/:id" element={<SoModulo modulo="emissor"><EmissaoDetalhePage /></SoModulo>} />
            <Route path="tomadores" element={<SoModulo modulo="emissor"><TomadoresPage /></SoModulo>} />
            <Route path="tomadores/novo" element={<SoModulo modulo="emissor"><VinculoFormPage /></SoModulo>} />
            <Route path="tomadores/:id" element={<SoModulo modulo="emissor"><VinculoFormPage /></SoModulo>} />
            <Route path="calendario" element={<SoModulo modulo="emissor"><CalendarioPage /></SoModulo>} />
            {/* Módulo financeiro — produto à parte (05/10/2026). */}
            <Route path="financeiro" element={<SoModulo modulo="financeiro"><FinanceiroPage /></SoModulo>} />
            <Route path="financeiro/conciliacao" element={<SoModulo modulo="financeiro"><ConciliacaoPage /></SoModulo>} />
            <Route path="financeiro/clientes" element={<SoModulo modulo="financeiro"><ClientesFinanceiroPage /></SoModulo>} />
            {/* Recebimentos e Despesas viraram uma aba só (28/09/2026). */}
            <Route path="recebimentos" element={<Navigate to="/app/financeiro" replace />} />
            <Route path="despesas" element={<Navigate to="/app/financeiro?aba=despesas" replace />} />
            {/* Configurações virou duas áreas (29/09/2026): Minha conta e Empresa.
                /configuracoes só redireciona (links antigos, âncoras e volta do Stripe). */}
            <Route path="conta" element={<ContaPage />} />
            <Route path="empresa" element={<EmpresaPage />} />
            <Route path="configuracoes" element={<ConfiguracoesPage />} />
            {/* Ajuda / FAQ (05/10/2026): vale pra qualquer módulo. */}
            <Route path="ajuda" element={<AjudaPage />} />
            <Route path="indique" element={<Navigate to="/app/conta?aba=indique" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  )
}
