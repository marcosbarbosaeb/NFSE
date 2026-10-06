import { BriefcaseBusiness, Clock, Lock } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { EVENTO_SEM_ASSINATURA } from "../../lib/api"
import { useAuth } from "../../lib/auth"
import { ehContador, resumoPermissoes } from "../../lib/contador"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"

// Avisos de quem pode o quê na empresa ativa (06/10/2026):
// - contador: está na empresa de um cliente, com as permissões que ele deu;
// - assinatura: teste acabando (só quando o bloqueio está valendo) ou empresa
//   já só pra consulta.

export function FaixaContador() {
  const { usuario } = useAuth()
  if (!ehContador(usuario)) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-primary-700 px-4 py-2 text-center text-sm text-white">
      <span className="flex items-center gap-1.5 font-semibold">
        <BriefcaseBusiness size={15} aria-hidden="true" /> Você está nesta empresa como contador(a)
      </span>
      <span className="text-white/90">Pode: {resumoPermissoes(usuario?.permissoes ?? [])}.</span>
      <Link to="/app/atendimentos" className="rounded-full bg-white/95 px-3 py-0.5 text-xs font-semibold text-primary-700 hover:bg-white">
        Empresas que atendo
      </Link>
    </div>
  )
}

export function FaixaAssinatura() {
  const { usuario } = useAuth()
  const acesso = usuario?.acesso
  if (!acesso || usuario?.demo) return null
  const contador = ehContador(usuario)
  if (acesso.bloqueado) {
    return (
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-danger-600 px-4 py-2 text-center text-sm text-white">
        <span className="flex items-center gap-1.5 font-semibold">
          <Lock size={15} aria-hidden="true" />
          {acesso.motivo === "teste_acabou" ? "O teste grátis desta empresa terminou" : "Esta empresa está sem assinatura"}
        </span>
        <span className="text-white/95">
          Dá pra ver e baixar tudo, mas não pra gerar notas nem lançar.
          {contador && " Avise o dono da empresa."}
          {!contador && usuario?.atende_empresas && " As empresas que você atende como contador(a) não são afetadas."}
        </span>
        {!contador && (
          <Link to="/app/conta?aba=assinatura" className="rounded-full bg-white px-3 py-0.5 text-xs font-semibold text-danger-700 hover:bg-white/90">
            Assinar agora
          </Link>
        )}
      </div>
    )
  }
  // Contagem regressiva do teste: só quando acabar o teste trava de verdade.
  const dias = acesso.dias_restantes
  if (!acesso.bloqueio_ativo || contador || acesso.motivo !== "teste" || dias === null || dias > 5) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-warning-50 px-4 py-2 text-center text-sm text-warning-800 dark:bg-warning-900/40 dark:text-warning-200">
      <span className="flex items-center gap-1.5 font-semibold">
        <Clock size={15} aria-hidden="true" />
        {dias <= 0 ? "Seu teste grátis termina hoje" : dias === 1 ? "Seu teste grátis termina amanhã" : `Seu teste grátis termina em ${dias} dias`}
      </span>
      <Link to="/app/conta?aba=assinatura" className="font-semibold underline">
        Ver os planos
      </Link>
    </div>
  )
}

/** Abre quando a API recusa uma ação por falta de assinatura (402). */
export function AvisoSemAssinatura() {
  const { usuario } = useAuth()
  const navigate = useNavigate()
  const [mensagem, setMensagem] = useState<string | null>(null)
  useEffect(() => {
    const ouvir = (e: Event) =>
      setMensagem((e as CustomEvent<string | null>).detail || "Esta empresa está sem assinatura. Assine um plano pra continuar.")
    window.addEventListener(EVENTO_SEM_ASSINATURA, ouvir)
    return () => window.removeEventListener(EVENTO_SEM_ASSINATURA, ouvir)
  }, [])
  if (!mensagem) return null
  const contador = ehContador(usuario)
  return (
    <Modal titulo="Pra continuar, é preciso assinar" onClose={() => setMensagem(null)}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600 dark:text-slate-300">{mensagem}</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {contador
            ? "Quem assina é o dono da empresa. Enquanto isso, você continua vendo e baixando tudo o que já está aqui."
            : "Nada foi apagado: suas notas, tomadores e lançamentos continuam aqui, e você pode ver e baixar tudo."}
        </p>
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variant="ghost" onClick={() => setMensagem(null)}>
            Agora não
          </Button>
          {!contador && (
            <Button
              type="button"
              variant="accent"
              onClick={() => {
                setMensagem(null)
                navigate("/app/conta?aba=assinatura")
              }}
            >
              Ver os planos
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
