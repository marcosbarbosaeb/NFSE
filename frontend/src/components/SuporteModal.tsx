import { CheckCircle2, Mail, MessageCircle, Send } from "lucide-react"
import { type FormEvent, type ReactNode, useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { useAuth } from "../lib/auth"
import { ApiError, api, formatarErro } from "../lib/api"
import { EMAIL_SUPORTE, MAILTO_SUPORTE } from "../lib/contato"
import type { CanaisSuporte } from "../lib/types"
import { Button } from "./ui/Button"
import { Modal } from "./ui/Modal"

// "O botão 'Fale com o suporte' precisa ativar alguma coisa" (28/09/2026):
// o link mailto: só abre algo pra quem tem programa de e-mail configurado no
// computador. Agora abre um formulário que manda direto pro suporte (e a
// resposta volta pro e-mail da pessoa), com WhatsApp quando configurado e o
// endereço de e-mail como alternativa.

const classeCampo =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function SuporteModal({ onClose, logado: logadoProp }: { onClose: () => void; logado?: boolean }) {
  const { usuario } = useAuth()
  // Conta de simulação não tem e-mail de verdade: pede o e-mail pra resposta.
  const logado = Boolean(logadoProp && usuario && !usuario.demo)
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

  return (
    <Modal titulo="Fale com o suporte" onClose={onClose}>
      {enviado ? (
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

/** Link/botão que abre o formulário de suporte. */
export function BotaoSuporte({ className, children, logado }: { className?: string; children: ReactNode; logado?: boolean }) {
  const [aberto, setAberto] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setAberto(true)} className={className}>
        {children}
      </button>
      {/* Portal: dentro da barra lateral (sticky) o modal ficaria atrás do topo. */}
      {aberto && createPortal(<SuporteModal logado={logado} onClose={() => setAberto(false)} />, document.body)}
    </>
  )
}
