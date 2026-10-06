import { BriefcaseBusiness, Eye, History, Loader2, Trash2, UserPlus } from "lucide-react"
import { type FormEvent, useCallback, useEffect, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { PERMISSOES_PADRAO, ehContador, quando } from "../lib/contador"
import type { AcessoContador, AcessosDaEmpresa, PermissaoContador, PermissaoInfo } from "../lib/types"
import { Badge } from "./ui/Badge"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"
import { Field } from "./ui/Field"
import { Modal } from "./ui/Modal"

// Empresa › Contador (06/10/2026): o dono convida o contador pelo e-mail e
// marca o que ele pode fazer. Ver é sempre liberado; o resto é escolha. O que
// o contador faz aparece no histórico (só o título da ação).

const erroDe = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

function Caixas({
  catalogo,
  marcadas,
  mudar,
  desligado = false,
}: {
  catalogo: PermissaoInfo[]
  marcadas: PermissaoContador[]
  mudar: (p: PermissaoContador[]) => void
  desligado?: boolean
}) {
  const alternar = (id: PermissaoContador) => mudar(marcadas.includes(id) ? marcadas.filter((p) => p !== id) : [...marcadas, id])
  return (
    <ul className="flex flex-col gap-2">
      <li className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-2.5 dark:bg-slate-900/40">
        <Eye size={17} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
        <span className="text-sm">
          <span className="font-medium text-slate-700 dark:text-slate-200">Ver as notas e o financeiro</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">Sempre liberado: sem isso o contador não consegue te ajudar.</span>
        </span>
      </li>
      {catalogo.map((p) => (
        <li key={p.id}>
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              checked={marcadas.includes(p.id)}
              disabled={desligado}
              onChange={() => alternar(p.id)}
            />
            <span className="text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-200">{p.nome}</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">{p.descricao}</span>
            </span>
          </label>
        </li>
      ))}
    </ul>
  )
}

export function ContadorCard() {
  const { usuario } = useAuth()
  const contador = ehContador(usuario)
  const [dados, setDados] = useState<AcessosDaEmpresa | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [email, setEmail] = useState("")
  const [novas, setNovas] = useState<PermissaoContador[]>(["emitir", "enviar", "tomadores", "financeiro"])
  const [enviando, setEnviando] = useState(false)
  const [salvando, setSalvando] = useState<string | null>(null)
  const [tirando, setTirando] = useState<AcessoContador | null>(null)

  const carregar = useCallback(() => {
    if (contador) return
    api
      .get<AcessosDaEmpresa>("/contador/acessos")
      .then(setDados)
      .catch((err) => setErro(erroDe(err)))
  }, [contador])
  useEffect(carregar, [carregar])

  if (contador) {
    return (
      <Card className="p-5">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Só o dono da empresa escolhe quem entra nela e o que cada um pode fazer. Você está aqui como contador(a).
        </p>
      </Card>
    )
  }

  const catalogo = dados?.permissoes?.length ? dados.permissoes : PERMISSOES_PADRAO

  async function convidar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setAviso(null)
    setEnviando(true)
    try {
      const r = await api.post<{ acesso: AcessoContador; email_enviado: boolean }>("/contador/acessos", { email: email.trim(), permissoes: novas })
      setAviso(
        r.email_enviado
          ? `Convite enviado pra ${r.acesso.email}. Assim que ele aceitar, a sua empresa aparece na conta dele.`
          : `Convite criado, mas o e-mail pra ${r.acesso.email} não saiu. Avise ele: é só entrar na Ana com esse e-mail e abrir “Empresas que atendo”.`,
      )
      setEmail("")
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  async function mudar(a: AcessoContador, permissoes: PermissaoContador[]) {
    setSalvando(a.id)
    setErro(null)
    // Mostra a mudança na hora; se o servidor recusar, a lista volta ao que era.
    setDados((d) => (d ? { ...d, acessos: d.acessos.map((x) => (x.id === a.id ? { ...x, permissoes } : x)) } : d))
    try {
      await api.patch(`/contador/acessos/${a.id}`, { permissoes })
    } catch (err) {
      setErro(erroDe(err))
      carregar()
    } finally {
      setSalvando(null)
    }
  }

  async function tirar(a: AcessoContador) {
    setSalvando(a.id)
    setErro(null)
    try {
      await api.delete(`/contador/acessos/${a.id}`)
      setTirando(null)
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setSalvando(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-5">
        <h2 className="mb-1 flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
          <BriefcaseBusiness size={18} className="text-primary-600 dark:text-primary-400" aria-hidden="true" /> Contador
        </h2>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Dê acesso ao seu contador pra ele cuidar das notas e do financeiro por você. Ele entra com o login dele (não precisa da sua
          senha), só faz o que você marcar aqui, e você pode mudar ou tirar o acesso quando quiser.
        </p>

        {erro && (
          <p role="alert" className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
            {erro}
          </p>
        )}
        {aviso && (
          <p className="mb-4 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">{aviso}</p>
        )}

        {dados === null && !erro && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

        {dados && dados.acessos.length > 0 && (
          <ul className="mb-6 flex flex-col gap-4">
            {dados.acessos.map((a) => (
              <li key={a.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="break-all text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {a.nome ? `${a.nome} · ` : ""}
                      {a.email}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {a.status === "ativo" ? `Entrou em ${quando(a.aceito_em).slice(0, 10)}` : `Convidado em ${quando(a.criado_em).slice(0, 10)} — ainda não aceitou`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {salvando === a.id && <Loader2 size={15} className="animate-spin text-slate-400" aria-label="Salvando" />}
                    <Badge variant={a.status === "ativo" ? "success" : "warning"}>{a.status === "ativo" ? "com acesso" : "convite pendente"}</Badge>
                    <button
                      type="button"
                      onClick={() => setTirando(a)}
                      className="rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500 dark:hover:bg-danger-900/30"
                      aria-label={`Tirar o acesso de ${a.email}`}
                      title="Tirar o acesso"
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                </div>
                <Caixas catalogo={catalogo} marcadas={a.permissoes} mudar={(p) => mudar(a, p)} desligado={salvando !== null} />
              </li>
            ))}
          </ul>
        )}

        {dados && (
          <form onSubmit={convidar} className="flex flex-col gap-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-900/40">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
              <UserPlus size={16} aria-hidden="true" /> {dados.acessos.length ? "Convidar outro contador" : "Convidar o contador"}
            </p>
            <Field
              label="E-mail do contador"
              type="email"
              required
              autoComplete="off"
              placeholder="contador@escritorio.com.br"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              hint="Tem que ser o e-mail que ele usa (ou vai usar) pra entrar na Agente Ana."
            />
            <div>
              <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">O que ele pode fazer</p>
              <Caixas catalogo={catalogo} marcadas={novas} mudar={setNovas} />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Fica sempre só com você: a assinatura, convidar ou tirar pessoas, ligar e desligar módulos e apagar a empresa ou os dados.
            </p>
            <div className="flex justify-end">
              <Button type="submit" variant="accent" disabled={enviando || !email.trim()}>
                {enviando ? "Enviando..." : "Enviar convite"}
              </Button>
            </div>
          </form>
        )}
      </Card>

      {dados && (dados.historico.length > 0 || dados.acessos.some((a) => a.status === "ativo")) && (
        <Card className="p-5">
          <h2 className="mb-1 flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
            <History size={18} className="text-slate-400" aria-hidden="true" /> O que o contador fez
          </h2>
          <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">As últimas ações de quem você convidou, da mais recente pra mais antiga.</p>
          {dados.historico.length === 0 ? (
            <p className="text-sm text-slate-400 dark:text-slate-500">Nada ainda.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {dados.historico.map((h) => (
                <li key={h.id} className="flex flex-col gap-x-4 py-2 text-sm sm:flex-row sm:items-baseline sm:justify-between">
                  <span className="text-slate-700 dark:text-slate-200">{h.acao}</span>
                  <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                    {h.email} · {quando(h.quando)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {tirando && (
        <Modal titulo="Tirar o acesso do contador?" onClose={() => setTirando(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              <strong className="break-all">{tirando.email}</strong> deixa de entrar na sua empresa na hora. O que ele já fez (notas, lançamentos)
              continua como está.
            </p>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="ghost" onClick={() => setTirando(null)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" disabled={salvando !== null} onClick={() => tirar(tirando)}>
                Tirar o acesso
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
