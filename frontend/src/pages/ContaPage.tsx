import {
  CheckCircle2,
  CreditCard,
  Gift,
  GraduationCap,
  KeyRound,
  LaptopMinimal,
  LogOut,
  Mail,
  Moon,
  Palette,
  ShieldCheck,
  Smartphone,
  Sun,
  Trash2,
  UserRound,
} from "lucide-react"
import { PedirLiberacao } from "../components/PedirLiberacao"
import { type FormEvent, useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { PaginaAbas, TituloSecao } from "../components/PaginaAbas"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { GoogleIcon } from "../components/ui/GoogleIcon"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { excluirComConfirmacao, mensagemDeErro } from "../lib/excluir"
import { useTheme } from "../lib/theme"
import { definirTutorialAtivo, mostrarDicasDaTela, reverTodasAsDicas, tutorialAtivo } from "../lib/tutorial"
import { GradeDePlanos, UsoDoMes } from "../components/PlanosAssinatura"
import { avisarUsoMudou } from "../lib/planos"
import type { Assinatura, CheckoutSessao, Conta, PlanoAssinatura, SessaoConectada, UsoDoPlano } from "../lib/types"
import { IndiqueConteudo } from "./IndiquePage"

// "Minha conta" (29/09/2026) — o que é da PESSOA (login, senha, aparelhos,
// assinatura, indicações). O que é da EMPRESA (emitente, certificado,
// alíquota, e-mails da nota) fica em /app/empresa.

function erroDe(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

export function ContaPage() {
  const { usuario } = useAuth()
  const [conta, setConta] = useState<Conta | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<Conta>("/conta")
      .then(setConta)
      .catch((err) => setErro(erroDe(err)))
  }, [])

  const demo = conta?.demo ?? usuario?.demo ?? false

  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
  if (!conta) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>

  return (
    <PaginaAbas
      titulo="Minha conta"
      subtitulo={usuario?.so_contador ? "Seu acesso e suas preferências." : "Seu acesso, sua assinatura e suas indicações."}
      abas={[
        { id: "perfil", rotulo: "Perfil", icone: UserRound, conteudo: () => <AbaPerfil conta={conta} onAtualizada={setConta} demo={demo} /> },
        { id: "autenticacao", rotulo: "Acesso e segurança", icone: ShieldCheck, conteudo: () => <AbaAutenticacao conta={conta} demo={demo} /> },
        { id: "preferencias", rotulo: "Preferências", icone: Palette, conteudo: () => <AbaPreferencias /> },
        // Conta só de contador não tem assinatura nem indicação.
        ...(usuario?.so_contador
          ? []
          : [
              { id: "assinatura", rotulo: "Assinatura", icone: CreditCard, conteudo: () => <AbaAssinatura demo={demo} /> },
              { id: "indique", rotulo: "Indique e ganhe", icone: Gift, conteudo: () => <IndiqueConteudo /> },
            ]),
      ]}
    />
  )
}

// --- Perfil ---------------------------------------------------------------

function AbaPerfil({ conta, onAtualizada, demo }: { conta: Conta; onAtualizada: (c: Conta) => void; demo: boolean }) {
  const { recarregarUsuario } = useAuth()
  const [nome, setNome] = useState(conta.nome ?? "")
  const [whats, setWhats] = useState(conta.telefone ?? "")
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setMsg(null)
    try {
      const nova = await api.patch<Conta>("/conta", { nome: nome.trim(), telefone: whats.trim() })
      onAtualizada(nova)
      setNome(nova.nome ?? "")
      setWhats(nova.telefone ?? "")
      await recarregarUsuario()
      setMsg({ ok: true, texto: "Dados salvos." })
    } catch (err) {
      setMsg({ ok: false, texto: erroDe(err) })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <>
      <Card className="p-5">
        <TituloSecao icone={UserRound}>Perfil</TituloSecao>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Como a Ana te chama no painel.</p>
        <form onSubmit={salvar} className="flex flex-col gap-4">
          <Field
            label="Seu nome"
            value={nome}
            maxLength={120}
            autoComplete="name"
            placeholder="Como você quer ser chamado(a)"
            onChange={(e) => setNome(e.target.value)}
          />
          <Field
            label="WhatsApp"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={whats}
            maxLength={25}
            placeholder="(00) 00000-0000"
            hint="Com DDD. É por onde a nossa equipe fala com você."
            onChange={(e) => setWhats(e.target.value)}
          />
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail de acesso</span>
            <p className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
              <Mail size={15} className="shrink-0 text-slate-400" aria-hidden="true" />
              <span className="truncate">{conta.email}</span>
            </p>
            <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
              O e-mail de acesso não muda por aqui — se precisar trocar, fale com o suporte.
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" variant="accent" disabled={salvando || (nome.trim() === (conta.nome ?? "") && whats.trim() === (conta.telefone ?? ""))}>
              {salvando ? "Salvando..." : "Salvar"}
            </Button>
            {msg && (
              <span role="status" className={`text-xs ${msg.ok ? "text-success-700" : "text-danger-600"}`}>
                {msg.texto}
              </span>
            )}
          </div>
        </form>
      </Card>

      {demo ? (
        <Card className="p-5">
          <TituloSecao>Conta de simulação</TituloSecao>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Esta é uma conta de exemplo, apagada automaticamente em 24 horas. Senha, assinatura e certificado digital só
            existem na conta de verdade — crie a sua pelo botão no topo da tela.
          </p>
        </Card>
      ) : (
        <ExcluirContaCard />
      )}
    </>
  )
}

function ExcluirContaCard() {
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  function fechar() {
    setAberto(false)
    setTexto("")
    setErro(null)
  }

  async function excluir(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setErro(null)
    try {
      await excluirComConfirmacao("/conta", texto.trim().toUpperCase())
      window.location.assign("/entrar")
    } catch (err) {
      setErro(mensagemDeErro(err))
      setEnviando(false)
    }
  }

  return (
    <Card className="border-danger-100 p-5 dark:border-danger-900/40">
      <TituloSecao icone={Trash2} perigo>
        Excluir conta
      </TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Apaga o seu login e as empresas em que você é o único usuário, com todas as notas, tomadores e registros delas aqui na
        Ana. As notas já emitidas continuam válidas na Receita. Não tem como desfazer.
      </p>
      <Button type="button" variant="outline" className="border-danger-300 text-danger-700 hover:bg-danger-50 dark:border-danger-900 dark:text-danger-300 dark:hover:bg-danger-900/30" onClick={() => setAberto(true)}>
        <Trash2 size={15} /> Excluir minha conta
      </Button>

      {aberto && (
        <Modal titulo="Excluir sua conta?" onClose={fechar}>
          <form onSubmit={excluir} className="flex flex-col gap-4 text-sm text-slate-600 dark:text-slate-300">
            <p>
              Tudo o que está guardado na sua conta vai ser apagado de vez. Se tiver assinatura ativa, cancele antes em
              Assinatura pra não ser cobrado(a) de novo.
            </p>
            <Field label="Digite EXCLUIR para confirmar" value={texto} onChange={(e) => setTexto(e.target.value)} autoComplete="off" />
            {erro && (
              <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-danger-700">
                {erro}
              </p>
            )}
            <div className="flex flex-wrap justify-end gap-3">
              <Button type="button" variant="outline" onClick={fechar}>
                Cancelar
              </Button>
              <Button type="submit" variant="danger" disabled={enviando || texto.trim().toUpperCase() !== "EXCLUIR"}>
                {enviando ? "Excluindo..." : "Excluir conta de vez"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </Card>
  )
}

// --- Acesso e segurança -----------------------------------------------------

function AbaAutenticacao({ conta, demo }: { conta: Conta; demo: boolean }) {
  const [versaoSessoes, setVersaoSessoes] = useState(0)

  if (demo) {
    return (
      <Card className="p-5">
        <TituloSecao icone={ShieldCheck}>Acesso e segurança</TituloSecao>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Na conta de simulação não há senha nem aparelhos conectados. Crie sua conta de verdade pelo botão no topo da tela.
        </p>
      </Card>
    )
  }

  return (
    <>
      <Card className="p-5">
        <TituloSecao icone={KeyRound}>Senha</TituloSecao>
        {conta.tem_senha ? (
          <>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              Trocar a senha desconecta os outros aparelhos em que você estiver logado(a).
            </p>
            <TrocarSenhaForm onTrocada={() => setVersaoSessoes((v) => v + 1)} />
          </>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Sua conta não usa senha — você entra com o Google ou com um código enviado por e-mail.
          </p>
        )}
      </Card>

      <Card className="p-5">
        <TituloSecao icone={ShieldCheck}>Outras formas de entrar</TituloSecao>
        <ul className="mt-3 divide-y divide-slate-100 text-sm dark:divide-slate-700/60">
          <li className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0">
            <span className="flex items-center gap-2.5 text-slate-700 dark:text-slate-200">
              <GoogleIcon /> Google
            </span>
            {conta.google_conectado ? <Badge variant="success">Conectado</Badge> : <Badge variant="neutral">Não conectado</Badge>}
          </li>
          <li className="flex flex-col gap-1 py-3 last:pb-0">
            <span className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2.5 text-slate-700 dark:text-slate-200">
                <Mail size={16} className="text-slate-400" aria-hidden="true" /> Código por e-mail
              </span>
              <Badge variant="success">Disponível</Badge>
            </span>
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Na tela de login, toque em “Entrar com código por e-mail”: mandamos 6 dígitos pra {conta.email}, válidos por 10
              minutos.
            </span>
          </li>
        </ul>
        {!conta.google_conectado && (
          <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
            Pra ligar o Google, saia e use “Continuar com Google” na tela de login com uma conta Google deste mesmo e-mail.
          </p>
        )}
      </Card>

      <DispositivosCard versao={versaoSessoes} />
    </>
  )
}

function formatarQuando(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

function DispositivosCard({ versao }: { versao: number }) {
  const [sessoes, setSessoes] = useState<SessaoConectada[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const carregar = useCallback(() => {
    setErro(null)
    api
      .get<SessaoConectada[]>("/conta/sessoes")
      .then(setSessoes)
      .catch((err) => setErro(erroDe(err)))
  }, [])

  useEffect(carregar, [carregar, versao])

  async function desconectar(id: string) {
    setOcupado(id)
    setAviso(null)
    try {
      await api.delete(`/conta/sessoes/${id}`)
      setSessoes((lista) => lista?.filter((s) => s.id !== id) ?? null)
      setAviso("Aparelho desconectado.")
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setOcupado(null)
    }
  }

  async function sairDasOutras() {
    setOcupado("todas")
    setAviso(null)
    try {
      const r = await api.post<{ desconectadas: number }>("/conta/sessoes/sair-das-outras")
      setSessoes((lista) => lista?.filter((s) => s.atual) ?? null)
      setAviso(r.desconectadas === 1 ? "1 aparelho desconectado." : `${r.desconectadas} aparelhos desconectados.`)
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setOcupado(null)
    }
  }

  const outras = sessoes?.filter((s) => !s.atual).length ?? 0

  return (
    <Card className="p-5">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <TituloSecao icone={LaptopMinimal}>Dispositivos conectados</TituloSecao>
        {outras > 0 && (
          <Button type="button" variant="outline" className="px-3 py-1.5 text-xs" disabled={ocupado !== null} onClick={sairDasOutras}>
            <LogOut size={14} /> {ocupado === "todas" ? "Saindo..." : "Sair de todos os outros"}
          </Button>
        )}
      </div>
      <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
        Onde sua conta está aberta agora. Não reconhece algum? Desconecte e troque a senha.
      </p>
      {erro && <p className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
      {aviso && (
        <p role="status" className="mb-3 flex items-center gap-1.5 text-xs text-success-700">
          <CheckCircle2 size={14} aria-hidden="true" /> {aviso}
        </p>
      )}
      {sessoes === null && !erro ? (
        <p className="text-sm text-slate-400">Carregando...</p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
          {sessoes?.map((s) => {
            const celular = /iphone|android|ipad/i.test(s.dispositivo)
            const Icone = celular ? Smartphone : LaptopMinimal
            return (
              <li key={s.id} className="flex items-center gap-3 py-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                  <Icone size={17} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-800 dark:text-slate-200">
                    {s.dispositivo}
                    {s.atual && <Badge variant="info">Este dispositivo</Badge>}
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {s.ip ? `IP ${s.ip} · ` : ""}último acesso {formatarQuando(s.ultimo_acesso)}
                  </p>
                </div>
                {!s.atual && (
                  <Button
                    type="button"
                    variant="ghost"
                    className="shrink-0 px-2.5 py-1.5 text-xs text-danger-700 hover:bg-danger-50 dark:text-danger-300 dark:hover:bg-danger-900/30"
                    disabled={ocupado !== null}
                    onClick={() => desconectar(s.id)}
                    aria-label={`Desconectar ${s.dispositivo}`}
                  >
                    {ocupado === s.id ? "..." : "Desconectar"}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function TrocarSenhaForm({ onTrocada }: { onTrocada?: () => void }) {
  const [aberto, setAberto] = useState(false)
  const [senhaAtual, setSenhaAtual] = useState("")
  const [senhaNova, setSenhaNova] = useState("")
  const [confirmacao, setConfirmacao] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  function fechar() {
    setAberto(false)
    setSenhaAtual("")
    setSenhaNova("")
    setConfirmacao("")
    setErro(null)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setSucesso(false)
    if (senhaNova.length < 8) {
      setErro("A nova senha precisa ter pelo menos 8 caracteres.")
      return
    }
    if (senhaNova !== confirmacao) {
      setErro("A confirmação não bate com a nova senha.")
      return
    }
    setEnviando(true)
    try {
      await api.post("/auth/trocar-senha", { senha_atual: senhaAtual, senha_nova: senhaNova })
      setSucesso(true)
      setSenhaAtual("")
      setSenhaNova("")
      setConfirmacao("")
      onTrocada?.()
      setTimeout(() => setAberto(false), 1500)
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  if (!aberto) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" onClick={() => setAberto(true)}>
          <KeyRound size={15} /> Trocar senha
        </Button>
        {sucesso && <span className="text-xs text-success-700">Senha alterada com sucesso.</span>}
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex max-w-md flex-col gap-3">
      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {sucesso && <p className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">Senha alterada com sucesso.</p>}
      <Field label="Senha atual" type="password" required autoComplete="current-password" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} />
      <Field label="Nova senha" type="password" required minLength={8} autoComplete="new-password" value={senhaNova} onChange={(e) => setSenhaNova(e.target.value)} hint="Pelo menos 8 caracteres." />
      <Field label="Confirmar nova senha" type="password" required autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="outline" onClick={fechar}>
          Cancelar
        </Button>
        <Button type="submit" variant="accent" disabled={enviando}>
          {enviando ? "Salvando..." : "Salvar nova senha"}
        </Button>
      </div>
    </form>
  )
}

// --- Preferências (aparência e dicas — ficam neste navegador) --------------

function AbaPreferencias() {
  const { tema, definirTema } = useTheme()
  return (
    <>
      <Card className="p-5">
        <TituloSecao icone={Palette}>Aparência</TituloSecao>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Vale para este navegador.</p>
        <div className="flex gap-3" role="radiogroup" aria-label="Tema">
          {(
            [
              { valor: "claro", rotulo: "Claro", Icone: Sun },
              { valor: "escuro", rotulo: "Escuro", Icone: Moon },
            ] as const
          ).map(({ valor, rotulo, Icone }) => {
            const ativo = tema === valor
            return (
              <button
                key={valor}
                type="button"
                role="radio"
                aria-checked={ativo}
                onClick={() => definirTema(valor)}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
                  ativo
                    ? "border-primary-500 bg-primary-50 text-primary-700 dark:border-primary-400 dark:bg-primary-900/40 dark:text-primary-300"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                }`}
              >
                <Icone size={16} aria-hidden="true" /> {rotulo}
              </button>
            )
          })}
        </div>
      </Card>
      <TutorialCard />
    </>
  )
}

// "Na aba de configurações coloque uma opção para ativar e desativar esse
// tutorial" (28/09/2026) — ver lib/tutorial.ts.
function TutorialCard() {
  const [ativo, setAtivo] = useState(tutorialAtivo())
  const [revisto, setRevisto] = useState(false)
  return (
    <Card className="p-5" data-tour="config-tutorial">
      <TituloSecao icone={GraduationCap}>Dicas da Ana (tutorial)</TituloSecao>
      <label className="mt-3 flex items-start gap-3 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={ativo}
          onChange={(e) => {
            setAtivo(e.target.checked)
            definirTutorialAtivo(e.target.checked)
          }}
          className="mt-0.5 rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
        />
        <span>
          Mostrar dicas na primeira vez que eu abrir cada tela
          <span className="block text-xs text-slate-400 dark:text-slate-500">
            Mesmo desligado, o botão ? no topo mostra as dicas da tela em que você estiver.
          </span>
        </span>
      </label>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            reverTodasAsDicas()
            setAtivo(true)
            definirTutorialAtivo(true)
            setRevisto(true)
          }}
        >
          Ver todas as dicas de novo
        </Button>
        <Button type="button" variant="ghost" onClick={mostrarDicasDaTela}>
          Dicas desta tela
        </Button>
      </div>
      {revisto && <p className="mt-2 text-xs text-success-700">Pronto — as dicas vão aparecer de novo em cada tela.</p>}
    </Card>
  )
}

// --- Assinatura -------------------------------------------------------------

const STATUS_LABEL: Record<Assinatura["status"], string> = {
  cortesia: "Conta cortesia",
  trial: "Período de teste",
  ativa: "Assinatura ativa",
  inadimplente: "Pagamento pendente",
  cancelada: "Assinatura cancelada",
}

function badgeVariante(assinatura: Assinatura): "success" | "warning" | "danger" | "neutral" {
  if (assinatura.status === "cortesia") return "neutral"
  if (assinatura.status === "ativa") return "success"
  if (assinatura.status === "inadimplente" || assinatura.status === "cancelada") return "danger"
  return "warning" // trial (ainda ativo ou já expirado — ambos avisam, nunca "sucesso" de verdade)
}

function AbaAssinatura({ demo }: { demo: boolean }) {
  const { usuario } = useAuth()
  const contador = usuario?.papel === "contador"
  const [params] = useSearchParams()
  const retorno = params.get("assinatura") // volta do Stripe (?assinatura=sucesso|cancelado)
  const [assinatura, setAssinatura] = useState<Assinatura | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (demo) return
    api
      .get<Assinatura>("/assinatura")
      .then(setAssinatura)
      .catch((err) => setErro(erroDe(err)))
  }, [demo])

  if (contador) {
    return (
      <Card className="p-5">
        <TituloSecao icone={CreditCard}>Assinatura</TituloSecao>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Você está na empresa de um cliente, como contador(a). A assinatura dela é assunto do dono. Pra ver a assinatura da sua própria
          empresa, troque de empresa no topo do menu.
        </p>
      </Card>
    )
  }

  if (demo) {
    return (
      <Card className="p-5">
        <TituloSecao icone={CreditCard}>Assinatura</TituloSecao>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          A conta de simulação não tem assinatura. Crie sua conta de verdade pelo botão no topo da tela — o período de teste é
          gratuito.
        </p>
      </Card>
    )
  }

  return (
    <>
      {retorno === "sucesso" && (
        <p role="status" className="flex items-center gap-2 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">
          <CheckCircle2 size={16} aria-hidden="true" /> Pagamento recebido — obrigado! Pode levar alguns instantes pra situação
          abaixo atualizar.
        </p>
      )}
      {retorno === "cancelado" && (
        <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          Você saiu do pagamento sem concluir. Nada foi cobrado.
        </p>
      )}
      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {!assinatura && !erro && <p className="text-sm text-slate-400">Carregando...</p>}
      {assinatura && (
        <AssinaturaCard
          assinatura={assinatura}
          aoMudar={() => api.get<Assinatura>("/assinatura").then(setAssinatura).catch(() => undefined)}
        />
      )}
    </>
  )
}

const dinheiro = (valor: number, moeda = "BRL") => valor.toLocaleString("pt-BR", { style: "currency", currency: moeda })

function AssinaturaCard({ assinatura, aoMudar }: { assinatura: Assinatura; aoMudar?: () => void }) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const { recarregarUsuario } = useAuth()
  const planos = (assinatura.planos ?? []).filter((p) => p.disponivel)
  const [confirmarPlano, setConfirmarPlano] = useState<PlanoAssinatura | null>(null)
  /** Financeiro somado ao plano de notas escolhido (Básico/Empreendedor). */
  const [escolhaFinanceiro, setEscolhaFinanceiro] = useState(false)
  const [uso, setUso] = useState<UsoDoPlano | null>(assinatura.uso ?? null)
  const [planoFeito, setPlanoFeito] = useState<string | null>(null)

  /** Assinar um plano (checkout) ou, pra quem já paga, trocar de plano. */
  async function escolherPlano(plano: PlanoAssinatura, comFinanceiro = escolhaFinanceiro) {
    setErro(null)
    setPlanoFeito(null)
    setCarregando(true)
    try {
      if (assinatura.tem_assinatura_stripe && assinatura.status !== "cancelada") {
        await api.post("/assinatura/plano", { plano: plano.id, com_financeiro: comFinanceiro })
        await recarregarUsuario()
        avisarUsoMudou()
        setConfirmarPlano(null)
        setPlanoFeito(`Pronto: seu plano agora é ${plano.nome}. A diferença de valor entra proporcional na próxima fatura.`)
        aoMudar?.()
      } else {
        const { url } = await api.post<CheckoutSessao>("/assinatura/checkout", { plano: plano.id, com_financeiro: comFinanceiro })
        window.location.href = url
      }
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setCarregando(false)
    }
  }

  async function iniciarCheckoutOuPortal() {
    setErro(null)
    setCarregando(true)
    try {
      const rota = assinatura.tem_assinatura_stripe ? "/assinatura/portal" : "/assinatura/checkout"
      const { url } = await api.post<CheckoutSessao>(rota, {})
      window.location.href = url
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErro("Cobrança ainda não está disponível — a conta Stripe está sendo configurada. Volte em breve.")
      } else {
        setErro(erroDe(err))
      }
    } finally {
      setCarregando(false)
    }
  }

  const diasRestantesTrial =
    assinatura.status === "trial" && assinatura.trial_termina_em
      ? Math.max(0, Math.ceil((new Date(assinatura.trial_termina_em).getTime() - Date.now()) / 86_400_000))
      : null

  // Liberação feita pela Gestão da plataforma (vale mesmo com o teste vencido).
  const liberadaNaMao = assinatura.situacao === "liberacao"
  // Fase sem cobrança: depois do teste, quem autoriza o uso é a equipe.
  const { usuario } = useAuth()
  const semCobranca = usuario?.acesso?.cobranca_ativa === false
  const testeAcabou = ["teste_acabou", "cancelada", "sem_assinatura"].includes(assinatura.situacao ?? "")

  return (
    <Card className="p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <TituloSecao icone={CreditCard}>Assinatura</TituloSecao>
        <Badge variant={liberadaNaMao ? "success" : assinatura.status === "trial" && !assinatura.ativa ? "danger" : badgeVariante(assinatura)}>
          {liberadaNaMao ? "Acesso liberado" : STATUS_LABEL[assinatura.status]}
        </Badge>
      </div>

      <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
        {assinatura.status === "cortesia" && "Sua conta tem acesso liberado — nada pra fazer aqui."}
        {liberadaNaMao &&
          (assinatura.liberado_ate
            ? `A equipe da Agente Ana liberou o uso desta empresa até ${new Date(assinatura.liberado_ate).toLocaleDateString("pt-BR")}. `
            : "A equipe da Agente Ana liberou o uso desta empresa, sem prazo. ")}
        {assinatura.status === "trial" &&
          !liberadaNaMao &&
          !semCobranca &&
          (diasRestantesTrial !== null && diasRestantesTrial > 0
            ? `Você está no período de teste gratuito — ${diasRestantesTrial} dia${diasRestantesTrial === 1 ? "" : "s"} restante${diasRestantesTrial === 1 ? "" : "s"}.${
                assinatura.bloqueio_ativo ? " Quando ele acabar, a empresa fica só pra consulta até você assinar." : ""
              }`
            : assinatura.bloqueio_ativo
              ? "Seu período de teste acabou. A empresa está só pra consulta: assine pra voltar a gerar notas e lançar."
              : "Seu período de teste acabou. Assine pra continuar usando a Agente Ana sem interrupção.")}
        {assinatura.status === "ativa" && "Sua assinatura está em dia."}
        {assinatura.status === "inadimplente" && "O último pagamento não foi confirmado — atualize a forma de pagamento pra evitar interrupção."}
        {assinatura.status === "cancelada" && "Sua assinatura foi cancelada. Assine de novo pra recuperar o acesso completo."}
      </p>

      {semCobranca && !liberadaNaMao && assinatura.status !== "cortesia" && assinatura.situacao !== "bloqueada" && (
        <div className="mb-4 rounded-xl border border-primary-200 bg-primary-50/60 px-4 py-3 text-sm text-slate-700 dark:border-primary-800 dark:bg-primary-900/20 dark:text-slate-200">
          {testeAcabou ? (
            <>
              <p className="font-semibold text-slate-900 dark:text-slate-100">Seu teste grátis terminou.</p>
              <p className="mb-3 mt-0.5">
                Nesta fase não há cobrança por aqui: quem libera o uso é a nossa equipe. Peça a liberação e a gente te chama no WhatsApp pra combinar.
                {assinatura.bloqueio_ativo ? " Enquanto isso, a empresa fica só pra consulta — nada é apagado." : ""}
              </p>
              <PedirLiberacao />
            </>
          ) : (
            <p>
              Você está no teste grátis{diasRestantesTrial !== null && diasRestantesTrial > 0 ? ` — ${diasRestantesTrial} dia${diasRestantesTrial === 1 ? "" : "s"} restante${diasRestantesTrial === 1 ? "" : "s"}` : ""}.
              Quando ele acabar, é só pedir a liberação aqui e a nossa equipe autoriza o uso. Nada é cobrado por enquanto.
            </p>
          )}
        </div>
      )}

      {erro && <p className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {planoFeito && <p className="mb-4 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">{planoFeito}</p>}

      {/* Uso do mês e planos por limite de notas (07/10/2026). */}
      {uso && assinatura.status !== "cortesia" && <UsoDoMes uso={uso} aoMudar={setUso} />}
      {assinatura.status !== "cortesia" && (
        <GradeDePlanos
          assinatura={{ ...assinatura, uso: uso ?? assinatura.uso }}
          carregando={carregando}
          aoEscolher={(p, comFinanceiro) => {
            setEscolhaFinanceiro(comFinanceiro)
            if (assinatura.tem_assinatura_stripe && assinatura.status !== "cancelada") setConfirmarPlano(p)
            else escolherPlano(p, comFinanceiro)
          }}
        />
      )}

      {assinatura.status !== "cortesia" && assinatura.tem_assinatura_stripe && (
        <Button type="button" variant="outline" disabled={carregando} onClick={iniciarCheckoutOuPortal}>
          {carregando ? "Um momento..." : "Forma de pagamento, faturas e cancelamento"}
        </Button>
      )}
      {assinatura.status !== "cortesia" && planos.length === 0 && !assinatura.tem_assinatura_stripe && (
        <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
          A cobrança ainda está sendo ligada: por enquanto não dá pra assinar por aqui, e nada é cobrado.
        </p>
      )}
      {confirmarPlano && (
        <Modal titulo={`Mudar pro plano ${confirmarPlano.nome}?`} onClose={() => (carregando ? null : setConfirmarPlano(null))}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              A partir de agora esta empresa fica com: <strong>{confirmarPlano.descricao}</strong>
              {escolhaFinanceiro && confirmarPlano.aceita_financeiro && <strong> Mais o Financeiro.</strong>}
              {confirmarPlano.valor != null && (
                <>
                  {" "}
                  O valor passa a ser{" "}
                  {dinheiro(confirmarPlano.valor + (escolhaFinanceiro && confirmarPlano.aceita_financeiro ? (assinatura.financeiro_a_parte?.valor ?? 0) : 0), confirmarPlano.moeda)} por mês;
                </>
              )}{" "}
              a diferença deste
              mês entra proporcional na próxima fatura. Nada é apagado.
            </p>
            {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{erro}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" disabled={carregando} onClick={() => setConfirmarPlano(null)}>
                Cancelar
              </Button>
              <Button type="button" variant="accent" disabled={carregando} onClick={() => escolherPlano(confirmarPlano)}>
                {carregando ? "Mudando..." : "Confirmar a mudança"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
      <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
        Cada indicado que assinar pelo seu link dá desconto na mensalidade — veja em “Indique e ganhe”.
      </p>
    </Card>
  )
}
