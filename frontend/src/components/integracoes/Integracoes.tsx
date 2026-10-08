import { CalendarDays, Cloud, MessageCircle } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { useModulos } from "../../lib/modulos"
import type { StatusDrive } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"
import { AgendaAssinatura } from "./AgendaAssinatura"

/** Empresa › Integrações (08/10/2026): "vamos deixar nas opções de envio
 * somente Enviar para o Drive e na integração ele conectar qual ele quer". Aqui
 * a pessoa liga cada serviço uma vez; no resto do painel só aparece "Drive". */

export const LINK_INTEGRACOES = "/app/empresa?aba=integracoes"

function Secao({ icone: Icone, titulo, texto, children }: { icone: typeof Cloud; titulo: string; texto: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300" aria-hidden>
          <Icone size={18} />
        </span>
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{titulo}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">{texto}</p>
        </div>
      </div>
      {children}
    </Card>
  )
}

function Servico({ nome, detalhe, estado, acao }: { nome: string; detalhe: ReactNode; estado: ReactNode; acao?: ReactNode }) {
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-slate-200 p-3.5 sm:flex-row sm:items-center dark:border-slate-700">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 font-medium text-slate-800 dark:text-slate-100">
          {nome} {estado}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{detalhe}</p>
      </div>
      {acao}
    </li>
  )
}

export function Integracoes() {
  const modulos = useModulos()
  const [drive, setDrive] = useState<StatusDrive | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null)

  useEffect(() => {
    if (!modulos.emissor) return
    api.get<StatusDrive>("/drive").then(setDrive).catch(() => setDrive(null))
    // volta do Google (?drive=conectado|recusado|falhou)
    const retorno = new URLSearchParams(window.location.search).get("drive")
    if (retorno === "conectado") setAviso({ ok: true, texto: "Google Drive conectado. As notas que você mandar pro Drive vão pra pasta “Agente Ana”." })
    else if (retorno) setAviso({ ok: false, texto: "Não consegui conectar o Google Drive. Tente de novo e aceite o acesso que o Google pedir." })
  }, [modulos.emissor])

  async function conectarGoogle() {
    setOcupado(true)
    setAviso(null)
    try {
      const { url } = await api.post<{ url: string }>(`/drive/conectar?voltar=${encodeURIComponent(LINK_INTEGRACOES)}`, {})
      window.location.assign(url)
    } catch (err) {
      setAviso({ ok: false, texto: err instanceof ApiError ? formatarErro(err.detail) : "Não consegui abrir o Google agora." })
      setOcupado(false)
    }
  }

  async function desconectar() {
    if (!window.confirm("Desconectar o Google Drive? Os arquivos que já estão lá continuam lá.")) return
    setOcupado(true)
    try {
      await api.delete("/drive")
      setDrive((d) => (d ? { ...d, conectado: false, email: null, provedor: null } : d))
    } finally {
      setOcupado(false)
    }
  }

  const emBreve = <Badge variant="neutral">em breve</Badge>

  return (
    <div className="flex flex-col gap-6">
      {modulos.emissor && (
        <Secao
          icone={Cloud}
          titulo="Drive (guardar as notas na nuvem)"
          texto="Conecte o serviço que você usa. Depois é só escolher “Enviar para o Drive” no tomador, na nota ou no lote."
        >
          {aviso && (
            <p className={`mb-3 rounded-lg px-3 py-2 text-sm ${aviso.ok ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300" : "bg-danger-50 text-danger-700"}`}>
              {aviso.texto}
            </p>
          )}
          <ul className="flex flex-col gap-2.5">
            <Servico
              nome="Google Drive"
              estado={drive?.conectado ? <Badge variant="success">conectado</Badge> : null}
              detalhe={
                drive?.conectado
                  ? `Conta ${drive.email ?? "do Google"} · as notas vão pra pasta Agente Ana › tomador › mês.`
                  : drive && !drive.disponivel
                    ? "Ainda não está disponível neste servidor."
                    : "Se você entra no painel com o Google, ele já abre na mesma conta — é só autorizar o acesso ao Drive."
              }
              acao={
                drive?.disponivel &&
                (drive.conectado ? (
                  <Button variant="outline" onClick={desconectar} disabled={ocupado}>
                    Desconectar
                  </Button>
                ) : (
                  <Button onClick={conectarGoogle} disabled={ocupado}>
                    {ocupado ? "Abrindo o Google..." : "Conectar"}
                  </Button>
                ))
              }
            />
            <Servico nome="OneDrive (Microsoft)" estado={emBreve} detalhe="Pra quem guarda os arquivos na conta Microsoft." />
            <Servico nome="Dropbox" estado={emBreve} detalhe="Pra quem guarda os arquivos no Dropbox." />
          </ul>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Um Drive por empresa. Trocar de serviço é desconectar um e conectar o outro.</p>
        </Secao>
      )}

      <div id="agenda" className="scroll-mt-24 rounded-xl transition-shadow">
        <Secao
          icone={CalendarDays}
          titulo="Google Agenda (e outras agendas)"
          texto="Os prazos de gerar nota, as previsões de recebimento e os seus lembretes, direto na agenda que você já usa."
        >
          <AgendaAssinatura />
        </Secao>
      </div>

      <Secao icone={MessageCircle} titulo="WhatsApp" texto="Lembretes das suas tarefas no WhatsApp, pra quem quiser receber.">
        <ul className="flex flex-col gap-2.5">
          <Servico nome="Lembretes pelo WhatsApp" estado={emBreve} detalhe="Estamos preparando. Quando ficar pronto, você liga aqui." />
        </ul>
      </Secao>
    </div>
  )
}
