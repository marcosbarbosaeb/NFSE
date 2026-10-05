import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react"
import { Link } from "react-router-dom"
import type { PontoConferencia } from "../lib/types"

// Conferência (05/10/2026): "controles para que o cadastro dos tomadores e a
// NF não saiam erradas". Mostra o que a Ana achou — vermelho o que precisa
// ser corrigido (a nota sairia errada), amarelo o que é só pra conferir —
// sempre com o jeito de consertar e, quando dá, o atalho pra tela certa.

const ABA_DA_EMPRESA: Record<string, { aba: string; rotulo: string }> = {
  certificado: { aba: "certificado", rotulo: "Abrir Empresa › Certificado" },
  aliquota: { aba: "aliquotas", rotulo: "Abrir Empresa › Alíquotas" },
  ambiente: { aba: "notas", rotulo: "Abrir Empresa › Notas" },
}

function atalho(ponto: PontoConferencia, vinculoId?: string | null): { para: string; rotulo: string } | null {
  if (ponto.onde === "tomador" && vinculoId) {
    // Nome e endereço têm edição própria na ficha ("Dados do tomador").
    const doEndereco = ["cep", "endereco", "cod_municipio", "razao_social"].includes(ponto.campo ?? "")
    return doEndereco
      ? { para: `/app/tomadores/${vinculoId}?editar=endereco`, rotulo: "Corrigir os dados do tomador" }
      : { para: `/app/tomadores/${vinculoId}`, rotulo: "Abrir o cadastro do tomador" }
  }
  if (ponto.onde === "empresa") {
    const destino = ABA_DA_EMPRESA[ponto.campo ?? ""]
    return destino ? { para: `/app/empresa?aba=${destino.aba}`, rotulo: destino.rotulo } : { para: "/app/empresa", rotulo: "Abrir Empresa" }
  }
  return null
}

export function contarPontos(pontos: PontoConferencia[] | null | undefined): { erros: number; avisos: number } {
  const erros = (pontos ?? []).filter((p) => p.nivel === "erro").length
  return { erros, avisos: (pontos ?? []).length - erros }
}

export function Conferencia({
  pontos,
  vinculoId,
  semAtalhoDoTomador = false,
  esconderSeTudoCerto = false,
  className = "",
}: {
  /** `null` = ainda conferindo. */
  pontos: PontoConferencia[] | null
  /** Tomador dos pontos — vira o atalho "Abrir o cadastro do tomador". */
  vinculoId?: string | null
  /** Na própria tela do tomador o atalho pra ela não faz sentido. */
  semAtalhoDoTomador?: boolean
  esconderSeTudoCerto?: boolean
  className?: string
}) {
  if (pontos === null) {
    return <p className={`text-xs text-slate-400 dark:text-slate-500 ${className}`}>Conferindo os dados...</p>
  }
  if (pontos.length === 0) {
    if (esconderSeTudoCerto) return null
    return (
      <p
        className={`flex items-center gap-2 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300 ${className}`}
      >
        <CheckCircle2 size={16} className="shrink-0" aria-hidden /> Conferi os dados: tudo certo.
      </p>
    )
  }
  const { erros, avisos } = contarPontos(pontos)
  // O que trava vem primeiro.
  const ordenados = [...pontos].sort((a, b) => (a.nivel === b.nivel ? 0 : a.nivel === "erro" ? -1 : 1))
  return (
    <div className={`flex flex-col gap-2 ${className}`} aria-live="polite">
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
        Conferi os dados e achei{" "}
        {[
          erros > 0 ? `${erros} ${erros === 1 ? "ponto que precisa ser corrigido" : "pontos que precisam ser corrigidos"}` : null,
          avisos > 0 ? `${avisos} ${avisos === 1 ? "ponto pra você conferir" : "pontos pra você conferir"}` : null,
        ]
          .filter(Boolean)
          .join(" e ")}
        :
      </p>
      <ul className="flex flex-col gap-2">
        {ordenados.map((ponto, i) => {
          const erro = ponto.nivel === "erro"
          const link = ponto.onde === "tomador" && semAtalhoDoTomador ? null : atalho(ponto, vinculoId)
          return (
            <li
              key={`${ponto.codigo}-${i}`}
              className={`flex gap-2.5 rounded-lg border px-3 py-2.5 text-sm ${
                erro
                  ? "border-danger-100 bg-danger-50 text-danger-700 dark:border-danger-900/60 dark:bg-danger-900/20 dark:text-danger-300"
                  : "border-warning-100 bg-warning-50 text-warning-700 dark:border-warning-900/60 dark:bg-warning-900/20 dark:text-warning-300"
              }`}
            >
              {erro ? <XCircle size={16} className="mt-0.5 shrink-0" aria-hidden /> : <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />}
              <div className="min-w-0 flex-1">
                <p className="break-words font-medium">
                  <span className="sr-only">{erro ? "Precisa corrigir: " : "Confira: "}</span>
                  {ponto.mensagem}
                </p>
                {ponto.como_corrigir && (
                  <p className="mt-0.5 break-words text-slate-700 dark:text-slate-300">
                    <span className="font-medium">Como resolver:</span> {ponto.como_corrigir}
                  </p>
                )}
                {link && (
                  <Link to={link.para} className="mt-1 inline-block font-semibold underline underline-offset-2">
                    {link.rotulo}
                  </Link>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
