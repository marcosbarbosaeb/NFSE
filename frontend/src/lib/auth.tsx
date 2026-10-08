import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { ApiError, EVENTO_SESSAO_EXPIRADA, api } from "./api"
import type { Usuario } from "./types"

interface AuthState {
  usuario: Usuario | null
  carregando: boolean
  login: (email: string, senha: string) => Promise<void>
  /** Login sem senha: código de 6 dígitos mandado por e-mail (POST /auth/codigo antes). */
  entrarComCodigo: (email: string, codigo: string) => Promise<void>
  /** Relê /auth/me (ex.: depois de trocar o nome em Minha conta). */
  recarregarUsuario: () => Promise<void>
  loginComGoogle: () => Promise<void>
  entrarNaSimulacao: (cenario?: string | null) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    // GET /api/auth/me — mesma checagem que o painel antigo fazia em
    // verificarSessao() (app/main.py): se o cookie de sessão ainda for
    // válido, entra direto sem pedir login de novo.
    api
      .get<Usuario>("/auth/me")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false))
  }, [])

  useEffect(() => {
    const expirou = () => setUsuario(null)
    window.addEventListener(EVENTO_SESSAO_EXPIRADA, expirou)
    return () => window.removeEventListener(EVENTO_SESSAO_EXPIRADA, expirou)
  }, [])

  async function login(email: string, senha: string) {
    const dados = await api.post<Usuario>("/auth/login", { email, senha })
    // /auth/me traz a empresa ativa completa (módulos ligados, conta de teste).
    setUsuario(await api.get<Usuario>("/auth/me").catch(() => dados))
  }

  async function entrarComCodigo(email: string, codigo: string) {
    const dados = await api.post<Usuario>("/auth/codigo/entrar", { email, codigo })
    setUsuario(await api.get<Usuario>("/auth/me").catch(() => dados))
  }

  async function recarregarUsuario() {
    try {
      setUsuario(await api.get<Usuario>("/auth/me"))
    } catch {
      /* mantém o que já tinha; o 401 de verdade é tratado pelo evento de sessão expirada */
    }
  }

  // Marco 16, item 1 — login/cadastro via Google (ver app/services/
  // google_oauth.py). Não seta `usuario` aqui: o passo 2 é um redirect de
  // página inteira pra Google (window.location, não fetch — precisa ser
  // navegação de topo pra tela de consentimento aparecer), e a sessão só
  // fica válida depois que a Google volta pro nosso /api/auth/google/callback
  // — a AuthProvider recarrega em /auth/me nesse próximo carregamento de
  // página, do jeito normal.
  async function loginComGoogle() {
    const dados = await api.post<{ url: string }>("/auth/google/iniciar")
    window.location.href = dados.url
  }

  // Ambiente de simulação: cria uma conta descartável com dados de exemplo
  // e já entra nela (ver backend/app/services/demo.py).
  async function entrarNaSimulacao(cenario?: string | null) {
    // cenário = o nicho dos dados de exemplo (backend/app/data/cenarios)
    const dados = await api.post<Usuario>(cenario ? `/demo?cenario=${encodeURIComponent(cenario)}` : "/demo")
    setUsuario(await api.get<Usuario>("/auth/me").catch(() => dados))
  }

  async function logout() {
    await api.post("/auth/logout")
    setUsuario(null)
  }

  return (
    <AuthContext.Provider value={{ usuario, carregando, login, entrarComCodigo, recarregarUsuario, loginComGoogle, entrarNaSimulacao, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>")
  return ctx
}

export { ApiError }
