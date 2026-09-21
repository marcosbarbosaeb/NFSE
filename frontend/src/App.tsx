import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { ProtectedRoute } from "./components/layout/ProtectedRoute"
import { AuthProvider } from "./lib/auth"
import { ThemeProvider } from "./lib/theme"
import { CadastroPage } from "./pages/CadastroPage"
import { CalendarioPage } from "./pages/CalendarioPage"
import { ConfiguracoesPage } from "./pages/ConfiguracoesPage"
import { ConfirmarEmailPage } from "./pages/ConfirmarEmailPage"
import { DashboardPage } from "./pages/DashboardPage"
import { DespesasPage } from "./pages/DespesasPage"
import { EmissaoDetalhePage } from "./pages/EmissaoDetalhePage"
import { LandingPage } from "./pages/LandingPage"
import { LoginPage } from "./pages/LoginPage"
import { NfsePage } from "./pages/NfsePage"
import { RecebimentosPage } from "./pages/RecebimentosPage"
import { TomadoresPage } from "./pages/TomadoresPage"
import { VinculoFormPage } from "./pages/VinculoFormPage"

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
          <Route path="/" element={<LandingPage />} />
          <Route path="/entrar" element={<LoginPage />} />
          <Route path="/cadastro" element={<CadastroPage />} />
          <Route path="/confirmar-email" element={<ConfirmarEmailPage />} />
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="nfse" element={<NfsePage />} />
            <Route path="nfse/:id" element={<EmissaoDetalhePage />} />
            <Route path="tomadores" element={<TomadoresPage />} />
            <Route path="tomadores/novo" element={<VinculoFormPage />} />
            <Route path="tomadores/:id" element={<VinculoFormPage />} />
            <Route path="calendario" element={<CalendarioPage />} />
            <Route path="recebimentos" element={<RecebimentosPage />} />
            <Route path="despesas" element={<DespesasPage />} />
            <Route path="configuracoes" element={<ConfiguracoesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  )
}
