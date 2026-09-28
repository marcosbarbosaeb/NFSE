import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'

// Depois de um deploy novo, uma aba aberta pode pedir um pedaço do app que
// não existe mais: recarrega a página (uma vez) em vez de quebrar a tela.
window.addEventListener('vite:preloadError', (evento) => {
  evento.preventDefault()
  try {
    if (sessionStorage.getItem('agenteana.recarregou') === location.pathname) return
    sessionStorage.setItem('agenteana.recarregou', location.pathname)
  } catch {
    // sem sessionStorage: recarrega mesmo assim
  }
  location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
