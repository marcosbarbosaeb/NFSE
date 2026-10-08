import { PastaDoMes } from "../components/pasta/PastaDoMes"

/** Pasta do mês da empresa (08/10/2026): o que o contador precisa todo mês,
 * os arquivos e a conversa com ele. O contador vê a mesma coisa pela ficha
 * da empresa no painel dele (pages/AtendimentosPage.tsx). */
export function PastaPage() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Pasta do mês</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Tudo o que o seu contador precisa em cada mês, num lugar só — e uma conversa pra deixar combinado por escrito.
        </p>
      </div>
      <PastaDoMes base="/pasta" />
    </div>
  )
}
