import { BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ChevronDown,
  DownloadCloud,
  Eraser,
  FileBadge,
  FlaskConical,
  LayoutGrid,
  Mail,
  MailPlus,
  Percent,
  Plug,
  ReceiptText,
  ShieldAlert,
  Trash2,
  UploadCloud,
} from "lucide-react"
import { type FormEvent, type ReactNode, type SelectHTMLAttributes, useEffect, useState } from "react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { CHAMADA_NACIONAL, useEmpresaVazia } from "../components/ComecarPeloNacional"
import { EditorModeloEmail, type ValorModeloEmail } from "../components/EditorModeloEmail"
import { ContadorCard } from "../components/ContadorCard"
import { Integracoes } from "../components/integracoes/Integracoes"
import { ImportacoesFeitas } from "../components/ImportacoesFeitas"
import { ImportarEmissorModal } from "../components/ImportarEmissorModal"
import { PaginaAbas, TituloSecao } from "../components/PaginaAbas"
import { avisarEmpresaAtualizada } from "../components/TrocaEmpresa"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { CampoCidade } from "../components/ui/CampoCidade"
import { CampoPercentual } from "../components/ui/CampoPercentual"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { Modal } from "../components/ui/Modal"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { ehContador } from "../lib/contador"
import { formatarDocumento, mascararCep, soDigitos } from "../lib/documento"
import { type Modulo, useModulos } from "../lib/modulos"
import { excluirComConfirmacao, mensagemDeErro } from "../lib/excluir"
import type { CertificadoStatus, EmitenteAtualizarRequest, Prestador } from "../lib/types"

// "Empresa" (29/09/2026) — tudo que é do CNPJ ativo: dados do emitente,
// e-mails da nota, alíquota, ambiente, certificado e limpeza/exclusão.
// Substitui a antiga tela única de Configurações (a parte da pessoa foi
// pra Minha conta).

function erroDe(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo."
}

type AoAtualizar = (p: Prestador) => void

// Atalhos antigos por âncora (ex.: "Precisa da sua atenção" → #aliquota)
// escolhem a aba certa e continuam rolando/destacando a seção.
const ABA_DA_ANCORA: Record<string, string> = {
  certificado: "certificado",
  aliquota: "emitente",
  ambiente: "notas",
  "email-nota": "notas",
  "emails-gerais": "notas",
  importacoes: "notas",
  limpar: "mais",
}

// 07/10/2026 — "precisamos simplificar o menu empresa": eram oito abas, são
// cinco. Os links antigos (?aba=aliquotas, ?aba=emails...) continuam valendo:
// caem na aba nova, já na seção certa.
const ABA_ANTIGA: Record<string, { aba: string; ancora?: string }> = {
  aliquotas: { aba: "emitente", ancora: "aliquota" },
  emails: { aba: "notas", ancora: "email-nota" },
  modulos: { aba: "mais" },
  dados: { aba: "mais", ancora: "limpar" },
}

export function EmpresaPage() {
  const [prestador, setPrestador] = useState<Prestador | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const location = useLocation()
  const [params] = useSearchParams()
  const navigate = useNavigate()

  const modulos = useModulos()
  const { usuario } = useAuth()
  useEffect(() => {
    api
      .get<Prestador>("/prestador")
      .then(setPrestador)
      .catch((err) => setErro(erroDe(err)))
  }, [])

  // Âncora sem ?aba= → escolhe a aba da seção (mantendo a âncora).
  const ancora = location.hash.slice(1)
  const abaPedida = params.get("aba")
  useEffect(() => {
    const antiga = abaPedida ? ABA_ANTIGA[abaPedida] : undefined
    if (antiga) {
      const destino = ancora || antiga.ancora
      navigate({ search: `?aba=${antiga.aba}`, hash: destino ? `#${destino}` : "" }, { replace: true })
      return
    }
    const aba = ABA_DA_ANCORA[ancora]
    if (aba && !abaPedida) navigate({ search: `?aba=${aba}`, hash: `#${ancora}` }, { replace: true })
  }, [ancora, abaPedida, navigate])
  // Os padrões de e-mail ficam recolhidos; quem chega por um atalho deles já vê aberto.
  const abrirEmails = ancora === "email-nota" || ancora === "emails-gerais"

  // Rola até a seção e destaca por alguns segundos (o React Router não faz
  // isso sozinho com âncoras).
  const carregado = prestador !== null
  useEffect(() => {
    if (!carregado || !ancora) return
    const t0 = setTimeout(() => {
      const alvo = document.getElementById(ancora)
      if (!alvo) return
      alvo.scrollIntoView({ behavior: "smooth", block: "center" })
      alvo.classList.add("ring-2", "ring-primary-400")
      alvo.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true })
      setTimeout(() => alvo.classList.remove("ring-2", "ring-primary-400"), 2500)
    }, 50)
    return () => clearTimeout(t0)
  }, [carregado, ancora, abaPedida])

  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>
  if (!prestador) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>

  const nome = prestador.nome_fantasia?.trim() || prestador.razao_social
  // Abas do emissor (e-mails da nota, alíquotas, ambiente, certificado) só
  // pra quem tem o módulo de notas.
  const soEmissor = <T,>(aba: T): T[] => (modulos.emissor ? [aba] : [])
  const contador = ehContador(usuario)

  return (
    <PaginaAbas
      titulo="Empresa"
      subtitulo={
        <>
          <span className="font-medium text-slate-700 dark:text-slate-300">{nome}</span> · CNPJ {formatarDocumento(prestador.cpf_cnpj)}
        </>
      }
      abas={[
        {
          id: "emitente",
          rotulo: "Dados da empresa",
          icone: Building2,
          conteudo: () => (
            <>
              <AbaEmitente prestador={prestador} onAtualizado={setPrestador} />
              {modulos.emissor && <AliquotaCard prestador={prestador} onAtualizado={setPrestador} />}
            </>
          ),
        },
        ...soEmissor({
          id: "notas",
          rotulo: "Notas e e-mails",
          icone: ReceiptText,
          conteudo: () => (
            <>
              <AmbienteNotasCard prestador={prestador} onAtualizado={setPrestador} />
              <ImportarNacionalCard />
              <div id="importacoes" className="scroll-mt-24 rounded-xl transition-shadow empty:hidden">
                <ImportacoesFeitas origem="nacional" />
              </div>
              {/* 07/10/2026: cada tomador tem o seu e-mail; aqui é só o padrão, opcional — por isso fica recolhido. */}
              <details open={abrirEmails} className="group rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 [&::-webkit-details-marker]:hidden">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                      <Mail size={16} className="text-slate-400" aria-hidden /> Padrões de e-mail
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300">opcional</span>
                    </span>
                    <span className="mt-0.5 block text-sm text-slate-500 dark:text-slate-400">
                      O e-mail de cada tomador você define no cadastro dele. Aqui é só o ponto de partida pra quem ainda não tem o seu.
                    </span>
                  </span>
                  <ChevronDown size={18} className="shrink-0 text-slate-400 transition-transform group-open:rotate-180" aria-hidden />
                </summary>
                <div className="flex flex-col gap-6 border-t border-slate-100 p-5 dark:border-slate-700">
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    Pra quem vai, assunto e mensagem de cada tomador ficam em{" "}
                    <Link to="/app/tomadores" className="font-medium text-primary-700 underline dark:text-primary-300">Tomadores</Link>.
                  </p>
                  <ModeloEmailCard prestador={prestador} onAtualizado={setPrestador} />
                  <EmailsGeraisCard prestador={prestador} onAtualizado={setPrestador} />
                </div>
              </details>
            </>
          ),
        }),
        ...soEmissor({ id: "certificado", rotulo: "Certificado", icone: FileBadge, conteudo: () => <CertificadoCard /> }),
        // Integrações (08/10/2026): Drive, Google Agenda e (em breve) WhatsApp.
        { id: "integracoes", rotulo: "Integrações", icone: Plug, conteudo: () => <Integracoes /> },
        // Contador (06/10/2026): quem mais entra na empresa e o que pode fazer.
        { id: "contador", rotulo: "Contador", icone: BriefcaseBusiness, conteudo: () => <ContadorCard /> },
        // Módulos e exclusão são só do dono: o contador nem vê a aba.
        ...(contador ? [] : [
          {
            id: "mais",
            rotulo: "Mais opções",
            icone: LayoutGrid,
            conteudo: () => (
              <>
                <ModulosCard />
                <div id="limpar" className="scroll-mt-24 flex flex-col gap-6 rounded-xl transition-shadow">
                  <AbaDados prestador={prestador} />
                </div>
              </>
            ),
          },
        ]),
      ]}
    />
  )
}

// --- Emitente ---------------------------------------------------------------

const classeSelect =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

function CampoSelect({ label, hint, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <select className={classeSelect} {...props}>
        {children}
      </select>
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  )
}

const OPCOES_SIMPLES = [
  { valor: "1", rotulo: "Não optante" },
  { valor: "2", rotulo: "MEI" },
  { valor: "3", rotulo: "ME/EPP (Simples Nacional)" },
] as const

const OPCOES_APURACAO = [
  { valor: "1", rotulo: "Tributos federais e municipal pelo Simples Nacional" },
  { valor: "2", rotulo: "Federais pelo Simples Nacional e ISSQN fora dele" },
  { valor: "3", rotulo: "Federais e municipal fora do Simples Nacional" },
] as const

const OPCOES_REGIME_ESPECIAL = [
  { valor: "0", rotulo: "Nenhum" },
  { valor: "1", rotulo: "Ato cooperado" },
  { valor: "2", rotulo: "Estimativa" },
  { valor: "3", rotulo: "Microempresa municipal" },
  { valor: "4", rotulo: "Notário ou registrador" },
  { valor: "5", rotulo: "Profissional autônomo" },
  { valor: "6", rotulo: "Sociedade de profissionais" },
] as const

function AbaEmitente({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: AoAtualizar }) {
  const inicial = (p: Prestador = prestador) => ({
    razao_social: p.razao_social ?? "",
    nome_fantasia: p.nome_fantasia ?? "",
    inscricao_municipal: p.inscricao_municipal ?? "",
    email: p.email ?? "",
    telefone: p.telefone ?? "",
    cep: mascararCep(p.cep ?? ""),
    logradouro: p.logradouro ?? "",
    numero: p.numero ?? "",
    complemento: p.complemento ?? "",
    bairro: p.bairro ?? "",
    cod_municipio: p.cod_municipio ?? "",
    op_simples_nacional: p.op_simples_nacional ?? "",
    regime_apuracao_sn: p.regime_apuracao_sn ?? "",
    regime_especial_trib: p.regime_especial_trib ?? "0",
  })
  const [f, setF] = useState(inicial)
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)

  const campo = (chave: keyof ReturnType<typeof inicial>) => ({
    value: f[chave],
    onChange: (e: { target: { value: string } }) => setF((atual) => ({ ...atual, [chave]: e.target.value })),
  })

  // "Sobre o completar os dados da empresa, falei para puxarmos pelo CNPJ"
  // (07/10/2026): a Receita preenche o que estiver em branco.
  const temCnpj = soDigitos(prestador.cpf_cnpj).length === 14
  const [buscando, setBuscando] = useState(false)
  const [receita, setReceita] = useState<{ ok: boolean; texto: string } | null>(null)
  async function preencherPeloCnpj() {
    setBuscando(true)
    setReceita(null)
    try {
      const r = await api.post<{ preenchidos: string[]; faltam: { rotulo: string }[] }>("/prestador/completar-pelo-cnpj", {})
      const novo = await api.get<Prestador>("/prestador")
      onAtualizado(novo)
      setF(inicial(novo))
      avisarEmpresaAtualizada()
      const falta = r.faltam.length ? ` Ainda falta: ${r.faltam.map((x) => x.rotulo).join("; ")}.` : ""
      setReceita({
        ok: true,
        texto: r.preenchidos.length
          ? `Preenchi pela Receita: ${r.preenchidos.join(", ")}. Confira e ajuste o que precisar.${falta}`
          : `Não tinha nada em branco que a Receita soubesse preencher.${falta}`,
      })
    } catch (err) {
      setReceita({ ok: false, texto: erroDe(err) })
    } finally {
      setBuscando(false)
    }
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!f.cod_municipio) {
      setMsg({ ok: false, texto: "Escolha a cidade da empresa na lista." })
      return
    }
    setSalvando(true)
    const corpo: EmitenteAtualizarRequest = {
      razao_social: f.razao_social.trim(),
      nome_fantasia: f.nome_fantasia.trim() || null,
      inscricao_municipal: f.inscricao_municipal.trim() || null,
      email: f.email.trim() || null,
      telefone: f.telefone.trim() || null,
      cep: soDigitos(f.cep) || null,
      logradouro: f.logradouro.trim() || null,
      numero: f.numero.trim() || null,
      complemento: f.complemento.trim() || null,
      bairro: f.bairro.trim() || null,
      cod_municipio: f.cod_municipio,
      regime_especial_trib: f.regime_especial_trib || "0",
    }
    if (f.op_simples_nacional) corpo.op_simples_nacional = f.op_simples_nacional as "1" | "2" | "3"
    if (f.op_simples_nacional === "3" && f.regime_apuracao_sn) corpo.regime_apuracao_sn = f.regime_apuracao_sn as "1" | "2" | "3"
    try {
      const p = await api.patch<Prestador>("/prestador", corpo)
      onAtualizado(p)
      avisarEmpresaAtualizada()
      setMsg({ ok: true, texto: "Dados salvos." })
    } catch (err) {
      setMsg({ ok: false, texto: erroDe(err) })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form onSubmit={salvar} className="flex flex-col gap-6">
      {temCnpj && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-200 bg-primary-50/60 px-4 py-3 dark:border-primary-800 dark:bg-primary-900/20">
          <p className="min-w-0 flex-1 basis-64 text-sm text-slate-700 dark:text-slate-200">
            <strong className="font-semibold">Não precisa digitar tudo.</strong> Eu busco na Receita, pelo CNPJ, o endereço e o regime da
            empresa e preencho só o que estiver em branco.
          </p>
          <Button type="button" variant="primary" onClick={() => void preencherPeloCnpj()} disabled={buscando || salvando}>
            <DownloadCloud size={16} aria-hidden /> {buscando ? "Buscando na Receita..." : "Preencher pelo CNPJ"}
          </Button>
          {receita && (
            <p role="status" className={`basis-full text-sm ${receita.ok ? "text-success-700 dark:text-success-300" : "text-danger-600"}`}>
              {receita.texto}
            </p>
          )}
        </div>
      )}
      <Card className="p-5">
        <TituloSecao icone={Building2}>Identificação</TituloSecao>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Como a empresa aparece nas notas que você emite.</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Razão social" required maxLength={200} {...campo("razao_social")} />
          </div>
          <Field label="Nome fantasia" maxLength={200} hint="Opcional. Aparece no seletor de empresas." {...campo("nome_fantasia")} />
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">CNPJ</span>
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
              {formatarDocumento(prestador.cpf_cnpj)}
            </p>
            <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">Não muda — outro CNPJ é outra empresa.</span>
          </div>
          <Field label="Inscrição municipal" maxLength={30} inputMode="numeric" {...campo("inscricao_municipal")} />
          <Field label="E-mail da empresa" type="email" maxLength={200} {...campo("email")} />
          <Field label="Telefone" type="tel" maxLength={20} autoComplete="tel" {...campo("telefone")} />
        </div>
      </Card>

      <Card className="p-5">
        <TituloSecao>Endereço</TituloSecao>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-6">
          <div className="sm:col-span-2">
            <Field
              label="CEP"
              inputMode="numeric"
              placeholder="00000-000"
              value={f.cep}
              onChange={(e) => setF((a) => ({ ...a, cep: mascararCep(e.target.value) }))}
            />
          </div>
          <div className="sm:col-span-4">
            <Field label="Logradouro" maxLength={200} {...campo("logradouro")} />
          </div>
          <div className="sm:col-span-2">
            <Field label="Número" maxLength={20} {...campo("numero")} />
          </div>
          <div className="sm:col-span-4">
            <Field label="Complemento" maxLength={100} {...campo("complemento")} />
          </div>
          <div className="sm:col-span-3">
            <Field label="Bairro" maxLength={100} {...campo("bairro")} />
          </div>
          <div className="sm:col-span-3">
            <CampoCidade label="Município" required codigo={f.cod_municipio} onChange={(c) => setF((a) => ({ ...a, cod_municipio: c }))} />
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <TituloSecao>Regime tributário</TituloSecao>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Vai em toda nota. Na dúvida, confirme com seu contador.</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <CampoSelect label="Simples Nacional" {...campo("op_simples_nacional")}>
            <option value="" disabled>
              Selecione...
            </option>
            {OPCOES_SIMPLES.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </CampoSelect>
          <CampoSelect label="Regime especial de tributação" {...campo("regime_especial_trib")}>
            {OPCOES_REGIME_ESPECIAL.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </CampoSelect>
          {f.op_simples_nacional === "3" && (
            <div className="sm:col-span-2">
              <CampoSelect label="Como os tributos são apurados" hint="Só vale para ME/EPP optante do Simples Nacional." {...campo("regime_apuracao_sn")}>
                <option value="" disabled>
                  Selecione...
                </option>
                {OPCOES_APURACAO.map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.rotulo}
                  </option>
                ))}
              </CampoSelect>
            </div>
          )}
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="accent" disabled={salvando}>
          {salvando ? "Salvando..." : "Salvar dados do emitente"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setF(inicial())} disabled={salvando}>
          Desfazer alterações
        </Button>
        {msg && (
          <span role="status" className={`text-sm ${msg.ok ? "text-success-700" : "text-danger-600"}`}>
            {msg.texto}
          </span>
        )}
      </div>
    </form>
  )
}

// --- E-mails ----------------------------------------------------------------

function ModeloEmailCard({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: AoAtualizar }) {
  const inicial = (): ValorModeloEmail => ({
    assunto: prestador.email_assunto_padrao ?? "",
    mensagem: prestador.email_mensagem_padrao ?? "",
    anexos: prestador.email_anexos_padrao ?? "",
    copia: prestador.email_copia_padrao ?? "",
  })
  const [valor, setValor] = useState<ValorModeloEmail>(inicial)
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)
  async function salvar() {
    setSalvando(true)
    setMsg(null)
    try {
      const p = await api.patch<Prestador>("/prestador/preferencias", {
        email_assunto_padrao: valor.assunto,
        email_mensagem_padrao: valor.mensagem,
        email_anexos_padrao: valor.anexos || "pdf_xml",
        email_copia_padrao: valor.copia ?? "",
      })
      onAtualizado(p)
      setMsg({ ok: true, texto: "Modelo salvo." })
    } catch (err) {
      setMsg({ ok: false, texto: erroDe(err) })
    } finally {
      setSalvando(false)
    }
  }
  return (
    <Card id="email-nota" className="scroll-mt-24 p-5 transition-shadow">
      <TituloSecao icone={Mail}>E-mail para o tomador</TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        O e-mail que vai pro tomador junto com a nota. Se algum tomador pedir um assunto ou texto diferente, ajuste na ficha
        dele (Tomadores › editar).
      </p>
      <EditorModeloEmail
        valor={valor}
        onChange={setValor}
        herdado={{ rotulo: "o texto padrão da Ana" }}
        mostrarCopia
        rotuloCopia="Sempre mandar cópia para"
        dicaCopia={`Vai em todo e-mail de nota — ex.: o seu próprio${prestador.email ? ` (${prestador.email})` : ""}.`}
      />
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button type="button" variant="accent" onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando..." : "Salvar modelo"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setValor({ ...valor, assunto: "", mensagem: "", anexos: "" })}>
          Voltar ao texto padrão
        </Button>
        {msg && (
          <span role="status" className={`text-xs ${msg.ok ? "text-success-700" : "text-danger-600"}`}>
            {msg.texto}
          </span>
        )}
      </div>
    </Card>
  )
}

// Mesmo texto de sempre do backend (app/services/mensagens.py,
// ASSUNTO_GERAL_PADRAO / MENSAGEM_GERAL_PADRAO) — só pra mostrar como fica
// quando os campos ficam em branco.
const ASSUNTO_GERAL_PADRAO = "NFS-e {numero_nota} — {razao_social_tomador} — {competencia}"
const MENSAGEM_GERAL_PADRAO = `Olá!

Segue a nota fiscal de serviço emitida por {prestador} para {razao_social_tomador}.

Competência: {competencia}
Valor: {valor}
Referente a: {descricao}

A nota está em anexo e também pode ser baixada aqui: {link}

{prestador}`

const RE_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function separarEmails(texto: string): { validos: string[]; invalidos: string[] } {
  const partes = texto
    .split(/[,;\s]+/)
    .map((p) => p.trim())
    .filter(Boolean)
  const validos: string[] = []
  const invalidos: string[] = []
  for (const p of partes) {
    const e = p.toLowerCase()
    if (RE_EMAIL.test(e)) {
      if (!validos.includes(e)) validos.push(e)
    } else invalidos.push(p)
  }
  return { validos, invalidos }
}

function EmailsGeraisCard({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: AoAtualizar }) {
  const [para, setPara] = useState(prestador.email_geral_para ?? "")
  const [valor, setValor] = useState<ValorModeloEmail>(() => ({
    assunto: prestador.email_geral_assunto ?? "",
    mensagem: prestador.email_geral_mensagem ?? "",
    anexos: prestador.email_geral_anexos ?? "",
  }))
  const [salvando, setSalvando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null)
  const { validos, invalidos } = separarEmails(para)

  async function salvar() {
    setMsg(null)
    if (invalidos.length) {
      setMsg({ ok: false, texto: `Confira: ${invalidos.join(", ")} não parece e-mail.` })
      return
    }
    setSalvando(true)
    try {
      const p = await api.patch<Prestador>("/prestador/preferencias", {
        email_geral_para: validos.join(", "),
        email_geral_assunto: valor.assunto,
        email_geral_mensagem: valor.mensagem,
        email_geral_anexos: valor.anexos || "pdf_xml",
      })
      onAtualizado(p)
      setPara(p.email_geral_para ?? "")
      setMsg({ ok: true, texto: "E-mails gerais salvos." })
    } catch (err) {
      setMsg({ ok: false, texto: erroDe(err) })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card id="emails-gerais" className="scroll-mt-24 p-5 transition-shadow">
      <TituloSecao icone={MailPlus}>E-mails gerais</TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Cada tomador recebe a nota de um jeito. Aqui você cadastra e-mails que recebem <strong>todas</strong> as notas (seu
        contador, você mesmo), com um texto próprio.
      </p>

      <label className="mb-4 flex flex-col gap-1 text-sm font-medium text-slate-700 dark:text-slate-300">
        Para
        <input
          value={para}
          onChange={(e) => setPara(e.target.value)}
          placeholder="contador@escritorio.com.br; voce@empresa.com"
          maxLength={400}
          autoComplete="off"
          aria-invalid={invalidos.length > 0}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
        <span className="text-xs font-normal text-slate-400">Separe vários com ponto e vírgula ou vírgula. Vazio = ninguém recebe.</span>
      </label>
      {(validos.length > 0 || invalidos.length > 0) && (
        <div className="-mt-2 mb-4 flex flex-wrap gap-1.5" aria-live="polite">
          {validos.map((e) => (
            <span key={e} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-200">
              {e}
            </span>
          ))}
          {invalidos.map((e) => (
            <span key={e} className="rounded-full bg-danger-50 px-2.5 py-0.5 text-xs text-danger-700 dark:bg-danger-900/40 dark:text-danger-300">
              {e} — inválido
            </span>
          ))}
        </div>
      )}

      <EditorModeloEmail
        valor={valor}
        onChange={setValor}
        herdado={{ assunto: ASSUNTO_GERAL_PADRAO, mensagem: MENSAGEM_GERAL_PADRAO, rotulo: "o texto padrão dos e-mails gerais" }}
      />
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button type="button" variant="accent" onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando..." : "Salvar e-mails gerais"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setValor({ assunto: "", mensagem: "", anexos: "" })}>
          Voltar ao texto padrão
        </Button>
        {msg && (
          <span role="status" className={`text-xs ${msg.ok ? "text-success-700" : "text-danger-600"}`}>
            {msg.texto}
          </span>
        )}
      </div>
    </Card>
  )
}

// --- Alíquotas --------------------------------------------------------------

function AliquotaCard({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: AoAtualizar }) {
  const [aliquota, setAliquota] = useState<number | null>(prestador.aliquota_atual)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  const confirmadaEsteMes = (() => {
    if (!prestador.aliquota_atualizada_em) return false
    const hoje = new Date()
    const data = new Date(`${prestador.aliquota_atualizada_em}T00:00:00`)
    return data.getFullYear() === hoje.getFullYear() && data.getMonth() === hoje.getMonth()
  })()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setSucesso(false)
    const numero = aliquota
    if (numero == null || numero < 0 || numero > 100) {
      setErro("Informe um percentual entre 0 e 100.")
      return
    }
    setEnviando(true)
    try {
      const atualizado = await api.patch<Prestador>("/prestador/aliquota", { aliquota: numero })
      onAtualizado(atualizado)
      setSucesso(true)
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card id="aliquota" className="scroll-mt-24 p-5 transition-shadow">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <TituloSecao icone={Percent}>Alíquota do Simples Nacional (referência)</TituloSecao>
        {confirmadaEsteMes ? (
          <Badge variant="success">Confirmada este mês</Badge>
        ) : (
          <Badge variant="warning">{prestador.aliquota_atual == null ? "Não definida" : "Revisar este mês"}</Badge>
        )}
      </div>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Usada só pra pré-preencher o campo de alíquota ao criar uma nova nota — não calcula nem gera boleto de imposto, é só pra
        você não esquecer de conferir o número todo mês (ver lembrete no calendário).
      </p>
      {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {sucesso && <p className="mb-3 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">Alíquota confirmada.</p>}
      <form onSubmit={onSubmit} className="flex max-w-md items-end gap-3">
        <div className="flex-1">
          <CampoPercentual label="Alíquota (%)" required valor={aliquota} onChange={setAliquota} />
        </div>
        <Button type="submit" variant="accent" disabled={enviando}>
          {enviando ? "Salvando..." : "Confirmar"}
        </Button>
      </form>
      {prestador.aliquota_atualizada_em && (
        <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
          Última confirmação: {new Date(`${prestador.aliquota_atualizada_em}T00:00:00`).toLocaleDateString("pt-BR")}
        </p>
      )}
    </Card>
  )
}

// --- Notas (ambiente) -------------------------------------------------------

// "Troque isso de produção e homologação" (28/09/2026): saiu da tela de gerar
// nota e virou uma chave da conta. Padrão: produção (notas de verdade).
function AmbienteNotasCard({ prestador, onAtualizado }: { prestador: Prestador; onAtualizado: AoAtualizar }) {
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const teste = prestador.tp_amb_padrao === "2"
  async function mudar(valor: "1" | "2") {
    setSalvando(true)
    setErro(null)
    try {
      onAtualizado(await api.patch<Prestador>("/prestador/preferencias", { tp_amb_padrao: valor }))
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setSalvando(false)
    }
  }
  return (
    <Card id="ambiente" className="scroll-mt-24 p-5 transition-shadow">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <TituloSecao icone={FlaskConical}>Ambiente das notas</TituloSecao>
        {teste ? <Badge variant="warning">Teste (homologação)</Badge> : <Badge variant="success">Produção</Badge>}
      </div>
      {prestador.modo_teste ? (
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Esta é uma <strong>conta de teste</strong>: as notas saem sempre em homologação (ambiente de teste da Receita) e não valem como
          nota fiscal. Os e-mails de nota vão só pro e-mail desta conta.
        </p>
      ) : (
      <label className="flex items-start gap-3 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={teste}
          disabled={salvando}
          onChange={(e) => mudar(e.target.checked ? "2" : "1")}
          className="mt-0.5 rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
        />
        <span>
          Gerar notas de teste (homologação)
          <span className="block text-xs text-slate-400 dark:text-slate-500">
            {teste
              ? "Ligado: as notas novas vão pro ambiente de teste da Receita e não valem como nota fiscal."
              : "Desligado: as notas novas são de verdade (produção). Ligue só pra testar."}
          </span>
        </span>
      </label>
      )}
      {erro && <p className="mt-2 text-xs text-danger-600">{erro}</p>}
    </Card>
  )
}

// --- Certificado ------------------------------------------------------------

/** Trazer as notas já emitidas no Emissor Nacional (saiu do topo da tela
 * NFS-e em 05/10/2026: usa-se uma vez, ao começar, e de vez em quando). */
function ImportarNacionalCard() {
  // Empresa ainda sem tomador nem nota: a importação é o jeito fácil de
  // começar (com o certificado, num passo a passo curto).
  const vazia = useEmpresaVazia()
  const [comecando, setComecando] = useState(false)
  if (vazia) {
    return (
      <Card className="border-primary-200 bg-primary-50/60 p-6 dark:border-primary-800 dark:bg-primary-900/20">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-primary-700 dark:text-primary-300">
          <DownloadCloud size={16} /> Importar do Emissor Nacional
        </h2>
        <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{CHAMADA_NACIONAL}</p>
        <p className="mb-4 mt-1 text-sm text-slate-600 dark:text-slate-300">
          Com o certificado digital (A1) da empresa eu leio as notas que ela já emitiu e <strong>você escolhe de quais tomadores trazer</strong>{" "}
          — já vêm marcados só os pré-cadastrados. É só leitura: nada é enviado a ninguém.
        </p>
        <Button type="button" variant="accent" onClick={() => setComecando(true)}>
          <DownloadCloud size={16} /> Trazer do Emissor Nacional
        </Button>
        {comecando && <ImportarEmissorModal modo="atual" onFechar={() => setComecando(false)} />}
      </Card>
    )
  }
  return (
    <Card className="p-6">
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        <DownloadCloud size={16} /> Importar do Emissor Nacional
      </h2>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Traga pra Ana as notas que você já emitiu no Emissor Nacional (ou por outro sistema): elas entram na lista de NFS-e e os
        tomadores já ficam cadastrados.
      </p>
      <Link
        to="/app/nfse?importar=1"
        className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        <DownloadCloud size={16} /> Importar notas
      </Link>
    </Card>
  )
}

function CertificadoCard() {
  const [certificado, setCertificado] = useState<CertificadoStatus | null>(null)
  const [erroCarga, setErroCarga] = useState<string | null>(null)
  const [pfx, setPfx] = useState<File | null>(null)
  const [chaveArquivo, setChaveArquivo] = useState(0)
  const [senha, setSenha] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  useEffect(() => {
    api
      .get<CertificadoStatus>("/certificado/status")
      .then(setCertificado)
      .catch((err) => setErroCarga(erroDe(err)))
  }, [])

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!pfx) return
    setErro(null)
    setSucesso(false)
    setEnviando(true)
    try {
      const form = new FormData()
      form.append("pfx", pfx)
      form.append("senha", senha)
      const status = await api.postForm<CertificadoStatus>("/certificado", form)
      setCertificado(status)
      setPfx(null)
      setSenha("")
      setChaveArquivo((n) => n + 1) // limpa o campo de arquivo (dá pra escolher o mesmo .pfx de novo)
      setSucesso(true)
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card id="certificado" className="scroll-mt-24 p-5 transition-shadow">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <TituloSecao icone={FileBadge}>Certificado digital (A1)</TituloSecao>
        {certificado &&
          (certificado.carregado ? (
            certificado.vencido ? (
              <Badge variant="danger">Vencido</Badge>
            ) : (
              <Badge variant="success">Carregado</Badge>
            )
          ) : (
            <Badge variant="neutral">Nenhum carregado</Badge>
          ))}
      </div>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">É com ele que a Ana assina as notas desta empresa.</p>
      {erroCarga && <p className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroCarga}</p>}

      {certificado?.carregado && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
          {certificado.vencido ? (
            <ShieldAlert size={16} className="text-danger-600" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={16} className="text-success-600" aria-hidden="true" />
          )}
          {certificado.validade
            ? `Validade: ${new Date(`${certificado.validade}T00:00:00`).toLocaleDateString("pt-BR")}`
            : "Sem data de validade informada."}
        </div>
      )}

      <form onSubmit={enviar} className="flex max-w-md flex-col gap-3">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
        {sucesso && <p className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">Certificado enviado.</p>}
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo .pfx</span>
          <input
            key={chaveArquivo}
            type="file"
            accept=".pfx,.p12,application/x-pkcs12"
            required
            onChange={(e) => setPfx(e.target.files?.[0] ?? null)}
            className="w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200 dark:text-slate-300 dark:file:bg-slate-700 dark:file:text-slate-200"
          />
        </label>
        <Field label="Senha do certificado" type="password" required autoComplete="off" value={senha} onChange={(e) => setSenha(e.target.value)} />
        <div>
          <Button type="submit" variant="accent" disabled={enviando || !pfx}>
            <UploadCloud size={15} /> {enviando ? "Enviando..." : certificado?.carregado ? "Substituir certificado" : "Enviar certificado"}
          </Button>
        </div>
      </form>
    </Card>
  )
}

// --- Limpar e excluir -------------------------------------------------------

function AbaDados({ prestador }: { prestador: Prestador }) {
  const { usuario } = useAuth()
  return (
    <>
      <LimparDadosCard />
      {!usuario?.demo && <ExcluirEmpresaCard prestador={prestador} />}
    </>
  )
}

// Emissor e financeiro são produtos separados (05/10/2026): aqui a empresa
// liga o que usa. Desligar não apaga nada — os dados ficam guardados.
const PRODUTOS: { id: Modulo; nome: string; texto: string }[] = [
  {
    id: "emissor",
    nome: "Notas",
    texto: "Emissão de NFS-e: tomadores, geração, assinatura, envio à prefeitura e ao tomador, calendário de emissão.",
  },
  {
    id: "financeiro",
    nome: "Financeiro",
    texto: "Recebimentos e despesas, contas e rotina do mês, extrato bancário e conciliação.",
  },
]

function ModulosCard() {
  const { lista } = useModulos()
  const { recarregarUsuario } = useAuth()
  const [salvando, setSalvando] = useState<Modulo | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  // Com plano pago, quem define os módulos é o plano (Conta › Assinatura).
  const [peloPlano, setPeloPlano] = useState(false)
  useEffect(() => {
    api
      .get<{ modulos_pelo_plano?: boolean }>("/assinatura")
      .then((a) => setPeloPlano(Boolean(a.modulos_pelo_plano)))
      .catch(() => undefined)
  }, [])

  async function alternar(id: Modulo) {
    const novos = lista.includes(id) ? lista.filter((m) => m !== id) : [...lista, id]
    if (novos.length === 0) {
      setErro("Pelo menos um módulo precisa ficar ligado.")
      return
    }
    setErro(null)
    setSalvando(id)
    try {
      await api.put("/empresa/modulos", { modulos: novos })
      await recarregarUsuario()
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setSalvando(null)
    }
  }

  return (
    <Card className="p-5">
      <TituloSecao icone={LayoutGrid}>Módulos desta empresa</TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Cada módulo é um produto à parte, com o menu e as telas dele. Desligar um módulo só esconde: nada é apagado, e tudo volta
        quando ele for ligado de novo.
      </p>
      {erro && <p className="mb-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {peloPlano && (
        <p className="mb-3 rounded-lg bg-primary-50 px-4 py-3 text-sm text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
          Os módulos desta empresa vêm do plano que você assina. Pra ligar ou desligar um módulo,{" "}
          <Link to="/app/conta?aba=assinatura" className="font-semibold underline">
            mude o plano em Conta › Assinatura
          </Link>
          .
        </p>
      )}
      <div className="flex flex-col gap-2">
        {PRODUTOS.map((p) => {
          const ligado = lista.includes(p.id)
          return (
            <label key={p.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-4 py-3 dark:border-slate-700">
              <input
                type="checkbox"
                role="switch"
                checked={ligado}
                disabled={salvando !== null || peloPlano}
                onChange={() => alternar(p.id)}
                className="mt-1"
                aria-label={`Módulo ${p.nome}`}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {p.nome}
                  <Badge variant={ligado ? "success" : "neutral"}>{ligado ? "ligado" : "desligado"}</Badge>
                </span>
                <span className="mt-0.5 block text-sm text-slate-500 dark:text-slate-400">{p.texto}</span>
              </span>
            </label>
          )
        })}
      </div>
    </Card>
  )
}

// "Coloque a opção de limpar dados dos tomadores, de NF-e, calendário,
// recebimentos e despesas" (28/09/2026) — POST /api/dados/limpar.
const CATEGORIAS_LIMPEZA = [
  { id: "tomadores", rotulo: "Tomadores", detalhe: "Tomadores com notas já emitidas ficam arquivados (as notas continuam guardadas)." },
  { id: "nfse", rotulo: "Notas (NFS-e)", detalhe: "Só as que nunca foram enviadas à Receita. Notas emitidas de verdade não podem ser apagadas." },
  { id: "calendario", rotulo: "Calendário", detalhe: "Lembretes criados por você e datas ajustadas." },
  { id: "recebimentos", rotulo: "Recebimentos", detalhe: "Todos os pagamentos registrados." },
  { id: "despesas", rotulo: "Despesas", detalhe: "Todas as despesas registradas." },
]

const ROTULOS_RESULTADO: Record<string, string> = {
  tomadores: "tomadores removidos",
  tomadores_arquivados: "arquivados por terem notas",
  nfse: "notas apagadas",
  nfse_mantidas: "notas emitidas mantidas",
  calendario: "itens do calendário",
  recebimentos: "recebimentos",
  despesas: "despesas",
}

const CATEGORIAS_DO_MODULO: Record<string, Modulo> = { nfse: "emissor", recebimentos: "financeiro", despesas: "financeiro" }

function LimparDadosCard() {
  const modulos = useModulos()
  // Só o que é dos módulos que a empresa tem ligados.
  const categorias = CATEGORIAS_LIMPEZA.filter((c) => !CATEGORIAS_DO_MODULO[c.id] || modulos[CATEGORIAS_DO_MODULO[c.id]])
  const [selecionadas, setSelecionadas] = useState<string[]>([])
  const [confirmando, setConfirmando] = useState(false)
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Record<string, number> | null>(null)

  function alternar(id: string) {
    setSelecionadas((atual) => (atual.includes(id) ? atual.filter((c) => c !== id) : [...atual, id]))
  }

  async function limpar() {
    setEnviando(true)
    setErro(null)
    try {
      const resp = await api.post<{ removidos: Record<string, number> }>("/dados/limpar", { categorias: selecionadas, confirmacao: texto })
      setResultado(resp.removidos)
      setSelecionadas([])
      setConfirmando(false)
      setTexto("")
    } catch (err) {
      setErro(erroDe(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card className="p-5" data-tour="config-limpar">
      <TituloSecao icone={Eraser}>Limpar dados</TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Apaga dados desta empresa por categoria — útil pra tirar dados de teste. Não tem como desfazer.
      </p>
      <div className="flex flex-col gap-2">
        {categorias.map((c) => (
          <label key={c.id} className="flex items-start gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700">
            <input type="checkbox" checked={selecionadas.includes(c.id)} onChange={() => alternar(c.id)} className="mt-0.5" />
            <span>
              <span className="font-medium text-slate-800 dark:text-slate-200">{c.rotulo}</span>
              <span className="block text-xs text-slate-400 dark:text-slate-500">{c.detalhe}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <Button type="button" variant="danger" disabled={selecionadas.length === 0} onClick={() => setConfirmando(true)}>
          Limpar selecionados
        </Button>
      </div>
      {resultado && (
        <p role="status" className="mt-3 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">
          Feito:{" "}
          {Object.entries(resultado)
            .map(([k, v]) => `${v} ${ROTULOS_RESULTADO[k] ?? k}`)
            .join(" · ")}
          .
        </p>
      )}

      {confirmando && (
        <Modal titulo="Tem certeza?" onClose={() => setConfirmando(false)}>
          <div className="flex flex-col gap-4 text-sm text-slate-600 dark:text-slate-300">
            <p>
              Você vai apagar:{" "}
              <strong>
                {CATEGORIAS_LIMPEZA.filter((c) => selecionadas.includes(c.id))
                  .map((c) => c.rotulo)
                  .join(", ")}
              </strong>
              . Não tem como desfazer.
            </p>
            <Field label="Digite LIMPAR para confirmar" value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus autoComplete="off" />
            {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-danger-700">{erro}</p>}
            <div className="flex flex-wrap justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setConfirmando(false)}>
                Cancelar
              </Button>
              <Button type="button" variant="danger" disabled={enviando || texto.trim().toUpperCase() !== "LIMPAR"} onClick={limpar}>
                {enviando ? "Apagando..." : "Apagar de vez"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  )
}

function ExcluirEmpresaCard({ prestador }: { prestador: Prestador }) {
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const cnpj = soDigitos(prestador.cpf_cnpj)
  const confere = soDigitos(texto) === cnpj

  function fechar() {
    setAberto(false)
    setTexto("")
    setErro(null)
  }

  async function excluir(e: FormEvent) {
    e.preventDefault()
    if (!confere) return
    setEnviando(true)
    setErro(null)
    try {
      const r = await excluirComConfirmacao<{ ok: boolean; conta_excluida?: boolean }>("/empresa", cnpj)
      // O backend já trocou pra outra empresa do login (ou encerrou a conta,
      // se era a única) — recarrega tudo do zero.
      window.location.assign(r.conta_excluida ? "/entrar" : "/app")
    } catch (err) {
      setErro(mensagemDeErro(err))
      setEnviando(false)
    }
  }

  return (
    <Card className="border-danger-100 p-5 dark:border-danger-900/40">
      <TituloSecao icone={Trash2} perigo>
        Excluir empresa
      </TituloSecao>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        Apaga esta empresa e todo o histórico dela aqui (tomadores, notas, recebimentos, certificado). As notas já emitidas
        continuam válidas na Receita. Se for a única empresa do seu login, a conta é excluída junto.
      </p>
      <Button type="button" variant="danger" onClick={() => setAberto(true)}>
        <Trash2 size={15} /> Excluir esta empresa
      </Button>

      {aberto && (
        <Modal titulo="Excluir esta empresa?" onClose={fechar}>
          <form onSubmit={excluir} className="flex flex-col gap-4 text-sm text-slate-600 dark:text-slate-300">
            <p>
              Você vai apagar <strong>{prestador.nome_fantasia?.trim() || prestador.razao_social}</strong> ({formatarDocumento(cnpj)}) e
              tudo o que está guardado dela. Não tem como desfazer.
            </p>
            <Field
              label="Digite o CNPJ da empresa para confirmar"
              inputMode="numeric"
              autoComplete="off"
              placeholder={formatarDocumento(cnpj)}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              hint="Só os números já bastam."
            />
            {erro && (
              <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-danger-700">
                {erro}
              </p>
            )}
            <div className="flex flex-wrap justify-end gap-3">
              <Button type="button" variant="outline" onClick={fechar}>
                Cancelar
              </Button>
              <Button type="submit" variant="danger" disabled={enviando || !confere}>
                {enviando ? "Excluindo..." : "Excluir empresa de vez"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </Card>
  )
}
