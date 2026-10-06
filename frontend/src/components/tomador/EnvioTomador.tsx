import { Ban, ExternalLink, FileDown, FolderUp, Mail, MessageCircle, Plus, Trash2 } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"
import { api } from "../../lib/api"
import type { EmailExtra, FormaDeEnvio, Prestador, StatusDrive } from "../../lib/types"
import { EditorModeloEmail, type ValorModeloEmail } from "../EditorModeloEmail"
import { Field } from "../ui/Field"

/** "Envio da nota" na ficha do tomador (05/10/2026):
 * - dá pra marcar MAIS DE UMA forma (e-mail + baixar o PDF ao finalizar...);
 * - um campo só de e-mail do tomador (antes havia "E-mail do tomador" e
 *   "Para" no modelo do e-mail);
 * - outros destinatários (contador, financeiro) recebem cada um o seu
 *   e-mail, com assunto e texto próprios. */

export interface ValorEnvio {
  formas: FormaDeEnvio[]
  email: string
  whatsapp: string
  portal_url: string
  modelo: ValorModeloEmail
  extras: EmailExtra[]
}

const FORMAS: { valor: FormaDeEnvio; titulo: string; dica: string; icone: typeof Mail }[] = [
  { valor: "email", titulo: "E-mail", dica: "Eu mando a nota com o PDF e o XML em anexo.", icone: Mail },
  { valor: "whatsapp", titulo: "WhatsApp", dica: "Abro a conversa com a mensagem e o link da nota — você só aperta enviar.", icone: MessageCircle },
  { valor: "portal", titulo: "Portal do tomador", dica: "Você sobe o PDF/XML no sistema dele e marca como enviada.", icone: ExternalLink },
  { valor: "download", titulo: "Baixar o PDF ao finalizar", dica: "Quando a prefeitura autorizar, o PDF já baixa no seu computador.", icone: FileDown },
  { valor: "drive", titulo: "Guardar no meu Google Drive", dica: "Quando a prefeitura autorizar, eu guardo o PDF e o XML numa pasta do seu Drive.", icone: FolderUp },
]

const MAXIMO_EXTRAS = 5

/** <details> que só usa o "aberto" como ponto de partida — senão fechava
 * sozinho a cada tecla enquanto os campos de dentro estavam vazios. */
function Detalhes({ abertoDeInicio, className, resumo, children }: { abertoDeInicio: boolean; className?: string; resumo: ReactNode; children: ReactNode }) {
  const [aberto, setAberto] = useState(abertoDeInicio)
  return (
    <details className={className} open={aberto} onToggle={(e) => setAberto(e.currentTarget.open)}>
      {resumo}
      {aberto && children}
    </details>
  )
}

export function EnvioTomador({ valor, onChange, prestador }: { valor: ValorEnvio; onChange: (v: ValorEnvio) => void; prestador: Prestador | null }) {
  const mudar = (parte: Partial<ValorEnvio>) => onChange({ ...valor, ...parte })
  const tem = (f: FormaDeEnvio) => valor.formas.includes(f)
  const alternar = (f: FormaDeEnvio) => mudar({ formas: tem(f) ? valor.formas.filter((x) => x !== f) : [...valor.formas, f] })
  const mudarExtra = (i: number, parte: Partial<EmailExtra>) => mudar({ extras: valor.extras.map((e, j) => (j === i ? { ...e, ...parte } : e)) })
  // Google Drive: só aparece como opção onde está disponível (ou se já estava marcado).
  const [drive, setDrive] = useState<StatusDrive | null>(null)
  const [conectando, setConectando] = useState(false)
  useEffect(() => {
    api.get<StatusDrive>("/drive").then(setDrive).catch(() => setDrive(null))
  }, [])
  const formasVisiveis = FORMAS.filter((f) => f.valor !== "drive" || drive?.disponivel || tem("drive"))
  async function conectarDrive() {
    setConectando(true)
    try {
      const voltar = encodeURIComponent(window.location.pathname)
      const { url } = await api.post<{ url: string }>(`/drive/conectar?voltar=${voltar}`, {})
      window.location.href = url
    } catch {
      setConectando(false)
    }
  }

  return (
    <>
      <fieldset className="mb-5">
        <legend className="mb-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
          Como este tomador recebe a nota <span className="font-normal text-slate-400">— pode marcar mais de uma forma</span>
        </legend>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {/* "Não é necessário enviar" (06/10/2026): opção à vista, em vez de
              depender de a pessoa descobrir que é só desmarcar tudo. Marcar
              limpa as outras formas; marcar qualquer outra desmarca esta. */}
          <label className="relative cursor-pointer sm:col-span-2">
            <input
              type="checkbox"
              checked={valor.formas.length === 0}
              onChange={() => mudar({ formas: valor.formas.length === 0 ? ["email"] : [] })}
              className="peer sr-only"
            />
            <span className="flex h-full items-start gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-600 transition-colors hover:border-primary-300 peer-checked:border-slate-500 peer-checked:bg-slate-100 peer-checked:text-slate-900 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 dark:border-slate-600 dark:text-slate-300 dark:peer-checked:bg-slate-700/60 dark:peer-checked:text-slate-100">
              <span
                aria-hidden
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold ${
                  valor.formas.length === 0 ? "border-slate-600 bg-slate-600 text-white" : "border-slate-300 dark:border-slate-500"
                }`}
              >
                {valor.formas.length === 0 ? "✓" : ""}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 font-medium">
                  <Ban size={14} className="shrink-0" aria-hidden /> Não é necessário enviar
                </span>
                <span className="mt-0.5 block text-xs font-normal text-slate-500 dark:text-slate-400">
                  Este tomador não precisa receber a nota. Ela não aparece como pendente de envio.
                </span>
              </span>
            </span>
          </label>
          {formasVisiveis.map((f) => {
            const Icone = f.icone
            return (
              <label key={f.valor} className="relative cursor-pointer">
                <input type="checkbox" checked={tem(f.valor)} onChange={() => alternar(f.valor)} className="peer sr-only" />
                <span className="flex h-full items-start gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-600 transition-colors hover:border-primary-300 peer-checked:border-primary-500 peer-checked:bg-primary-50 peer-checked:text-primary-900 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 dark:border-slate-600 dark:text-slate-300 dark:peer-checked:bg-primary-900/30 dark:peer-checked:text-primary-100">
                  <span
                    aria-hidden
                    className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold ${
                      tem(f.valor) ? "border-primary-600 bg-primary-600 text-white" : "border-slate-300 dark:border-slate-500"
                    }`}
                  >
                    {tem(f.valor) ? "✓" : ""}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 font-medium">
                      <Icone size={14} className="shrink-0" aria-hidden /> {f.titulo}
                    </span>
                    <span className="mt-0.5 block text-xs font-normal text-slate-500 dark:text-slate-400">{f.dica}</span>
                  </span>
                </span>
              </label>
            )
          })}
        </div>
        {tem("drive") && drive && (
          <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
            {drive.conectado ? (
              <>
                Google Drive conectado{drive.email ? ` (${drive.email})` : ""}. Cada nota vai pra pasta <strong>Agente Ana › nome do tomador › mês</strong>.
              </>
            ) : drive.disponivel ? (
              <>
                Falta conectar o seu Google Drive. <strong>Salve este tomador primeiro</strong> e depois{" "}
                <button type="button" onClick={conectarDrive} disabled={conectando} className="font-semibold text-primary-600 underline disabled:opacity-60 dark:text-primary-300">
                  {conectando ? "abrindo o Google..." : "conecte o Google Drive"}
                </button>
                . Eu só enxergo a pasta que eu mesma crio lá.
              </>
            ) : (
              <>O Google Drive ainda não está disponível por aqui.</>
            )}
          </p>
        )}
      </fieldset>

      <div className="flex flex-col gap-4">
        {tem("email") && (
          <Field
            label="E-mail do tomador"
            value={valor.email}
            onChange={(e) => mudar({ email: e.target.value })}
            placeholder="financeiro@empresa.com"
            maxLength={400}
            hint="É pra cá que a nota vai. Mais de um? Separe com vírgula."
          />
        )}
        {tem("whatsapp") && (
          <Field
            label="WhatsApp do tomador"
            type="tel"
            value={valor.whatsapp}
            onChange={(e) => mudar({ whatsapp: e.target.value })}
            placeholder="(92) 99999-0000"
            hint="Vazio = você escolhe o contato quando o WhatsApp abrir."
          />
        )}
        {tem("portal") && (
          <Field
            label="Link do portal do tomador"
            inputMode="url"
            autoComplete="url"
            value={valor.portal_url}
            onChange={(e) => mudar({ portal_url: e.target.value })}
            placeholder="https://fornecedores.empresa.com.br"
            maxLength={400}
            hint="Aparece como “Abrir portal” na hora de enviar cada nota."
          />
        )}
      </div>

      {tem("email") && (
        <>
          <Detalhes
            className="group mt-5 rounded-xl border border-slate-200 dark:border-slate-700"
            abertoDeInicio={Boolean(valor.modelo.assunto || valor.modelo.mensagem || valor.modelo.anexos || valor.modelo.copia)}
            resumo={
              <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                Mudar o texto do e-mail deste tomador
                <span className="ml-2 text-xs font-normal text-slate-400">assunto, mensagem, anexos e cópia</span>
              </summary>
            }
          >
            <div className="border-t border-slate-200 p-4 dark:border-slate-700">
              <EditorModeloEmail
                valor={valor.modelo}
                onChange={(v) => mudar({ modelo: v })}
                herdado={{
                  assunto: prestador?.email_assunto_padrao,
                  mensagem: prestador?.email_mensagem_padrao,
                  anexos: prestador?.email_anexos_padrao ?? null,
                  rotulo: "o modelo padrão de Empresa › E-mails",
                }}
                mostrarCopia
                rotuloCopia="Cópia (recebem o mesmo e-mail)"
                dicaCopia={
                  prestador?.email_copia_padrao
                    ? `Além destes, vai cópia pra ${prestador.email_copia_padrao} (Empresa › E-mails).`
                    : "Quem está em cópia recebe o mesmo e-mail do tomador."
                }
              />
            </div>
          </Detalhes>

          <div className="mt-5 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Outras pessoas que recebem esta nota</p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              Contador, sócio, o seu próprio e-mail... Cada um recebe um e-mail separado — e você pode escrever um texto diferente pra cada
              um (em branco, vai o mesmo do tomador).
            </p>
            <ul className="mt-3 flex flex-col gap-3">
              {valor.extras.map((extra, i) => (
                <li key={i} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                  <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
                    <Field label="Quem é" value={extra.rotulo ?? ""} onChange={(e) => mudarExtra(i, { rotulo: e.target.value })} placeholder="Contador" maxLength={60} />
                    <Field label="E-mail" value={extra.email} onChange={(e) => mudarExtra(i, { email: e.target.value })} placeholder="contador@escritorio.com" maxLength={200} />
                    <button
                      type="button"
                      aria-label={`Tirar ${extra.rotulo || extra.email || "destinatário"}`}
                      title="Tirar"
                      onClick={() => mudar({ extras: valor.extras.filter((_, j) => j !== i) })}
                      className="mb-0.5 rounded-lg p-2 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <Detalhes
                    className="mt-2"
                    abertoDeInicio={Boolean(extra.assunto || extra.mensagem)}
                    resumo={
                      <summary className="cursor-pointer select-none text-xs font-semibold text-primary-600 hover:underline dark:text-primary-300">
                        Escrever um e-mail diferente pra {extra.rotulo?.trim() || "esta pessoa"}
                      </summary>
                    }
                  >
                    <div className="mt-3">
                      <EditorModeloEmail
                        valor={{ assunto: extra.assunto ?? "", mensagem: extra.mensagem ?? "", anexos: extra.anexos ?? "" }}
                        onChange={(v) => mudarExtra(i, { assunto: v.assunto, mensagem: v.mensagem, anexos: v.anexos || null })}
                        herdado={{
                          assunto: valor.modelo.assunto || prestador?.email_assunto_padrao,
                          mensagem: valor.modelo.mensagem || prestador?.email_mensagem_padrao,
                          anexos: valor.modelo.anexos || prestador?.email_anexos_padrao || null,
                          rotulo: "o mesmo e-mail do tomador",
                        }}
                      />
                    </div>
                  </Detalhes>
                </li>
              ))}
            </ul>
            {valor.extras.length < MAXIMO_EXTRAS && (
              <button
                type="button"
                onClick={() => mudar({ extras: [...valor.extras, { email: "", rotulo: valor.extras.length === 0 ? "Contador" : "" }] })}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-dashed border-primary-300 px-3 py-1.5 text-sm font-medium text-primary-700 hover:bg-primary-50 dark:border-primary-700 dark:text-primary-300 dark:hover:bg-primary-900/30"
              >
                <Plus size={15} /> Adicionar pessoa
              </button>
            )}
          </div>
        </>
      )}
    </>
  )
}
