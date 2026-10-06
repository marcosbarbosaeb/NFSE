import { AlertTriangle, BriefcaseBusiness, Building2, Check, Loader2, Lock, LogIn, MailPlus } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { nomeEmpresa } from "../components/TrocaEmpresa"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { PERMISSOES_PADRAO, quando } from "../lib/contador"
import { formatarDocumento } from "../lib/documento"
import type { Atendimentos, ClienteAtendido, ConviteContador, PermissaoContador, PermissaoInfo } from "../lib/types"

// Contador (06/10/2026): as empresas que este login atende. O cliente convida
// pelo e-mail em Empresa › Contador e escolhe o que o contador pode fazer;
// aqui o contador aceita e abre cada empresa (a troca recarrega o painel).

const erroDe = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

export function AtendimentosPage() {
  const { usuario, recarregarUsuario } = useAuth()
  const [dados, setDados] = useState<Atendimentos | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [fazendo, setFazendo] = useState<string | null>(null)
  const [saindo, setSaindo] = useState<ClienteAtendido | null>(null)

  const carregar = useCallback(() => {
    api
      .get<Atendimentos>("/contador/atendimentos")
      .then((d) => {
        setDados(d)
        setErro(null)
      })
      .catch((err) => setErro(erroDe(err)))
  }, [])
  useEffect(carregar, [carregar])

  const catalogo = dados?.permissoes?.length ? dados.permissoes : PERMISSOES_PADRAO

  async function responder(c: ConviteContador, aceitar: boolean) {
    setFazendo(c.id)
    setErro(null)
    try {
      await api.post(`/contador/convites/${c.id}/${aceitar ? "aceitar" : "recusar"}`)
      await recarregarUsuario()
      carregar()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(null)
    }
  }

  async function abrir(c: ClienteAtendido) {
    setFazendo(c.id)
    setErro(null)
    try {
      await api.post(`/empresas/${c.prestador_id}/ativar`)
      window.location.assign("/app")
    } catch (err) {
      setErro(erroDe(err))
      setFazendo(null)
    }
  }

  async function sair(c: ClienteAtendido) {
    setFazendo(c.id)
    setErro(null)
    try {
      await api.delete(`/contador/atendimentos/${c.id}`)
      // Se estava dentro dela, o painel inteiro volta pra empresa do contador.
      if (c.prestador_id === dados?.ativa) window.location.assign("/app/atendimentos")
      else {
        setSaindo(null)
        await recarregarUsuario()
        carregar()
      }
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setFazendo(null)
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
          <BriefcaseBusiness size={24} className="text-primary-600 dark:text-primary-400" aria-hidden="true" /> Empresas que atendo
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Para contadores: as empresas de clientes em que você entra pra cuidar das notas e do financeiro, cada uma com o que o cliente
          liberou.
        </p>
      </header>

      {erro && (
        <p role="alert" className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
          {erro}
        </p>
      )}

      {dados === null && !erro && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>}

      {dados && dados.convites.length > 0 && (
        <section className="flex flex-col gap-3" aria-label="Convites esperando resposta">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Convites esperando a sua resposta</h2>
          {dados.convites.map((c) => (
            <Card key={c.id} className="border-primary-300 p-5 dark:border-primary-700">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
                    <MailPlus size={18} className="shrink-0 text-primary-600 dark:text-primary-400" aria-hidden="true" />
                    <span className="truncate">{c.empresa}</span>
                  </p>
                  <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                    CNPJ {formatarDocumento(c.cnpj)}
                    {c.convidado_por && <> · convite de {c.convidado_por}</>}
                  </p>
                  <Permissoes catalogo={catalogo} marcadas={c.permissoes} />
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button type="button" variant="ghost" disabled={fazendo !== null} onClick={() => responder(c, false)}>
                    Recusar
                  </Button>
                  <Button type="button" variant="accent" disabled={fazendo !== null} onClick={() => responder(c, true)}>
                    {fazendo === c.id ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Aceitar
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </section>
      )}

      {dados && dados.clientes.length > 0 && (
        <section className="flex flex-col gap-3" aria-label="Empresas atendidas">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {dados.clientes.length === 1 ? "1 empresa" : `${dados.clientes.length} empresas`}
          </h2>
          {dados.clientes.map((c) => {
            const dentro = c.prestador_id === dados.ativa
            return (
              <Card key={c.id} className={`p-5 ${dentro ? "ring-2 ring-primary-500" : ""}`}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
                      <Building2 size={18} className="shrink-0 text-slate-400" aria-hidden="true" />
                      <span className="truncate">{nomeEmpresa({ nome_fantasia: c.nome_fantasia, razao_social: c.empresa })}</span>
                      {dentro && <Badge variant="info">você está nela</Badge>}
                    </p>
                    <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                      CNPJ {formatarDocumento(c.cnpj)}
                      {c.desde && <> · desde {quando(c.desde).slice(0, 10)}</>}
                    </p>
                    <Permissoes catalogo={catalogo} marcadas={c.permissoes} />
                    {c.situacao.bloqueado && (
                      <p className="mt-3 flex items-start gap-1.5 text-sm text-danger-700 dark:text-danger-300">
                        <Lock size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                        Empresa sem assinatura: só dá pra consultar. Avise o seu cliente.
                      </p>
                    )}
                    {!c.situacao.bloqueado && c.aviso && c.modulos.includes("emissor") && (
                      <p className="mt-3 flex items-start gap-1.5 text-sm text-warning-700 dark:text-warning-300">
                        <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                        {c.aviso}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
                    <Button type="button" variant={dentro ? "outline" : "primary"} disabled={fazendo !== null || dentro} onClick={() => abrir(c)}>
                      {fazendo === c.id ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
                      {dentro ? "Aberta" : "Abrir empresa"}
                    </Button>
                    <button
                      type="button"
                      onClick={() => setSaindo(c)}
                      className="text-xs font-medium text-slate-400 underline-offset-2 hover:text-danger-600 hover:underline dark:text-slate-500"
                    >
                      Deixar de atender
                    </button>
                  </div>
                </div>
              </Card>
            )
          })}
        </section>
      )}

      {dados && dados.clientes.length === 0 && dados.convites.length === 0 && (
        <Card className="p-6">
          <p className="text-base font-semibold text-slate-900 dark:text-slate-100">Você ainda não atende nenhuma empresa por aqui.</p>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-600 dark:text-slate-300">
            <li>
              Peça ao seu cliente pra abrir <strong>Empresa › Contador</strong> na conta dele e convidar o seu e-mail:{" "}
              <strong className="break-all">{usuario?.email}</strong>.
            </li>
            <li>Ele marca o que você pode fazer: só ver, gerar notas, enviar, cuidar dos tomadores, do financeiro...</li>
            <li>O convite aparece aqui. Você aceita e a empresa dele entra na sua lista — e no seletor de empresas, lá no topo do menu.</li>
          </ol>
        </Card>
      )}

      {saindo && (
        <Modal titulo="Deixar de atender esta empresa?" onClose={() => setSaindo(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Você perde o acesso a <strong>{saindo.empresa}</strong> na hora. Nada da empresa é apagado. Pra voltar, o cliente precisa te
              convidar de novo.
            </p>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="ghost" onClick={() => setSaindo(null)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" disabled={fazendo !== null} onClick={() => sair(saindo)}>
                Deixar de atender
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Permissoes({ catalogo, marcadas }: { catalogo: PermissaoInfo[]; marcadas: PermissaoContador[] }) {
  return (
    <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="O que você pode fazer">
      <li>
        <Badge variant="neutral">Ver notas e financeiro</Badge>
      </li>
      {catalogo
        .filter((p) => marcadas.includes(p.id))
        .map((p) => (
          <li key={p.id} title={p.descricao}>
            <Badge variant="success">{p.nome}</Badge>
          </li>
        ))}
    </ul>
  )
}
