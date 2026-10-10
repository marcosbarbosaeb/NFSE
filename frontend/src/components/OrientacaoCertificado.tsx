import { MessageCircle, ShieldCheck } from "lucide-react"
import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { CanaisSuporte } from "../lib/types"
import { BotaoSuporte } from "./SuporteModal"

// Orientação de compra do certificado (2026.10.7, item C do roteiro): "Ainda
// não tem certificado digital? Fale com a gente: nosso parceiro tem preço
// especial", com o contato de suporte que já existe. O texto e o WhatsApp vêm
// do servidor (CERTIFICADO_ORIENTACAO / CERTIFICADO_ORIENTACAO_WHATSAPP) pra
// trocar sem publicar versão. Sem texto configurado, o quadro não aparece.

let cache: Promise<CanaisSuporte | null> | null = null
function canais(): Promise<CanaisSuporte | null> {
  cache ??= api.get<CanaisSuporte>("/suporte").catch(() => {
    cache = null
    return null
  })
  return cache
}

const LINK = "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"

export function OrientacaoCertificado({ className = "" }: { className?: string }) {
  const [dados, setDados] = useState<CanaisSuporte | null>(null)
  useEffect(() => {
    let vivo = true
    canais().then((c) => vivo && setDados(c))
    return () => {
      vivo = false
    }
  }, [])
  const texto = dados?.certificado_texto
  if (!texto) return null
  const whatsapp = dados?.certificado_whatsapp
    ? `https://wa.me/${dados.certificado_whatsapp}?text=${encodeURIComponent("Olá! Quero saber do certificado digital com preço especial.")}`
    : null
  return (
    <div className={`flex flex-col gap-2 rounded-lg border border-primary-100 bg-primary-50/60 px-3 py-2.5 text-sm text-slate-700 dark:border-primary-800 dark:bg-primary-900/20 dark:text-slate-200 sm:flex-row sm:items-center sm:justify-between ${className}`}>
      <p className="flex items-start gap-2">
        <ShieldCheck size={16} aria-hidden="true" className="mt-0.5 shrink-0 text-primary-600 dark:text-primary-300" />
        <span>{texto}</span>
      </p>
      <div className="flex shrink-0 flex-wrap gap-2">
        {whatsapp && (
          <a href={whatsapp} target="_blank" rel="noreferrer" className={`${LINK} bg-success-600 text-white hover:bg-success-700`}>
            <MessageCircle size={14} aria-hidden="true" /> WhatsApp
            <span className="sr-only"> (abre em outra aba)</span>
          </a>
        )}
        <BotaoSuporte logado inicio="equipe" className={`${LINK} border border-primary-300 text-primary-700 hover:bg-primary-50 dark:border-primary-700 dark:text-primary-200 dark:hover:bg-primary-900/40`}>
          Falar com a gente
        </BotaoSuporte>
      </div>
    </div>
  )
}
