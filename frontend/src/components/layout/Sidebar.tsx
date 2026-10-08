import { ArrowLeftRight, BriefcaseBusiness, Building2, CalendarDays, CircleHelp, Contact, FileText, FolderOpen, Gift, Home, Layers, ShieldCheck, UserRound, Users, Wallet } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, NavLink, useLocation } from "react-router-dom"
import { api } from "../../lib/api"
import { useAuth } from "../../lib/auth"
import { useModulos } from "../../lib/modulos"
import { useVersao } from "../../lib/novidades"
import { BotaoSuporte } from "../SuporteModal"
import { TrocaEmpresa } from "../TrocaEmpresa"
import { AnaAvatar, Marca } from "../brand/Marca"

// Emissor e financeiro são produtos separados (05/10/2026): o menu mostra
// um grupo pra cada módulo que a empresa tem ligado.
// A Visão geral é da empresa, não de um módulo (05/10/2026): fica no topo,
// logo abaixo da empresa, e junta os cards dos módulos que estão ligados.
const INICIO_ITEM = { to: "/app", label: "Visão geral", icon: Home, end: true }
const NOTAS = [
  { to: "/app/nfse", label: "NFS-e", icon: FileText, exceto: "/app/nfse/lote" },
  { to: "/app/nfse/lote", label: "Notas em lote", icon: Layers },
  { to: "/app/tomadores", label: "Tomadores", icon: Users },
  { to: "/app/calendario", label: "Calendário", icon: CalendarDays },
]
const FINANCEIRO = [
  { to: "/app/financeiro", label: "Painel", icon: Wallet, end: true },
  { to: "/app/financeiro/conciliacao", label: "Conciliação", icon: ArrowLeftRight },
]
// Só pra quem tem o Financeiro sozinho: com o módulo de notas, os clientes
// já estão na tela Tomadores.
const CLIENTES = { to: "/app/financeiro/clientes", label: "Clientes", icon: Contact }
// "Configurações" virou "Empresa" (dados do CNPJ ativo) + "Minha conta"
// (no pé da barra e no menu do usuário) — 29/09/2026.
const GERAL = [
  { to: "/app/empresa", label: "Empresa", icon: Building2 },
  // Pasta do mês (08/10/2026): arquivos e conversa com o contador.
  { to: "/app/pasta", label: "Pasta do mês", icon: FolderOpen },
]

const classeItem = (ativo: boolean) =>
  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 ${
    ativo ? "bg-primary-600 text-white" : "text-slate-300 hover:bg-brand-800 hover:text-white"
  }`

// Celular (revisão de 28/09/2026): abaixo de "lg" a barra vira uma gaveta
// que abre pelo botão de menu do topo e fecha ao escolher uma tela.
/** Versão que está no ar e em qual ambiente (08/10/2026) — pra bater o olho
 * e saber se o teste e o real estão na mesma. Leva pra tela Novidades. */
function RodapeVersao({ onFechar }: { onFechar?: () => void }) {
  const v = useVersao()
  if (!v) return null
  return (
    <Link to="/app/novidades" onClick={onFechar} className="mt-2 block px-1 text-center text-[11px] tabular-nums text-slate-400 hover:text-slate-200" title="Ver o que mudou em cada versão">
      versão {v.versao}
      {v.ambiente === "teste" && <span className="ml-1.5 rounded bg-warning-600/80 px-1.5 py-0.5 font-semibold text-white">teste</span>}
    </Link>
  )
}

export function Sidebar({ aberto = false, onFechar }: { aberto?: boolean; onFechar?: () => void }) {
  const { pathname, search } = useLocation()
  const naConta = pathname.replace(/\/+$/, "") === "/app/conta"
  const naIndicacao = naConta && new URLSearchParams(search).get("aba") === "indique"
  const modulos = useModulos()
  const { usuario } = useAuth()
  const soContador = usuario?.so_contador === true
  const grupos = soContador ? [] : [
    ...(modulos.emissor ? [{ titulo: "Notas", itens: NOTAS }] : []),
    ...(modulos.financeiro ? [{ titulo: "Financeiro", itens: modulos.emissor ? FINANCEIRO : [...FINANCEIRO, CLIENTES] }] : []),
    { titulo: "", itens: GERAL },
  ]
  const doisProdutos = modulos.emissor && modulos.financeiro
  // Selo da Conciliação (05/10/2026): a soma das DUAS conciliações — notas
  // por conferir (atrasadas, com diferença...) + linhas do extrato sem
  // classificar. O título do selo diz quanto é de cada uma.
  const [conciliar, setConciliar] = useState<{ notas: number; extrato: number } | null>(null)
  const noFinanceiro = pathname.startsWith("/app/financeiro")
  useEffect(() => {
    if (!modulos.financeiro) return
    api
      .get<{ notas: { aplica: boolean; pendencias: number }; extrato: { pendentes: number } }>("/conciliacao/resumo")
      .then((r) => setConciliar({ notas: r.notas.aplica ? r.notas.pendencias : 0, extrato: r.extrato.pendentes }))
      .catch(() => undefined)
  }, [modulos.financeiro, noFinanceiro, pathname === "/app/financeiro/conciliacao"])
  useEffect(() => {
    // A tela de Conciliação avisa quando uma baixa muda a conta.
    const ouvir = (e: Event) => setConciliar((e as CustomEvent<{ notas: number; extrato: number }>).detail)
    window.addEventListener("agenteana:conciliacao", ouvir)
    return () => window.removeEventListener("agenteana:conciliacao", ouvir)
  }, [])
  const totalConciliar = conciliar ? conciliar.notas + conciliar.extrato : 0
  // Selo da Pasta do mês: mensagens e arquivos que o contador mandou e a pessoa ainda não viu.
  const [pastaNova, setPastaNova] = useState(0)
  useEffect(() => {
    if (soContador) return
    const buscar = () =>
      api
        .get<{ mensagens: number; arquivos: number }>("/pasta/novidades")
        .then((r) => setPastaNova(r.mensagens + r.arquivos))
        .catch(() => undefined)
    buscar()
    window.addEventListener("agenteana:pasta-lida", buscar)
    return () => window.removeEventListener("agenteana:pasta-lida", buscar)
  }, [soContador, pathname])
  // "Gestão" (06/10/2026): só pra administração da plataforma. Enquanto a
  // resposta não chega — ou se a consulta falhar — o item não aparece.
  const [gestor, setGestor] = useState(false)
  useEffect(() => {
    api
      .get<{ gestor: boolean }>("/gestao/acesso")
      .then((r) => setGestor(r.gestor === true))
      .catch(() => setGestor(false))
  }, [])
  return (
    <>
      {aberto && <div className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden" onClick={onFechar} aria-hidden="true" />}
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col justify-between overflow-y-auto bg-brand-900 px-4 py-6 text-slate-300 transition-transform lg:sticky lg:top-0 lg:z-auto lg:translate-x-0 lg:self-start ${
        aberto ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div>
        {/* 08/10/2026: clicar na marca volta pro começo (Visão geral; no caso do contador, o painel dele). */}
        <Link
          to={soContador ? "/app/atendimentos" : "/app"}
          onClick={onFechar}
          title={soContador ? "Ir para o painel do contador" : "Ir para a Visão geral"}
          data-tour="marca"
          className="mb-5 flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-brand-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
        >
          <Marca escuro subtitulo={soContador ? "Conta de contador" : doisProdutos ? "Notas e financeiro" : modulos.financeiro ? "Financeiro" : "Emissor de notas"} />
        </Link>

        <div className="mb-5">
          <TrocaEmpresa />
        </div>

        <nav className="flex flex-col gap-1" data-tour="menu">
          {soContador ? (
            <NavLink to="/app/atendimentos" onClick={onFechar} className={({ isActive }) => classeItem(isActive)}>
              <BriefcaseBusiness size={18} />
              Painel do contador
            </NavLink>
          ) : (
            <NavLink to={INICIO_ITEM.to} end onClick={onFechar} className={({ isActive }) => classeItem(isActive)}>
              <Home size={18} />
              {INICIO_ITEM.label}
            </NavLink>
          )}
          {grupos.map((grupo) => (
            <div key={grupo.titulo || "geral"} className="flex flex-col gap-1">
              {grupo.titulo && (
                <p className="mt-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500 first:mt-0">{grupo.titulo}</p>
              )}
              {!grupo.titulo && <div className="my-2 border-t border-brand-800" />}
              {grupo.itens.map(({ to, label, icon: Icon, end, exceto }: { to: string; label: string; icon: typeof Home; end?: boolean; exceto?: string }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={onFechar}
                  className={({ isActive }) => classeItem(isActive && !(exceto && pathname.startsWith(exceto)))}
                >
                  <Icon size={18} />
                  {label}
                  {to === "/app/financeiro/conciliacao" && totalConciliar > 0 && conciliar && (
                    <span
                      className="ml-auto rounded-full bg-accent-500 px-1.5 text-xs font-semibold text-white"
                      title={`Pra conferir: ${conciliar.notas} nas notas (foram pagas?) e ${conciliar.extrato} no extrato (sem classificar)`}
                      aria-label={`${totalConciliar} pendências na conciliação: ${conciliar.notas} nas notas e ${conciliar.extrato} no extrato`}
                    >
                      {totalConciliar}
                    </span>
                  )}
                  {to === "/app/pasta" && pastaNova > 0 && (
                    <span className="ml-auto rounded-full bg-accent-500 px-1.5 text-xs font-semibold text-white" aria-label={`${pastaNova} novidades do contador`}>
                      {pastaNova}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </div>

      <div className="mt-6 flex flex-col gap-3">
        <div className="border-t border-brand-800 pt-3">
          <Link to="/app/conta" onClick={onFechar} aria-current={naConta && !naIndicacao ? "page" : undefined} className={classeItem(naConta && !naIndicacao)}>
            <UserRound size={18} aria-hidden="true" />
            Minha conta
          </Link>
          {/* Contador (06/10/2026): só pra quem atende empresas ou tem convite. */}
          {usuario?.atende_empresas && !soContador && (
            <NavLink to="/app/atendimentos" onClick={onFechar} className={({ isActive }) => `mt-1 ${classeItem(isActive)}`}>
              <BriefcaseBusiness size={18} aria-hidden="true" />
              Painel do contador
            </NavLink>
          )}
          {gestor && (
            <NavLink to="/app/gestao" onClick={onFechar} className={({ isActive }) => `mt-1 ${classeItem(isActive)}`}>
              <ShieldCheck size={18} aria-hidden="true" />
              Gestão
            </NavLink>
          )}
          {/* Ajuda / FAQ (05/10/2026): perguntas frequentes e o guia completo. */}
          <NavLink to="/app/ajuda" onClick={onFechar} className={({ isActive }) => `mt-1 ${classeItem(isActive)}`}>
            <CircleHelp size={18} aria-hidden="true" />
            Ajuda
          </NavLink>
          {!soContador && (
          <Link
            to="/app/conta?aba=indique"
            onClick={onFechar}
            aria-current={naIndicacao ? "page" : undefined}
            className={`mt-1 flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 ${
              naIndicacao ? "bg-brand-800 text-accent-200" : "text-accent-300 hover:bg-brand-800 hover:text-accent-200"
            }`}
          >
            <Gift size={15} aria-hidden="true" />
            Indique e ganhe desconto
          </Link>
          )}
        </div>

      <div className="rounded-xl bg-brand-800/70 p-4 text-slate-300">
        <div className="mb-2 flex items-center gap-2">
          <AnaAvatar size={28} />
          <p className="text-sm font-medium text-white">Deixa comigo.</p>
        </div>
        <p className="text-xs text-slate-400">
          {soContador
            ? "Abra a empresa de um cliente e eu deixo tudo à mão: notas, tomadores e financeiro, com o que ele liberou."
            : modulos.emissor
            ? "Cadastre cada tomador uma vez — todo mês eu preparo a nota e você só confere."
            : "Importe o extrato do banco — eu separo o que entrou do que saiu e lembro como você classifica."}
        </p>
        <BotaoSuporte logado className="mt-3 inline-block text-left text-xs font-medium text-accent-300 hover:text-accent-200">
          Precisa de ajuda? Fale com o suporte
        </BotaoSuporte>
      </div>
      <RodapeVersao onFechar={onFechar} />
      </div>
    </aside>
    </>
  )
}
