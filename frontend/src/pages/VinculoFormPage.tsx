import { Check, ExternalLink, Loader2, Mail, MessageCircle, MinusCircle, Sparkles, Wand2 } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { EditorModeloEmail, type ValorModeloEmail } from "../components/EditorModeloEmail"
import { CampoCodigoUsado, type CodigoUsado } from "../components/tomador/CampoCodigoUsado"
import { DescricaoNota, previaDescricao } from "../components/tomador/DescricaoNota"
import { type DadosNotaAntiga, NotaAntiga, ResumoNotaAntiga } from "../components/tomador/NotaAntiga"
import { CaixaBusca } from "../components/ui/CaixaBusca"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { CampoCidade } from "../components/ui/CampoCidade"
import { CampoServico, formatarCodigoServico } from "../components/ui/CampoServico"
import { Field, FieldWrap } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"
import { useModulos } from "../lib/modulos"
import { formatarDocumento } from "../lib/documento"
import type { ConsultaCnpj, FormaEnvio, Prestador, Tomador, VinculoCriarRequest, VinculoDetalhe, VinculoResumo } from "../lib/types"

// Pedido do Marcos (28/09/2026):
// - "usar tomador existente": todos os dados com prévia de sugestão de
//   preenchimento com o que já foi usado (com este tomador, no catálogo, e
//   por você nos seus outros tomadores);
// - "cadastrar novo": digitar o CNPJ puxa todos os dados;
// - código de serviço só pela busca na lista oficial (nada de inventar);
// - sem calendário nem "método de captura" no cadastro — o dia de gerar a
//   nota se ajusta depois (aqui na edição, na lista de Tomadores ou no
//   Calendário), e o jeito de informar o valor se escolhe na hora de gerar.

const MODELOS_PADRAO = [
  "Comissão de vendas - {mes_nome_upper}/{ano}",
  "Serviços de divulgação e publicidade - {competencia_mm_aaaa}",
  "Comissão sobre vendas como afiliado - {mes_nome_upper}/{ano}",
]

/** "AWIN BRASIL SERVICOS DE MARKETING LTDA" -> "Awin Brasil" */
function apelidoDe(razaoSocial: string): string {
  const ignorar = new Set(["LTDA", "S/A", "SA", "S.A.", "ME", "EPP", "EIRELI", "DE", "DA", "DO", "E", "DOS", "DAS"])
  const palavras = razaoSocial
    .replace(/\(.*?\)/g, "")
    .split(/\s+/)
    .filter((p) => p && !ignorar.has(p.toUpperCase().replace(/[.,]/g, "")))
    .slice(0, 2)
  return palavras.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ")
}

interface FormState {
  apelido: string
  cod_local_prestacao: string
  cod_trib_nacional: string
  cod_trib_municipal: string
  template_descricao: string
  serie: string
  metodo_captura_valor: string
  requer_revisao: boolean
  ativo: boolean
  dia_limite_emissao: string
  dias_para_recebimento: string
  email_contato: string
  whatsapp_contato: string
  email_modelo: ValorModeloEmail
  /** Como recebe a nota — null = e-mail (padrão). */
  envio_canal: FormaEnvio | null
  portal_url: string
  cod_nbs: string
  incluir_intermediario: boolean
  /** Só controle de recebimento — a Ana não gera nota pra este tomador. */
  sem_nota: boolean
}

const ESTADO_INICIAL: FormState = {
  apelido: "",
  cod_local_prestacao: "",
  cod_trib_nacional: "",
  cod_trib_municipal: "",
  template_descricao: "",
  serie: "1",
  metodo_captura_valor: "manual",
  requer_revisao: true,
  ativo: true,
  dia_limite_emissao: "",
  dias_para_recebimento: "",
  email_contato: "",
  whatsapp_contato: "",
  email_modelo: { assunto: "", mensagem: "", anexos: "", copia: "", para: "" },
  envio_canal: null,
  portal_url: "",
  cod_nbs: "",
  incluir_intermediario: false,
  sem_nota: false,
}

// 29/09/2026: "cada tomador pede a nota de um jeito" — portal próprio,
// e-mail, WhatsApp, ou nem precisa.
const FORMAS_ENVIO: { valor: FormaEnvio; titulo: string; icone: typeof Mail }[] = [
  { valor: "email", titulo: "E-mail", icone: Mail },
  { valor: "whatsapp", titulo: "WhatsApp", icone: MessageCircle },
  { valor: "portal", titulo: "Portal do tomador", icone: ExternalLink },
  { valor: "nenhum", titulo: "Não precisa enviar", icone: MinusCircle },
]

const DICA_FORMA: Record<FormaEnvio, string> = {
  email: "A Ana manda a nota por e-mail com PDF/XML em anexo (dá pra ajustar o e-mail abaixo).",
  whatsapp: "O envio abre o WhatsApp com a mensagem e o link da nota — é só apertar enviar.",
  portal: "Você baixa o PDF/XML e sobe no sistema do tomador; depois marca a nota como enviada.",
  nenhum: "A nota não aparece como pendente de envio. Dá pra mandar pro contador mesmo assim.",
}

/** NBS: 9 dígitos, exibido como 1.1406.20.00. */
function mascaraNbs(valor: string): string {
  const d = valor.replace(/\D/g, "").slice(0, 9)
  return [d.slice(0, 1), d.slice(1, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(".")
}

// Quem manda o valor de um jeito próprio (28/09/2026): AWIN em PDF, Shopee
// no relatório mensal em planilha. O resto, digitado.
const METODO_POR_CNPJ: Record<string, string> = {
  "14182871000188": "pdf", // AWIN
  "35635824000112": "csv", // Shopee
}

const NOVO_TOMADOR_VAZIO = { cnpj: "", razao_social: "", cod_municipio: "", cep: "", logradouro: "", numero: "", complemento: "", bairro: "" }

interface Sugestao {
  campo: keyof FormState
  rotulo: string
  valor: string
  exibicao?: string
}

export function VinculoFormPage() {
  // "Só controle" e o prazo de pagamento são do módulo financeiro.
  const { financeiro } = useModulos()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const editando = Boolean(id)

  const [form, setForm] = useState<FormState>(ESTADO_INICIAL)
  const [tomadorExistenteId, setTomadorExistenteId] = useState<string | null>(searchParams.get("tomador_id"))
  const [modoTomador, setModoTomador] = useState<"existente" | "novo">(searchParams.get("tomador_id") ? "existente" : "novo")
  const [tomadorSelecionado, setTomadorSelecionado] = useState<Tomador | null>(null)
  const [tomadores, setTomadores] = useState<Tomador[]>([])
  const [meusVinculos, setMeusVinculos] = useState<VinculoResumo[]>([])
  const [novoTomador, setNovoTomador] = useState(NOVO_TOMADOR_VAZIO)
  const [consultaCnpj, setConsultaCnpj] = useState<{ estado: "consultando" | "ok" | "aviso"; texto: string } | null>(null)

  const [carregando, setCarregando] = useState(editando)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [prestadorModelo, setPrestadorModelo] = useState<Prestador | null>(null)
  const [emailAberto, setEmailAberto] = useState(false)
  // Cadastro assistido: o que veio de uma nota antiga (enviada agora ou a
  // última nota deste tomador) e os códigos já usados nas notas da empresa.
  const [notaAntiga, setNotaAntiga] = useState<DadosNotaAntiga | null>(null)
  const [buscandoUltima, setBuscandoUltima] = useState(false)
  const [codigosUsados, setCodigosUsados] = useState<{ municipais: CodigoUsado[]; nbs: CodigoUsado[] }>({ municipais: [], nbs: [] })
  useEffect(() => {
    api.get<Prestador>("/prestador").then(setPrestadorModelo).catch(() => {})
  }, [])

  // Modo edição: carrega o vínculo existente.
  useEffect(() => {
    if (!editando || !id) return
    api
      .get<VinculoDetalhe>(`/vinculos/${id}`)
      .then((v) => {
        setForm({
          apelido: v.apelido,
          cod_local_prestacao: v.cod_local_prestacao,
          cod_trib_nacional: v.cod_trib_nacional,
          cod_trib_municipal: v.cod_trib_municipal ?? "",
          template_descricao: v.template_descricao,
          serie: v.serie,
          metodo_captura_valor: v.metodo_captura_valor,
          requer_revisao: v.requer_revisao,
          ativo: v.ativo,
          dia_limite_emissao: v.dia_limite_emissao?.toString() ?? "",
          dias_para_recebimento: v.dias_para_recebimento?.toString() ?? "",
          email_contato: v.email_contato ?? "",
          whatsapp_contato: v.whatsapp_contato ?? "",
          email_modelo: {
            assunto: v.email_assunto ?? "",
            mensagem: v.email_mensagem ?? "",
            anexos: v.email_anexos ?? "",
            copia: v.email_copia ?? "",
            para: v.email_para ?? "",
          },
          envio_canal: v.envio_canal ?? null,
          portal_url: v.portal_url ?? "",
          cod_nbs: mascaraNbs(v.cod_nbs ?? ""),
          incluir_intermediario: Boolean(v.incluir_intermediario),
          sem_nota: Boolean(v.sem_nota),
        })
        setTomadorSelecionado(v.tomador)
        // Abre a seção do e-mail se o tomador já tem algo personalizado.
        setEmailAberto(Boolean(v.email_assunto || v.email_mensagem || v.email_anexos || v.email_copia || v.email_para))
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao carregar."))
      .finally(() => setCarregando(false))
  }, [editando, id])

  // Catálogo + seus tomadores (fonte das sugestões) + cidade do prestador.
  useEffect(() => {
    api.get<VinculoResumo[]>("/vinculos?todos=true").then(setMeusVinculos).catch(() => {})
    if (editando) return
    api.get<Tomador[]>("/tomadores?apenas_meus=false").then(setTomadores).catch(() => {})
    api
      .get<Prestador>("/prestador")
      .then((p) => setForm((f) => (f.cod_local_prestacao ? f : { ...f, cod_local_prestacao: p.cod_municipio })))
      .catch(() => {})
  }, [editando])

  useEffect(() => {
    if (tomadorExistenteId) {
      const achado = tomadores.find((t) => t.id === tomadorExistenteId)
      if (achado) setTomadorSelecionado(achado)
    } else if (!editando) {
      setTomadorSelecionado(null)
    }
  }, [tomadorExistenteId, tomadores, editando])

  function atualizarCampo<K extends keyof FormState>(campo: K, valor: FormState[K]) {
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  // O que você mais usa nos seus outros tomadores.
  const meusCodigos = useMemo(() => {
    const contagem = new Map<string, number>()
    meusVinculos.forEach((v) => v.cod_trib_nacional && contagem.set(v.cod_trib_nacional, (contagem.get(v.cod_trib_nacional) ?? 0) + 1))
    return [...contagem.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c)
  }, [meusVinculos])

  // Descrições JÁ CADASTRADAS pra este mesmo tomador (no catálogo, e nos
  // seus outros vínculos com ele — ex.: AWIN e AWIN Rchlo). Nada de
  // descrição de outros tomadores (pedido do Marcos, 28/09/2026: "deixe ela
  // associada ao tomador escolhido, com base no que nós cadastrarmos").
  const modelosDescricao = useMemo(() => {
    if (!tomadorSelecionado) return []
    const lista = [
      tomadorSelecionado.sug_template_descricao,
      ...meusVinculos.filter((v) => v.tomador_id === tomadorSelecionado.id && v.id !== id).map((v) => v.template_descricao),
    ].filter((t): t is string => Boolean(t))
    return [...new Set(lista)]
  }, [tomadorSelecionado, meusVinculos, id])

  // Sugestões pro tomador escolhido (modo "usar tomador existente").
  const sugestoes: Sugestao[] = useMemo(() => {
    if (editando || !tomadorSelecionado) return []
    const t = tomadorSelecionado
    const lista: Sugestao[] = [{ campo: "apelido", rotulo: "Apelido", valor: apelidoDe(t.razao_social) }]
    const codigo = t.sug_cod_trib_nacional || meusCodigos[0]
    if (codigo) lista.push({ campo: "cod_trib_nacional", rotulo: "Código do serviço", valor: codigo, exibicao: formatarCodigoServico(codigo) })
    const modelo = modelosDescricao[0] || MODELOS_PADRAO[0]
    lista.push({ campo: "template_descricao", rotulo: "Descrição", valor: modelo, exibicao: previaDescricao(modelo) })
    if (t.sug_dia_emissao) lista.push({ campo: "dia_limite_emissao", rotulo: "Dia de gerar a nota", valor: String(t.sug_dia_emissao), exibicao: `todo dia ${t.sug_dia_emissao}` })
    if (t.sug_dias_recebimento != null)
      lista.push({ campo: "dias_para_recebimento", rotulo: "Pagamento", valor: String(t.sug_dias_recebimento), exibicao: `${t.sug_dias_recebimento} dias depois da nota` })
    return lista
  }, [editando, tomadorSelecionado, meusCodigos, modelosDescricao])

  const sugestoesPendentes = sugestoes.filter((s) => form[s.campo] !== s.valor)

  function aplicarSugestoes(lista: Sugestao[]) {
    setForm((f) => {
      const novo = { ...f }
      lista.forEach((s) => {
        ;(novo[s.campo] as string) = s.valor
      })
      return novo
    })
  }

  // Ao escolher um tomador do catálogo, preenche o que estiver vazio.
  useEffect(() => {
    if (editando || !tomadorSelecionado) return
    setForm((f) => {
      const novo = { ...f, metodo_captura_valor: METODO_POR_CNPJ[tomadorSelecionado.cnpj] ?? "manual" }
      sugestoes.forEach((s) => {
        if (!f[s.campo]) (novo[s.campo] as string) = s.valor
      })
      return novo
    })
    // só quando troca de tomador
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tomadorSelecionado?.id])

  // Códigos municipais e NBS que já saíram nas notas com este código nacional.
  useEffect(() => {
    if (!form.cod_trib_nacional) return
    let vivo = true
    api
      .get<{ municipais: CodigoUsado[]; nbs: CodigoUsado[] }>(`/servicos/codigos-usados?cod_trib_nacional=${form.cod_trib_nacional}`)
      .then((c) => vivo && setCodigosUsados(c))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [form.cod_trib_nacional])

  /** Preenche o cadastro com o que veio de uma nota já emitida. */
  function aplicarNotaAntiga(d: DadosNotaAntiga, opcoes: { comTomador: boolean }) {
    setNotaAntiga(d)
    setErro(null)
    if (opcoes.comTomador) {
      const doc = (d.tomador.documento ?? "").replace(/\D/g, "")
      const noCatalogo = tomadores.find((t) => t.cnpj === doc)
      if (noCatalogo) {
        setModoTomador("existente")
        setTomadorExistenteId(noCatalogo.id)
      } else {
        setModoTomador("novo")
        setTomadorExistenteId(null)
        setNovoTomador({
          cnpj: d.tomador.documento ?? "",
          razao_social: d.tomador.razao_social ?? "",
          cod_municipio: d.tomador.cod_municipio ?? "",
          cep: d.tomador.cep ?? "",
          logradouro: d.tomador.logradouro ?? "",
          numero: d.tomador.numero ?? "",
          complemento: d.tomador.complemento ?? "",
          bairro: d.tomador.bairro ?? "",
        })
        setConsultaCnpj(null)
      }
    }
    setForm((f) => ({
      ...f,
      sem_nota: false,
      apelido: f.apelido || apelidoDe(d.tomador.razao_social ?? ""),
      cod_trib_nacional: d.cod_trib_nacional || f.cod_trib_nacional,
      cod_trib_municipal: d.cod_trib_municipal ?? f.cod_trib_municipal,
      cod_nbs: d.cod_nbs ? mascaraNbs(d.cod_nbs) : f.cod_nbs,
      cod_local_prestacao: d.cod_local_prestacao || f.cod_local_prestacao,
      serie: d.serie || f.serie,
      template_descricao: d.modelo_sugerido || f.template_descricao,
      email_contato: f.email_contato || d.tomador.email || "",
      metodo_captura_valor: METODO_POR_CNPJ[(d.tomador.documento ?? "").replace(/\D/g, "")] ?? f.metodo_captura_valor,
    }))
  }

  /** Tomador que veio de importação/controle: configura com a última nota dele. */
  async function configurarPelaUltimaNota() {
    if (!id) return
    setBuscandoUltima(true)
    setErro(null)
    try {
      const { nota } = await api.get<{ nota: DadosNotaAntiga | null }>(`/vinculos/${id}/ultima-nota`)
      if (nota) aplicarNotaAntiga(nota, { comTomador: false })
      else {
        atualizarCampo("sem_nota", false)
        setErro("Não achei nenhuma nota deste tomador com os dados completos. Preencha o código do serviço e a descrição abaixo.")
      }
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setBuscandoUltima(false)
    }
  }

  async function consultarCnpj(valor: string) {
    const digitos = valor.replace(/\D/g, "")
    if (digitos.length !== 14) return
    const noCatalogo = tomadores.find((t) => t.cnpj === digitos)
    if (noCatalogo) {
      setModoTomador("existente")
      setTomadorExistenteId(noCatalogo.id)
      setConsultaCnpj({ estado: "ok", texto: `${noCatalogo.razao_social} já está cadastrado — usamos o cadastro existente.` })
      return
    }
    setConsultaCnpj({ estado: "consultando", texto: "Buscando os dados na Receita..." })
    try {
      const d = await api.get<ConsultaCnpj>(`/cnpj/${digitos}`)
      setNovoTomador((t) => ({
        ...t,
        razao_social: d.razao_social || t.razao_social,
        cod_municipio: d.cod_municipio_sugerido || t.cod_municipio,
        cep: d.cep ?? t.cep,
        logradouro: d.logradouro ?? t.logradouro,
        numero: d.numero ?? t.numero,
        complemento: d.complemento ?? t.complemento,
        bairro: d.bairro ?? t.bairro,
      }))
      setForm((f) => ({
        ...f,
        metodo_captura_valor: METODO_POR_CNPJ[digitos] ?? f.metodo_captura_valor,
        apelido: f.apelido || apelidoDe(d.razao_social),
        cod_trib_nacional: f.cod_trib_nacional || meusCodigos[0] || "",
        template_descricao: f.template_descricao || MODELOS_PADRAO[0],
      }))
      const situacao = d.situacao_cadastral && d.situacao_cadastral.toUpperCase() !== "ATIVA" ? ` Atenção: situação na Receita = ${d.situacao_cadastral}.` : ""
      setConsultaCnpj({ estado: situacao ? "aviso" : "ok", texto: `Dados preenchidos a partir do CNPJ (${d.municipio}/${d.uf}).${situacao}` })
    } catch (err) {
      setConsultaCnpj({
        estado: "aviso",
        texto:
          err instanceof ApiError && err.status === 404
            ? "Não encontramos esse CNPJ — confira os números ou preencha à mão."
            : "Não deu pra consultar o CNPJ agora — preencha os dados à mão.",
      })
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    const nbs = form.cod_nbs.replace(/\D/g, "")
    if (nbs && nbs.length !== 9) {
      setErro("Código NBS tem 9 dígitos (ex.: 1.1406.20.00).")
      return
    }
    if (!form.sem_nota && !form.cod_local_prestacao) {
      setErro("Falta a cidade onde o serviço é prestado (em “Mais opções”).")
      return
    }
    setEnviando(true)
    try {
      // "Só controle": os campos de emissão ficam escondidos, mas a API ainda
      // pede código e descrição — vai o que estiver no formulário ou um padrão
      // (o código mais usado nos seus tomadores; 17.06.01 se não houver).
      const codigo = form.cod_trib_nacional || (form.sem_nota ? meusCodigos[0] || "170601" : "")
      const descricao = form.template_descricao.trim() || (form.sem_nota ? "Serviço prestado" : form.template_descricao)
      const base = {
        apelido: form.apelido.trim(),
        cod_local_prestacao: form.cod_local_prestacao,
        cod_trib_nacional: codigo,
        cod_trib_municipal: form.cod_trib_municipal || null,
        template_descricao: descricao,
        serie: form.serie.trim() || "1",
        metodo_captura_valor: form.metodo_captura_valor,
        requer_revisao: form.requer_revisao,
        dia_limite_emissao: form.dia_limite_emissao ? Number(form.dia_limite_emissao) : null,
        dias_para_recebimento: form.dias_para_recebimento ? Number(form.dias_para_recebimento) : null,
        email_contato: form.email_contato.trim() || null,
        whatsapp_contato: form.whatsapp_contato.trim() || null,
        email_assunto: form.email_modelo.assunto.trim() || null,
        email_mensagem: form.email_modelo.mensagem.trim() || null,
        email_anexos: form.email_modelo.anexos || null,
        email_copia: (form.email_modelo.copia ?? "").trim() || null,
        email_para: (form.email_modelo.para ?? "").trim() || null,
        envio_canal: form.envio_canal,
        portal_url: form.portal_url.trim() || null,
        cod_nbs: nbs || null,
        incluir_intermediario: form.incluir_intermediario,
        sem_nota: form.sem_nota,
      }

      if (editando && id) {
        await api.patch(`/vinculos/${id}`, { ...base, ativo: form.ativo })
        navigate("/app/tomadores")
        return
      }

      const payload: VinculoCriarRequest =
        modoTomador === "existente"
          ? { ...base, tomador_id: tomadorExistenteId }
          : {
              ...base,
              novo_tomador: {
                ...novoTomador,
                cnpj: novoTomador.cnpj.replace(/\D/g, ""),
                cep: novoTomador.cep.replace(/\D/g, "") || null,
              },
            }

      await api.post<VinculoDetalhe>("/vinculos", payload)
      navigate("/app/tomadores")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>

  const destaquesCodigo = [tomadorSelecionado?.sug_cod_trib_nacional, ...meusCodigos].filter((c): c is string => Boolean(c))

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{editando ? form.apelido || "Tomador" : "Adicionar tomador"}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {editando
            ? "Estas regras valem para as próximas notas deste tomador — não alteram notas já emitidas."
            : "O jeito mais fácil é enviar uma nota antiga deste cliente. Se não tiver, digite o CNPJ que eu preencho o resto."}
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-6">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        {editando ? (
          tomadorSelecionado && (
            <Card className="p-5">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Tomador</h2>
              <p className="font-medium text-slate-800 dark:text-slate-200">{tomadorSelecionado.razao_social}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {tomadorSelecionado.cnpj ? formatarDocumento(tomadorSelecionado.cnpj) : "Sem CNPJ (só controle)"}
              </p>
            </Card>
          )
        ) : (
          <>
          {notaAntiga ? <ResumoNotaAntiga dados={notaAntiga} /> : <NotaAntiga onLida={(d) => aplicarNotaAntiga(d, { comTomador: true })} />}
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Quem é o tomador</h2>
            <div className="mb-4 flex rounded-lg bg-slate-100 p-1 text-sm dark:bg-slate-700">
              {(["novo", "existente"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setModoTomador(m)}
                  className={`flex-1 rounded-md px-3 py-1.5 font-medium transition-colors ${
                    modoTomador === m ? "bg-white text-primary-700 shadow-sm dark:bg-slate-800" : "text-slate-500 dark:text-slate-400"
                  }`}
                >
                  {m === "existente" ? "Escolher do catálogo" : "Digitar o CNPJ"}
                </button>
              ))}
            </div>

            {modoTomador === "existente" ? (
              <div className="flex flex-col gap-3">
                <FieldWrap label="Tomador do catálogo">
                  <CaixaBusca
                    valor={tomadorExistenteId ?? ""}
                    opcoes={tomadores.map((t) => ({ id: t.id, rotulo: `${t.razao_social} — ${formatarDocumento(t.cnpj)}` }))}
                    onEscolher={(v) => setTomadorExistenteId(v || null)}
                    placeholder="Digite o nome ou o CNPJ pra buscar"
                    ariaLabel="Tomador do catálogo"
                    className="[&_input]:py-2 [&_input]:pl-3"
                    quebrar
                  />
                </FieldWrap>
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Não achou? Use “Digitar o CNPJ”.
                </p>

                {sugestoes.length > 0 && (
                  <div className="rounded-xl border border-accent-100 bg-accent-50/60 p-4 dark:border-accent-900/40 dark:bg-accent-900/20">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="flex items-center gap-1.5 text-sm font-semibold text-accent-700 dark:text-accent-200">
                        <Sparkles size={15} /> Sugestão de preenchimento
                      </p>
                      {sugestoesPendentes.length > 0 ? (
                        <button
                          type="button"
                          onClick={() => aplicarSugestoes(sugestoesPendentes)}
                          className="rounded-md bg-accent-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-accent-600"
                        >
                          Usar todas
                        </button>
                      ) : (
                        <span className="text-xs font-medium text-success-700 dark:text-success-300">já preenchido abaixo</span>
                      )}
                    </div>
                    <ul className="flex flex-col gap-1.5">
                      {sugestoes.map((s) => (
                        <li key={s.campo} className="flex items-start justify-between gap-3 text-sm">
                          <span className="min-w-0 text-slate-600 dark:text-slate-300">
                            <span className="text-slate-400">{s.rotulo}:</span> <span className="font-medium">{s.exibicao ?? s.valor}</span>
                          </span>
                          {form[s.campo] === s.valor ? (
                            <Check size={15} className="shrink-0 text-success-600" aria-label="em uso" />
                          ) : (
                            <button
                              type="button"
                              onClick={() => aplicarSugestoes([s])}
                              className="shrink-0 text-xs font-medium text-accent-700 hover:underline dark:text-accent-200"
                            >
                              usar
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-slate-400">Baseado no que já foi usado com este tomador e nos seus outros tomadores.</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Field
                    label="CNPJ"
                    required
                    inputMode="numeric"
                    value={novoTomador.cnpj}
                    onChange={(e) => {
                      const valor = e.target.value
                      setNovoTomador((t) => ({ ...t, cnpj: valor }))
                      if (valor.replace(/\D/g, "").length === 14) consultarCnpj(valor)
                    }}
                    onBlur={(e) => consultarCnpj(e.target.value)}
                    placeholder="Digite o CNPJ — o resto a gente preenche"
                  />
                  {consultaCnpj && (
                    <p
                      className={`mt-1.5 flex items-center gap-1.5 text-xs ${
                        consultaCnpj.estado === "aviso" ? "text-warning-700" : "text-success-700 dark:text-success-300"
                      }`}
                    >
                      {consultaCnpj.estado === "consultando" ? <Loader2 size={13} className="animate-spin" /> : consultaCnpj.estado === "ok" ? <Check size={13} /> : null}
                      {consultaCnpj.texto}
                    </p>
                  )}
                </div>
                <div className="sm:col-span-2">
                  <Field
                    label="Razão social"
                    required
                    value={novoTomador.razao_social}
                    onChange={(e) => setNovoTomador((t) => ({ ...t, razao_social: e.target.value }))}
                  />
                </div>
                <CampoCidade
                  label="Cidade do tomador"
                  required
                  codigo={novoTomador.cod_municipio}
                  onChange={(codigo) => setNovoTomador((t) => ({ ...t, cod_municipio: codigo }))}
                />
                <details className="sm:col-span-2" open={Boolean(consultaCnpj?.estado === "aviso")}>
                  <summary className="cursor-pointer select-none text-xs font-semibold text-slate-500 hover:text-primary-600 dark:text-slate-400">
                    Endereço {novoTomador.logradouro ? `— ${novoTomador.logradouro}${novoTomador.numero ? `, ${novoTomador.numero}` : ""}` : "(preenchido pelo CNPJ)"}
                  </summary>
                  <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="CEP" value={novoTomador.cep} onChange={(e) => setNovoTomador((t) => ({ ...t, cep: e.target.value }))} />
                <Field label="Logradouro" value={novoTomador.logradouro} onChange={(e) => setNovoTomador((t) => ({ ...t, logradouro: e.target.value }))} />
                <Field label="Número" value={novoTomador.numero} onChange={(e) => setNovoTomador((t) => ({ ...t, numero: e.target.value }))} />
                <Field label="Complemento" value={novoTomador.complemento} onChange={(e) => setNovoTomador((t) => ({ ...t, complemento: e.target.value }))} />
                <Field label="Bairro" value={novoTomador.bairro} onChange={(e) => setNovoTomador((t) => ({ ...t, bairro: e.target.value }))} />
                  </div>
                </details>
              </div>
            )}
          </Card>
          </>
        )}

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {form.sem_nota ? "Cadastro" : "Como a nota sai"}
          </h2>

          <label className={`mb-4 cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-700 ${financeiro || form.sem_nota ? "flex" : "hidden"}`}>
            <input
              type="checkbox"
              role="switch"
              checked={form.sem_nota}
              onChange={(e) => atualizarCampo("sem_nota", e.target.checked)}
              className="peer sr-only"
            />
            <span
              aria-hidden
              className="relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full bg-slate-300 transition-colors peer-checked:bg-primary-600 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 dark:bg-slate-600 after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:after:translate-x-4"
            />
            <span className="text-sm text-slate-700 dark:text-slate-300">
              Não emito nota pra este cliente por aqui (só controlo o que ele me paga)
              <span className="mt-0.5 block text-xs text-slate-400 dark:text-slate-500">
                {form.sem_nota
                  ? "Desligue pra configurar a nota dele — os dados ficam guardados."
                  : "Pra quem paga sem nota pela Ana: parcerias, pessoa física, exterior."}
              </span>
            </span>
          </label>
          {editando && form.sem_nota && tomadorSelecionado?.cnpj && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-accent-50 px-4 py-3 text-sm text-slate-700 dark:bg-accent-900/20 dark:text-slate-200">
              <p className="min-w-0 flex-1">
                <strong>Falta configurar a nota deste tomador.</strong> Eu preencho o código do serviço e a descrição com base na última
                nota dele — você só confere.
              </p>
              <Button type="button" variant="accent" disabled={buscandoUltima} onClick={configurarPelaUltimaNota}>
                <Wand2 size={16} /> {buscandoUltima ? "Buscando..." : "Configurar pra gerar notas"}
              </Button>
            </div>
          )}
          {editando && notaAntiga && <div className="mb-4"><ResumoNotaAntiga dados={notaAntiga} /></div>}
          {editando && tomadorSelecionado && !tomadorSelecionado.cnpj && !form.sem_nota && (
            <p className="mb-4 rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
              Este tomador não tem CNPJ cadastrado — sem ele a Ana não consegue gerar nota. Deixe como “só controle” ou cadastre o
              tomador com CNPJ.
            </p>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              label="Apelido"
              required
              value={form.apelido}
              onChange={(e) => atualizarCampo("apelido", e.target.value)}
              placeholder='Como você chama esse tomador (ex.: "Awin")'
            />
            {!form.sem_nota && (
              <>
              <div className="sm:col-span-2" data-tour="form-codigo">
                <CampoServico
                  label="Código do serviço"
                  required
                  codigo={form.cod_trib_nacional}
                  onChange={(codigo) => atualizarCampo("cod_trib_nacional", codigo)}
                  destaques={destaquesCodigo}
                  hint="O tipo de serviço, pela lista nacional. Afiliados costumam usar 17.06.01 (propaganda e publicidade) — confirme com seu contador."
                />
              </div>
              <CampoCodigoUsado
                label="Código de tributação municipal"
                valor={form.cod_trib_municipal}
                onChange={(c) => atualizarCampo("cod_trib_municipal", c)}
                opcoes={codigosUsados.municipais}
                hint={
                  codigosUsados.municipais.length
                    ? "Os que já saíram nas suas notas com esse serviço. Só é preciso se a sua prefeitura exigir."
                    : "Só se a sua prefeitura exigir — escolha “Nenhum” se não souber."
                }
              />
              <CampoCodigoUsado
                label="Item da NBS"
                valor={form.cod_nbs}
                onChange={(c) => atualizarCampo("cod_nbs", mascaraNbs(c))}
                opcoes={codigosUsados.nbs}
                formatar={mascaraNbs}
                hint={
                  codigosUsados.nbs.length
                    ? "Nomenclatura Brasileira de Serviços — os que já saíram nas suas notas com esse serviço."
                    : "Nomenclatura Brasileira de Serviços (9 dígitos). Opcional."
                }
              />
              </>
            )}
          </div>

          {!form.sem_nota && (
            <>
            <div className="mt-5">
              {modelosDescricao.filter((m) => m !== form.template_descricao).length > 0 && (
                <div className="mb-3 flex flex-col gap-1.5">
                  {modelosDescricao
                    .filter((m) => m !== form.template_descricao)
                    .map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => atualizarCampo("template_descricao", m)}
                        className="flex items-start gap-2 rounded-lg border border-dashed border-accent-200 px-3 py-2 text-left text-xs text-slate-600 hover:border-accent-400 hover:bg-accent-50/50 dark:border-accent-900/50 dark:text-slate-300"
                      >
                        <Sparkles size={14} className="mt-0.5 shrink-0 text-accent-500" />
                        <span>
                          <span className="font-semibold text-accent-700 dark:text-accent-200">Usar a que já foi cadastrada pra este tomador: </span>
                          {previaDescricao(m)}
                        </span>
                      </button>
                    ))}
                </div>
              )}
              <DescricaoNota modelo={form.template_descricao} onChange={(m) => atualizarCampo("template_descricao", m)} />
            </div>

            <details className="mt-5 rounded-xl border border-slate-200 dark:border-slate-700">
              <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                Mais opções
                <span className="ml-2 text-xs font-normal text-slate-400">quase ninguém precisa mexer</span>
              </summary>
              <div className="border-t border-slate-200 p-4 dark:border-slate-700">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <CampoCidade
                  label="Cidade onde o serviço é prestado"
                  codigo={form.cod_local_prestacao}
                  onChange={(codigo) => atualizarCampo("cod_local_prestacao", codigo)}
                  hint="Normalmente é a sua própria cidade."
                />
                <Field label="Série da nota" value={form.serie} onChange={(e) => atualizarCampo("serie", e.target.value)} hint="Deixe 1 se não souber." />
              </div>
            <label className="mt-4 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={form.requer_revisao}
                onChange={(e) => atualizarCampo("requer_revisao", e.target.checked)}
                className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
              />
              Quero revisar cada nota antes de assinar
            </label>

            <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-700">
              <input
                type="checkbox"
                role="switch"
                checked={form.incluir_intermediario}
                onChange={(e) => atualizarCampo("incluir_intermediario", e.target.checked)}
                className="peer sr-only"
              />
              <span
                aria-hidden
                className="relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full bg-slate-300 transition-colors peer-checked:bg-primary-600 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 dark:bg-slate-600 after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:after:translate-x-4"
              />
              <span className="text-sm text-slate-700 dark:text-slate-300">
                Declarar o marketplace como intermediário
                <span className="mt-0.5 block text-xs text-slate-400 dark:text-slate-500">
                  Nas notas emitidas para vendedores (ex.: Shopee), o tomador cadastrado aqui entra como intermediário na NFS-e.
                </span>
              </span>
            </label>
              </div>
            </details>
            </>
          )}

          {editando && (
            <label className="mt-2 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={form.ativo}
                onChange={(e) => atualizarCampo("ativo", e.target.checked)}
                className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
              />
              Tomador ativo
            </label>
          )}
        </Card>

        {editando && (
          <Card className="p-5">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Calendário</h2>
            <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">Opcional — aparece no Calendário e na lista de Tomadores.</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {!form.sem_nota && (
                <Field
                  label="Dia de gerar a nota"
                  type="number"
                  min={1}
                  max={31}
                  value={form.dia_limite_emissao}
                  onChange={(e) => atualizarCampo("dia_limite_emissao", e.target.value)}
                  hint="Dia do mês em que você costuma gerar a nota deste tomador."
                />
              )}
              {financeiro && (
                <Field
                  label="Dias até o pagamento cair"
                  type="number"
                  min={0}
                  value={form.dias_para_recebimento}
                  onChange={(e) => atualizarCampo("dias_para_recebimento", e.target.value)}
                  hint="Contados a partir da data de emissão da nota."
                />
              )}
            </div>
          </Card>
        )}

        {!form.sem_nota && (
          <Card className="p-6">
            <h2 className="mb-1 text-base font-semibold text-slate-800 dark:text-slate-200">Envio da nota</h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              Como a nota chega a este tomador. Em cada nota dá pra mudar na hora — e o último jeito usado fica lembrado.
            </p>

            <fieldset className="mb-5">
              <legend className="mb-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">Como este tomador recebe a nota</legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {FORMAS_ENVIO.map((f) => {
                  const Icone = f.icone
                  return (
                    <label key={f.valor} className="relative cursor-pointer">
                      <input
                        type="radio"
                        name="envio_canal"
                        value={f.valor}
                        checked={(form.envio_canal ?? "email") === f.valor}
                        onChange={() => atualizarCampo("envio_canal", f.valor)}
                        className="peer sr-only"
                      />
                      <span className="flex h-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-primary-300 peer-checked:border-primary-500 peer-checked:bg-primary-50 peer-checked:text-primary-800 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 dark:border-slate-600 dark:text-slate-300 dark:peer-checked:bg-primary-900/30 dark:peer-checked:text-primary-200">
                        <Icone size={15} className="shrink-0" aria-hidden />
                        {f.titulo}
                      </span>
                    </label>
                  )
                })}
              </div>
              <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">{DICA_FORMA[form.envio_canal ?? "email"]}</p>
              {form.envio_canal === "portal" && (
                <div className="mt-3">
                  <Field
                    label="Link do portal"
                    inputMode="url"
                    autoComplete="url"
                    value={form.portal_url}
                    onChange={(e) => atualizarCampo("portal_url", e.target.value)}
                    placeholder="https://fornecedores.empresa.com.br"
                    maxLength={400}
                    hint="Aparece como “Abrir portal” na hora de enviar cada nota."
                  />
                </div>
              )}
            </fieldset>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="E-mail do tomador"
                type="email"
                value={form.email_contato}
                onChange={(e) => atualizarCampo("email_contato", e.target.value)}
                placeholder="financeiro@empresa.com"
              />
              <Field
                label="WhatsApp do tomador"
                type="tel"
                value={form.whatsapp_contato}
                onChange={(e) => atualizarCampo("whatsapp_contato", e.target.value)}
                placeholder="(92) 99999-0000"
              />
            </div>

            <details
              className="group mt-5 rounded-xl border border-slate-200 dark:border-slate-700"
              open={emailAberto}
              onToggle={(e) => setEmailAberto(e.currentTarget.open)}
            >
              <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                E-mail da nota pra este tomador
                <span className="ml-2 text-xs font-normal text-slate-400">destinatário, cópia, assunto, texto e anexos</span>
              </summary>
              <div className="border-t border-slate-200 p-4 dark:border-slate-700">
                <EditorModeloEmail
                  valor={form.email_modelo}
                  onChange={(v) => setForm((f) => ({ ...f, email_modelo: v }))}
                  herdado={{
                    assunto: prestadorModelo?.email_assunto_padrao,
                    mensagem: prestadorModelo?.email_mensagem_padrao,
                    anexos: prestadorModelo?.email_anexos_padrao ?? null,
                    rotulo: "o modelo padrão de Empresa › E-mails",
                  }}
                  mostrarCopia
                  dicaCopia={
                    prestadorModelo?.email_copia_padrao
                      ? `Além destes, vai cópia pra ${prestadorModelo.email_copia_padrao} (Empresa › E-mails).`
                      : undefined
                  }
                  mostrarPara
                  paraPadrao={form.email_contato.trim() || null}
                />
              </div>
            </details>
          </Card>
        )}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => navigate("/app/tomadores")}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando}>
            {enviando ? "Salvando..." : editando ? "Salvar alterações" : "Cadastrar tomador"}
          </Button>
        </div>
      </form>
    </div>
  )
}
