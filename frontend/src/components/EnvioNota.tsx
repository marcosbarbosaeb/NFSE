import { Check, ExternalLink, FileCode2, FileDown, Info, Loader2, Mail, MessageCircle, Send, Users } from "lucide-react"
import { type ReactNode, useEffect, useId, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, api, formatarErro } from "../lib/api"
import type { EnviarEmailBody, EnviarGeralBody, Envio, PreviaEmail, WhatsappBody } from "../lib/types"
import type { NotaParaAcoes } from "./AcoesNota"

// Envio da nota ao tomador (29/09/2026). Pedidos do Marcos:
// - "o e-mail não é obrigatório, podem enviar pelo WhatsApp" / "no reenvio,
//   permita trocar pro WhatsApp";
// - "permita alterar o assunto e o corpo se a pessoa quiser";
// - "salve sempre as últimas configurações que a pessoa usou pra cada
//   tomador" (checkbox "Lembrar", ligado por padrão → salvar_padrao);
// - "cada tomador pede a nota de um jeito: uns querem o PDF no sistema deles
//   (portal), outros por e-mail, outros não exigem, outros mandam pro
//   contador ou pro próprio e-mail".
// O mesmo painel aparece no popover do selo (listas) e no card da página da nota.

type Aba = "email" | "whatsapp" | "portal" | "geral"

const ABAS: { valor: Aba; rotulo: string; icone: ReactNode }[] = [
  { valor: "email", rotulo: "E-mail", icone: <Mail size={13} aria-hidden /> },
  { valor: "whatsapp", rotulo: "WhatsApp", icone: <MessageCircle size={13} aria-hidden /> },
  { valor: "portal", rotulo: "Portal", icone: <ExternalLink size={13} aria-hidden /> },
  { valor: "geral", rotulo: "Contador/geral", icone: <Users size={13} aria-hidden /> },
]

/** Nota autorizada (ou de teste, em homologação) — dá pra mandar ao tomador. */
export function envioLiberado(nota: NotaParaAcoes): boolean {
  return nota.estado === "confirmado" || Boolean(nota.homologacao && ["montado", "assinado", "submetido"].includes(nota.estado))
}

const lista = (t: string) =>
  t
    .split(/[,;\s]+/)
    .map((e) => e.trim())
    .filter(Boolean)

const msgErro = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

function urlPortal(u: string): string {
  const t = u.trim()
  return /^https?:\/\//i.test(t) ? t : `https://${t}`
}

function abaInicial(previa: PreviaEmail, nota: NotaParaAcoes): Aba {
  if (nota.avulsa || previa.avulsa) return "email"
  // Só "baixar o PDF" marcado: a pessoa entrega do jeito dela e marca como enviada.
  if (previa.formas && previa.formas.length > 0 && previa.formas.every((f) => f === "download")) return "portal"
  const canal = previa.canal_preferido ?? nota.envio_forma ?? "email"
  if (canal === "whatsapp" || canal === "portal") return canal
  // "Não precisa enviar": o que costuma sobrar é mandar pro contador.
  if (canal === "nenhum") return "geral"
  if (previa.destinos.length === 0) return "whatsapp"
  return "email"
}

export function EnvioNota({
  nota,
  onMudou,
  onConcluido,
  modo = "card",
}: {
  nota: NotaParaAcoes
  /** Chamado depois de qualquer ação (recarrega a lista/o histórico). */
  onMudou: () => void
  /** Depois de entregar ao tomador (e-mail, WhatsApp, marcar enviada) — o popover fecha. */
  onConcluido?: () => void
  modo?: "popover" | "card"
}) {
  const uid = useId()
  const [previa, setPrevia] = useState<PreviaEmail | null>(null)
  const [erroPrevia, setErroPrevia] = useState<string | null>(null)
  const [aba, setAba] = useState<Aba>("email")

  // E-mail ao tomador
  const [para, setPara] = useState("")
  const [copia, setCopia] = useState("")
  const [assunto, setAssunto] = useState("")
  const [texto, setTexto] = useState("")
  // WhatsApp
  const [numero, setNumero] = useState("")
  const [textoZap, setTextoZap] = useState("")
  // Contador / e-mails gerais
  const [geralPara, setGeralPara] = useState("")
  const [geralAssunto, setGeralAssunto] = useState("")
  const [geralTexto, setGeralTexto] = useState("")

  // Outros destinatários do tomador (contador...) — cada um recebe o e-mail dele.
  const [extrasMarcados, setExtrasMarcados] = useState<string[]>([])
  const [lembrar, setLembrar] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<{ aba: Aba; texto: string } | null>(null)
  const [feito, setFeito] = useState<{ aba: Aba; texto: string } | null>(null)

  const liberado = envioLiberado(nota)
  const enviada = nota.envio_status === "enviado"
  // Nota de vendedor da Shopee já autorizada: o destinatário é o do relatório (o backend ignora "Para").
  const avulsa = Boolean(nota.avulsa || previa?.avulsa)
  const paraTravado = Boolean(avulsa && nota.estado === "confirmado")
  const compacto = modo === "popover"

  useEffect(() => {
    let vivo = true
    setPrevia(null)
    setErroPrevia(null)
    api
      .get<PreviaEmail>(`/dps/${nota.id}/email-previa`)
      .then((p) => {
        if (!vivo) return
        setPrevia(p)
        setAba(abaInicial(p, nota))
        setPara(p.destinos.join(", "))
        setCopia(p.copia.join(", "))
        setAssunto(p.assunto)
        setTexto(p.texto)
        setNumero(p.whatsapp ?? "")
        setTextoZap(p.whatsapp_texto ?? "")
        setGeralPara((p.geral_destinos ?? []).join(", "))
        setGeralAssunto(p.geral_assunto ?? "")
        setGeralTexto(p.geral_texto ?? "")
        setExtrasMarcados((p.extras ?? []).map((x) => x.email))
      })
      .catch((err) => vivo && setErroPrevia(msgErro(err)))
    return () => {
      vivo = false
    }
    // Recarrega só quando muda a nota (não a cada recarga da lista).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nota.id])

  async function executar(alvo: Aba, acao: () => Promise<string>, entregue: boolean) {
    setEnviando(true)
    setErro(null)
    setFeito(null)
    try {
      const ok = await acao()
      setFeito({ aba: alvo, texto: ok })
      onMudou()
      if (entregue) onConcluido?.()
    } catch (err) {
      setErro({ aba: alvo, texto: msgErro(err) })
    } finally {
      setEnviando(false)
    }
  }

  function enviarEmail() {
    executar(
      "email",
      async () => {
        const destinos = lista(para)
        if (!paraTravado && destinos.length === 0) throw new ApiError(400, "Informe pelo menos um destinatário.")
        const body: EnviarEmailBody = {
          para: paraTravado ? null : destinos,
          copia: lista(copia),
          assunto: assunto.trim() || null,
          texto: texto.trim() || null,
          extras: extrasMarcados,
          salvar_padrao: lembrar && !avulsa,
        }
        const envio = await api.post<Envio>(`/dps/${nota.id}/enviar-email`, body)
        if (envio.status === "falha") throw new ApiError(400, `O e-mail não saiu: ${envio.erro ?? "erro no provedor"}. Tente de novo.`)
        return extrasMarcados.length > 0 ? `E-mail enviado — e também pra ${extrasMarcados.length === 1 ? extrasMarcados[0] : `${extrasMarcados.length} outras pessoas`}.` : "E-mail enviado."
      },
      true,
    )
  }

  function abrirWhatsapp() {
    // Abre a aba já no clique (senão o navegador bloqueia como pop-up) e só
    // depois aponta pro link que o backend montou.
    const janela = window.open("", "_blank")
    executar(
      "whatsapp",
      async () => {
        const body: WhatsappBody = { numero: numero.trim(), texto: textoZap.trim() || null, salvar_padrao: lembrar && !avulsa }
        try {
          const { url } = await api.post<{ url: string; envio: Envio }>(`/dps/${nota.id}/whatsapp`, body)
          if (janela) janela.location.href = url
          else window.location.href = url
        } catch (err) {
          janela?.close()
          throw err
        }
        return "WhatsApp aberto — é só apertar enviar lá."
      },
      true,
    )
  }

  function marcarEnviada(forma: "portal" | "outro") {
    executar(
      "portal",
      async () => {
        await api.post<Envio>(`/dps/${nota.id}/marcar-enviada`, { forma })
        return "Marcada como enviada."
      },
      true,
    )
  }

  function enviarGeral() {
    executar(
      "geral",
      async () => {
        const destinos = lista(geralPara)
        if (destinos.length === 0) throw new ApiError(400, "Informe pelo menos um e-mail (ou cadastre os e-mails gerais em Empresa › Notas e e-mails e e-mails (Padrões de e-mail)).")
        const body: EnviarGeralBody = { para: destinos, assunto: geralAssunto.trim() || null, texto: geralTexto.trim() || null }
        const envio = await api.post<Envio>(`/dps/${nota.id}/enviar-geral`, body)
        if (envio.status === "falha") throw new ApiError(400, `O e-mail não saiu: ${envio.erro ?? "erro no provedor"}. Tente de novo.`)
        return `Enviado para ${destinos.join(", ")}.`
      },
      false,
    )
  }

  const campo =
    "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 read-only:bg-slate-50 read-only:text-slate-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:read-only:bg-slate-800"
  const rotulo = "mb-0.5 block text-xs font-medium text-slate-500 dark:text-slate-400"
  const dica = "mt-0.5 block text-[11px] leading-snug text-slate-400 dark:text-slate-500"
  const botaoPrincipal =
    "inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
  const botaoSecundario =
    "inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
  const botaoDesligado =
    "inline-flex cursor-not-allowed items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-300 dark:border-slate-700 dark:text-slate-600"
  const linhasTexto = compacto ? 5 : 8

  const checkboxLembrar = !avulsa && (
    <label className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
      <input
        type="checkbox"
        checked={lembrar}
        onChange={(e) => setLembrar(e.target.checked)}
        className="mt-0.5 rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
      />
      <span>
        Lembrar para este tomador
        <span className={dica}>Da próxima vez já vem assim. Mês, valor e nomes desta nota viram campos que se atualizam sozinhos.</span>
      </span>
    </label>
  )

  const mensagens = (alvo: Aba) => (
    <>
      {erro?.aba === alvo && (
        <p role="alert" className="rounded-lg bg-danger-50 px-2.5 py-1.5 text-xs text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">
          {erro.texto}
          {alvo === "geral" && (
            <>
              {" "}
              <Link to="/app/empresa?aba=emails" className="font-semibold underline">
                Configurar e-mails gerais
              </Link>
            </>
          )}
        </p>
      )}
      {feito?.aba === alvo && (
        <p role="status" className="flex items-center gap-1.5 rounded-lg bg-success-50 px-2.5 py-1.5 text-xs text-success-700 dark:bg-success-900/30 dark:text-success-300">
          <Check size={13} aria-hidden /> {feito.texto}
        </p>
      )}
    </>
  )

  const avisoBloqueado = !liberado && (
    <p className="rounded-lg bg-warning-50 px-2.5 py-1.5 text-xs text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
      Dá pra enviar ao tomador depois que a prefeitura autorizar a nota.
    </p>
  )

  if (erroPrevia) return <p className="text-xs text-danger-600">{erroPrevia}</p>
  if (!previa)
    return (
      <p className="flex items-center gap-1.5 text-xs text-slate-400">
        <Loader2 size={13} className="animate-spin" aria-hidden /> Carregando o envio...
      </p>
    )

  const motivoEmail =
    previa.motivo_desabilitado && !previa.motivo_desabilitado.startsWith("Cadastre") ? previa.motivo_desabilitado : null
  const geralSemDestino = (previa.geral_destinos ?? []).length === 0
  const idAba = (a: Aba) => `${uid}-aba-${a}`
  const idPainel = (a: Aba) => `${uid}-painel-${a}`

  return (
    <div className="flex flex-col gap-3 text-left text-sm">
      {previa.canal_preferido === "nenhum" && !avulsa && (
        <p className="flex items-start gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-600 dark:bg-slate-700/60 dark:text-slate-300">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
          Este tomador não precisa receber a nota. Envie só se quiser — ou mande pro contador.
        </p>
      )}

      <div role="tablist" aria-label="Como enviar a nota" className={`${compacto ? "flex" : "grid grid-cols-2 sm:flex"} gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-700`}>
        {ABAS.map((a) => {
          const ativo = aba === a.valor
          return (
            <button
              key={a.valor}
              id={idAba(a.valor)}
              type="button"
              role="tab"
              aria-selected={ativo}
              aria-controls={idPainel(a.valor)}
              onClick={() => {
                setAba(a.valor)
                setErro(null)
              }}
              className={`inline-flex flex-auto items-center justify-center gap-1 whitespace-nowrap rounded-md px-1.5 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 ${
                ativo ? "bg-white text-primary-700 shadow-sm dark:bg-slate-800 dark:text-primary-300" : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              {!compacto && a.icone}
              {a.rotulo}
            </button>
          )
        })}
      </div>

      {aba === "email" && (
        <div role="tabpanel" id={idPainel("email")} aria-labelledby={idAba("email")} className="flex flex-col gap-2">
          <div className={compacto ? "flex flex-col gap-2" : "grid grid-cols-1 gap-2 sm:grid-cols-2"}>
            <label className="block">
              <span className={rotulo}>Para</span>
              <input
                value={para}
                readOnly={paraTravado}
                onChange={(e) => setPara(e.target.value)}
                placeholder="financeiro@empresa.com"
                className={campo}
              />
              <span className={dica}>
                {paraTravado ? "Nota de vendedor (Shopee): vai sempre pro e-mail que veio no relatório." : "Vários? Separe com vírgula."}
              </span>
            </label>
            <label className="block">
              <span className={rotulo}>Cópia</span>
              <input value={copia} onChange={(e) => setCopia(e.target.value)} placeholder="opcional" className={campo} />
            </label>
          </div>
          <label className="block">
            <span className={rotulo}>Assunto</span>
            <input value={assunto} onChange={(e) => setAssunto(e.target.value)} maxLength={300} className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Mensagem</span>
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={linhasTexto} maxLength={5000} className={campo} />
            <span className={dica}>Já vem com os dados desta nota — edite à vontade.</span>
          </label>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            <span className="text-slate-400">Anexos:</span> {previa.arquivos.join(", ") || "—"}
          </p>
          {(previa.extras ?? []).length > 0 && (
            <fieldset className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
              <legend className="px-1 text-xs font-medium text-slate-500 dark:text-slate-400">Também recebem (cada um num e-mail separado)</legend>
              <div className="flex flex-col gap-1.5">
                {(previa.extras ?? []).map((x) => (
                  <label key={x.email} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={extrasMarcados.includes(x.email)}
                      onChange={(e) => setExtrasMarcados((a) => (e.target.checked ? [...a, x.email] : a.filter((y) => y !== x.email)))}
                    />
                    <span className="min-w-0 break-words">
                      {x.rotulo ? <strong className="font-medium">{x.rotulo}</strong> : null}
                      {x.rotulo ? " — " : ""}
                      {x.email}
                      <span className={dica}>{x.proprio ? `Com o e-mail próprio: “${x.assunto}”` : "Com o mesmo e-mail do tomador."}</span>
                    </span>
                  </label>
                ))}
              </div>
              <span className={dica}>
                Pra mudar quem recebe ou o texto de cada um, abra a{" "}
                <Link to={nota.vinculo_id ? `/app/tomadores/${nota.vinculo_id}` : "/app/tomadores"} className="font-medium text-primary-600 hover:underline">
                  ficha do tomador
                </Link>
                .
              </span>
            </fieldset>
          )}
          {motivoEmail && (
            <p className="rounded-lg bg-warning-50 px-2.5 py-1.5 text-xs text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">{motivoEmail}</p>
          )}
          {checkboxLembrar}
          {avisoBloqueado}
          {mensagens("email")}
          <div className="flex justify-end">
            <button type="button" disabled={!liberado || enviando || Boolean(motivoEmail)} onClick={enviarEmail} className={botaoPrincipal}>
              {enviando ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Send size={14} aria-hidden />}
              {enviada ? "Reenviar e-mail" : "Enviar e-mail"}
            </button>
          </div>
        </div>
      )}

      {aba === "whatsapp" && (
        <div role="tabpanel" id={idPainel("whatsapp")} aria-labelledby={idAba("whatsapp")} className="flex flex-col gap-2">
          <label className="block">
            <span className={rotulo}>Número</span>
            <input type="tel" inputMode="tel" value={numero} onChange={(e) => setNumero(e.target.value)} placeholder="(92) 99999-0000" className={campo} />
            <span className={dica}>Vazio = você escolhe o contato quando o WhatsApp abrir.</span>
          </label>
          <label className="block">
            <span className={rotulo}>Mensagem</span>
            <textarea value={textoZap} onChange={(e) => setTextoZap(e.target.value)} rows={linhasTexto} maxLength={3000} className={campo} />
            <span className={dica}>Vai com o link pra baixar a nota. Ao abrir, a nota fica marcada como enviada.</span>
          </label>
          {checkboxLembrar}
          {avisoBloqueado}
          {mensagens("whatsapp")}
          <div className="flex justify-end">
            <button type="button" disabled={!liberado || enviando} onClick={abrirWhatsapp} className={botaoPrincipal}>
              {enviando ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <MessageCircle size={14} aria-hidden />}
              Abrir WhatsApp
            </button>
          </div>
        </div>
      )}

      {aba === "portal" && (
        <div role="tabpanel" id={idPainel("portal")} aria-labelledby={idAba("portal")} className="flex flex-col gap-2">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Este tomador recebe a nota pelo sistema dele. Baixe os arquivos, envie no portal e marque como enviada.
          </p>
          <div className="flex flex-wrap gap-2">
            {nota.tem_pdf ? (
              <a href={`/api/dps/${nota.id}/pdf`} download className={botaoSecundario}>
                <FileDown size={14} aria-hidden /> Baixar PDF
              </a>
            ) : (
              <span className={botaoDesligado} title="O PDF oficial sai depois que a prefeitura autoriza a nota">
                <FileDown size={14} aria-hidden /> Baixar PDF
              </span>
            )}
            {nota.estado !== "rascunho" ? (
              <a href={`/api/dps/${nota.id}/download`} download className={botaoSecundario}>
                <FileCode2 size={14} aria-hidden /> Baixar XML
              </a>
            ) : (
              <span className={botaoDesligado} title="Sem XML ainda">
                <FileCode2 size={14} aria-hidden /> Baixar XML
              </span>
            )}
            {previa.portal_url && (
              <a href={urlPortal(previa.portal_url)} target="_blank" rel="noopener noreferrer" className={botaoSecundario}>
                <ExternalLink size={14} aria-hidden /> Abrir portal
              </a>
            )}
          </div>
          {!previa.portal_url && !avulsa && (
            <p className={dica}>
              Dica: cadastre o link do portal na{" "}
              <Link to={nota.vinculo_id ? `/app/tomadores/${nota.vinculo_id}` : "/app/tomadores"} className="font-medium text-primary-600 hover:underline">
                ficha do tomador
              </Link>{" "}
              pra abrir direto daqui.
            </p>
          )}
          {avisoBloqueado}
          {mensagens("portal")}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              disabled={!liberado || enviando}
              onClick={() => marcarEnviada("outro")}
              className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 disabled:opacity-50 dark:hover:bg-slate-700"
            >
              Enviei de outro jeito
            </button>
            <button type="button" disabled={!liberado || enviando} onClick={() => marcarEnviada("portal")} className={botaoPrincipal}>
              {enviando ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Check size={14} aria-hidden />}
              Marcar como enviada
            </button>
          </div>
        </div>
      )}

      {aba === "geral" && (
        <div role="tabpanel" id={idPainel("geral")} aria-labelledby={idAba("geral")} className="flex flex-col gap-2">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Manda a nota pros seus e-mails gerais (contador, o seu). <strong className="font-medium">Não conta como enviada ao tomador.</strong>
          </p>
          <label className="block">
            <span className={rotulo}>Destinatários</span>
            <input value={geralPara} onChange={(e) => setGeralPara(e.target.value)} placeholder="contador@escritorio.com" className={campo} />
            <span className={dica}>
              {geralSemDestino ? "Nenhum e-mail geral cadastrado ainda. " : "Vale só pra este envio. "}
              <Link to="/app/empresa?aba=emails" className="font-medium text-primary-600 hover:underline">
                {geralSemDestino ? "Cadastrar em Empresa › Notas e e-mails e e-mails (Padrões de e-mail)" : "Mudar o padrão"}
              </Link>
            </span>
          </label>
          <label className="block">
            <span className={rotulo}>Assunto</span>
            <input value={geralAssunto} onChange={(e) => setGeralAssunto(e.target.value)} maxLength={300} className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Mensagem</span>
            <textarea value={geralTexto} onChange={(e) => setGeralTexto(e.target.value)} rows={linhasTexto} maxLength={5000} className={campo} />
          </label>
          {avisoBloqueado}
          {mensagens("geral")}
          <div className="flex justify-end">
            <button type="button" disabled={!liberado || enviando} onClick={enviarGeral} className={botaoPrincipal}>
              {enviando ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Send size={14} aria-hidden />}
              Enviar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
