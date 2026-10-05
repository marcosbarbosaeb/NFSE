import { Building2, Check, FileText, Globe2, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { formatarDocumento, mascararCep, mascararCnpj, soDigitos } from "../../lib/documento"
import type { ConsultaCnpj, IdentificarTomadorResposta, Tomador } from "../../lib/types"
import { Button } from "../ui/Button"
import { CampoCidade } from "../ui/CampoCidade"
import { Card } from "../ui/Card"
import { Field } from "../ui/Field"
import { AvisoNotaExterior, CamposEmpresaDeFora, type DadosEmpresaDeFora, corpoEmpresaDeFora, empresaDeForaCompleta } from "./EmpresaDeFora"

/** "Quer emitir nota pra este cliente?" (05/10/2026) — o caminho pra quem
 * começou a vida no sistema como "só controle" (um recebimento lançado no
 * financeiro, uma importação sem CNPJ) virar tomador de verdade:
 *
 *   passo 1, aqui: QUEM é — o CNPJ (empresa do Brasil) ou nome, país e número
 *   fiscal (empresa de fora, o caso do Google AdSense);
 *   passo 2, na própria ficha: COMO a nota sai — quem chama este cartão
 *   preenche código, descrição e envio com o que já existe e a pessoa confere.
 *
 * O cliente continua sendo o mesmo: recebimentos e notas que ele já tinha
 * não saem do lugar. */

type Tipo = "cnpj" | "exterior"

interface Manual {
  razao_social: string
  cod_municipio: string
  cep: string
  logradouro: string
  numero: string
  complemento: string
  bairro: string
}

const MANUAL_VAZIO: Manual = { razao_social: "", cod_municipio: "", cep: "", logradouro: "", numero: "", complemento: "", bairro: "" }

type Consulta =
  | { estado: "consultando" }
  | { estado: "achou"; nome: string; onde: string; aviso?: string }
  | { estado: "manual"; motivo: string }
  | { estado: "invalido"; motivo: string }

const msg = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

export function EmitirNotaCliente({
  vinculoId,
  nome,
  tomador,
  comecarAberto = false,
  tipoInicial = null,
  onIdentificado,
  onFechar,
}: {
  vinculoId: string
  /** Como a pessoa chama este cliente (o apelido). */
  nome: string
  tomador: Tomador
  /** Veio de "Emitir nota pra este cliente": já abre no passo 1. */
  comecarAberto?: boolean
  tipoInicial?: Tipo | null
  onIdentificado: (resposta: IdentificarTomadorResposta) => void
  /** Quando existe, aparece "Deixar como está" (fecha sem mudar nada). */
  onFechar?: () => void
}) {
  const [aberto, setAberto] = useState(comecarAberto)
  const [tipo, setTipo] = useState<Tipo | null>(tipoInicial)
  const [cnpj, setCnpj] = useState("")
  const [consulta, setConsulta] = useState<Consulta | null>(null)
  const [manual, setManual] = useState<Manual>(MANUAL_VAZIO)
  const [catalogo, setCatalogo] = useState<Tomador[] | null>(null)
  const [fora, setFora] = useState<DadosEmpresaDeFora>({
    razao_social: tomador.razao_social ?? "",
    pais: tomador.pais ?? "",
    nif: tomador.nif ?? "",
    endereco: tomador.pais || tomador.nif ? (tomador.logradouro ?? "") : "",
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const raiz = useRef<HTMLDivElement>(null)
  // A consulta que vale é a do último CNPJ digitado.
  const consultaAtual = useRef("")

  useEffect(() => {
    if (comecarAberto) {
      setAberto(true)
      raiz.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }, [comecarAberto])

  // O catálogo de tomadores (pra reconhecer um CNPJ que já está cadastrado
  // sem depender da Receita) — só quando a pessoa escolhe "empresa do Brasil".
  useEffect(() => {
    if (tipo !== "cnpj" || catalogo !== null) return
    api
      .get<Tomador[]>("/tomadores?apenas_meus=false")
      .then(setCatalogo)
      .catch(() => setCatalogo([]))
  }, [tipo, catalogo])

  async function consultarCnpj(texto: string) {
    const digitos = soDigitos(texto)
    setErro(null)
    if (digitos.length !== 14) {
      consultaAtual.current = ""
      setConsulta(null)
      return
    }
    if (consultaAtual.current === digitos) return
    consultaAtual.current = digitos
    const noCatalogo = (catalogo ?? []).find((t) => t.cnpj === digitos)
    if (noCatalogo) {
      setConsulta({ estado: "achou", nome: noCatalogo.razao_social, onde: "já está no meu cadastro de tomadores" })
      return
    }
    setConsulta({ estado: "consultando" })
    try {
      const d = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      if (consultaAtual.current !== digitos) return
      setManual({
        razao_social: d.razao_social ?? "",
        cod_municipio: d.cod_municipio_sugerido ?? "",
        cep: mascararCep(d.cep ?? ""),
        logradouro: d.logradouro ?? "",
        numero: d.numero ?? "",
        complemento: d.complemento ?? "",
        bairro: d.bairro ?? "",
      })
      const situacao = d.situacao_cadastral && d.situacao_cadastral.toUpperCase() !== "ATIVA" ? `Atenção: na Receita a situação dela é “${d.situacao_cadastral}”.` : undefined
      if (d.razao_social && d.cod_municipio_sugerido) setConsulta({ estado: "achou", nome: d.razao_social, onde: `${d.municipio}/${d.uf}, pela Receita`, aviso: situacao })
      else setConsulta({ estado: "manual", motivo: "A Receita devolveu os dados pela metade. Complete o nome e a cidade da empresa." })
    } catch (err) {
      if (consultaAtual.current !== digitos) return
      if (err instanceof ApiError && err.status === 422) {
        setConsulta({ estado: "invalido", motivo: "Esse CNPJ não existe: os números não fecham. Deve ter um dígito trocado — confira no contrato ou numa nota antiga." })
      } else if (err instanceof ApiError && err.status === 404) {
        setConsulta({ estado: "manual", motivo: "Não achei esse CNPJ na Receita. Confira os números — se estiverem certos, escreva o nome e a cidade da empresa." })
      } else {
        setConsulta({ estado: "manual", motivo: "Não consegui consultar a Receita agora. Escreva o nome e a cidade da empresa que eu sigo daqui." })
      }
    }
  }

  async function confirmar(corpo: Record<string, unknown>) {
    setSalvando(true)
    setErro(null)
    try {
      onIdentificado(await api.post<IdentificarTomadorResposta>(`/vinculos/${vinculoId}/identificar`, corpo))
    } catch (err) {
      setErro(msg(err))
    } finally {
      setSalvando(false)
    }
  }

  const confirmarCnpj = () =>
    confirmar({
      tipo: "cnpj",
      cnpj: soDigitos(cnpj),
      razao_social: manual.razao_social.trim() || null,
      cod_municipio: manual.cod_municipio || null,
      cep: soDigitos(manual.cep) || null,
      logradouro: manual.logradouro.trim() || null,
      numero: manual.numero.trim() || null,
      complemento: manual.complemento.trim() || null,
      bairro: manual.bairro.trim() || null,
    })

  const mudarManual = (campo: keyof Manual, valor: string) => setManual((m) => ({ ...m, [campo]: valor }))
  const podeConfirmarCnpj =
    consulta?.estado === "achou" || (consulta?.estado === "manual" && manual.razao_social.trim().length >= 2 && Boolean(manual.cod_municipio))

  return (
    <Card className="p-5 ring-2 ring-accent-200 dark:ring-accent-800/70">
      <div
        ref={raiz}
        id="emitir-nota"
        className="scroll-mt-24"
        // Este cartão fica dentro do formulário do tomador: Enter num campo
        // daqui não pode salvar o formulário de fora.
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT" && !e.defaultPrevented) e.preventDefault()
        }}
      >
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-100 text-accent-700 dark:bg-accent-900/40 dark:text-accent-200">
            <FileText size={18} aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Quer emitir nota pra este cliente?</h2>
            <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
              Hoje <strong>{nome}</strong> está só no controle do que te paga. Pra eu gerar nota pra ele, são dois passos — e nada do que
              você já lançou sai do lugar:
            </p>
            <ol className="mt-2 flex flex-col gap-1 text-sm text-slate-600 dark:text-slate-300">
              <li className="flex gap-2">
                <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${aberto ? "bg-accent-500 text-white" : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300"}`}>
                  1
                </span>
                <span>
                  <strong>Quem é</strong> — o CNPJ dele. Se a empresa é de fora do Brasil (como o Google), o país e o número fiscal dela.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  2
                </span>
                <span>
                  <strong>Como a nota sai</strong> — o serviço, a descrição e pra onde enviar. Eu deixo preenchido o que eu souber; você só confere.
                </span>
              </li>
            </ol>
          </div>
        </div>

        {!aberto ? (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button type="button" variant="accent" onClick={() => setAberto(true)}>
              Quero emitir nota pra ele
            </Button>
            <p className="min-w-0 flex-1 text-xs text-slate-400 dark:text-slate-500">
              Não emite nota pra ele? Não precisa fazer nada: ele continua só no controle.
            </p>
          </div>
        ) : (
          <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-700/60">
            <p className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">Passo 1 de 2 — Quem é este cliente?</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Tipo de empresa">
              {(
                [
                  { id: "cnpj", Icone: Building2, titulo: "Empresa do Brasil", sub: "Tem CNPJ" },
                  { id: "exterior", Icone: Globe2, titulo: "Empresa de fora do Brasil", sub: "Não tem CNPJ (ex.: Google, Meta, plataformas de fora)" },
                ] as const
              ).map(({ id, Icone, titulo, sub }) => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={tipo === id}
                  onClick={() => {
                    setTipo(id)
                    setErro(null)
                  }}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-3 text-left transition-colors ${
                    tipo === id
                      ? "border-accent-400 bg-accent-50 dark:border-accent-500 dark:bg-accent-900/20"
                      : "border-slate-200 hover:border-accent-300 dark:border-slate-700 dark:hover:border-accent-700"
                  }`}
                >
                  <Icone size={18} className="mt-0.5 shrink-0 text-accent-600 dark:text-accent-300" aria-hidden />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">{titulo}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">{sub}</span>
                  </span>
                </button>
              ))}
            </div>

            {tipo === "cnpj" && (
              <div className="mt-4 flex flex-col gap-3">
                <Field
                  label="CNPJ da empresa"
                  inputMode="numeric"
                  value={cnpj}
                  onChange={(e) => {
                    const valor = mascararCnpj(e.target.value)
                    setCnpj(valor)
                    void consultarCnpj(valor)
                  }}
                  placeholder="00.000.000/0000-00"
                  hint="Digite o CNPJ que eu busco o nome e o endereço. Ele vem no contrato, no informe de pagamento ou numa nota antiga."
                />
                {consulta?.estado === "consultando" && (
                  <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                    <Loader2 size={14} className="animate-spin" /> Buscando os dados na Receita...
                  </p>
                )}
                {consulta?.estado === "invalido" && (
                  <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{consulta.motivo}</p>
                )}
                {consulta?.estado === "achou" && (
                  <div className="rounded-lg border border-success-200 bg-success-50/70 px-3 py-2.5 text-sm dark:border-success-900/50 dark:bg-success-900/20">
                    <p className="flex items-start gap-1.5 font-semibold text-success-700 dark:text-success-300">
                      <Check size={15} className="mt-0.5 shrink-0" /> Achei: {consulta.nome}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">
                      CNPJ {formatarDocumento(cnpj)} — {consulta.onde}. É essa a empresa que te paga?
                    </p>
                    {consulta.aviso && <p className="mt-1 text-xs font-medium text-warning-700 dark:text-warning-300">{consulta.aviso}</p>}
                  </div>
                )}
                {consulta?.estado === "manual" && (
                  <>
                    <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">{consulta.motivo}</p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div className="sm:col-span-2">
                        <Field label="Nome da empresa (razão social)" value={manual.razao_social} onChange={(e) => mudarManual("razao_social", e.target.value)} maxLength={200} />
                      </div>
                      <CampoCidade label="Cidade da empresa" required codigo={manual.cod_municipio} onChange={(codigo) => mudarManual("cod_municipio", codigo)} />
                      <Field
                        label="CEP (opcional)"
                        inputMode="numeric"
                        value={manual.cep}
                        onChange={(e) => mudarManual("cep", mascararCep(e.target.value))}
                        placeholder="00000-000"
                      />
                      <Field label="Rua / avenida (opcional)" value={manual.logradouro} onChange={(e) => mudarManual("logradouro", e.target.value)} maxLength={200} />
                      <Field label="Número (opcional)" value={manual.numero} onChange={(e) => mudarManual("numero", e.target.value)} maxLength={20} />
                      <Field label="Complemento (opcional)" value={manual.complemento} onChange={(e) => mudarManual("complemento", e.target.value)} maxLength={100} />
                      <Field label="Bairro (opcional)" value={manual.bairro} onChange={(e) => mudarManual("bairro", e.target.value)} maxLength={100} />
                    </div>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      Sem o endereço inteiro a nota sai sem o endereço dele — pode completar depois, em “Dados do tomador”.
                    </p>
                  </>
                )}
              </div>
            )}

            {tipo === "exterior" && (
              <div className="mt-4 flex flex-col gap-3">
                <CamposEmpresaDeFora valor={fora} onChange={setFora} />
                <AvisoNotaExterior />
              </div>
            )}

            {erro && <p className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}

            <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                disabled={salvando}
                onClick={() => {
                  setAberto(false)
                  setErro(null)
                  onFechar?.()
                }}
              >
                {onFechar ? "Deixar como está" : "Agora não"}
              </Button>
              {tipo === "cnpj" && (
                <Button type="button" variant="accent" disabled={salvando || !podeConfirmarCnpj} onClick={confirmarCnpj}>
                  {salvando ? "Salvando..." : consulta?.estado === "achou" ? "É essa empresa — continuar" : "Continuar"}
                </Button>
              )}
              {tipo === "exterior" && (
                <Button type="button" variant="accent" disabled={salvando || !empresaDeForaCompleta(fora)} onClick={() => confirmar(corpoEmpresaDeFora(fora))}>
                  {salvando ? "Salvando..." : "Continuar"}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
