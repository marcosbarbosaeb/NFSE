import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

export type Tema = "claro" | "escuro"

const CHAVE_LOCALSTORAGE = "notafacil.tema"

interface ThemeState {
  tema: Tema
  definirTema: (tema: Tema) => void
  alternarTema: () => void
}

const ThemeContext = createContext<ThemeState | null>(null)

function lerTemaInicial(): Tema {
  try {
    const salvo = localStorage.getItem(CHAVE_LOCALSTORAGE)
    if (salvo === "claro" || salvo === "escuro") return salvo
  } catch {
    // localStorage pode não estar disponível (modo privado, storage bloqueado) — cai no default abaixo.
  }
  const prefereEscuro = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
  return prefereEscuro ? "escuro" : "claro"
}

function aplicarClasseNoHtml(tema: Tema) {
  document.documentElement.classList.toggle("dark", tema === "escuro")
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(lerTemaInicial)

  useEffect(() => {
    aplicarClasseNoHtml(tema)
    try {
      localStorage.setItem(CHAVE_LOCALSTORAGE, tema)
    } catch {
      // per-viewer apenas — se não der pra persistir, o tema ainda funciona nesta sessão.
    }
  }, [tema])

  function definirTema(novo: Tema) {
    setTema(novo)
  }

  function alternarTema() {
    setTema((t) => (t === "claro" ? "escuro" : "claro"))
  }

  return <ThemeContext.Provider value={{ tema, definirTema, alternarTema }}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme precisa estar dentro de <ThemeProvider>")
  return ctx
}
