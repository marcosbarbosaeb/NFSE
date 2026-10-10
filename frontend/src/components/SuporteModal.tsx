import { ArrowLeft, CheckCircle2, ChevronDown, Mail, MessageCircle, Search, Send, Sparkles } from "lucide-react"
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { createPortal } from "react-dom"
import { useAuth } from "../lib/auth"
import { ApiError, api, formatarErro } from "../lib/api"
import { EMAIL_SUPORTE, MAILTO_SUPORTE } from "../lib/contato"
import { buscarDuvida } from "../lib/buscaFaq"
import { FAQ, perguntaVisivel } from "../lib/faq"
import { useModulos } from "../lib/modulos"
import type { AjudaInfo, CanaisSuporte } from "../lib/types"
import { PergunteAna } from "./ajuda/PergunteAna"
import { Button } from "./ui/Button"
import { Modal } from "./ui/Modal"

// "O botão 'Fale com o suporte' precisa ativar alguma coisa" (28/09/2026):
// o link mailto: só abre algo pra quem tem programa de e-mail configurado no
// computador. Agora abre um formulário que manda direto pro suporte (e a
// resposta volta pro e-mail da pessoa), com WhatsApp quando configurado e o
// endereço de e-mail como alternativa.

const classeCampo =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

// Observações de teste (10/10/2026): "o 'Pergunte à Ana' vai para dentro do
// fale com o suporte. A pessoa procura a dúvida primeiro e só depois, se não
// achar, entra no chat com a IA." Logado, o suporte vira um funil:
//   1. buscar — as perguntas da Ajuda (src/lib/faq.ts);
//   2. ana — o "Pergunte à Ana" (só com a IA ligada);
//   3. equipe — WhatsApp e o formulário de sempre.
// Sem login (site, cadastro) ou com `inicio="equipe"` (contratar, comprar
// certificado), vai direto pra equipe.
export type EtapaSuporte = "buscar" | "ana" | "equipe"

export function SuporteModal({
  onClose,
  logado: logadoProp,
  inicio,
  textoInicial = "",
}: {
  onClose: () => void
  logado?: boolean
  inicio?: EtapaSuporte
  textoInicial?: string
}) {
  const { usuario } = useAuth()
  // Conta de simulação não tem e-mail de verdade: pede o e-mail pra resposta.
  const logado = Boolean(logadoProp && usuario && !usuario.demo)
  const [etapa, setEtapa] = useState<EtapaSuporte>(logado ? (inicio ?? "buscar") : "equipe")
  const [duvida, setDuvida] = useState(textoInicial)
  const [ia, setIa] = useState<{ restantes: number | null; limite: number | null } | null>(null)
  const [canais, setCanais] = useState<CanaisSuporte | null>(null)
  const [assunto, setAssunto] = useState("")
  const [mensagem, setMensagem] = useState("")
  const [nome, setNome] = useState("")
  const [email, setEmail] = useState("")
  const [site, setSite] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)

  useEffect(() => {
    api.get<CanaisSuporte>("/suporte").then(setCanais).catch(() => setCanais({ email: EMAIL_SUPORTE, whatsapp: null, formulario: false }))
  }, [])
  useEffect(() => {
    if (!logado) return
    api
      .get<AjudaInfo>("/ajuda")
      .then((r) => setIa(r.ia_ativa ? { restantes: r.ia_restantes ?? null, limite: r.ia_limite ?? null } : null))
      .catch(() => setIa(null))
  }, [logado])

  function irParaEquipe(pergunta: string, resposta: string | null) {
    const texto = pergunta.trim()
    if (texto && !assunto) setAssunto(texto.slice(0, 150))
    if (texto && !mensagem) setMensagem(resposta ? `${texto}\n\n(A Ana respondeu: ${resposta.slice(0, 1500)})` : texto)
    setEtapa("equipe")
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setErro(null)
    try {
      await api.post("/suporte", {
        assunto,
        mensagem,
        nome: nome || null,
        email: email || null,
        pagina: window.location.pathname,
        site: site || null,
      })
      setEnviado(true)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    } finally {
      setEnviando(false)
    }
  }

  const whatsapp = canais?.whatsapp
    ? `https://wa.me/${canais.whatsapp}?text=${encodeURIComponent("Olá! Preciso de ajuda com a Agente Ana.")}`
    : null

  const titulo = etapa === "buscar" ? "Fale com o suporte" : etapa === "ana" ? "Pergunte à Ana" : "Fale com a equipe"
  return (
    <Modal titulo={titulo} onClose={onClose}>
      {etapa === "buscar" ? (
        <BuscarDuvida
          duvida={duvida}
          aoMudar={setDuvida}
          temIa={ia !== null}
          aoFechar={onClose}
          aoNaoAchar={() => (ia ? setEtapa("ana") : irParaEquipe(duvida, null))}
        />
      ) : etapa === "ana" && ia ? (
        <div className="flex flex-col gap-3">
          <button type="button" onClick={() => setEtapa("buscar")} className="inline-flex items-center gap-1 self-start text-xs font-medium text-slate-500 hover:text-primary-600 dark:text-slate-400">
            <ArrowLeft size={13} aria-hidden="true" /> Voltar pras perguntas
          </button>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            <Sparkles size={15} className="mr-1 inline align-[-2px] text-accent-500" aria-hidden="true" />
            Eu respondo com base nas minhas explicações. Dúvida de imposto ou de qual código usar é com o seu contador.
          </p>
          <PergunteAna perguntaInicial={duvida} restantesIniciais={ia.restantes} limite={ia.limite} aoPrecisarDaEquipe={irParaEquipe} />
        </div>
      ) : enviado ? (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <CheckCircle2 size={40} className="text-success-600" />
          <p className="font-medium text-slate-800 dark:text-slate-100">Mensagem enviada!</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">A gente responde no seu e-mail, normalmente no mesmo dia útil.</p>
          <Button variant="outline" onClick={onClose}>
            Fechar
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {logado && inicio !== "equipe" && (
            <button type="button" onClick={() => setEtapa(ia ? "ana" : "buscar")} className="inline-flex items-center gap-1 self-start text-xs font-medium text-slate-500 hover:text-primary-600 dark:text-slate-400">
              <ArrowLeft size={13} aria-hidden="true" /> {ia ? "Voltar pra Ana" : "Voltar pras perguntas"}
            </button>
          )}
          {whatsapp && (
            <a
              href={whatsapp}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 rounded-lg bg-[#25D366] px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90"
            >
              <MessageCircle size={18} /> Chamar no WhatsApp
            </a>
          )}
          {canais && !canais.formulario ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Escreva para{" "}
              <a href={MAILTO_SUPORTE} className="font-medium text-primary-600 underline">
                {EMAIL_SUPORTE}
              </a>
              .
            </p>
          ) : (
            <form onSubmit={enviar} className="flex flex-col gap-3">
              {whatsapp && <p className="text-center text-xs text-slate-400">ou mande uma mensagem por aqui</p>}
              {!logado && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Rotulo texto="Seu nome">
                    <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={120} className={classeCampo} />
                  </Rotulo>
                  <Rotulo texto="Seu e-mail (pra resposta)">
                    <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={200} className={classeCampo} />
                  </Rotulo>
                </div>
              )}
              <Rotulo texto="Assunto">
                <input required minLength={2} value={assunto} onChange={(e) => setAssunto(e.target.value)} maxLength={150} placeholder="Ex.: dúvida ao gerar a nota" className={classeCampo} />
              </Rotulo>
              <Rotulo texto="Mensagem">
                <textarea required minLength={5} value={mensagem} onChange={(e) => setMensagem(e.target.value)} rows={5} maxLength={5000} className={classeCampo} />
              </Rotulo>
              {/* robôs preenchem isto; gente não vê */}
              <input tabIndex={-1} autoComplete="off" value={site} onChange={(e) => setSite(e.target.value)} className="hidden" aria-hidden="true" />
              {erro && <p className="text-sm text-danger-600">{erro}</p>}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <a href={MAILTO_SUPORTE} className="flex items-center gap-1 text-xs text-slate-400 hover:text-primary-600">
                  <Mail size={13} /> {EMAIL_SUPORTE}
                </a>
                <Button type="submit" variant="accent" disabled={enviando}>
                  <Send size={15} /> {enviando ? "Enviando..." : "Enviar"}
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </Modal>
  )
}

function Rotulo({ texto, children }: { texto: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
      {texto}
      {children}
    </label>
  )
}

/** Etapa 1 do suporte: a pessoa procura a dúvida nas perguntas da Ajuda. */
function BuscarDuvida({
  duvida,
  aoMudar,
  temIa,
  aoFechar,
  aoNaoAchar,
}: {
  duvida: string
  aoMudar: (t: string) => void
  temIa: boolean
  aoFechar: () => void
  aoNaoAchar: () => void
}) {
  const modulos = useModulos()
  const visiveis = useMemo(() => FAQ.filter((p) => perguntaVisivel(p, { emissor: modulos.emissor, financeiro: modulos.financeiro })), [modulos.emissor, modulos.financeiro])
  const achadas = useMemo(() => buscarDuvida(visiveis, duvida), [visiveis, duvida])
  const [aberta, setAberta] = useState<string | null>(null)
  const digitou = duvida.trim().length >= 2
  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="suporte-duvida" className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Qual é a sua dúvida? Eu procuro nas respostas que já tenho.
      </label>
      <div className="relative">
        <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          id="suporte-duvida"
          type="search"
          autoFocus
          value={duvida}
          onChange={(e) => aoMudar(e.target.value.slice(0, 300))}
          placeholder="Ex.: cancelar nota, certificado, extrato..."
          className={`${classeCampo} pl-9`}
        />
      </div>
      <div role="status" aria-live="polite">
        {digitou && achadas.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">Não achei uma resposta pronta pra isso.</p>}
      </div>
      {achadas.length > 0 && (
        <ul className="max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200 dark:divide-slate-700/60 dark:border-slate-700">
          {achadas.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                aria-expanded={aberta === p.id}
                onClick={() => setAberta(aberta === p.id ? null : p.id)}
                className="flex w-full items-start justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium text-slate-800 hover:bg-slate-50 dark:text-slate-100 dark:hover:bg-slate-700/40"
              >
                <span>{p.pergunta}</span>
                <ChevronDown size={16} aria-hidden="true" className={`mt-0.5 shrink-0 text-slate-400 transition-transform ${aberta === p.id ? "rotate-180" : ""}`} />
              </button>
              {aberta === p.id && (
                <div className="px-3 pb-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                  <p>{p.resposta}</p>
                  {p.link && (
                    <Link to={p.link} onClick={aoFechar} className="mt-2 inline-block font-semibold text-primary-600 hover:underline dark:text-primary-300">
                      Ir pra essa tela
                    </Link>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 dark:border-slate-700/60">
        <Link to="/app/ajuda" onClick={aoFechar} className="text-xs font-medium text-slate-500 hover:text-primary-600 dark:text-slate-400">
          Ver todas as perguntas
        </Link>
        <Button type="button" variant={digitou && achadas.length === 0 ? "accent" : "outline"} onClick={aoNaoAchar}>
          {temIa ? <Sparkles size={15} aria-hidden="true" /> : null} {temIa ? "Não achei: perguntar à Ana" : "Não achei: falar com a equipe"}
        </Button>
      </div>
    </div>
  )
}

/** Link/botão que abre o suporte (logado: busca → Ana → equipe). */
export function BotaoSuporte({
  className,
  children,
  logado,
  inicio,
  textoInicial,
}: {
  className?: string
  children: ReactNode
  logado?: boolean
  inicio?: EtapaSuporte
  textoInicial?: string
}) {
  const [aberto, setAberto] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setAberto(true)} className={className}>
        {children}
      </button>
      {/* Portal: dentro da barra lateral (sticky) o modal ficaria atrás do topo. */}
      {aberto && createPortal(<SuporteModal logado={logado} inicio={inicio} textoInicial={textoInicial} onClose={() => setAberto(false)} />, document.body)}
    </>
  )
}
