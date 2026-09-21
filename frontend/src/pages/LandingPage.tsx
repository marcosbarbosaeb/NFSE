import { CalendarDays, FileText, Landmark, ShieldCheck, Users, Wallet } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { useAuth } from "../lib/auth"

const RECURSOS = [
  {
    icon: FileText,
    titulo: "Emissão de NFS-e sem retrabalho",
    descricao: "Cadastre o vínculo com cada tomador uma vez só — descrição, tributação e série ficam salvos pra próxima nota sair em segundos.",
  },
  {
    icon: Users,
    titulo: "Fornecedores e tomadores organizados",
    descricao: "Um catálogo só, com apelido, CNPJ e endereço reaproveitados em toda emissão — sem digitar os mesmos dados todo mês.",
  },
  {
    icon: CalendarDays,
    titulo: "Calendário de prazos e recebimentos",
    descricao: "Prazo de emissão, previsão e confirmação de recebimento num só lugar — nada de planilha pra lembrar o que vence quando.",
  },
  {
    icon: Wallet,
    titulo: "Recebimentos com extrato automático",
    descricao: "Suba o PDF do extrato bancário e a gente reconhece as transações pra você só revisar e casar com o fornecedor certo.",
  },
]

export function LandingPage() {
  const { usuario, carregando } = useAuth()

  return (
    <div className="min-h-screen bg-canvas dark:bg-canvas-dark">
      <header className="border-b border-slate-100 dark:border-slate-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white">
              <FileText size={18} />
            </div>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Nota<span className="text-primary-600">Fácil</span>
            </p>
          </div>

          <nav className="flex items-center gap-3">
            {!carregando && usuario ? (
              <Link to="/app">
                <Button variant="accent">Ir para o painel</Button>
              </Link>
            ) : (
              <>
                <Link to="/entrar" className="text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-primary-600">
                  Entrar
                </Link>
                <Link to="/cadastro">
                  <Button variant="accent">Criar conta grátis</Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-4xl px-6 pb-16 pt-20 text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-5xl">
            NFS-e sem complicação
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600 dark:text-slate-300">
            Cadastre seus tomadores uma vez, emita nota em segundos e acompanhe prazos e recebimentos num painel só —
            sem planilha, sem digitar os mesmos dados todo mês.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to="/cadastro">
              <Button variant="accent" className="px-6 py-3 text-base">
                Criar conta grátis
              </Button>
            </Link>
            <Link to="/entrar" className="text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-primary-600">
              Já tem conta? Entrar
            </Link>
          </div>
          <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
            Teste grátis por 14 dias — sem precisar de cartão pra começar.
          </p>
        </section>

        <section className="border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900/40">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid grid-cols-1 gap-8 sm:grid-cols-2">
              {RECURSOS.map(({ icon: Icon, titulo, descricao }) => (
                <div key={titulo} className="flex gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{titulo}</h3>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{descricao}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-6 py-16 text-center">
          <div className="mb-4 flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400">
            <ShieldCheck size={18} />
            <span className="text-sm">Seus dados ficam isolados por conta — cada empresa só enxerga o que é seu.</span>
          </div>
          <div className="mb-8 flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400">
            <Landmark size={18} />
            <span className="text-sm">Cobrança recorrente simples, sem contrato de fidelidade.</span>
          </div>
          <Link to="/cadastro">
            <Button variant="accent" className="px-6 py-3 text-base">
              Começar agora
            </Button>
          </Link>
        </section>
      </main>

      <footer className="border-t border-slate-100 dark:border-slate-800 px-6 py-8 text-center text-xs text-slate-400 dark:text-slate-500">
        NotaFácil — NFS-e sem complicação.
      </footer>
    </div>
  )
}
