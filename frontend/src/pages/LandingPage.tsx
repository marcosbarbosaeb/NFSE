import {
  ArrowRight,
  BellRing,
  CalendarDays,
  Check,
  ChevronDown,
  FileCheck2,
  FileText,
  Megaphone,
  ShieldCheck,
  Sparkles,
  Store,
  Users,
  Wallet,
} from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { AnaAvatar, Marca } from "../components/brand/Marca"
import { useAuth } from "../lib/auth"
import { BotaoSuporte } from "../components/SuporteModal"
import { EMAIL_SUPORTE } from "../lib/contato"
import { ehDominioRaiz, urlEmissor } from "../lib/dominios"

// Landing única da Agente Ana (agenteana.com.br). Hoje só o emissor de
// notas está no ar — os outros produtos do ecossistema entram depois, então
// aqui só fica uma "deixa" de que vem mais coisa (seção "Em breve"), sem
// prometer funcionalidade específica.
//
// Textos: a Ana fala em primeira pessoa (é a personagem da marca), mas sem
// prometer o que o sistema ainda não faz — ela PREPARA a nota e o usuário
// confere/aprova (a responsabilidade fiscal é dele), e o envio ao
// fornecedor é "deixar pronto pra enviar", não disparo automático.

const BTN_PRINCIPAL =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-accent-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-accent-500/25 transition hover:bg-accent-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
const BTN_SECUNDARIO =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white/70 px-6 py-3 text-base font-medium text-slate-700 transition hover:bg-white dark:border-slate-600 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:bg-slate-800"

// Link pra uma tela do emissor: no domínio raiz vai pro subdomínio notas
// (link absoluto); em qualquer outro host é navegação interna normal.
function LinkEmissor({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  if (ehDominioRaiz()) {
    return (
      <a href={urlEmissor(to)} className={className}>
        {children}
      </a>
    )
  }
  return (
    <Link to={to} className={className}>
      {children}
    </Link>
  )
}

const PASSOS = [
  {
    n: "1",
    titulo: "Cadastre cada fornecedor uma vez",
    texto: "CNPJ, descrição do serviço, código de tributação e prazo de pagamento. Eu guardo tudo e reaproveito todo mês.",
  },
  {
    n: "2",
    titulo: "Me diga o valor do mês",
    texto: "Eu monto a nota com tudo preenchido. Você confere na tela e aprova — sem digitar o mesmo formulário de novo.",
  },
  {
    n: "3",
    titulo: "Eu emito e organizo o resto",
    texto: "Nota emitida no padrão nacional, PDF oficial guardado, mensagem pronta pro fornecedor e recebimento no calendário.",
  },
]

const PUBLICO = [
  {
    icon: Store,
    titulo: "Afiliados",
    texto: "Recebe comissão de várias lojas e programas e precisa emitir uma nota pra cada um, todo mês.",
  },
  {
    icon: Megaphone,
    titulo: "Criadores de conteúdo",
    texto: "Faz publis e parcerias recorrentes com marcas e agências que pedem nota pra liberar o pagamento.",
  },
  {
    icon: Users,
    titulo: "Prestadores com clientes fixos",
    texto: "Atende as mesmas empresas todo mês e cansou de preencher tudo à mão no emissor da prefeitura.",
  },
]

const RECURSOS = [
  {
    icon: FileText,
    titulo: "NFS-e no padrão nacional",
    texto: "Emissão direta no Sistema Nacional da NFS-e, assinada com o seu certificado digital A1.",
  },
  {
    icon: FileCheck2,
    titulo: "PDF oficial e histórico",
    texto: "Cada nota fica guardada com o DANFSe oficial, pronta pra baixar ou mandar de novo quando pedirem.",
  },
  {
    icon: CalendarDays,
    titulo: "Calendário de prazos e recebimentos",
    texto: "Prazo de emissão e previsão de pagamento de cada fornecedor num calendário só, com lembretes.",
  },
  {
    icon: Wallet,
    titulo: "Recebimentos conferidos",
    texto: "Suba o PDF do extrato do banco e eu reconheço os pagamentos pra você só confirmar.",
  },
  {
    icon: BellRing,
    titulo: "Lembrete da alíquota",
    texto: "Todo mês eu te lembro de atualizar a alíquota do Simples antes da primeira nota.",
  },
  {
    icon: ShieldCheck,
    titulo: "Seus dados isolados",
    texto: "Cada conta só enxerga o que é dela — nada de dados misturados entre clientes.",
  },
]

const PERGUNTAS = [
  {
    p: "Preciso de certificado digital?",
    r: "Sim, um e-CNPJ do tipo A1 (arquivo .pfx). É com ele que eu assino as notas no Sistema Nacional da NFS-e, do mesmo jeito que o Emissor Nacional do gov.br faz.",
  },
  {
    p: "Funciona na minha cidade?",
    r: "Eu emito pelo padrão nacional da NFS-e, que as prefeituras estão adotando no país inteiro. Se a sua cidade já recebe notas pelo Emissor Nacional, funciona.",
  },
  {
    p: "A Ana decide os meus impostos?",
    r: "Não. Você informa a sua alíquota do Simples Nacional (normalmente quem passa é o seu contador) e eu uso nas notas. Todo mês eu te lembro de conferir se ela mudou.",
  },
  {
    p: "Eu perco o controle das notas?",
    r: "Nunca. Eu preparo tudo, mas nenhuma nota sai sem você conferir e aprovar. E todas continuam aparecendo no portal do Emissor Nacional.",
  },
  {
    p: "Quanto custa pra testar?",
    r: "Nada. São 14 dias grátis, sem precisar cadastrar cartão pra começar.",
  },
  {
    p: "E se eu precisar de ajuda?",
    r: `É só escrever pra ${EMAIL_SUPORTE}. Tem gente de verdade do outro lado pra te ajudar a configurar tudo.`,
  },
]

function ConversaExemplo() {
  // Ilustração do "jeito Ana" de trabalhar — valores e fornecedores
  // fictícios, só pra mostrar o fluxo.
  const notas = [
    { nome: "Loja Parceira", valor: "R$ 3.240,00" },
    { nome: "Programa de Afiliados", valor: "R$ 1.180,50" },
    { nome: "Agência de Publis", valor: "R$ 5.000,00" },
  ]
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-accent-400/30 via-primary-400/20 to-transparent blur-2xl" />
      <div className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-2xl shadow-brand-900/10 dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-4 flex items-center gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
          <AnaAvatar size={40} />
          <div className="leading-tight">
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Ana</p>
            <p className="flex items-center gap-1 text-xs text-success-600 dark:text-success-400">
              <span className="h-1.5 w-1.5 rounded-full bg-success-600 dark:bg-success-400" /> cuidando das suas notas
            </p>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="max-w-[90%] rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            O mês fechou! Já preparei as notas dos seus fornecedores:
            <ul className="mt-2 space-y-1.5">
              {notas.map((n) => (
                <li key={n.nome} className="flex items-center justify-between gap-3 rounded-lg bg-white px-3 py-1.5 text-xs dark:bg-slate-900">
                  <span className="truncate">{n.nome}</span>
                  <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{n.valor}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="ml-auto w-fit rounded-2xl rounded-tr-sm bg-accent-500 px-4 py-2.5 text-white">
            Conferi. Pode emitir!
          </div>
          <div className="max-w-[90%] rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            <p className="flex items-center gap-1.5 font-medium text-slate-900 dark:text-slate-100">
              <Check size={16} className="text-success-600 dark:text-success-400" /> 3 notas emitidas
            </p>
            <p className="mt-1">PDFs guardados, mensagens prontas pra cada fornecedor e os recebimentos já estão no seu calendário.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export function LandingPage() {
  const { usuario, carregando } = useAuth()
  const logado = !carregando && !!usuario

  return (
    <div className="min-h-screen bg-canvas text-slate-900 dark:bg-canvas-dark dark:text-slate-100">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-canvas/85 backdrop-blur dark:border-slate-800 dark:bg-canvas-dark/85">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <a href="#topo" aria-label="Agente Ana — início">
            <Marca />
          </a>
          <nav className="flex items-center gap-2 sm:gap-6">
            <a href="#como-funciona" className="hidden text-sm text-slate-600 hover:text-slate-900 md:inline dark:text-slate-300 dark:hover:text-white">
              Como funciona
            </a>
            <a href="#para-quem" className="hidden text-sm text-slate-600 hover:text-slate-900 md:inline dark:text-slate-300 dark:hover:text-white">
              Para quem é
            </a>
            <a href="#perguntas" className="hidden text-sm text-slate-600 hover:text-slate-900 md:inline dark:text-slate-300 dark:hover:text-white">
              Perguntas
            </a>
            {logado ? (
              <LinkEmissor to="/app" className="whitespace-nowrap rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-600">
                Ir para o painel
              </LinkEmissor>
            ) : (
              <>
                <LinkEmissor to="/entrar" className="whitespace-nowrap px-2 text-sm font-medium text-slate-700 hover:text-accent-600 dark:text-slate-200">
                  Entrar
                </LinkEmissor>
                <LinkEmissor to="/cadastro" className="whitespace-nowrap rounded-lg bg-accent-500 px-3 py-2 text-sm font-semibold text-white hover:bg-accent-600 sm:px-4">
                  <span className="sm:hidden">Começar</span>
                  <span className="hidden sm:inline">Começar grátis</span>
                </LinkEmissor>
              </>
            )}
          </nav>
        </div>
      </header>

      <main id="topo">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[36rem] bg-[radial-gradient(ellipse_at_top_right,rgba(236,72,153,0.14),transparent_55%),radial-gradient(ellipse_at_top_left,rgba(47,79,209,0.12),transparent_50%)]" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-14 sm:px-6 md:pt-20 lg:grid-cols-2">
            <div>
              <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent-200 bg-accent-50 px-3 py-1 text-xs font-medium text-accent-700 dark:border-accent-800 dark:bg-accent-900/30 dark:text-accent-200">
                <Sparkles size={14} /> Sua agente de notas fiscais
              </p>
              <h1 className="text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
                Sua nota fiscal <span className="bg-gradient-to-r from-accent-500 to-primary-600 bg-clip-text text-transparent">no automático.</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600 dark:text-slate-300">
                Oi, eu sou a Ana. Cuido das notas fiscais de serviço das suas comissões e parcerias: você cadastra cada
                fornecedor uma vez e, todo mês, eu preparo tudo. Você só confere e aprova.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <LinkEmissor to={logado ? "/app" : "/cadastro"} className={BTN_PRINCIPAL}>
                  {logado ? "Ir para o painel" : "Começar grátis"} <ArrowRight size={18} />
                </LinkEmissor>
                {logado ? (
                  <a href="#como-funciona" className={BTN_SECUNDARIO}>
                    Ver como funciona
                  </a>
                ) : (
                  <LinkEmissor to="/simulacao" className={BTN_SECUNDARIO}>
                    Testar sem cadastro
                  </LinkEmissor>
                )}
              </div>
              <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
                {["14 dias grátis", "Sem cartão pra começar", "NFS-e padrão nacional"].map((t) => (
                  <li key={t} className="flex items-center gap-1.5">
                    <Check size={16} className="text-success-600 dark:text-success-400" /> {t}
                  </li>
                ))}
              </ul>
            </div>
            <ConversaExemplo />
          </div>
        </section>

        {/* Como funciona */}
        <section id="como-funciona" className="scroll-mt-20 border-y border-slate-200/70 bg-white py-20 dark:border-slate-800 dark:bg-slate-900/40">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-accent-600 dark:text-accent-300">Como funciona</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Três passos. Um deles só uma vez.</h2>
            </div>
            <ol className="mt-12 grid gap-6 md:grid-cols-3">
              {PASSOS.map((p) => (
                <li key={p.n} className="rounded-2xl border border-slate-200 bg-canvas p-6 dark:border-slate-800 dark:bg-canvas-dark">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-accent-500 to-primary-600 text-base font-bold text-white">
                    {p.n}
                  </span>
                  <h3 className="mt-4 text-lg font-semibold">{p.titulo}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{p.texto}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Para quem é */}
        <section id="para-quem" className="scroll-mt-20 py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-accent-600 dark:text-accent-300">Para quem é</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Feita pra quem vive de comissão</h2>
              <p className="mt-4 text-slate-600 dark:text-slate-400">
                Se todo mês você emite as mesmas notas pras mesmas empresas, eu fui feita pra você.
              </p>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {PUBLICO.map(({ icon: Icon, titulo, texto }) => (
                <div key={titulo} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-50 text-accent-600 dark:bg-accent-900/30 dark:text-accent-300">
                    <Icon size={20} />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{titulo}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Recursos */}
        <section className="border-y border-slate-200/70 bg-white py-20 dark:border-slate-800 dark:bg-slate-900/40">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-accent-600 dark:text-accent-300">O que eu faço por você</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Da emissão ao dinheiro na conta</h2>
            </div>
            <div className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {RECURSOS.map(({ icon: Icon, titulo, texto }) => (
                <div key={titulo} className="flex gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h3 className="font-semibold">{titulo}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{texto}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Em breve */}
        <section className="py-20">
          <div className="mx-auto max-w-4xl px-4 sm:px-6">
            <div className="relative overflow-hidden rounded-3xl bg-brand-900 px-6 py-10 text-center text-white sm:px-12">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(236,72,153,0.35),transparent_45%),radial-gradient(circle_at_90%_100%,rgba(47,79,209,0.45),transparent_45%)]" />
              <div className="relative">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-accent-200">
                  <Sparkles size={14} /> Em breve
                </span>
                <h2 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">Eu estou só começando</h2>
                <p className="mx-auto mt-3 max-w-xl text-slate-300">
                  As notas fiscais são a primeira parte da sua operação que eu assumo. Logo, logo eu vou cuidar de
                  outras tarefas do dia a dia de quem vive de comissão — pra você focar só em vender.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Perguntas */}
        <section id="perguntas" className="scroll-mt-20 border-t border-slate-200/70 bg-white py-20 dark:border-slate-800 dark:bg-slate-900/40">
          <div className="mx-auto max-w-3xl px-4 sm:px-6">
            <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">Perguntas frequentes</h2>
            <div className="mt-10 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-canvas dark:divide-slate-800 dark:border-slate-800 dark:bg-canvas-dark">
              {PERGUNTAS.map(({ p, r }) => (
                <details key={p} className="group px-5 py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                    {p}
                    <ChevronDown size={18} className="shrink-0 text-slate-400 transition group-open:rotate-180" />
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA final */}
        <section className="py-20">
          <div className="mx-auto flex max-w-3xl flex-col items-center px-4 text-center sm:px-6">
            <AnaAvatar size={72} />
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">Deixa a nota comigo.</h2>
            <p className="mt-3 max-w-lg text-slate-600 dark:text-slate-400">
              Cadastre seus fornecedores hoje e deixe o próximo mês por minha conta.
            </p>
            <LinkEmissor to={logado ? "/app" : "/cadastro"} className={`${BTN_PRINCIPAL} mt-8`}>
              {logado ? "Ir para o painel" : "Começar grátis por 14 dias"} <ArrowRight size={18} />
            </LinkEmissor>
            {!logado && (
              <LinkEmissor to="/simulacao" className="mt-4 text-sm font-medium text-slate-500 underline-offset-4 hover:text-accent-600 hover:underline dark:text-slate-400">
                ou teste antes num ambiente de simulação, sem cadastro
              </LinkEmissor>
            )}
            {!logado && (
              <LinkEmissor to="/cadastro?tipo=contador" className="mt-2 text-sm font-medium text-slate-500 underline-offset-4 hover:text-accent-600 hover:underline dark:text-slate-400">
                É contador(a)? Crie a sua conta de contador
              </LinkEmissor>
            )}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200/70 dark:border-slate-800">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:px-6 dark:text-slate-400">
          <Marca tamanho={28} />
          <div className="flex flex-col items-center gap-1 sm:items-end">
            <BotaoSuporte className="font-medium text-slate-600 hover:text-accent-600 dark:text-slate-300">
              Fale com o suporte · {EMAIL_SUPORTE}
            </BotaoSuporte>
            <p className="flex gap-3">
              <Link to="/privacidade" className="hover:text-accent-600">Privacidade</Link>
              <Link to="/termos" className="hover:text-accent-600">Termos de uso</Link>
            </p>
            <p>Sua nota fiscal no automático. © {new Date().getFullYear()} Agente Ana</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
