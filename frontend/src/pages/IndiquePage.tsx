import { Check, Copy, Gift, MessageCircle, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { StatCard } from "../components/ui/StatCard"
import { ApiError, api, formatarErro } from "../lib/api"
import type { Indicacao } from "../lib/types"

// Programa de indicação (28/09/2026): "10% para cada 1 [indicado com
// assinatura ativa] até 100%". O desconto vira cupom na assinatura do Stripe.

const STATUS: Record<string, { rotulo: string; variante: "success" | "warning" | "danger" | "neutral" }> = {
  ativa: { rotulo: "Assinante", variante: "success" },
  trial: { rotulo: "Testando", variante: "neutral" },
  inadimplente: { rotulo: "Pagamento atrasado", variante: "warning" },
  cancelada: { rotulo: "Cancelou", variante: "danger" },
  cortesia: { rotulo: "Cortesia", variante: "neutral" },
}

/** Página avulsa (antigo /app/indique). Hoje a rota redireciona pra
 * Minha conta › Indique e ganhe, que usa só o <IndiqueConteudo />. */
export function IndiquePage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Indique e ganhe</h1>
      <IndiqueConteudo />
    </div>
  )
}

export function IndiqueConteudo() {
  const [dados, setDados] = useState<Indicacao | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)

  useEffect(() => {
    api
      .get<Indicacao>("/indicacao")
      .then(setDados)
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
  }, [])

  async function copiar() {
    if (!dados) return
    try {
      await navigator.clipboard.writeText(dados.link)
    } catch {
      const campo = document.getElementById("link-indicacao") as HTMLInputElement | null
      campo?.select()
      document.execCommand?.("copy")
    }
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  const faltam = dados ? Math.max(0, Math.ceil((dados.pct_maximo - dados.desconto_pct) / dados.pct_por_indicado)) : 0
  const textoZap = dados
    ? `Uso a Agente Ana pra emitir minhas notas fiscais todo mês, sem dor de cabeça. Cria sua conta por este link: ${dados.link}`
    : ""

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Cada pessoa que assinar pelo seu link vale <strong>{dados?.pct_por_indicado ?? 10}% de desconto</strong> na sua
          mensalidade, enquanto ela continuar assinante. Com {dados ? dados.pct_maximo / dados.pct_por_indicado : 10}{" "}
          indicados ativos, você não paga nada.
        </p>
      </div>

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {dados && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              icon={<Gift size={18} />}
              iconClassName="bg-accent-50 text-accent-600"
              label="Seu desconto"
              value={`${dados.desconto_pct}%`}
              sublabel={dados.desconto_pct >= dados.pct_maximo ? "mensalidade zerada!" : `faltam ${faltam} pra zerar`}
            />
            <StatCard
              icon={<Users size={18} />}
              iconClassName="bg-success-50 text-success-600"
              label="Indicados assinantes"
              value={dados.ativos}
              sublabel={`de ${dados.total} que se cadastraram`}
            />
            <Card className="p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Progresso</p>
              <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                <div className="h-full rounded-full bg-accent-500 transition-all" style={{ width: `${dados.desconto_pct}%` }} />
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {dados.desconto_pct}% de {dados.pct_maximo}%
              </p>
            </Card>
          </div>

          <Card className="p-5">
            <h2 className="mb-3 text-base font-semibold text-slate-800 dark:text-slate-200">Seu link</h2>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="link-indicacao"
                readOnly
                value={dados.link}
                onFocus={(e) => e.target.select()}
                className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
              />
              <Button type="button" variant="accent" onClick={copiar}>
                {copiado ? <Check size={16} /> : <Copy size={16} />} {copiado ? "Copiado!" : "Copiar link"}
              </Button>
              <a
                href={`https://wa.me/?text=${encodeURIComponent(textoZap)}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#25D366] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                <MessageCircle size={16} /> Enviar no WhatsApp
              </a>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Seu código: <strong className="text-slate-600 dark:text-slate-300">{dados.codigo}</strong>
            </p>
            {!dados.cobranca_ativa && (
              <p className="mt-3 rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700">
                A cobrança das assinaturas ainda não foi ligada — as indicações já contam e o desconto entra
                automaticamente assim que ela começar.
              </p>
            )}
            {dados.cobranca_ativa && dados.desconto_aplicado_pct !== dados.desconto_pct && (
              <p className="mt-3 text-xs text-slate-500">
                Desconto aplicado hoje na sua assinatura: {dados.desconto_aplicado_pct}% (atualiza quando você assinar ou quando um
                indicado mudar de situação).
              </p>
            )}
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-base font-semibold text-slate-800 dark:text-slate-200">Quem veio pelo seu link</h2>
            {dados.indicados.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">Ninguém ainda — mande o link pra quem também emite nota todo mês.</p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                {dados.indicados.map((i, n) => {
                  const st = STATUS[i.status] ?? { rotulo: i.status, variante: "neutral" as const }
                  return (
                    <li key={n} className="flex items-center justify-between py-2.5 text-sm">
                      <span className="text-slate-700 dark:text-slate-200">
                        {i.nome}
                        <span className="ml-2 text-xs text-slate-400">desde {new Date(`${i.desde}T00:00:00`).toLocaleDateString("pt-BR")}</span>
                      </span>
                      <Badge variant={st.variante}>{st.rotulo}</Badge>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
