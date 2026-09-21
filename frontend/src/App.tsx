import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { ProtectedRoute } from "./components/layout/ProtectedRoute"
import { AuthProvider } from "./lib/auth"
import { ThemeProvider } from "./lib/theme"
import { CalendarioPage } from "./pages/CalendarioPage"
import { ConfiguracoesPage } from "./pages/ConfiguracoesPage"
import { DashboardPage } from "./pages/DashboardPage"
import { DespesasPage } from "./pages/DespesasPage"
import { EmissaoDetalhePage } from "./pages/EmissaoDetalhePage"
import { LoginPage } from "./pages/LoginPage"
import { NfsePage } from "./pages/NfsePage"
import { RecebimentosPage } from "./pages/RecebimentosPage"
import { TomadoresPage } from "./pages/TomadoresPage"
import { VinculoFormPage } from "./pages/VinculoFormPage"

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Routes>
          <Route path="/entrar" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/nfse" element={<NfsePage />} />
            <Route path="/nfse/:id" element={<EmissaoDetalhePage />} />
            <Route path="/tomadores" element={<TomadoresPage />} />
            <Route path="/tomadores/novo" element={<VinculoFormPage />} />
            <Route path="/tomadores/:id" element={<VinculoFormPage />} />
            <Route path="/calendario" element={<CalendarioPage />} />
            <Route path="/recebimentos" element={<RecebimentosPage />} />
            <Route path="/despesas" element={<DespesasPage />} />
            <Route path="/configuracoes" element={<ConfiguracoesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  )
}
