import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { ApiError, api } from "./api"
import type { Usuario } from "./types"

interface AuthState {
  usuario: Usuario | null
  carregando: boolean
  login: (email: string, senha: string) => Promise<void>
  loginComGoogle: () => Promise<void>
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

  async function login(email: string, senha: string) {
    const dados = await api.post<Usuario>("/auth/login", { email, senha })
    setUsuario(dados)
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

  async function logout() {
    await api.post("/auth/logout")
    setUsuario(null)
  }

  return (
    <AuthContext.Provider value={{ usuario, carregando, login, loginComGoogle, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>")
  return ctx
}

export { ApiError }
