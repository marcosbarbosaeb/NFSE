import { AlertTriangle, ArrowLeft, Building2, Check, CheckCircle2, ChevronsUpDown, DownloadCloud, Loader2, PencilLine, Plus } from "lucide-react"
import { type FormEvent, useCallback, useEffect, useId, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { ApiError, api, formatarErro } from "../lib/api"
import { useAuth } from "../lib/auth"
import { formatarDocumento, mascararCep, mascararCnpj, soDigitos } from "../lib/documento"
import type { ConsultaCnpj, Empresa, EmpresaCriarRequest } from "../lib/types"
import { ImportarEmissorModal } from "./ImportarEmissorModal"
import { Button } from "./ui/Button"
import { CampoCidade } from "./ui/CampoCidade"
import { Field } from "./ui/Field"
import { Modal } from "./ui/Modal"

// Várias empresas no mesmo login (29/09/2026). A empresa ativa aparece no
// topo da barra lateral; trocar recarrega o painel inteiro pra todas as
// telas buscarem os dados da empresa nova.

/** Disparado quando os dados da empresa mudam (ex.: nome fantasia em Empresa › Emitente). */
export const EVENTO_EMPRESA_ATUALIZADA = "agenteana:empresa-atualizada"

export function avisarEmpresaAtualizada() {
  window.dispatchEvent(new Event(EVENTO_EMPRESA_ATUALIZADA))
}

export function nomeEmpresa(e: Pick<Empresa, "nome_fantasia" | "razao_social">): string {
  return e.nome_fantasia?.trim() || e.razao_social
}

export function TrocaEmpresa() {
  const { usuario } = useAuth()
  const [empresas, setEmpresas] = useState<Empresa[] | null>(null)
  const [aberto, setAberto] = useState(false)
  const [adicionando, setAdicionando] = useState(false)
  const [trocando, setTrocando] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const idLista = useId()

  const carregar = useCallback(() => {
    api
      .get<Empresa[]>("/empresas")
      .then(setEmpresas)
      .catch(() => setEmpresas([]))
  }, [])

  useEffect(() => {
    carregar()
    window.addEventListener(EVENTO_EMPRESA_ATUALIZADA, carregar)
    return () => window.removeEventListener(EVENTO_EMPRESA_ATUALIZADA, carregar)
  }, [carregar])

  // Fecha ao clicar fora ou apertar Esc.
  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setAberto(false)
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAberto(false)
        ref.current?.querySelector<HTMLButtonElement>("button")?.focus()
      }
    }
    document.addEventListener("mousedown", fora)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", fora)
      document.removeEventListener("keydown", esc)
    }
  }, [aberto])

  async function ativar(e: Empresa) {
    if (e.ativa) {
      setAberto(false)
      return
    }
    setTrocando(e.id)
    setErro(null)
    try {
      await api.post(`/empresas/${e.id}/ativar`)
      window.location.assign("/app")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
      setTrocando(null)
    }
  }

  const ativa = empresas?.find((e) => e.ativa) ?? empresas?.[0]

  if (empresas === null) {
    return <div className="h-[58px] animate-pulse rounded-xl bg-brand-800/60" aria-hidden="true" />
  }
  if (!ativa) return null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-controls={idLista}
        className="flex w-full items-center gap-3 rounded-xl border border-brand-700/60 bg-brand-800/60 px-3 py-2.5 text-left transition-colors hover:bg-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-accent-300">
          <Building2 size={16} aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block text-[11px] font-medium uppercase tracking-wide text-slate-400">Empresa</span>
          <span className="block truncate text-sm font-medium text-white" title={nomeEmpresa(ativa)}>
            {nomeEmpresa(ativa)}
          </span>
          <span className="block truncate text-xs text-slate-400">{formatarDocumento(ativa.cnpj)}</span>
        </span>
        <ChevronsUpDown size={16} className="shrink-0 text-slate-400" aria-hidden="true" />
      </button>

      {aberto && (
        <div
          id={idLista}
          className="absolute inset-x-0 z-30 mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-slate-700 shadow-xl dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
        >
          <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Suas empresas</p>
          <ul className="max-h-72 overflow-y-auto">
            {empresas.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => ativar(e)}
                  disabled={trocando !== null}
                  aria-current={e.ativa ? "true" : undefined}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none disabled:opacity-60 dark:hover:bg-slate-700/60 dark:focus-visible:bg-slate-700/60"
                >
                  <span className="min-w-0 flex-1 leading-tight">
                    <span className={`block truncate text-sm ${e.ativa ? "font-semibold text-primary-700 dark:text-primary-300" : "font-medium"}`}>
                      {nomeEmpresa(e)}
                    </span>
                    <span className="block text-xs text-slate-400">{formatarDocumento(e.cnpj)}</span>
                  </span>
                  {trocando === e.id ? (
                    <Loader2 size={15} className="shrink-0 animate-spin text-slate-400" aria-label="Trocando" />
                  ) : (
                    e.ativa && <Check size={16} className="shrink-0 text-primary-600 dark:text-primary-400" aria-label="Empresa ativa" />
                  )}
                </button>
              </li>
            ))}
          </ul>
          {erro && <p className="mx-3 my-1 rounded-lg bg-danger-50 px-2 py-1.5 text-xs text-danger-700">{erro}</p>}
          {!usuario?.demo && (
            <>
              <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
              <button
                type="button"
                onClick={() => {
                  setAberto(false)
                  setAdicionando(true)
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium text-primary-700 hover:bg-primary-50 focus-visible:bg-primary-50 focus-visible:outline-none dark:text-primary-300 dark:hover:bg-primary-900/30"
              >
                <Plus size={16} aria-hidden="true" /> Adicionar empresa
              </button>
            </>
          )}
        </div>
      )}

      {/* Portal: a barra lateral tem transform (gaveta do celular), que
          prenderia o modal "fixed" dentro dela. */}
      {adicionando && createPortal(<AdicionarEmpresaModal onFechar={() => setAdicionando(false)} />, document.body)}
    </div>
  )
}

// Dois caminhos pra pôr mais uma empresa no login (05/10/2026): importar do
// Emissor Nacional com o certificado (a Ana traz cadastro, tomadores e notas)
// ou preencher do zero, como sempre foi.
function AdicionarEmpresaModal({ onFechar }: { onFechar: () => void }) {
  const [caminho, setCaminho] = useState<"importar" | "zero" | null>(null)

  if (caminho === "importar") return <ImportarEmissorModal modo="nova" onFechar={onFechar} onVoltar={() => setCaminho(null)} />
  if (caminho === "zero") return <CadastrarDoZeroModal onFechar={onFechar} onVoltar={() => setCaminho(null)} />

  const OPCAO =
    "flex w-full items-start gap-3 rounded-xl border px-4 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
  return (
    <Modal titulo="Adicionar empresa" onClose={onFechar} largura="max-w-xl">
      <div className="flex flex-col gap-3">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Outro CNPJ no mesmo login. Cada empresa tem seus tomadores, notas e certificado. Como você quer começar?
        </p>

        <button
          type="button"
          onClick={() => setCaminho("importar")}
          className={`${OPCAO} border-primary-300 bg-primary-50/60 hover:bg-primary-50 dark:border-primary-700 dark:bg-primary-900/20 dark:hover:bg-primary-900/30`}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-600 text-white">
            <DownloadCloud size={18} aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
              Importar do Emissor Nacional
              <span className="rounded-full bg-accent-500 px-2 py-0.5 text-[11px] font-semibold text-white">recomendado</span>
            </span>
            <span className="mt-0.5 block text-sm text-slate-600 dark:text-slate-300">
              Você escolhe o certificado digital (A1) da empresa e eu trago o cadastro, os tomadores e as notas que ela já emitiu.
            </span>
          </span>
        </button>

        <button
          type="button"
          onClick={() => setCaminho("zero")}
          className={`${OPCAO} border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40`}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            <PencilLine size={18} aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">Cadastrar do zero</span>
            <span className="mt-0.5 block text-sm text-slate-600 dark:text-slate-300">
              Você digita o CNPJ e confere os dados. Tomadores, certificado e notas ficam para depois.
            </span>
          </span>
        </button>

        <div className="flex justify-end">
          <Button type="button" variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function CadastrarDoZeroModal({ onFechar, onVoltar }: { onFechar: () => void; onVoltar: () => void }) {
  const [cnpj, setCnpj] = useState("")
  const [razaoSocial, setRazaoSocial] = useState("")
  const [nomeFantasia, setNomeFantasia] = useState("")
  const [codMunicipio, setCodMunicipio] = useState("")
  const [cep, setCep] = useState("")
  const [logradouro, setLogradouro] = useState("")
  const [numero, setNumero] = useState("")
  const [complemento, setComplemento] = useState("")
  const [bairro, setBairro] = useState("")

  const [consultando, setConsultando] = useState(false)
  const [consultado, setConsultado] = useState<string | null>(null)
  const [resumo, setResumo] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  // Mesma consulta do cadastro (GET /cnpj/{cnpj}) — preenche o que der; tudo
  // continua editável se vier errado ou a consulta falhar.
  async function consultar() {
    const digitos = soDigitos(cnpj)
    if (digitos.length !== 14 || digitos === consultado) return
    setConsultado(digitos)
    setAviso(null)
    setResumo(null)
    setConsultando(true)
    try {
      const d = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      if (d.razao_social) setRazaoSocial(d.razao_social)
      if (d.cod_municipio_sugerido) setCodMunicipio(d.cod_municipio_sugerido)
      setCep(mascararCep(d.cep ?? ""))
      setLogradouro(d.logradouro ?? "")
      setNumero(d.numero ?? "")
      setComplemento(d.complemento ?? "")
      setBairro(d.bairro ?? "")
      setResumo(`${d.municipio}/${d.uf}`)
      if (d.situacao_cadastral && d.situacao_cadastral.toUpperCase() !== "ATIVA") {
        setAviso(`Situação cadastral na Receita: ${d.situacao_cadastral}. Confira se é esse mesmo.`)
      }
    } catch (err) {
      setAviso(
        err instanceof ApiError && err.status === 404
          ? "Não encontramos esse CNPJ — confira os números ou preencha os dados manualmente."
          : "Não deu pra consultar o CNPJ agora — preencha os dados manualmente.",
      )
    } finally {
      setConsultando(false)
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    const digitos = soDigitos(cnpj)
    if (digitos.length !== 14) {
      setErro("Informe os 14 dígitos do CNPJ.")
      return
    }
    if (!codMunicipio) {
      setErro("Escolha a cidade da empresa na lista.")
      return
    }
    setEnviando(true)
    const corpo: EmpresaCriarRequest = {
      cpf_cnpj: digitos,
      razao_social: razaoSocial.trim(),
      nome_fantasia: nomeFantasia.trim() || null,
      cod_municipio: codMunicipio,
      cep: soDigitos(cep) || null,
      logradouro: logradouro.trim() || null,
      numero: numero.trim() || null,
      complemento: complemento.trim() || null,
      bairro: bairro.trim() || null,
    }
    try {
      const nova = await api.post<Empresa>("/empresas", corpo)
      // O backend já deixa a nova ativa nesta sessão; ativar também faz ela
      // abrir primeiro no próximo login.
      await api.post(`/empresas/${nova.id}/ativar`).catch(() => {})
      window.location.assign("/app")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Cadastrar empresa do zero" onClose={onFechar} largura="max-w-xl">
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Outro CNPJ no mesmo login. Cada empresa tem seus tomadores, notas e certificado — você troca entre elas no topo da
          barra lateral.
        </p>

        <div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Field
                label="CNPJ"
                required
                inputMode="numeric"
                autoComplete="off"
                placeholder="00.000.000/0000-00"
                value={cnpj}
                onChange={(e) => setCnpj(mascararCnpj(e.target.value))}
                onBlur={consultar}
              />
            </div>
            <Button type="button" variant="outline" onClick={consultar} disabled={consultando || soDigitos(cnpj).length !== 14}>
              {consultando ? <Loader2 size={15} className="animate-spin" /> : "Buscar"}
            </Button>
          </div>
          <div aria-live="polite">
            {consultando && <p className="mt-1.5 text-xs text-slate-400">Consultando CNPJ...</p>}
            {resumo && !consultando && (
              <p className="mt-1.5 flex items-start gap-1.5 text-xs text-success-700">
                <CheckCircle2 size={13} className="mt-0.5 shrink-0" aria-hidden="true" /> Dados encontrados — {resumo}. Confira abaixo.
              </p>
            )}
            {aviso && !consultando && (
              <p className="mt-1.5 flex items-start gap-1.5 text-xs text-warning-700">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" /> {aviso}
              </p>
            )}
          </div>
        </div>

        <Field label="Razão social" required maxLength={200} value={razaoSocial} onChange={(e) => setRazaoSocial(e.target.value)} />
        <Field
          label="Nome fantasia (opcional)"
          maxLength={200}
          value={nomeFantasia}
          onChange={(e) => setNomeFantasia(e.target.value)}
          hint="É o nome que aparece no seletor de empresas."
        />
        <CampoCidade label="Cidade" required codigo={codMunicipio} onChange={setCodMunicipio} />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[9rem_1fr]">
          <Field label="CEP" inputMode="numeric" value={cep} onChange={(e) => setCep(mascararCep(e.target.value))} placeholder="00000-000" />
          <Field label="Logradouro" value={logradouro} onChange={(e) => setLogradouro(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Número" value={numero} onChange={(e) => setNumero(e.target.value)} />
          <Field label="Complemento" value={complemento} onChange={(e) => setComplemento(e.target.value)} />
          <div className="col-span-2 sm:col-span-1">
            <Field label="Bairro" value={bairro} onChange={(e) => setBairro(e.target.value)} />
          </div>
        </div>

        {erro && (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            {erro}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button type="button" variant="ghost" onClick={onVoltar} disabled={enviando}>
            <ArrowLeft size={15} /> Voltar
          </Button>
          <div className="flex flex-wrap gap-3">
            <Button type="button" variant="outline" onClick={onFechar}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={enviando}>
              {enviando ? "Adicionando..." : "Adicionar e abrir"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
