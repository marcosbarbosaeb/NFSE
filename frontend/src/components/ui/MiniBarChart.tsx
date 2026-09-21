import type { PontoSerieMensal } from "../../lib/types"
import { formatBRL } from "../../lib/format"
import { formatCompetenciaAbrev } from "../../lib/format"

// Sparkline simples (sem lib de gráfico) pro painel "Recebimentos" — cada
// barra leva um `title` com o valor por extenso pra não depender só da
// altura pra ser lida (inclusive em leitor de tela via `aria-label`).
export function MiniBarChart({ dados }: { dados: PontoSerieMensal[] }) {
  const maximo = Math.max(1, ...dados.map((d) => d.valor))

  return (
    <div className="flex h-24 items-end gap-2">
      {dados.map((ponto) => {
        const alturaPct = Math.max(4, (ponto.valor / maximo) * 100)
        const ehUltimo = ponto === dados[dados.length - 1]
        return (
          <div
            key={ponto.competencia}
            className="flex flex-1 flex-col items-center gap-1"
            title={`${formatCompetenciaAbrev(ponto.competencia)}: ${formatBRL(ponto.valor)}`}
            aria-label={`${formatCompetenciaAbrev(ponto.competencia)}: ${formatBRL(ponto.valor)}`}
          >
            <div
              className={`w-full rounded-t-sm ${ehUltimo ? "bg-success-600" : "bg-success-600/30"}`}
              style={{ height: `${alturaPct}%` }}
            />
            <span className="text-[10px] text-slate-400">{formatCompetenciaAbrev(ponto.competencia)}</span>
          </div>
        )
      })}
    </div>
  )
}
