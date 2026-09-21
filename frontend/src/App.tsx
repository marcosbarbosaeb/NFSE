import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { ProtectedRoute } from "./components/layout/ProtectedRoute"
import { AuthProvider } from "./lib/auth"
import { CalendarioPage } from "./pages/CalendarioPage"
import { DashboardPage } from "./pages/DashboardPage"
import { LoginPage } from "./pages/LoginPage"
import { PlaceholderPage } from "./pages/PlaceholderPage"
import { TomadoresPage } from "./pages/TomadoresPage"
import { VinculoFormPage } from "./pages/VinculoFormPage"

export default function App() {
  return (
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
          <Route path="/nfse" element={<PlaceholderPage titulo="NFS-e" />} />
          <Route path="/tomadores" element={<TomadoresPage />} />
          <Route path="/tomadores/novo" element={<VinculoFormPage />} />
          <Route path="/tomadores/:id" element={<VinculoFormPage />} />
          <Route path="/calendario" element={<CalendarioPage />} />
          <Route path="/recebimentos" element={<PlaceholderPage titulo="Recebimentos" />} />
          <Route path="/despesas" element={<PlaceholderPage titulo="Despesas" />} />
          <Route path="/configuracoes" element={<PlaceholderPage titulo="Configurações" />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
