import { DownloadCloud, UserPlus } from "lucide-react"
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import type { VinculoResumo } from "../lib/types"
import { ImportarEmissorModal } from "./ImportarEmissorModal"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"

// Empresa que ainda não tem tomador nem nota (05/10/2026): o jeito mais fácil
// de começar é trazer tudo do Emissor Nacional com o certificado — "Já emite
// pelo Emissor Nacional? Eu trago seus tomadores e notas". Aparece na Visão
// geral e em Empresa › Notas; some sozinho depois do primeiro tomador.

export const CHAMADA_NACIONAL = "Já emite pelo Emissor Nacional? Eu trago seus tomadores e notas"

/** true = a empresa aberta não tem nenhum tomador (logo, nenhuma nota).
 * null enquanto carrega ou se a consulta falhar — aí ninguém mostra nada. */
export function useEmpresaVazia(): boolean | null {
  const { usuario } = useAuth()
  const [vazia, setVazia] = useState<boolean | null>(null)
  const pular = !usuario || Boolean(usuario.demo)
  useEffect(() => {
    if (pular) return
    let cancelado = false
    api
      .get<VinculoResumo[]>("/vinculos?todos=true")
      .then((v) => !cancelado && setVazia(v.length === 0))
      .catch(() => !cancelado && setVazia(null))
    return () => {
      cancelado = true
    }
  }, [pular])
  return pular ? null : vazia
}

/** Cartão de começo da Visão geral. Não ocupa espaço quando a empresa já tem dados. */
export function ComecarPeloNacional() {
  const vazia = useEmpresaVazia()
  const [aberto, setAberto] = useState(false)
  if (!vazia) return null
  return (
    <Card className="border-primary-200 bg-primary-50/60 p-5 dark:border-primary-800 dark:bg-primary-900/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-600 text-white">
          <DownloadCloud size={22} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{CHAMADA_NACIONAL}</h2>
          <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
            É o jeito mais fácil de começar: você escolhe o certificado digital (A1) da empresa e eu cadastro os tomadores com as notas que
            ela já emitiu. É só leitura — nada é enviado a ninguém.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <Button type="button" variant="accent" onClick={() => setAberto(true)}>
            <DownloadCloud size={16} /> Trazer do Emissor Nacional
          </Button>
          <Link
            to="/app/tomadores/novo"
            className="inline-flex items-center justify-center gap-1.5 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300"
          >
            <UserPlus size={14} aria-hidden="true" /> Prefiro cadastrar um tomador
          </Link>
        </div>
      </div>
      {aberto && <ImportarEmissorModal modo="atual" onFechar={() => setAberto(false)} />}
    </Card>
  )
}
