import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy /api pro backend FastAPI (porta 8000 por padrão em dev) — assim o
// navegador só fala com a origem do Vite, e o cookie de sessão (assinado
// via SessionMiddleware, same_site="lax") viaja como se fosse same-origin.
// Sem isso, frontend (5173) e backend (8000) seriam origens diferentes e o
// cookie de login não voltaria nas próximas chamadas.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
