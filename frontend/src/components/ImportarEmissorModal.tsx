import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  Circle,
  DownloadCloud,
  FileBadge,
  Loader2,
  Square,
  Users,
  XCircle,
} from "lucide-react"
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatarDocumento, mascararCep, mascararCnpj, soDigitos } from "../lib/documento"
import { formatBRL, formatCompetenciaLonga } from "../lib/format"
import type {
  CertificadoLido,
  CertificadoStatus,
  ConsultaCnpj,
  Empresa,
  EmpresaImportada,
  GrupoImportacao,
  PreviaNacional,
  RegraImportacao,
  ResultadoImportarEmissor,
} from "../lib/types"
import { ORDENS_IMPORTACAO, type OrdemImportacao, buscarGrupos, documentoLegivel, faixaCompetencias, mensagemDe, ordenarGrupos, padrao } from "./ImportarNacionalModal"
import { Button } from "./ui/Button"
import { CampoCidade } from "./ui/CampoCidade"
import { Field } from "./ui/Field"
import { Modal } from "./ui/Modal"

// "Importar emissor" (05/10/2026) — "O Importar do Emissor Nacional é uma boa
// forma para cadastrar um novo emissor". Com o certificado A1 a Ana descobre
// de quem é a empresa, cria o cadastro, guarda o certificado e traz os
// tomadores e as notas que a empresa já emitiu.
//
// - modo "nova": mais um CNPJ no login (vem de "Adicionar empresa").
// - modo "atual": a empresa aberta ainda está vazia (vem da Visão geral e de
//   Empresa › Notas e e-mails) — só falta o certificado e a importação.
//
// A leitura e a gravação das notas são as mesmas de ImportarNacionalModal
// (POST /importar/nacional/buscar e POST /importar/nacional).

type Modo = "nova" | "atual"
type Fase = "carregando" | "certificado" | "confirmar" | "andamento" | "revisar" | "resumo"
type Situacao = "espera" | "fazendo" | "feito" | "erro"
type Etapa = "leitura" | "gravacao"

const CAMINHO_DEPOIS = "Empresa › Notas e e-mails › Importar do Emissor Nacional"
const MES = /^\d{4}-\d{2}$/

function dataBR(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR")
}

function plural(n: number, um: string, varios: string): string {
  return `${n} ${n === 1 ? um : varios}`
}

function erroSimples(err: unknown): string {
  return err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Confira a internet e tente de novo."
}

/** Troca de tela com recarga: a empresa ativa pode ter mudado, e todas as
 * telas precisam buscar os dados dela. */
function irPara(caminho: string) {
  window.location.assign(caminho)
}

const CAIXA_ERRO = "flex items-start gap-2 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300"
const CAIXA_AVISO = "flex items-start gap-2 rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300"
const CAIXA_NEUTRA = "rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/40"

export function ImportarEmissorModal({ modo, onFechar, onVoltar }: { modo: Modo; onFechar: () => void; onVoltar?: () => void }) {
  const [fase, setFase] = useState<Fase>(modo === "atual" ? "carregando" : "certificado")
  const [erro, setErro] = useState<string | null>(null)

  // Passo 1 — certificado. O arquivo e a senha ficam só na memória desta
  // tela, até o certificado ser guardado (aí são apagados daqui).
  const [pfx, setPfx] = useState<File | null>(null)
  const [senha, setSenha] = useState("")
  const [lendoCertificado, setLendoCertificado] = useState(false)
  const [lido, setLido] = useState<CertificadoLido | null>(null)

  // Passo 2 — dados da empresa.
  const [cnpj, setCnpj] = useState("")
  const [razaoSocial, setRazaoSocial] = useState("")
  const [nomeFantasia, setNomeFantasia] = useState("")
  const [codMunicipio, setCodMunicipio] = useState("")
  const [endereco, setEndereco] = useState({ cep: "", logradouro: "", numero: "", complemento: "", bairro: "" })
  const [consultando, setConsultando] = useState(false)
  const [consultado, setConsultado] = useState<string | null>(null)
  const [avisoConsulta, setAvisoConsulta] = useState<string | null>(null)
  const [desde, setDesde] = useState(() => `${new Date().getFullYear()}-01`)

  // Modo "atual": a empresa aberta e o certificado que ela já tem.
  const [ativa, setAtiva] = useState<Empresa | null>(null)
  const [certificadoAtual, setCertificadoAtual] = useState<CertificadoStatus | null>(null)

  // Passo 3 — criação e importação.
  const [empresaCriada, setEmpresaCriada] = useState(false)
  const [certificadoGuardado, setCertificadoGuardado] = useState(false)
  const [nomeEmpresa, setNomeEmpresa] = useState("")
  const [leitura, setLeitura] = useState<Situacao>("espera")
  const [gravacao, setGravacao] = useState<Situacao>("espera")
  const [falha, setFalha] = useState<{ etapa: Etapa; mensagem: string; expirou?: boolean } | null>(null)
  const [parando, setParando] = useState(false)
  const [previa, setPrevia] = useState<PreviaNacional | null>(null)
  const [fora, setFora] = useState<Record<string, boolean>>({})
  const [resultado, setResultado] = useState<ResultadoImportarEmissor | null>(null)

  const montado = useRef(true)
  const parar = useRef(false)
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
      parar.current = true
    }
  }, [])

  // Modo "atual": qual é a empresa aberta e se ela já tem certificado válido
  // (aí não precisa pedir de novo).
  useEffect(() => {
    if (modo !== "atual") return
    Promise.all([
      api.get<Empresa[]>("/empresas").catch(() => [] as Empresa[]),
      api.get<CertificadoStatus>("/certificado/status").catch(() => null),
    ]).then(([empresas, certificado]) => {
      if (!montado.current) return
      const aberta = empresas.find((e) => e.ativa) ?? null
      setAtiva(aberta)
      setNomeEmpresa(aberta ? aberta.nome_fantasia?.trim() || aberta.razao_social : "")
      setCertificadoAtual(certificado)
      if (certificado?.carregado && !certificado.vencido) {
        setCertificadoGuardado(true)
        setFase("confirmar")
      } else {
        setFase("certificado")
      }
    })
  }, [modo])

  const mexeuNaConta = empresaCriada || resultado !== null
  const ocupado = lendoCertificado || (fase === "andamento" && !certificadoGuardado)

  function fechar() {
    if (ocupado) return // criando a empresa: espera terminar pra não deixar pela metade
    parar.current = true
    if (mexeuNaConta) irPara("/app")
    else onFechar()
  }

  // --- passo 1: ler o certificado (nada é guardado ainda) ---------------------

  async function lerCertificado(e: FormEvent) {
    e.preventDefault()
    if (!pfx) {
      setErro("Escolha o arquivo do certificado (.pfx ou .p12).")
      return
    }
    setErro(null)
    setLendoCertificado(true)
    try {
      const form = new FormData()
      form.append("pfx", pfx)
      form.append("senha", senha)
      const c = await api.postForm<CertificadoLido>("/certificado/ler", form)
      if (!montado.current) return
      if (c.vencido) {
        setErro(`Este certificado venceu em ${dataBR(c.valido_ate)}. Com ele não dá pra ler as notas — escolha um certificado válido.`)
        return
      }
      setLido(c)
      if (modo === "nova") {
        setCnpj(mascararCnpj(c.cnpj ?? ""))
        setRazaoSocial(c.pessoa_fisica ? "" : (c.titular ?? ""))
        setConsultado(null)
        setAvisoConsulta(null)
        if (c.cnpj) void consultarCnpj(c.cnpj)
      }
      setFase("confirmar")
    } catch (err) {
      if (montado.current) setErro(erroSimples(err))
    } finally {
      if (montado.current) setLendoCertificado(false)
    }
  }

  // Mesma consulta do cadastro (GET /cnpj/{cnpj}): preenche cidade e endereço.
  // Se falhar, a pessoa escolhe a cidade na mão.
  async function consultarCnpj(valor: string) {
    const digitos = soDigitos(valor)
    if (digitos.length !== 14 || digitos === consultado) return
    setConsultado(digitos)
    setAvisoConsulta(null)
    setConsultando(true)
    try {
      const d = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      if (!montado.current) return
      if (d.razao_social) setRazaoSocial(d.razao_social)
      if (d.cod_municipio_sugerido) setCodMunicipio(d.cod_municipio_sugerido)
      setEndereco({
        cep: mascararCep(d.cep ?? ""),
        logradouro: d.logradouro ?? "",
        numero: d.numero ?? "",
        complemento: d.complemento ?? "",
        bairro: d.bairro ?? "",
      })
      if (d.situacao_cadastral && d.situacao_cadastral.toUpperCase() !== "ATIVA") {
        setAvisoConsulta(`Situação cadastral na Receita: ${d.situacao_cadastral}. Confira se é essa empresa mesmo.`)
      }
    } catch (err) {
      if (!montado.current) return
      setAvisoConsulta(
        err instanceof ApiError && err.status === 404
          ? "Não encontrei esse CNPJ na Receita — confira os números e escolha a cidade da empresa."
          : "Não consegui buscar o endereço agora — escolha a cidade da empresa abaixo.",
      )
    } finally {
      if (montado.current) setConsultando(false)
    }
  }

  // Certificado de outra empresa (a raiz do CNPJ — 8 primeiros números — é a
  // mesma pra matriz e filial).
  const cnpjDaEmpresa = modo === "nova" ? soDigitos(cnpj) : (ativa?.cnpj ?? "")
  const certificadoDeOutra = Boolean(lido?.cnpj && cnpjDaEmpresa.length === 14 && lido.cnpj.slice(0, 8) !== cnpjDaEmpresa.slice(0, 8))

  // --- passo 2: confirmar → criar a empresa e guardar o certificado -----------

  async function confirmar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (!MES.test(desde)) {
      setErro("Escolha a partir de que mês eu trago as notas.")
      return
    }
    if (!certificadoGuardado) {
      if (!pfx) {
        setFase("certificado")
        return
      }
      const form = new FormData()
      form.append("pfx", pfx)
      form.append("senha", senha)
      if (modo === "nova") {
        if (soDigitos(cnpj).length !== 14) {
          setErro("Informe os 14 números do CNPJ.")
          return
        }
        if (!razaoSocial.trim()) {
          setErro("Informe a razão social da empresa.")
          return
        }
        if (!codMunicipio) {
          setErro("Escolha a cidade da empresa na lista.")
          return
        }
        form.append("cpf_cnpj", soDigitos(cnpj))
        form.append("razao_social", razaoSocial.trim())
        form.append("cod_municipio", codMunicipio)
        if (nomeFantasia.trim()) form.append("nome_fantasia", nomeFantasia.trim())
        for (const [campo, valor] of Object.entries(endereco)) {
          if (valor.trim()) form.append(campo, valor.trim())
        }
      }
      setFalha(null)
      setLeitura("espera")
      setGravacao("espera")
      setFase("andamento")
      try {
        if (modo === "nova") {
          const criada = await api.postForm<EmpresaImportada>("/empresas/importar", form)
          if (!montado.current) return
          setEmpresaCriada(true)
          setNomeEmpresa(criada.empresa.nome_fantasia?.trim() || criada.empresa.razao_social)
        } else {
          await api.postForm<CertificadoStatus>("/certificado", form)
          if (!montado.current) return
        }
      } catch (err) {
        // Nada foi criado (empresa e certificado entram juntos): volta pra corrigir.
        if (!montado.current) return
        setErro(erroSimples(err))
        setFase("confirmar")
        return
      }
      setCertificadoGuardado(true)
      // Guardado no servidor (cifrado): daqui a tela não precisa mais deles.
      setPfx(null)
      setSenha("")
    }
    void lerNotas(true)
  }

  // --- passo 3: ler as notas no Emissor Nacional (a importação de sempre) -----

  async function lerNotas(doInicio: boolean) {
    parar.current = false
    setParando(false)
    setFalha(null)
    setLeitura("fazendo")
    setGravacao("espera")
    setFase("andamento")
    let corpo: Record<string, boolean | string> = { ...(doInicio ? { desde_inicio: true } : {}), desde }
    let ultima: PreviaNacional | null = null
    try {
      for (;;) {
        const p = await api.post<PreviaNacional>("/importar/nacional/buscar", corpo)
        corpo = { desde }
        if (!montado.current) return
        setPrevia(p)
        ultima = p
        if (p.terminou || parar.current) break
      }
    } catch (err) {
      if (!montado.current) return
      setLeitura("erro")
      setFalha({ etapa: "leitura", mensagem: mensagemDe(err).mensagem })
      return
    }
    setLeitura("feito")
    // Só os que a pessoa já tem e os pré-cadastrados vêm marcados; o resto ela escolhe.
    setFora(Object.fromEntries((ultima?.grupos ?? []).filter((g) => padrao(g).acao === "ignorar").map((g) => [g.documento, true])))
    setFase(ultima && ultima.grupos.length > 0 ? "revisar" : "resumo")
  }

  const grupos = useMemo(() => previa?.grupos ?? [], [previa])
  const escolhidos = useMemo(() => grupos.filter((g) => !fora[g.documento]), [grupos, fora])
  const totalNotas = escolhidos.reduce((soma, g) => soma + g.quantidade, 0)
  const semCnpj = grupos.filter((g) => g.tipo !== "CNPJ")
  // Buscar, ordenar e marcar o que está na tela (08/10/2026).
  const [busca, setBusca] = useState("")
  const [ordem, setOrdem] = useState<OrdemImportacao>("valor")
  const listados = useMemo(() => ordenarGrupos(buscarGrupos(grupos, busca), ordem), [grupos, busca, ordem])
  const marcarListados = (marcar: boolean) =>
    setFora((atual) => ({ ...atual, ...Object.fromEntries(listados.map((g) => [g.documento, !marcar])) }))

  async function gravar() {
    setFalha(null)
    setGravacao("fazendo")
    setFase("andamento")
    const mapeamento: RegraImportacao[] = grupos.map((g) => {
      if (fora[g.documento]) return { documento: g.documento, acao: "ignorar", vinculo_id: null }
      const r = padrao(g)
      // marcado à mão um tomador que eu não conhecia: entra como tomador novo
      if (r.acao === "ignorar") return { documento: g.documento, acao: "novo", vinculo_id: null }
      return { documento: g.documento, acao: r.acao, vinculo_id: r.acao === "novo" ? null : r.vinculo_id }
    })
    try {
      const res = await api.post<ResultadoImportarEmissor>("/importar/nacional", { mapeamento, ajustar_modelos: true })
      if (!montado.current) return
      setGravacao("feito")
      setResultado(res)
      setFase("resumo")
    } catch (err) {
      if (!montado.current) return
      setGravacao("erro")
      // 409 = a leitura expirou no servidor: precisa ler de novo.
      setFalha({ etapa: "gravacao", mensagem: mensagemDe(err).mensagem, expirou: err instanceof ApiError && err.status === 409 })
    }
  }

  function tentarDeNovo() {
    if (falha?.etapa === "gravacao" && !falha.expirou) void gravar()
    else void lerNotas(false)
  }

  const passoAtual = fase === "carregando" || fase === "certificado" ? 1 : fase === "confirmar" ? 2 : 3
  const titulo = modo === "nova" ? "Importar empresa do Emissor Nacional" : "Trazer do Emissor Nacional"

  return (
    <Modal titulo={titulo} onClose={fechar} largura="max-w-2xl">
      <Passos atual={passoAtual} concluido={fase === "resumo"} />

      {erro && (
        <div role="alert" className={`mb-4 ${CAIXA_ERRO}`}>
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
          <p>{erro}</p>
        </div>
      )}

      {fase === "carregando" && (
        <p className="flex items-center justify-center gap-2 py-10 text-sm text-slate-400 dark:text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Carregando...
        </p>
      )}

      {/* ------------------------------------------------ 1. certificado */}
      {fase === "certificado" && (
        <form onSubmit={lerCertificado} className="flex flex-col gap-4">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {modo === "nova"
              ? "Escolha o certificado digital (A1) da empresa. Com ele eu descubro de quem é a empresa, crio o cadastro e trago os tomadores e as notas que ela já emitiu no Emissor Nacional."
              : `Escolha o certificado digital (A1) ${nomeEmpresa ? `de ${nomeEmpresa}` : "da empresa"}. Com ele eu trago os tomadores e as notas que ela já emitiu no Emissor Nacional.`}
          </p>
          {modo === "atual" && certificadoAtual?.carregado && certificadoAtual.vencido && (
            <p className={CAIXA_AVISO}>
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden /> O certificado guardado aqui está vencido. Escolha o novo.
            </p>
          )}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo do certificado (.pfx ou .p12)</span>
            <input
              type="file"
              accept=".pfx,.p12,application/x-pkcs12"
              onChange={(e) => {
                setPfx(e.target.files?.[0] ?? null)
                setErro(null)
              }}
              className="w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200 dark:text-slate-300 dark:file:bg-slate-700 dark:file:text-slate-200"
            />
            {pfx && <span className="mt-1 block truncate text-xs text-slate-400 dark:text-slate-500">Escolhido: {pfx.name}</span>}
          </label>
          <Field
            label="Senha do certificado"
            type="password"
            required
            autoComplete="off"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            hint="É a senha que você criou quando recebeu o certificado. Só você digita — eu não sei qual é."
          />
          <p className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
            <FileBadge size={14} className="mt-0.5 shrink-0" aria-hidden />
            Nesta etapa eu só leio de quem é o certificado. Ele só é guardado (protegido por criptografia) depois que você confirmar a
            empresa.
          </p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            {onVoltar ? (
              <Button type="button" variant="ghost" onClick={onVoltar} disabled={lendoCertificado}>
                <ArrowLeft size={15} /> Voltar
              </Button>
            ) : (
              <Button type="button" variant="ghost" onClick={fechar} disabled={lendoCertificado}>
                Cancelar
              </Button>
            )}
            <Button type="submit" variant="accent" disabled={lendoCertificado || !pfx || !senha}>
              {lendoCertificado ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Lendo o certificado...
                </>
              ) : (
                <>
                  Continuar <ArrowRight size={15} />
                </>
              )}
            </Button>
          </div>
        </form>
      )}

      {/* ------------------------------------------------ 2. confirmar */}
      {fase === "confirmar" && (
        <form onSubmit={confirmar} className="flex flex-col gap-4">
          {modo === "nova" && lido && (
            <>
              <div className={CAIXA_NEUTRA}>
                <p className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                  <Building2 size={16} className="mt-0.5 shrink-0 text-primary-600 dark:text-primary-300" aria-hidden />
                  <span>
                    {lido.cnpj ? (
                      <>
                        Empresa: <strong>{razaoSocial || lido.titular || "—"}</strong> — CNPJ <strong>{formatarDocumento(lido.cnpj)}</strong>
                      </>
                    ) : (
                      <>
                        Certificado de <strong>{lido.titular ?? "nome não informado"}</strong>
                      </>
                    )}
                  </span>
                </p>
                <p className="mt-1 pl-6 text-xs text-slate-500 dark:text-slate-400">Certificado válido até {dataBR(lido.valido_ate)}.</p>
              </div>

              {lido.ja_cadastrada && (
                <p className={CAIXA_ERRO}>
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
                  <span>
                    Essa empresa já está no seu login. Para trazer as notas dela, troque para ela no topo do menu e use {CAMINHO_DEPOIS}.
                  </span>
                </p>
              )}

              {!lido.cnpj && (
                <>
                  <p className={CAIXA_AVISO}>
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
                    <span>
                      {lido.pessoa_fisica
                        ? "Este certificado parece ser de uma pessoa (e-CPF), não da empresa. Digite o CNPJ da empresa — mas pode ser que o Emissor Nacional só libere as notas com o certificado da própria empresa."
                        : "Não consegui achar o CNPJ dentro do certificado. Digite o CNPJ da empresa."}
                    </span>
                  </p>
                  <Field
                    label="CNPJ da empresa"
                    required
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="00.000.000/0000-00"
                    value={cnpj}
                    onChange={(e) => setCnpj(mascararCnpj(e.target.value))}
                    onBlur={() => void consultarCnpj(cnpj)}
                  />
                </>
              )}

              <div aria-live="polite">
                {consultando && (
                  <p className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                    <Loader2 size={13} className="animate-spin" /> Buscando o endereço da empresa...
                  </p>
                )}
                {avisoConsulta && !consultando && (
                  <p className="flex items-start gap-1.5 text-xs text-warning-700 dark:text-warning-300">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden /> {avisoConsulta}
                  </p>
                )}
              </div>

              <Field label="Razão social" required maxLength={200} value={razaoSocial} onChange={(e) => setRazaoSocial(e.target.value)} />
              <CampoCidade label="Cidade da empresa" required codigo={codMunicipio} onChange={setCodMunicipio} />
              <Field
                label="Nome fantasia (opcional)"
                maxLength={200}
                value={nomeFantasia}
                onChange={(e) => setNomeFantasia(e.target.value)}
                hint="É o nome que aparece no seletor de empresas. O endereço você confere depois em Empresa › Dados da empresa."
              />
            </>
          )}

          {modo === "atual" && (
            <div className={CAIXA_NEUTRA}>
              <p className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                <Building2 size={16} className="mt-0.5 shrink-0 text-primary-600 dark:text-primary-300" aria-hidden />
                <span>
                  Empresa: <strong>{nomeEmpresa || "a empresa aberta"}</strong>
                  {ativa && (
                    <>
                      {" "}
                      — CNPJ <strong>{formatarDocumento(ativa.cnpj)}</strong>
                    </>
                  )}
                </span>
              </p>
              <p className="mt-1 pl-6 text-xs text-slate-500 dark:text-slate-400">
                {lido
                  ? `Certificado de ${lido.titular ?? "nome não informado"}${lido.cnpj ? ` (CNPJ ${formatarDocumento(lido.cnpj)})` : ""}, válido até ${dataBR(lido.valido_ate)}.`
                  : `Vou usar o certificado que já está guardado${certificadoAtual?.validade ? ` (válido até ${dataBR(certificadoAtual.validade)})` : ""}.`}
              </p>
            </div>
          )}

          {certificadoDeOutra && lido?.cnpj && (
            <p className={CAIXA_ERRO}>
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
              <span>
                Este certificado é do CNPJ {formatarDocumento(lido.cnpj)}, diferente do CNPJ da empresa. Volte e escolha o certificado da
                própria empresa.
              </span>
            </p>
          )}

          <label className="flex flex-wrap items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            Trazer as notas emitidas a partir de
            <input
              type="month"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <p className="-mt-2 text-xs text-slate-500 dark:text-slate-400">
            É só leitura: nada é enviado à prefeitura nem aos tomadores. Antes de gravar eu mostro o que encontrei.
          </p>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            {certificadoGuardado ? (
              <Button type="button" variant="ghost" onClick={fechar}>
                Cancelar
              </Button>
            ) : (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setErro(null)
                  setFase("certificado")
                }}
              >
                <ArrowLeft size={15} /> Trocar o certificado
              </Button>
            )}
            <Button type="submit" variant="accent" disabled={consultando || certificadoDeOutra || Boolean(modo === "nova" && lido?.ja_cadastrada)}>
              <DownloadCloud size={16} />
              {certificadoGuardado
                ? "Trazer minhas notas"
                : modo === "nova"
                  ? "Criar empresa e trazer minhas notas"
                  : "Guardar certificado e trazer minhas notas"}
            </Button>
          </div>
        </form>
      )}

      {/* ------------------------------------------------ 3. andamento */}
      {fase === "andamento" && (
        <div className="flex flex-col gap-4" aria-live="polite">
          <ul className="flex flex-col gap-2.5">
            {modo === "nova" && <LinhaAndamento situacao={empresaCriada ? "feito" : "fazendo"} texto={empresaCriada ? `Empresa criada${nomeEmpresa ? `: ${nomeEmpresa}` : ""}` : "Criando a empresa..."} />}
            <LinhaAndamento
              situacao={certificadoGuardado ? "feito" : "fazendo"}
              texto={certificadoGuardado ? "Certificado guardado (protegido por criptografia)" : "Guardando o certificado..."}
            />
            <LinhaAndamento
              situacao={leitura}
              texto={
                leitura === "feito"
                  ? `Notas lidas no Emissor Nacional (${plural(previa?.total_notas ?? 0, "nota", "notas")})`
                  : leitura === "erro"
                    ? "Não consegui ler as notas no Emissor Nacional"
                    : leitura === "fazendo"
                      ? parando
                        ? "Parando depois deste pedaço..."
                        : "Lendo suas notas no Emissor Nacional..."
                      : "Ler suas notas no Emissor Nacional"
              }
              detalhe={
                leitura === "fazendo" && previa
                  ? `${plural(previa.total_notas, "nota encontrada", "notas encontradas")}${previa.grupos.length > 0 ? ` · ${plural(previa.grupos.length, "tomador", "tomadores")}` : ""}`
                  : undefined
              }
            />
            <LinhaAndamento
              situacao={gravacao}
              texto={
                gravacao === "fazendo"
                  ? "Cadastrando os tomadores e as notas..."
                  : gravacao === "erro"
                    ? "Não consegui cadastrar os tomadores e as notas"
                    : "Cadastrar os tomadores e as notas"
              }
            />
          </ul>

          {leitura === "fazendo" && (
            <div className="flex flex-col items-start gap-2">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Pode levar alguns minutos se a empresa emite muitas notas. Dá pra parar e seguir com o que já foi lido.
              </p>
              <Button
                type="button"
                variant="outline"
                disabled={parando}
                onClick={() => {
                  parar.current = true
                  setParando(true)
                }}
              >
                <Square size={14} /> Parar
              </Button>
            </div>
          )}

          {falha && (
            <div className="flex flex-col gap-3">
              <div role="alert" className={CAIXA_ERRO}>
                <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
                <p>{falha.mensagem}</p>
              </div>
              <div className={`${CAIXA_NEUTRA} text-sm text-slate-600 dark:text-slate-300`}>
                <p className="font-medium text-slate-800 dark:text-slate-100">Nada se perdeu.</p>
                <p className="mt-1">
                  {modo === "nova" ? "A empresa foi criada e o certificado dela está guardado" : "O certificado está guardado"} — só faltou
                  trazer as notas. Você pode tentar de novo agora ou depois, em <strong>{CAMINHO_DEPOIS}</strong>.
                </p>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={() => irPara("/app")}>
                  Ir para a visão geral
                </Button>
                <Button type="button" variant="accent" onClick={tentarDeNovo}>
                  <DownloadCloud size={16} /> Tentar de novo
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------ 3b. o que encontrei */}
      {fase === "revisar" && previa && (
        <div className="flex flex-col gap-4">
          <div>
            <p className="font-medium text-slate-800 dark:text-slate-100">
              Encontrei {plural(previa.total_notas, "nota", "notas")} de {plural(grupos.length, "tomador", "tomadores")}.
            </p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              <strong>Você escolhe quem trazer.</strong> Deixei marcados só os tomadores pré-cadastrados e os que você já tem; marque os
              outros que quiser. Cada marcado vira um tomador no seu cadastro, já com o serviço e a descrição da última nota.
              {semCnpj.length > 0 && " Quem não tem CNPJ entra só para controle."}
            </p>
          </div>

          {!previa.terminou && (
            <p className={CAIXA_AVISO}>
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
              <span>A leitura parou antes do fim — pode faltar nota. Dá pra trazer o que já veio e continuar depois em {CAMINHO_DEPOIS}.</span>
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar nome, CPF/CNPJ, descrição..."
              aria-label="Buscar tomador na importação"
              className="min-w-0 flex-1 basis-56 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              Ordenar
              <select
                value={ordem}
                onChange={(e) => setOrdem(e.target.value as OrdemImportacao)}
                aria-label="Ordenar os tomadores"
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                {ORDENS_IMPORTACAO.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.rotulo}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {escolhidos.length} de {grupos.length} marcados
            </span>
            {busca.trim() && listados.length > 0 && (
              <>
                <Button type="button" variant="outline" className="px-2.5 py-1 text-xs" onClick={() => marcarListados(true)}>
                  Marcar os {listados.length} da busca
                </Button>
                <Button type="button" variant="outline" className="px-2.5 py-1 text-xs" onClick={() => marcarListados(false)}>
                  Desmarcar os da busca
                </Button>
              </>
            )}
            {semCnpj.length > 0 && (
              <Button
                type="button"
                variant="outline"
                className="px-2.5 py-1 text-xs"
                onClick={() => setFora((atual) => ({ ...atual, ...Object.fromEntries(semCnpj.map((g) => [g.documento, true])) }))}
              >
                Desmarcar os {semCnpj.length} sem CNPJ
              </Button>
            )}
            <Button type="button" variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => setFora({})}>
              Marcar todos
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="px-2.5 py-1 text-xs"
              onClick={() => setFora(Object.fromEntries(grupos.map((g) => [g.documento, true])))}
            >
              Desmarcar todos
            </Button>
          </div>

          <ul className="-mx-5 max-h-[46vh] divide-y divide-slate-100 overflow-y-auto border-y border-slate-100 dark:divide-slate-700/60 dark:border-slate-700/60">
            {listados.length === 0 && <li className="px-5 py-8 text-center text-sm text-slate-400 dark:text-slate-500">Nenhum tomador com essa busca.</li>}
            {listados.map((g) => (
              <LinhaEncontrada
                key={g.documento}
                grupo={g}
                marcado={!fora[g.documento]}
                onMudar={(marcado) => setFora((atual) => ({ ...atual, [g.documento]: !marcado }))}
              />
            ))}
          </ul>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
            <Button type="button" variant="ghost" onClick={() => irPara("/app")} title={`Dá pra importar depois em ${CAMINHO_DEPOIS}`}>
              Deixar para depois
            </Button>
            <Button type="button" variant="accent" disabled={totalNotas === 0} onClick={() => void gravar()}>
              <DownloadCloud size={16} /> Trazer {plural(escolhidos.length, "tomador", "tomadores")} e {plural(totalNotas, "nota", "notas")}
            </Button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------ fim: resumo */}
      {fase === "resumo" &&
        (resultado ? (
          <Resumo resultado={resultado} modo={modo} nomeEmpresa={nomeEmpresa} incompleta={Boolean(previa && !previa.terminou)} />
        ) : (
          <div className="flex flex-col gap-4" aria-live="polite">
            <div className="flex items-start gap-3">
              <CheckCircle2 size={24} className="mt-0.5 shrink-0 text-success-600" aria-hidden />
              <div>
                <p className="font-medium text-slate-800 dark:text-slate-100">
                  {modo === "nova" ? `Empresa criada${nomeEmpresa ? `: ${nomeEmpresa}` : ""}.` : "Certificado guardado."} Não encontrei notas para
                  trazer.
                </p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {previa && previa.ja_importadas > 0
                    ? `As ${previa.ja_importadas} notas que encontrei já estavam aqui.`
                    : `Não achei notas emitidas por esta empresa no Emissor Nacional a partir de ${MES.test(desde) ? formatCompetenciaLonga(desde).toLowerCase() : "esse mês"}.`}{" "}
                  Se ela emitiu antes disso, escolha um mês mais antigo e procure de novo.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              Procurar notas a partir de
              <input
                type="month"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
              <Button type="button" variant="outline" className="py-1.5" disabled={!MES.test(desde)} onClick={() => void lerNotas(true)}>
                <DownloadCloud size={15} /> Procurar de novo
              </Button>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={() => irPara("/app/tomadores/novo")}>
                <Users size={16} /> Cadastrar um tomador
              </Button>
              <Button type="button" variant="accent" onClick={() => irPara("/app")}>
                Ir para a visão geral
              </Button>
            </div>
          </div>
        ))}
    </Modal>
  )
}

function Passos({ atual, concluido }: { atual: number; concluido: boolean }) {
  const nomes = ["Certificado", "Confirmar", "Trazer notas"]
  return (
    <ol className="mb-5 flex items-center gap-2 text-xs" aria-label="Etapas">
      {nomes.map((nome, i) => {
        const n = i + 1
        const feito = concluido || n < atual
        const agora = !concluido && n === atual
        return (
          <li key={nome} className="flex min-w-0 flex-1 items-center gap-1.5" aria-current={agora ? "step" : undefined}>
            <span
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                feito
                  ? "bg-success-600 text-white"
                  : agora
                    ? "bg-primary-600 text-white"
                    : "bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500"
              }`}
            >
              {feito ? "✓" : n}
            </span>
            <span className={`truncate ${agora ? "font-medium text-slate-800 dark:text-slate-100" : "text-slate-400 dark:text-slate-500"}`}>{nome}</span>
            {n < nomes.length && <span className="h-px min-w-3 flex-1 bg-slate-200 dark:bg-slate-700" aria-hidden />}
          </li>
        )
      })}
    </ol>
  )
}

function LinhaAndamento({ situacao, texto, detalhe }: { situacao: Situacao; texto: string; detalhe?: string }) {
  return (
    <li className="flex items-start gap-2.5 text-sm">
      {situacao === "feito" ? (
        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-success-600" aria-label="Feito" />
      ) : situacao === "fazendo" ? (
        <Loader2 size={18} className="mt-0.5 shrink-0 animate-spin text-primary-600 dark:text-primary-300" aria-label="Fazendo" />
      ) : situacao === "erro" ? (
        <XCircle size={18} className="mt-0.5 shrink-0 text-danger-600" aria-label="Não deu certo" />
      ) : (
        <Circle size={18} className="mt-0.5 shrink-0 text-slate-300 dark:text-slate-600" aria-label="Ainda não começou" />
      )}
      <span className={situacao === "espera" ? "text-slate-400 dark:text-slate-500" : "text-slate-700 dark:text-slate-200"}>
        {texto}
        {detalhe && <span className="block text-xs text-slate-500 dark:text-slate-400">{detalhe}</span>}
      </span>
    </li>
  )
}

function LinhaEncontrada({ grupo: g, marcado, onMudar }: { grupo: GrupoImportacao; marcado: boolean; onMudar: (marcado: boolean) => void }) {
  return (
    <li>
      <label className="flex cursor-pointer items-start gap-3 px-5 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-700/40">
        <input type="checkbox" checked={marcado} onChange={(e) => onMudar(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-primary-600" />
        <span className={`min-w-0 flex-1 ${marcado ? "" : "opacity-50"}`}>
          <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">{g.nome}</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            {documentoLegivel(g)}
            {g.tipo !== "CNPJ" && " · só para controle"}
          </span>
        </span>
        <span className={`shrink-0 text-right ${marcado ? "" : "opacity-50"}`}>
          <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">{formatBRL(g.total)}</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            {plural(g.quantidade, "nota", "notas")} · {faixaCompetencias(g.competencias)}
          </span>
        </span>
      </label>
    </li>
  )
}

function Resumo({
  resultado,
  modo,
  nomeEmpresa,
  incompleta,
}: {
  resultado: ResultadoImportarEmissor
  modo: Modo
  nomeEmpresa: string
  incompleta: boolean
}) {
  const tomadores = resultado.tomadores ?? []
  const soControle = tomadores.filter((t) => t.sem_nota).length
  const inativos = tomadores.filter((t) => !t.ativo && !t.sem_nota).length
  // Quem ainda pede um ajuste antes da próxima nota.
  const paraConfigurar = tomadores.filter((t) => !t.sem_nota && (t.pendencia || t.modelo_ajustado))
  const MOSTRAR = 8

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <div className="flex items-start gap-3">
        <CheckCircle2 size={24} className="mt-0.5 shrink-0 text-success-600" aria-hidden />
        <div>
          <p className="font-medium text-slate-800 dark:text-slate-100">
            Pronto! {modo === "nova" ? `${nomeEmpresa || "A empresa"} já está na Ana.` : "Trouxe o que você já tinha no Emissor Nacional."}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">As notas entram como já entregues ao tomador — nada foi enviado a ninguém.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className={CAIXA_NEUTRA}>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{resultado.vinculos_criados}</p>
          <p className="text-sm text-slate-600 dark:text-slate-300">{resultado.vinculos_criados === 1 ? "tomador cadastrado" : "tomadores cadastrados"}</p>
        </div>
        <div className={CAIXA_NEUTRA}>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{resultado.importadas}</p>
          <p className="text-sm text-slate-600 dark:text-slate-300">{resultado.importadas === 1 ? "nota importada" : "notas importadas"}</p>
        </div>
      </div>

      {(soControle > 0 || inativos > 0 || incompleta) && (
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-slate-600 dark:text-slate-300">
          {soControle > 0 && (
            <li>
              {plural(soControle, "cliente sem CNPJ ficou", "clientes sem CNPJ ficaram")} só para controle (sem CNPJ não dá para emitir nota).
            </li>
          )}
          {inativos > 0 && (
            <li>
              {plural(inativos, "tomador entrou como inativo", "tomadores entraram como inativos")} porque não {inativos === 1 ? "recebe" : "recebem"}{" "}
              nota há mais de um mês — é só reativar quando precisar.
            </li>
          )}
          {incompleta && <li>A leitura parou antes do fim: para trazer o resto, use {CAMINHO_DEPOIS}.</li>}
        </ul>
      )}

      <div>
        <p className="mb-1.5 text-sm font-medium text-slate-800 dark:text-slate-100">
          {paraConfigurar.length > 0
            ? `${plural(paraConfigurar.length, "tomador ainda precisa", "tomadores ainda precisam")} da sua conferência:`
            : "Nenhum tomador ficou precisando de configuração."}
        </p>
        {paraConfigurar.length > 0 ? (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100 text-sm dark:divide-slate-700/60 dark:border-slate-700/60">
            {paraConfigurar.slice(0, MOSTRAR).map((t) => (
              <li key={t.id}>
                <a href={`/app/tomadores/${t.id}`} className="flex items-start justify-between gap-3 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-700/40">
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-slate-800 dark:text-slate-100">{t.apelido}</span>
                    <span className={`block text-xs ${t.pendencia ? "text-warning-700 dark:text-warning-300" : "text-slate-500 dark:text-slate-400"}`}>
                      {t.pendencia ?? "Troquei o mês da descrição por um campo automático — confira se ficou certo."}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs font-medium text-primary-700 dark:text-primary-300">Conferir</span>
                </a>
              </li>
            ))}
            {paraConfigurar.length > MOSTRAR && (
              <li className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                e mais {paraConfigurar.length - MOSTRAR} — todos aparecem em Tomadores.
              </li>
            )}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Eles já saem com o serviço e a descrição da última nota. Vale passar o olho antes de gerar a primeira nota por aqui.
          </p>
        )}
      </div>

      {resultado.puladas.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-medium text-warning-700 dark:text-warning-300">
            {plural(resultado.puladas.length, "nota ficou", "notas ficaram")} de fora
          </summary>
          <ul className="mt-1.5 max-h-40 list-disc overflow-y-auto pl-5 text-xs text-slate-600 dark:text-slate-300">
            {resultado.puladas.map((p, i) => (
              <li key={`${p.chave}-${i}`}>{p.motivo}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={() => irPara("/app")}>
          Ir para a visão geral
        </Button>
        <Button type="button" variant="accent" onClick={() => irPara("/app/tomadores")}>
          <Users size={16} /> Ver tomadores
        </Button>
      </div>
    </div>
  )
}
