import { Bot, Building2, EyeOff, Handshake, LayoutDashboard, Lock, Mail, RefreshCw } from "lucide-react"
import { type ReactNode, useCallback, useEffect, useState } from "react"
import { PaginaAbas } from "../components/PaginaAbas"
import { ParceirasAdmin } from "../components/ParceirasAdmin"
import { AjudaIaGestao } from "../components/gestao/AjudaIaGestao"
import { ContasGestao } from "../components/gestao/ContasGestao"
import { EmailsGestao } from "../components/gestao/EmailsGestao"
import { VisaoGeralGestao } from "../components/gestao/VisaoGeralGestao"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { ApiError, api } from "../lib/api"
import { diaHora, erroDe } from "../lib/gestao"
import type { AcessoGestao, PainelGestao } from "../lib/types"

// Gestão da plataforma (06/10/2026) — "um painel geral de administrador/gestor":
// quem tem conta, quem está ativo, o que mais usam, os e-mails e as parceiras.
// Só entra quem está em ADMIN_EMAILS (GET /gestao/acesso); o painel em si
// (GET /gestao) só é pedido depois dessa resposta.

const classeErro = "rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300"

export function GestaoPage() {
  const [acesso, setAcesso] = useState<AcessoGestao | null>(null)
  const [erroAcesso, setErroAcesso] = useState<string | null>(null)
  const [painel, setPainel] = useState<PainelGestao | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)
  /** "Atualizar" também recarrega a lista de parceiras (que busca os próprios dados). */
  const [versao, setVersao] = useState(0)

  const conferirAcesso = useCallback(() => {
    setErroAcesso(null)
    api
      .get<AcessoGestao>("/gestao/acesso")
      .then((r) => setAcesso({ gestor: r.gestor === true, configurado: r.configurado !== false }))
      .catch((err) => setErroAcesso(erroDe(err)))
  }, [])

  const carregar = useCallback(() => {
    setCarregando(true)
    setErro(null)
    api
      .get<PainelGestao>("/gestao")
      .then(setPainel)
      .catch((err) => {
        // Saiu de ADMIN_EMAILS no meio do caminho: vira a tela de área restrita.
        if (err instanceof ApiError && err.status === 403) setAcesso((a) => ({ gestor: false, configurado: a?.configurado ?? true }))
        else setErro(erroDe(err))
      })
      .finally(() => setCarregando(false))
  }, [])

  useEffect(conferirAcesso, [conferirAcesso])
  const gestor = acesso?.gestor === true
  useEffect(() => {
    if (gestor) carregar()
  }, [gestor, carregar])

  if (erroAcesso) {
    return (
      <div className="mx-auto flex max-w-xl flex-col items-start gap-3">
        <p role="alert" className={classeErro}>{erroAcesso}</p>
        <Button type="button" variant="outline" onClick={conferirAcesso}>
          Tentar de novo
        </Button>
      </div>
    )
  }
  if (!acesso) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>
  if (!acesso.gestor) return <AreaRestrita configurado={acesso.configurado} />

  /** As abas de números esperam o painel; Parceiras e Ajuda não dependem dele. */
  const comPainel = (montar: (p: PainelGestao) => ReactNode) => () => (
    <>
      <AvisoPrivacidade />
      {erro && (
        <p role="alert" className={classeErro}>
          {erro}
        </p>
      )}
      {painel ? montar(painel) : !erro && <p className="text-sm text-slate-400 dark:text-slate-500">Carregando os números...</p>}
    </>
  )

  return (
    <PaginaAbas
      largo
      titulo="Gestão"
      subtitulo={painel ? `Atualizado em ${diaHora(painel.gerado_em)}` : "Contas, uso das ferramentas, e-mails e parceiras."}
      cabecalho={
        <Button type="button" variant="outline" disabled={carregando}
          onClick={() => {
            carregar()
            setVersao((v) => v + 1)
          }}
        >
          <RefreshCw size={15} className={carregando ? "animate-spin" : ""} aria-hidden="true" /> {carregando ? "Atualizando..." : "Atualizar"}
        </Button>
      }
      abas={[
        { id: "visao", rotulo: "Visão geral", icone: LayoutDashboard, conteudo: comPainel((p) => <VisaoGeralGestao painel={p} />) },
        { id: "contas", rotulo: "Contas", icone: Building2, conteudo: comPainel((p) => <ContasGestao painel={p} />) },
        { id: "emails", rotulo: "E-mails", icone: Mail, conteudo: comPainel((p) => <EmailsGestao painel={p} />) },
        {
          id: "parceiras",
          rotulo: "Parceiras",
          icone: Handshake,
          conteudo: () => (
            <>
              <AvisoPrivacidade />
              <ParceirasAdmin key={versao} />
            </>
          ),
        },
        {
          id: "ajuda",
          rotulo: "Ajuda (IA)",
          icone: Bot,
          conteudo: () => (
            <>
              <AvisoPrivacidade />
              <AjudaIaGestao />
            </>
          ),
        },
      ]}
    />
  )
}

function AvisoPrivacidade() {
  return (
    <p className="-mb-2 flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
      <EyeOff size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
      Aqui aparecem só números de uso. O conteúdo das notas e do financeiro de cada cliente não é exibido.
    </p>
  )
}

function AreaRestrita({ configurado }: { configurado: boolean }) {
  return (
    <Card className="mx-auto flex max-w-xl flex-col items-center gap-3 p-8 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300">
        <Lock size={22} aria-hidden="true" />
      </span>
      <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Área restrita à administração da plataforma</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">Esta tela só abre pra quem cuida da Agente Ana.</p>
      {!configurado && (
        <p className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
          Falta definir a variável <code className="font-semibold">ADMIN_EMAILS</code> no servidor, com o e-mail de login de quem
          administra. Enquanto ela não existir, ninguém entra aqui.
        </p>
      )}
    </Card>
  )
}
