import { Construction } from "lucide-react"

export function PlaceholderPage({ titulo }: { titulo: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-white/60 py-24 text-center">
      <Construction size={28} className="text-slate-400" />
      <h1 className="text-lg font-semibold text-slate-700">{titulo}</h1>
      <p className="max-w-sm text-sm text-slate-500">
        Essa tela ainda não foi construída nesta fase — é uma das próximas etapas do plano combinado com o Marcos.
      </p>
    </div>
  )
}
