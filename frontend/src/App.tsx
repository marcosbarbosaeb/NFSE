import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { SoNoEmissor } from "./components/layout/SoNoEmissor"
import { ProtectedRoute } from "./components/layout/ProtectedRoute"
import { AuthProvider } from "./lib/auth"
import { ehDominioNotas } from "./lib/dominios"
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
          {/* No subdomínio notas.agenteana.com.br a raiz é o próprio emissor
              (a landing mora em agenteana.com.br) — ver lib/dominios.ts. */}
          <Route path="/" element={ehDominioNotas() ? <Navigate to="/app" replace /> : <LandingPage />} />
          <Route path="/entrar" element={<SoNoEmissor><LoginPage /></SoNoEmissor>} />
          <Route path="/cadastro" element={<SoNoEmissor><CadastroPage /></SoNoEmissor>} />
          <Route path="/confirmar-email" element={<SoNoEmissor><ConfirmarEmailPage /></SoNoEmissor>} />
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
