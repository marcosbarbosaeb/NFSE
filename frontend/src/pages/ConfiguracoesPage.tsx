import { Navigate, useLocation } from "react-router-dom"

// A antiga tela única de Configurações (até 28/09/2026) foi dividida em
// "Minha conta" (/app/conta — perfil, acesso, preferências, assinatura,
// indicações) e "Empresa" (/app/empresa — emitente, e-mails, alíquota,
// ambiente, certificado, limpar/excluir). Este componente só mantém os
// links antigos funcionando:
//   /app/configuracoes#aliquota            → /app/empresa?aba=aliquotas#aliquota
//   /app/configuracoes?assinatura=sucesso  → /app/conta?aba=assinatura&assinatura=sucesso (volta do Stripe)
//   /app/configuracoes                     → /app/empresa

const ABA_DA_ANCORA: Record<string, string> = {
  certificado: "certificado",
  aliquota: "aliquotas",
  ambiente: "notas",
  "email-nota": "emails",
}

export function ConfiguracoesPage() {
  const { search, hash } = useLocation()
  const params = new URLSearchParams(search)

  const retornoStripe = params.get("assinatura")
  if (retornoStripe) {
    return <Navigate to={`/app/conta?aba=assinatura&assinatura=${encodeURIComponent(retornoStripe)}`} replace />
  }

  const ancora = hash.slice(1)
  const aba = ABA_DA_ANCORA[ancora]
  if (aba) return <Navigate to={`/app/empresa?aba=${aba}#${ancora}`} replace />

  return <Navigate to="/app/empresa" replace />
}
