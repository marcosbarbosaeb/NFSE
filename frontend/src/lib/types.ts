export interface Usuario {
  email: string
  prestador_id: string
  demo?: boolean
}

export interface CadastroRequest {
  email: string
  senha: string
  razao_social: string
  cpf_cnpj: string
  cod_municipio: string
  cep?: string | null
  logradouro?: string | null
  numero?: string | null
  complemento?: string | null
  bairro?: string | null
  codigo_indicacao?: string | null
}

export interface VinculoResumo {
  id: string
  apelido: string
  tomador_razao_social: string
  tomador_cnpj: string
  serie: string
  template_descricao: string
  requer_revisao: boolean
  ativo?: boolean
  tomador_id?: string | null
  cod_trib_nacional?: string | null
  cod_local_prestacao?: string | null
  dia_limite_emissao?: number | null
  dias_para_recebimento?: number | null
  emissao_id?: string | null
  emissao_estado?: string | null
  emissao_valor?: number | null
  emissao_quantidade?: number
  metodo_captura_valor?: string
}

export interface VendedorShopee {
  competencia: string
  documento: string
  tipo_documento: "CNPJ" | "CPF" | "NIF"
  razao_social: string
  lojas: string[]
  valor: number
  cidade: string | null
  uf: string | null
  estrangeiro: boolean
  avisos: string[]
  ja_gerada: boolean
}

export interface PreviaShopee {
  linhas_lidas: number
  linhas_ignoradas: string[]
  competencias: { competencia: string; vendedores: number; total: number; estrangeiros: number; ja_geradas: number }[]
  vendedores: VendedorShopee[]
}

export interface GeracaoShopee {
  geradas: number
  ja_existiam: number
  puladas: number
  total: number
  erros: string[]
}

export interface ServicoNacional {
  codigo: string
  descricao: string
  grupo: string
}

export interface EmissaoResumoLinha {
  emissao_id: string
  vinculo_id?: string | null
  quantidade?: number
  apelido: string
  tomador_razao_social: string
  competencia: string
  valor: number
  estado: string
  estado_label: string
  envio_status: string | null
  pagamento_recebido: boolean
  tem_pdf?: boolean
  tem_email?: boolean
  homologacao?: boolean
}

export interface AtencaoItem {
  tipo: string
  titulo: string
  mensagem: string
  link?: string | null
  link_label?: string | null
}

export interface PontoSerieMensal {
  competencia: string
  valor: number
}

export interface Tomador {
  id: string
  cnpj: string
  razao_social: string
  cod_municipio: string
  cep: string | null
  logradouro: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  sug_cod_trib_nacional?: string | null
  sug_template_descricao?: string | null
  sug_dia_emissao?: number | null
  sug_dias_recebimento?: number | null
}

export interface TomadorCriarRequest {
  cnpj: string
  razao_social: string
  cod_municipio: string
  cep?: string | null
  logradouro?: string | null
  numero?: string | null
  complemento?: string | null
  bairro?: string | null
}

export interface VinculoDetalhe {
  id: string
  apelido: string
  tomador: Tomador
  cod_local_prestacao: string
  cod_trib_nacional: string
  cod_trib_municipal: string | null
  template_descricao: string
  metodo_captura_valor: string
  serie: string
  requer_revisao: boolean
  ativo: boolean
  dia_limite_emissao: number | null
  dias_para_recebimento: number | null
  email_contato: string | null
  whatsapp_contato: string | null
  email_assunto?: string | null
  email_mensagem?: string | null
  email_anexos?: "pdf_xml" | "pdf" | "xml" | null
  email_copia?: string | null
}

export interface VinculoCriarRequest {
  tomador_id?: string | null
  novo_tomador?: TomadorCriarRequest | null
  apelido: string
  cod_local_prestacao: string
  cod_trib_nacional: string
  cod_trib_municipal?: string | null
  template_descricao: string
  metodo_captura_valor?: string
  serie?: string
  requer_revisao?: boolean
  dia_limite_emissao?: number | null
  dias_para_recebimento?: number | null
  email_contato?: string | null
  whatsapp_contato?: string | null
  email_assunto?: string | null
  email_mensagem?: string | null
  email_anexos?: string | null
  email_copia?: string | null
}

export type VinculoAtualizarRequest = Partial<Omit<VinculoCriarRequest, "tomador_id" | "novo_tomador">> & {
  ativo?: boolean
}

export type TipoEventoCalendario =
  | "prazo_emissao"
  | "recebimento_previsto"
  | "recebimento_confirmado"
  | "revisar_aliquota"
  | "manual"

export interface EventoCalendario {
  data: string
  tipo: TipoEventoCalendario
  titulo: string
  vinculo_id: string | null
  apelido: string | null
  valor: number | null
  // Marco 15 — só preenchidos pra tipo "manual" (os outros 3 tipos são
  // computados na hora pelo backend, sem id próprio).
  id?: string | null
  descricao?: string | null
  // Marco 17 — categoria (manual) e ajuste de ocorrência (calculados).
  categoria?: CategoriaEventoManual | null
  chave?: string | null
  ajustado?: boolean
  data_original?: string | null
  regra_valor?: number | null
}

export type CategoriaEventoManual = "lembrete" | "recebimento_previsto" | "prazo_emissao"

export interface Calendario {
  inicio: string
  fim: string
  eventos: EventoCalendario[]
}

export interface EventoManualCriarRequest {
  data: string
  titulo: string
  descricao?: string | null
  categoria?: CategoriaEventoManual
  valor?: number | null
  vinculo_id?: string | null
}

export type EventoManualAtualizarRequest = Partial<EventoManualCriarRequest>

// --- Marco 15 (item 4): assinatura/cobrança ---

export type StatusAssinatura = "cortesia" | "trial" | "ativa" | "inadimplente" | "cancelada"

export interface Assinatura {
  status: StatusAssinatura
  ativa: boolean
  trial_termina_em: string | null
  tem_assinatura_stripe: boolean
}

export interface CheckoutSessao {
  url: string
}

// --- Marco 15 (item 5): extrato bancário em PDF ---

export interface TransacaoExtraida {
  linha: number
  data: string | null
  descricao: string
  valor: number
  credito: boolean
}

export interface ExtratoExtraido {
  total_transacoes: number
  transacoes: TransacaoExtraida[]
  formato?: string
  linhas_lidas?: number
}

export interface ItemConfirmarExtrato {
  vinculo_id: string
  competencia: string
  valor: number
  data_recebimento?: string | null
}

export interface ItemConfirmadoExtrato {
  indice: number
  ok: boolean
  mensagem: string | null
  pagamento_id: string | null
}

export interface ConfirmarExtratoResultado {
  total: number
  sucesso: number
  erro: number
  despesas_registradas?: number
  itens: ItemConfirmadoExtrato[]
}

// --- Marco 14: NFS-e (lista + nova emissão + detalhe), Recebimentos, Despesas, Configurações ---

export interface EmissaoListaLinha {
  id: string
  vinculo_id: string
  apelido: string
  tomador_razao_social: string
  competencia: string
  valor: number
  serie: string
  n_dps: number | null
  estado: string
  estado_label: string
  criado_em: string
  pagamento_recebido: boolean
  envio_status?: string | null
  tem_pdf?: boolean
  tem_email?: boolean
  homologacao?: boolean
}

export interface GerarDpsRequest {
  vinculo_id: string
  competencia: string
  valor: number
  ordem?: string | null
  aliq_sn?: number | null
  tpAmb?: string
}

export interface VerificarDuplicata {
  existe: boolean
  emissao_id: string | null
  estado: string | null
}

export interface Municipio {
  codigo: string
  nome: string
  uf: string
  rotulo: string
}

export interface ConsultaCnpj {
  razao_social: string
  logradouro: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  cep: string | null
  municipio: string
  uf: string
  cod_municipio_sugerido: string | null
  situacao_cadastral: string | null
}

export interface Emissao {
  id: string
  estado: string
  n_dps: number
  serie: string
  competencia: string
  valor: number
  apelido: string
  tomador: string
  descricao: string
  xml: string | null
  chave_acesso: string | null
  erro_detalhe: string | null
  atualizado_em: string
}

export interface PrestadorVisual {
  razao_social: string
  cnpj: string | null
  inscricao_municipal: string | null
  endereco: string | null
  telefone: string | null
  email: string | null
}

export interface TomadorVisual {
  razao_social: string | null
  cnpj: string | null
  endereco: string | null
}

export interface ServicoVisual {
  descricao: string | null
  codigo_tributacao_nacional: string | null
  codigo_tributacao_municipal: string | null
  codigo_local_prestacao: string | null
}

export interface ValoresVisual {
  valor_servico: number
  issqn: string | null
  total_tributos: string | null
}

export interface NotaVisual {
  estado: string
  estado_label: string
  ambiente: string | null
  ambiente_label: string | null
  id_dps: string | null
  serie: string
  n_dps: number
  competencia: string
  dh_emissao: string | null
  chave_acesso: string | null
  erro_detalhe: string | null
  prestador: PrestadorVisual
  tomador: TomadorVisual
  servico: ServicoVisual
  valores: ValoresVisual
  xml_disponivel: boolean
}

export interface ImportacaoLinha {
  linha: number
  apelido: string
  ok: boolean
  mensagem: string | null
  emissao_id: string | null
  n_dps: number | null
}

export interface ImportacaoCsvResultado {
  total: number
  sucesso: number
  erro: number
  linhas: ImportacaoLinha[]
}

export type CanalEnvio = "download" | "email" | "whatsapp" | "direto_fornecedor" | "mensagem_pronta"

export interface Envio {
  id: string
  emissao_id: string
  canal: CanalEnvio
  status: string
  tentativas: number
  enviado_em: string | null
  destino?: string | null
  erro?: string | null
}

export interface OpcoesEnvio {
  email_habilitado: boolean
  email_motivo_desabilitado: string | null
  email_destino: string | null
  whatsapp_destino: string | null
  link_publico: string
  tem_pdf: boolean
  vinculo_id: string | null
}

export interface Pagamento {
  id: string
  apelido: string
  competencia: string
  valor: number
  data_recebimento: string | null
}

export interface RegistrarPagamentoRequest {
  vinculo_id: string
  competencia: string
  valor: number
  data_recebimento?: string | null
}

export interface Despesa {
  id: string
  categoria: string
  competencia: string
  valor: number
}

export interface RegistrarDespesaRequest {
  categoria: string
  competencia: string
  valor: number
}

export interface CertificadoStatus {
  carregado: boolean
  validade: string | null
  vencido: boolean
}

export interface Prestador {
  razao_social: string
  cpf_cnpj: string
  inscricao_municipal: string | null
  cod_municipio: string
  cep: string | null
  logradouro: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  telefone: string | null
  email: string | null
  municipio_rotulo: string | null
  dia_lembrete_aliquota: number | null
  // Marco 16, item 5 — alíquota de referência do Simples Nacional (só pra
  // pré-preencher a Nova emissão; confirmação continua sempre obrigatória).
  aliquota_atual: number | null
  aliquota_atualizada_em: string | null
  tp_amb_padrao?: "1" | "2"
  email_assunto_padrao?: string | null
  email_mensagem_padrao?: string | null
  email_anexos_padrao?: "pdf_xml" | "pdf" | "xml" | null
}

export interface AliquotaAtualizarRequest {
  aliquota: number
}

export interface DashboardResumo {
  competencia: string
  total_vinculos: number
  emitidas: number
  aguardando: number
  a_receber: number
  pagamentos_pendentes: number
  recebido_no_mes: number
  recebido_mes_anterior: number
  delta_recebimentos_pct: number | null
  serie_recebimentos: PontoSerieMensal[]
  emissoes: EmissaoResumoLinha[]
  atencao: AtencaoItem[]
  a_receber_total?: number
  notas_a_receber?: number
  recebido_total?: number
  notas_recebidas?: number
}

export interface PendenciaItem {
  tipo: "assinar" | "prefeitura" | "erro" | "enviar_tomador" | "gerar" | "receber" | string
  titulo: string
  acao: string
  link: string
  emissao_id?: string | null
  vinculo_id?: string | null
  valor?: number | null
  competencia?: string | null
}

export interface AgendaItem {
  data: string
  tipo: string
  titulo: string
  detalhe?: string | null
  valor?: number | null
}

export interface Proximos {
  pendencias: PendenciaItem[]
  total_pendencias: number
  agenda: AgendaItem[]
}

export interface NotaAberta {
  vinculo_id: string
  apelido: string
  competencia: string
  emissao_id: string
  estado: string
  valor: number
  quantidade: number
  emitida_em: string
  dias_em_aberto: number
}

export interface PreviaEmail {
  destino: string | null
  copia: string[]
  assunto: string
  texto: string
  anexos: "pdf_xml" | "pdf" | "xml"
  arquivos: string[]
  motivo_desabilitado: string | null
}

export interface ModeloEmailPadrao {
  assunto: string
  mensagem: string
  codigos: { codigo: string; descricao: string; exemplo: string }[]
}

export interface OrdemAwin {
  numero: string | null
  valor: number | null
  data: string | null
  moeda: string | null
  competencia_sugerida: string | null
  avisos: string[]
  ja_usada: { emissao_id: string; apelido: string; competencia: string; estado: string } | null
}

export interface Indicacao {
  codigo: string
  link: string
  ativos: number
  total: number
  desconto_pct: number
  desconto_aplicado_pct: number
  pct_por_indicado: number
  pct_maximo: number
  cobranca_ativa: boolean
  indicados: { nome: string; status: string; desde: string }[]
}

export interface CanaisSuporte {
  email: string
  whatsapp: string | null
  formulario: boolean
}
