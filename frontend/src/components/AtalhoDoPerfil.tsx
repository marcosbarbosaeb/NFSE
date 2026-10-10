import { ArrowRight, Zap } from "lucide-react"
import { Link } from "react-router-dom"
import { useAuth } from "../lib/auth"

// Perfis (2026.10.7): na tela inicial, o atalho em destaque é o do perfil
// principal da empresa — sempre pra uma tela que já existe (envio do relatório
// da Shopee pra quem emite "muitas notas de uma vez"; nova nota pros demais).

export function AtalhoDoPerfil() {
  const { usuario } = useAuth()
  const atalho = usuario?.perfil_principal?.atalho
  if (!atalho || usuario?.papel === "contador") return null
  return (
    <Link
      to={atalho.link}
      data-tour="atalho-perfil"
      className="flex items-center justify-between gap-3 rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-3 text-sm font-semibold text-primary-800 transition-colors hover:bg-primary-100 dark:border-primary-800 dark:bg-primary-900/20 dark:text-primary-200 dark:hover:bg-primary-900/40"
    >
      <span className="flex items-center gap-2">
        <Zap size={16} aria-hidden="true" /> {atalho.rotulo}
      </span>
      <ArrowRight size={16} aria-hidden="true" />
    </Link>
  )
}
