export interface Usuario {
  email: string
  prestador_id: string
  demo?: boolean
  nome?: string | null
  /** Empresa ativa é conta de teste: notas só em homologação, e-mails só pra quem testa. */
  teste?: boolean
  /** Produtos ligados na empresa ativa (emissor, financeiro). */
  modulos?: ("emissor" | "financeiro")[]
  /** Na empresa ativa: dono ou contador convidado (06/10/2026). */
  papel?: "dono" | "contador"
  /** O que o contador pode fazer nela (o dono pode tudo). */
  permissoes?: PermissaoContador[]
  /** Este login atende empresas como contador, ou tem convite esperando. */
  atende_empresas?: boolean
  /** Assinatura da empresa ativa. */
  acesso?: SituacaoAcesso
  /** Conta só de contador, fora da empresa de um cliente: sem notas nem financeiro próprios. */
  so_contador?: boolean
}

// --- Contador com permissões e bloqueio sem assinatura (06/10/2026) ---

export type PermissaoContador = "emitir" | "enviar" | "tomadores" | "financeiro" | "empresa"

export interface SituacaoAcesso {
  liberado: boolean
  /** cortesia | assinatura | pagamento_pendente | liberacao | teste | teste_acabou | cancelada | sem_assinatura */
  motivo: string
  ate: string | null
  dias_restantes: number | null
  /** O bloqueio de quem não tem assinatura está valendo na plataforma. */
  bloqueio_ativo?: boolean
  /** Empresa só pra consulta: não gera, não envia, não lança. */
  bloqueado?: boolean
  mensagem?: string | null
  /** A cobrança (Stripe) está no ar. Sem ela, depois do teste a pessoa pede a liberação à equipe. */
  cobranca_ativa?: boolean
  liberacao_pedida_em?: string | null
}

export interface PermissaoInfo {
  id: PermissaoContador
  nome: string
  descricao: string
}

export interface AcessoContador {
  id: string
  email: string
  nome: string | null
  status: "pendente" | "ativo"
  permissoes: PermissaoContador[]
  criado_em: string | null
  aceito_em: string | null
}

export interface RegistroContador {
  id: string
  email: string
  acao: string
  quando: string
}

export interface AcessosDaEmpresa {
  permissoes: PermissaoInfo[]
  acessos: AcessoContador[]
  historico: RegistroContador[]
}

export interface ConviteContador {
  id: string
  empresa: string
  cnpj: string
  convidado_por: string | null
  permissoes: PermissaoContador[]
  criado_em: string | null
}

export interface ClienteAtendido {
  id: string
  prestador_id: string
  empresa: string
  nome_fantasia: string | null
  cnpj: string
  permissoes: PermissaoContador[]
  desde: string | null
  modulos: string[]
  pode_emitir: boolean
  aviso: string | null
  situacao: SituacaoAcesso
  /** O que tem pra fazer nesta empresa (só títulos e quantidades). */
  pendencias?: PendenciaDoCliente[]
  total_pendencias?: number
  /** Números da empresa pro painel do contador (backend/app/services/raio_x.py). */
  raio_x?: RaioX | null
  alertas?: AlertaDoCliente[]
  /** Quem cuida da empresa (o dono que convidou), pra falar com ele. */
  dono?: { nome: string | null; email: string; telefone: string | null } | null
  /** Pasta do mês (do mês passado): o que falta e o que a empresa mandou de novo. */
  pasta?: ResumoPasta | null
}

export interface ResumoPasta {
  competencia: string
  itens: number
  pendentes: number
  prontos: number
  novidades: { mensagens: number; arquivos: number }
}

export interface RaioX {
  /** Mês a mês: os 12 anteriores + o atual (notas autorizadas e valor). */
  serie?: { competencia: string; notas: number; valor: number }[]
  municipio?: string | null
  inscricao_municipal?: string | null
  /** Alíquota de referência do Simples informada no cadastro. */
  aliquota?: number | null
  /** Conciliação dos três últimos meses (do mais antigo pro atual). */
  fechamentos?: { competencia: string; estado: "fechado" | "pendente" | "aguardando" | "vazio"; notas_atrasadas: number; extrato_pendentes: number }[]
  /** "1" fora do Simples, "2" MEI, "3" Simples (ME/EPP); null = não informado */
  regime: string | null
  regime_nome: string
  competencia: string
  notas_mes: number
  faturado_mes: number
  faturado_ano: number
  /** Notas autorizadas nos 12 meses antes do mês corrente (base do RBT12). */
  faturado_12m: number
  limite: number | null
  limite_pct: number | null
  certificado: { situacao: "ok" | "falta" | "vencido" | "vencendo"; validade: string | null; dias: number | null } | null
  recusadas: number
  fechamento: { competencia: string; estado: "fechado" | "pendente" | "aguardando" | "vazio" } | null
  sem_nota: number | null
}

export interface AlertaDoCliente {
  tipo: string
  nivel: "critico" | "atencao"
  texto: string
  link: string
}

export interface ResumoCarteira {
  empresas: number
  notas_mes: number
  faturado_mes: number
  pendencias: number
  alertas_criticos: number
  alertas: number
  competencia: string | null
}

export interface PendenciaDoCliente {
  tipo: string
  titulo: string
  link: string
  quantidade: number
  atrasada: boolean
}

/** Bonificação do contador: % de cada mensalidade paga pelos clientes que ele atende. */
export interface BonificacaoContador {
  pct: number
  ativo: boolean
  painel: string
  link: string
  clientes: number
  clientes_pagando: number
  total: number
  a_receber: number
}

export interface Atendimentos {
  permissoes: PermissaoInfo[]
  ativa: string
  convites: ConviteContador[]
  clientes: ClienteAtendido[]
  bonificacao?: BonificacaoContador | null
  resumo?: ResumoCarteira
}

export interface CadastroRequest {
  email: string
  senha: string
  /** WhatsApp com DDD (obrigatório desde 08/10/2026). */
  whatsapp: string
  razao_social: string
  cpf_cnpj: string
  cod_municipio: string
  cep?: string | null
  logradouro?: string | null
  numero?: string | null
  complemento?: string | null
  bairro?: string | null
  codigo_indicacao?: string | null
  /** /cadastro?teste=1 — conta de teste. */
  modo_teste?: boolean
  /** Produto contratado: emissor (padrão), financeiro ou ambos. */
  produto?: "emissor" | "financeiro" | "ambos"
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
  /** Só controle de recebimento — a Ana não gera nota pra ele. */
  sem_nota?: boolean
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
  competencias: { competencia: string; vendedores: number; total: number; estrangeiros: number; ja_geradas: number; total_estrangeiros?: number; total_ja_geradas?: number }[]
  vendedores: VendedorShopee[]
}

export interface GeracaoShopee {
  geradas: number
  ja_existiam: number
  puladas: number
  total: number
  erros: string[]
  /** "Gerar e fazer tudo": o lote em segundo plano que continua a sequência. */
  lote?: Lote | null
  aviso_lote?: string | null
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
  /** Linha de vendedores: quantas notas já foram entregues, de quantas autorizadas. */
  enviadas?: number | null
  a_enviar?: number | null
  /** Linha de vendedores: a conta do grupo pras colunas Assinatura e Prefeitura. */
  total_grupo?: number
  assinadas?: number
  autorizadas?: number
  recusadas?: number
  tem_pdf?: boolean
  tem_email?: boolean
  homologacao?: boolean
  envio_forma?: FormaEnvio | null
  /** Linha das notas de vendedores da Shopee (pagamento junto com a nota da Shopee). */
  vendedores?: boolean
  /** Motivo da recusa da prefeitura (só no estado "erro"). */
  erro_detalhe?: string | null
  erro_corrigivel?: boolean
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
  /** Padrão do catálogo (05/10/2026): NBS e "mês de referência" da descrição.
   * O código municipal não é sugerido: muda de cidade pra cidade. */
  sug_cod_nbs?: string | null
  sug_meses_atras?: number | null
  /** Como este tomador costuma receber a nota e o modelo do e-mail (sem dado pessoal). */
  sug_envio_formas?: FormaDeEnvio[] | null
  sug_email_assunto?: string | null
  sug_email_mensagem?: string | null
  sug_email_anexos?: "pdf_xml" | "pdf" | "xml" | null
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
  email_para?: string | null
  cod_nbs?: string | null
  incluir_intermediario?: boolean
  envio_canal?: FormaEnvio | null
  envio_formas?: FormaDeEnvio[] | null
  email_extras?: EmailExtra[] | null
  descricao_meses_atras?: number
  portal_url?: string | null
  sem_nota?: boolean
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
  email_para?: string | null
  cod_nbs?: string | null
  incluir_intermediario?: boolean
  envio_canal?: FormaEnvio | null
  envio_formas?: FormaDeEnvio[] | null
  email_extras?: EmailExtra[] | null
  descricao_meses_atras?: number
  portal_url?: string | null
  sem_nota?: boolean
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
  situacao?: string
  liberado_ate?: string | null
  bloqueio_ativo?: boolean
  com_financeiro?: boolean
  uso?: UsoDoPlano
  financeiro_a_parte?: { valor: number; disponivel: boolean }
  plano?: "emissor" | "financeiro" | "ambos" | null
  planos?: PlanoAssinatura[]
  modulos_pelo_plano?: boolean
}

/** Notas autorizadas no mês x limite do plano (07/10/2026). */
export interface UsoDoPlano {
  competencia: string
  usadas: number
  limite: number | null
  restantes: number | null
  pct: number | null
  /** "perto" = 80% ou mais; "limite" = chegou no limite. */
  aviso: "perto" | "limite" | null
  plano: string | null
  plano_nome: string | null
  em_teste: boolean
  proximo_plano: { id: string; nome: string; limite_notas: number | null; valor: number | null } | null
  excedente_preco: number
  /** Tem plano assinado: pode aceitar pagar por nota a mais. */
  excedente_pode: boolean
  excedente_aceito: boolean
  excedentes: number
  excedente_valor: number
  trava_ligada: boolean
  travado: boolean
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
  // Sugestões de classificação (03/10/2026)
  chave?: string
  vinculo_id?: string | null
  competencia?: string | null
  emissao_id?: string | null
  categoria?: string | null
  tipo_despesa?: "despesa" | "retirada"
  origem_sugestao?: "lembrado" | "nome" | "valor" | null
  nota?: { emissao_id: string; competencia: string; valor: number; exata: boolean } | null
  ja_lancado?: boolean
}

/** Nota em aberto que um recebimento pode pagar (baixa por nota). */
export interface NotaParaBaixa {
  emissao_id: string
  vinculo_id: string
  competencia: string
  valor: number
  n_dps?: number | null
}

// --- Conciliação do extrato (05/10/2026) ---

export interface LancamentoPendente {
  id: string
  data: string | null
  descricao: string
  valor: number
  credito: boolean
  vinculo_id: string | null
  emissao_id: string | null
  nota_exata: boolean
  categoria: string
  tipo_despesa: "despesa" | "retirada"
  origem_sugestao: "lembrado" | "nome" | "valor" | null
  /** Conta a pagar em aberto que bate com essa saída. */
  despesa_id: string | null
}

export interface ContaAPagar {
  id: string
  nome: string
  categoria: string
  tipo: "despesa" | "retirada"
  competencia: string
  vencimento: string | null
  valor: number
}

export interface PainelConciliacao {
  lancamentos: LancamentoPendente[]
  ignorados: number
  notas_abertas: (NotaParaBaixa & { apelido: string })[]
  contas_a_pagar: ContaAPagar[]
  categorias: string[]
  categorias_retirada: string[]
}

export interface ExtratoExtraido {
  total_transacoes: number
  transacoes: TransacaoExtraida[]
  categorias?: string[]
  categorias_retirada?: string[]
  notas_abertas?: NotaParaBaixa[]
  formato?: string
  linhas_lidas?: number
}

export interface ItemConfirmarExtrato {
  vinculo_id: string
  competencia: string
  valor: number
  data_recebimento?: string | null
  descricao?: string | null
  emissao_id?: string | null
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
  sem_nota?: RecebimentoSemNota[]
  /** Lançamentos do extrato guardados sem classificar (Conciliação). */
  pendentes?: number
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
  envio_status?: string | null
  tem_pdf?: boolean
  tem_email?: boolean
  homologacao?: boolean
  avulsa?: boolean
  envio_forma?: FormaEnvio | null
  /** Motivo da recusa da prefeitura (só no estado "erro"). */
  erro_detalhe?: string | null
  erro_corrigivel?: boolean
}

export interface GerarDpsRequest {
  vinculo_id: string
  competencia: string
  valor: number
  ordem?: string | null
  aliq_sn?: number | null
  tpAmb?: string
  /** AAAA-MM-DD — dia de competência escolhido; sem = hoje. */
  data_competencia?: string | null
  /** Pedido que veio de outro módulo (ex.: "fin:pagamento:<id>") — o emissor só repassa. */
  origem?: string | null
  /** Trocar a nota do mês que ainda não foi enviada por esta. */
  substituir?: boolean
}

export interface VerificarDuplicata {
  existe: boolean
  emissao_id: string | null
  estado: string | null
  valor?: number | null
  /** A nota existente ainda não foi pra prefeitura: dá pra gerar outra no lugar. */
  pode_substituir?: boolean
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
  n_dps: number | null
  serie: string
  competencia: string
  valor: number
  apelido: string
  tomador: string
  descricao: string
  xml: string | null
  chave_acesso: string | null
  erro_detalhe: string | null
  erro_corrigivel?: boolean
  atualizado_em: string
  /** 'importada' = trazida do Emissor Nacional (dá pra mudar de tomador). */
  origem?: "ana" | "importada"
  vinculo_id?: string | null
  avulsa?: boolean
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

export type CanalEnvio = "download" | "email" | "email_geral" | "whatsapp" | "direto_fornecedor" | "mensagem_pronta" | "drive"

/** Como o tomador recebe a nota (configurado no tomador). null = e-mail. */
export type FormaEnvio = "email" | "whatsapp" | "portal" | "nenhum"

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
  /** Resposta do POST /pagamentos: caiu sem nota do tomador nesse mês. */
  sem_nota?: boolean
  vinculo_id?: string | null
  /** A nota que esse dinheiro paga. */
  emissao_id?: string | null
  /** Recebimento sem nota de um tomador que recebe nota: dá pra gerar a dele. */
  pode_gerar_nota?: boolean
}

/** GET /financeiro/recebimentos-sem-nota — dinheiro que caiu sem nota no mês
 * (ex.: Mercado Livre paga antes). Gerar: /app/nfse?gerar={vinculo_id}&pagamento={pagamento_id}.
 * Ignorar: POST /painel/pendencias/ignorar {chave}. */
export interface RecebimentoSemNota {
  pagamento_id: string
  vinculo_id: string
  apelido: string
  competencia: string
  valor: number
  data_recebimento: string | null
  chave: string
}

export interface RegistrarPagamentoRequest {
  vinculo_id: string
  competencia: string
  valor: number
  data_recebimento?: string | null
  emissao_id?: string | null
}

export type TipoLancamento = "despesa" | "retirada"

export interface Despesa {
  id: string
  categoria: string
  competencia: string
  valor: number
  descricao?: string | null
  tipo?: TipoLancamento
  conta?: string | null
  vencimento?: string | null
  pago?: boolean
  pago_em?: string | null
  recorrente_id?: string | null
  /** Conta fixa de valor variável ainda sem o valor do mês. */
  /** Conta recorrente com pagamento agendado que cobre este mês (AAAA-MM). */
  agendado_ate?: string | null
  valor_a_definir?: boolean
}

export interface RegistrarDespesaRequest {
  categoria: string
  competencia: string
  valor: number
  descricao?: string | null
  tipo?: TipoLancamento
  conta?: string | null
  vencimento?: string | null
  pago?: boolean
  pago_em?: string | null
}

/** PATCH /despesas/{id} — editar ou ticar ("pagou ✓"). DELETE /despesas/{id}. */
export type AtualizarDespesaRequest = Partial<RegistrarDespesaRequest>

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
  modo_teste?: boolean
  email_assunto_padrao?: string | null
  email_mensagem_padrao?: string | null
  email_anexos_padrao?: "pdf_xml" | "pdf" | "xml" | null
  email_copia_padrao?: string | null
  nome_fantasia?: string | null
  op_simples_nacional?: "1" | "2" | "3" | null
  regime_apuracao_sn?: "1" | "2" | "3" | null
  regime_especial_trib?: string | null
  email_geral_para?: string | null
  email_geral_assunto?: string | null
  email_geral_mensagem?: string | null
  email_geral_anexos?: "pdf_xml" | "pdf" | "xml" | null
}

export type EmitenteAtualizarRequest = Partial<{
  razao_social: string
  nome_fantasia: string | null
  cod_municipio: string
  inscricao_municipal: string | null
  email: string | null
  telefone: string | null
  cep: string | null
  logradouro: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  op_simples_nacional: "1" | "2" | "3"
  regime_apuracao_sn: "1" | "2" | "3"
  regime_especial_trib: string
}>

export interface AliquotaAtualizarRequest {
  aliquota: number
}

export interface DashboardResumo {
  competencia: string
  total_vinculos: number
  emitidas: number
  aguardando: number
  /** Valor das notas do mês (recebimento é do módulo financeiro). */
  faturado_no_mes: number
  faturado_mes_anterior: number
  delta_faturamento_pct: number | null
  serie_faturamento: PontoSerieMensal[]
  emissoes: EmissaoResumoLinha[]
  atencao: AtencaoItem[]
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
  /** POST /painel/pendencias/ignorar {chave, ignorar} — "ignorar este aviso". */
  chave?: string | null
  /** Dia combinado pra fazer (AAAA-MM-DD) e se já passou. */
  data?: string | null
  atrasada?: boolean
  /** Linha que junta várias ("Gerar 8 notas"): cada uma, pra abrir na tela. */
  itens?: PendenciaItem[] | null
  /** O grupo já chega aberto (o dia que vence primeiro). */
  aberto?: boolean
}

export interface AgendaItem {
  data: string
  tipo: string
  titulo: string
  detalhe?: string | null
  valor?: number | null
  /** > 1 quando a linha junta vários avisos iguais do mesmo dia. */
  quantidade?: number
}

export interface Proximos {
  pendencias: PendenciaItem[]
  total_pendencias: number
  agenda: AgendaItem[]
  /** Quantas linhas a agenda dos próximos 30 dias tem (vêm só as primeiras). */
  total_agenda?: number
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
  n_dps?: number | null
}

export interface PreviaEmail {
  destino: string | null
  destinos: string[]
  copia: string[]
  assunto: string
  texto: string
  anexos: "pdf_xml" | "pdf" | "xml"
  arquivos: string[]
  motivo_desabilitado: string | null
  whatsapp?: string | null
  whatsapp_texto?: string
  canal_preferido?: FormaEnvio
  /** Todas as formas de envio padrão do tomador. */
  formas?: FormaDeEnvio[]
  /** Outros destinatários (contador...) com e-mail próprio. */
  extras?: { email: string; rotulo: string | null; assunto: string; texto: string; proprio: boolean }[]
  portal_url?: string | null
  avulsa?: boolean
  geral_destinos?: string[]
  geral_assunto?: string
  geral_texto?: string
}

export interface EnviarEmailBody {
  para?: string[] | null
  copia?: string[] | null
  assunto?: string | null
  texto?: string | null
  /** Quais dos outros destinatários também recebem (sem o campo = todos). */
  extras?: string[]
  salvar_padrao?: boolean
}

export interface WhatsappBody {
  numero?: string | null
  texto?: string | null
  salvar_padrao?: boolean
}

export interface EnviarGeralBody {
  para?: string[] | null
  assunto?: string | null
  texto?: string | null
}

// --- Ações em lote (29/09/2026) ---
// POST /lotes/previa → PreviaLote; POST /lotes → Lote; GET /lotes/{id};
// POST /lotes/{id}/cancelar | /retomar | /refazer-falhas; GET /lotes (recentes)
export type AcaoLote = "email" | "email_geral" | "assinar" | "submeter" | "completo" | "drive"
/** Passos do lote "completo": assinar -> prefeitura -> e-mail ao tomador. */
export type PassoLote = "assinar" | "submeter" | "email"
/** "aguardando": o serviço de e-mail atingiu o limite; o lote volta sozinho. */
export type StatusLote = "fila" | "executando" | "aguardando" | "concluido" | "cancelado" | "interrompido"

export interface CriarLoteBody {
  acao: AcaoLote
  emissao_ids?: string[]
  vinculo_id?: string
  competencia?: string
  reenviar?: boolean
  passos?: PassoLote[]
  /** Lote "drive": o que sobe (pdf | xml | ambos). */
  conteudo?: "pdf" | "xml" | "ambos"
  /** Só as notas avulsas do relatório (uma por vendedor). */
  so_avulsas?: boolean
}

export interface Lote {
  id: string
  acao: AcaoLote
  status: StatusLote
  total: number
  feitos: number
  falhas: number
  erros: { emissao_id: string; nome: string; erro: string }[]
  criado_em: string | null
  concluido_em: string | null
  /** Lote "completo": os passos pedidos e o relatório do que aconteceu. */
  passos?: PassoLote[]
  relatorio?: Record<string, number>
  linhas_relatorio?: string[]
  /** Falhas que ainda estão pendentes de verdade (as já corrigidas saem). */
  pendentes?: number
  resolvidas?: number
  /** Não é falha: nota que não tinha como ser enviada (vendedor sem e-mail). */
  avisos?: { emissao_id: string; nome: string; aviso: string }[]
  /** O resumo do fim do lote não foi pro e-mail da conta (formato inválido). */
  aviso_conta?: string | null
  /** Lote "drive": link da pasta no Google Drive. */
  link?: string | null
  /** Lote aguardando: o limite que estourou foi o do mês (não o do dia). */
  cota_mensal?: boolean
}

/** GET /lotes/andamento?vinculo_id&competencia — o passo a passo do mês. */
export interface AndamentoLote {
  meses: { competencia: string; vinculo_id: string; notas: number }[]
  competencia: string | null
  vinculo_id: string | null
  total: number
  valor: number
  assinadas: number
  autorizadas: number
  enviadas: number
  a_assinar: number
  a_prefeitura: number
  a_enviar: number
  recusadas: { emissao_id: string; nome: string; motivo: string; corrigivel: boolean }[]
  total_recusadas: number
  sem_email: { emissao_id: string; nome: string }[]
  total_sem_email: number
  etapa: "assinar" | "prefeitura" | "enviar" | "pacote"
  /** "Guardar os arquivos" (opcional) já foi feito ou marcado como concluído. */
  pacote_feito?: boolean
  regular: boolean
  lote_ativo: Lote | null
}

export interface PreviaLote {
  acao: AcaoLote
  quantidade: number
}

/** GET /envios/resumo?vinculo_id&competencia — só envios ao fornecedor. */
export interface ResumoEnvios {
  enviados: number
  falhas: number
  notas_sem_envio: number
}

// --- Conta e empresas (29/09/2026) ---
export interface Conta {
  telefone?: string | null
  nome: string | null
  email: string
  demo: boolean
  tem_senha: boolean
  google_conectado: boolean
}

export interface SessaoConectada {
  id: string
  dispositivo: string
  ip: string | null
  criado_em: string | null
  ultimo_acesso: string | null
  atual: boolean
}

export interface Empresa {
  id: string
  razao_social: string
  nome_fantasia: string | null
  cnpj: string
  ativa: boolean
  /** "contador" = empresa de um cliente que este login atende. */
  papel?: "dono" | "contador"
  /** A "casa" de uma conta só de contador (não é empresa de verdade). */
  so_contador?: boolean
}

export interface EmpresaCriarRequest {
  cpf_cnpj: string
  razao_social: string
  nome_fantasia?: string | null
  cod_municipio: string
  cep?: string | null
  logradouro?: string | null
  numero?: string | null
  complemento?: string | null
  bairro?: string | null
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


// --- Financeiro (28/09/2026) ---
// GET /financeiro/resumo?ano=AAAA
export interface ResumoFinanceiro {
  ano: string
  meses: string[] // "01".."12"
  faturado: number[]
  recebido: number[]
  despesas: number[]
  impostos: number[]
  ferramentas: number[]
  retiradas: number[]
  lucro: number[]
  margem: (number | null)[] // %
  saldo_a_distribuir: number[] // acumulado (lucro − retiradas)
  totais: {
    faturado: number
    recebido: number
    despesas: number
    impostos: number
    ferramentas: number
    retiradas: number
    lucro: number
    margem: number | null
    carga_impostos: number | null
    saldo_a_distribuir: number
    a_receber: number
  }
  categorias: { categoria: string; total: number }[]
}

// GET /financeiro/mes?competencia=AAAA-MM (cria os lançamentos das contas fixas do mês)
export interface RotinaDoMes {
  id: string
  nome: string
  feita: boolean
  feita_em: string | null
}

export interface ContasDoMes {
  competencia: string
  contas: Despesa[]
  rotinas: RotinaDoMes[]
  total_previsto: number
  total_pago: number
  a_pagar: number
  rotinas_feitas: number
}

// GET/POST /financeiro/contas-fixas, PATCH/DELETE /financeiro/contas-fixas/{id}
export interface ContaFixa {
  id: string
  nome: string
  categoria: string
  tipo: TipoLancamento
  valor_padrao: number | null
  dia_vencimento: number | null
  conta: string | null
  ativa: boolean
  /** Pagamento agendado até este mês (AAAA-MM, inclusive). */
  agendado_ate?: string | null
}

export interface ContaFixaRequest {
  nome: string
  categoria?: string | null
  tipo?: TipoLancamento
  valor_padrao?: number | null
  dia_vencimento?: number | null
  conta?: string | null
  ativa?: boolean
  agendado_ate?: string | null
}

// GET/POST /financeiro/rotinas, PATCH /financeiro/rotinas/{id} {nome?, ativa?},
// POST /financeiro/rotinas/{id}/check {competencia, feita}
export interface Rotina {
  id: string
  nome: string
  ativa: boolean
}

// --- Importar a planilha de controle ---
// POST /importar/planilha/previa (multipart: arquivo, ano?) → PreviaPlanilha
// POST /importar/planilha (multipart: arquivo, ano?, escolhas=JSON EscolhasPlanilha) → ResultadoPlanilha
export interface ReceitaPlanilha {
  linha: number
  nome: string
  valores: (number | null)[] // 12 meses
  total: number
  /** 0 = pagamento no mês da nota; 1 = pagamento lançado no mês anterior ao da nota. */
  deslocamento: 0 | 1
  nf_nome: string | null
  acao: "vinculo" | "novo"
  vinculo_id: string | null
}

export interface DespesaPlanilha {
  nome: string
  categoria: string
  valores: (number | null)[]
  total: number
  recorrente: boolean
  valor_padrao: number | null
}

export interface PreviaPlanilha {
  ano: number
  receitas: ReceitaPlanilha[]
  despesas: DespesaPlanilha[]
  retiradas: { nome: string; conta: string; valores: (number | null)[]; total: number }[]
  rotinas: { nome: string; feitos: number[] }[]
  notas_na_planilha: number
}

export interface EscolhasPlanilha {
  receitas: { linha: number; acao: "vinculo" | "novo" | "ignorar"; vinculo_id?: string | null; deslocamento: number }[]
  despesas: boolean
  recorrentes: boolean
  retiradas: boolean
  rotinas: boolean
}

export interface ResultadoPlanilha {
  pagamentos: number
  pagamentos_existentes: number
  tomadores_criados: number
  despesas: number
  contas_fixas: number
  retiradas: number
  rotinas: number
  avisos: string[]
}

// --- Importar do Emissor Nacional ---
// GET /importar/nacional → PreviaNacional (o que já foi buscado nesta sessão do servidor)
// POST /importar/nacional/buscar {recomecar?, desde_inicio?} → PreviaNacional (chamar de novo enquanto !terminou)
// POST /importar/nacional {mapeamento: RegraImportacao[]} → ResultadoNacional
export type AcaoImportacao = "vinculo" | "avulsa" | "novo" | "ignorar"

export interface GrupoImportacao {
  documento: string
  tipo: "CNPJ" | "CPF" | "NIF" | null
  nome: string
  quantidade: number
  total: number
  canceladas: number
  competencias: string[]
  descricao_exemplo: string | null
  intermediario: string | null
  sugestao: Exclude<AcaoImportacao, "ignorar">
  vinculo_id: string | null
  /** Tomador dos pré-cadastrados: o único tipo que já vem marcado pra importar. */
  pre_cadastrado?: boolean
}

/** GET /empresa/prontidao — o que falta pra empresa emitir. */
export interface Prontidao {
  aplica: boolean
  pode_emitir: boolean
  motivo: string | null
  certificado: "ok" | "falta" | "vencido"
  /** `obrigatorio`: a nota exige (hoje, só o regime). O resto pode ficar em branco. */
  dados_faltando: { campo: string; rotulo: string; link: string; obrigatorio?: boolean; por_que?: string }[]
  tomadores: number
  pronta: boolean
}

export interface PreviaNacional {
  terminou: boolean
  nsu: number
  total_notas: number
  ja_importadas: number
  recebidas: number
  grupos: GrupoImportacao[]
}

export interface RegraImportacao {
  documento: string
  acao: AcaoImportacao
  vinculo_id?: string | null
}

export interface ResultadoNacional {
  importadas: number
  vinculos_criados: number
  puladas: { chave: string; motivo: string }[]
}

// GET /financeiro/mes-a-mes?ano=AAAA — o detalhe por trás de cada total do
// "Mês a mês" (05/10/2026). A soma das linhas de um mês = total do resumo.
export type SecaoMesAMes = "faturado" | "recebido" | "despesas" | "retiradas"

export interface LinhaMesAMes {
  /** Só nas linhas de cliente (recebido/faturado). */
  id?: string
  nome: string
  valores: number[] // 12 meses
  total: number
  /** Só nas categorias (despesas/retiradas): as coisas dentro dela. */
  itens?: LinhaMesAMes[]
}

export interface DetalheMesAMes {
  ano: string
  meses: string[] // "01".."12"
  faturado: LinhaMesAMes[]
  recebido: LinhaMesAMes[]
  despesas: LinhaMesAMes[]
  retiradas: LinhaMesAMes[]
}

// --- Importar emissor (05/10/2026): certificado -> empresa nova -> importação ---
// POST /certificado/ler (multipart: pfx, senha) → CertificadoLido (nada é guardado)
// POST /empresas/importar (multipart: pfx, senha + campos de EmpresaCriarRequest) → EmpresaImportada
// POST /importar/nacional {mapeamento, ajustar_modelos: true} → ResultadoImportarEmissor
export interface CertificadoLido {
  /** Nome de quem é o certificado (razão social, num e-CNPJ). */
  titular: string | null
  /** CNPJ (14 números) quando deu pra tirar do certificado. */
  cnpj: string | null
  /** Certificado de pessoa (e-CPF), não da empresa. */
  pessoa_fisica: boolean
  valido_de: string
  valido_ate: string
  vencido: boolean
  /** Esse CNPJ já é uma das empresas deste login. */
  ja_cadastrada: boolean
}

export interface EmpresaImportada {
  empresa: Empresa
  certificado: CertificadoStatus
}

/** Tomador criado pela importação. `pendencia`: o que falta pra gerar a próxima nota. */
export interface TomadorImportado {
  id: string
  apelido: string
  documento: string | null
  notas: number
  ativo: boolean
  /** Sem CNPJ: entra só pra controle. */
  sem_nota: boolean
  /** O mês/ano da descrição virou campo automático. */
  modelo_ajustado: boolean
  pendencia: string | null
}

export interface ResultadoImportarEmissor extends ResultadoNacional {
  tomadores?: TomadorImportado[]
}

// Conferência (05/10/2026, ver backend app/services/conferencia.py): o que a
// Ana achou de errado ("erro": a nota sairia errada) ou estranho ("aviso":
// a pessoa confirma) no cadastro do tomador, na empresa ou na nota.
export interface PontoConferencia {
  nivel: "erro" | "aviso"
  codigo: string
  campo: string | null
  mensagem: string
  como_corrigir: string | null
  onde: "tomador" | "empresa" | "nota"
}

// GET /dps/{id}/conferencia e POST /dps/conferir
export interface ConferenciaNota {
  pontos: PontoConferencia[]
}

// GET /vinculos/{id}/conferencia
export interface ConferenciaVinculo extends ConferenciaNota {
  erros: number
  avisos: number
}

// GET /conferencia/tomadores — por id do vínculo (só os ativos).
export type ConferenciaTomadores = Record<string, { erros: number; avisos: number }>

/** Formas de envio padrão de um tomador (pode ser mais de uma). */
/** "drive": guardar o PDF e o XML no Google Drive da própria pessoa. */
export type FormaDeEnvio = "email" | "whatsapp" | "portal" | "download" | "drive"

/** GET /drive */
export interface StatusDrive {
  disponivel: boolean
  conectado: boolean
  email: string | null
  /** Qual nuvem está conectada (hoje só "google"). */
  provedor?: string | null
}

// --- Pasta do mês (08/10/2026, backend/app/services/pasta.py) ---

export interface ArquivoPasta {
  id: string
  nome: string
  tamanho: number
  tipo_mime: string
  pedido_id: string | null
  papel: "empresa" | "contador"
  enviado_por: string | null
  criado_em: string
}

export interface ItemPasta {
  id: string
  titulo: string
  descricao: string | null
  tipo: "arquivo" | "extrato"
  situacao: "pendente" | "entregue" | "nao_tem" | "conferido"
  arquivos: ArquivoPasta[]
  extrato_linhas: number | null
  marcado_por: string | null
}

export interface MensagemPasta {
  id: string
  texto: string
  papel: "empresa" | "contador"
  autor_nome: string
  competencia: string | null
  criado_em: string
}

export interface PastaDoMes {
  papel: "empresa" | "contador"
  empresa: string
  mes: {
    competencia: string
    itens: ItemPasta[]
    avulsos: ArquivoPasta[]
    resumo: { itens: number; pendentes: number; prontos: number }
    limite_arquivo: number
  }
  mensagens: MensagemPasta[]
  novidades: { mensagens: number; arquivos: number }
  tem_contador: boolean
  sugestoes: { titulo: string; descricao: string; tipo: string }[]
}

/** Outro destinatário do tomador que recebe a nota num e-mail próprio. */
export interface EmailExtra {
  email: string
  rotulo?: string | null
  assunto?: string | null
  mensagem?: string | null
  anexos?: "pdf_xml" | "pdf" | "xml" | null
}

export interface ProximaNota {
  proxima: { id: string; nome: string; competencia: string; valor: number; passo: string } | null
  restantes: number
}

export interface Compatibilidade {
  emissor: "sim" | "nao" | "indefinido"
  cidade: string | null
  cod_municipio: string | null
  mensagem: string
  avisos: string[]
  lista_atualizada_em: string | null
  razao_social?: string | null
}

export interface PlanoAssinatura {
  id: "basico" | "empreendedor" | "empresa" | "avancado" | "ilimitado" | "financeiro" | "emissor" | "ambos"
  nome: string
  descricao: string
  modulos: string[]
  /** Notas autorizadas por mês (null = sem limite; 0 = plano sem notas). */
  limite_notas?: number | null
  /** Plano só de notas: dá pra somar o Financeiro. */
  aceita_financeiro?: boolean
  disponivel: boolean
  atual: boolean
  valor?: number
  moeda?: string
  intervalo?: string
}

// --- Tomador de fora do Brasil / cliente de controle que vira tomador (05/10/2026) ---
// (complementa as interfaces acima: o TypeScript junta declarações com o mesmo nome)

export interface Tomador {
  /** 'interno' = só desta conta, sem CNPJ (aí `cnpj` vem vazio). */
  status?: string
  /** Empresa de fora do Brasil: país (ISO, 2 letras) e identificação fiscal de lá. */
  pais?: string | null
  nif?: string | null
  /** Empresa de fora sem número fiscal: "1" dispensada, "2" o país não exige. */
  motivo_sem_nif?: string | null
}

export interface VinculoResumo {
  tomador_pais?: string | null
  tomador_nif?: string | null
  tomador_motivo_sem_nif?: string | null
}

export interface IdentificarTomadorResposta {
  vinculo: VinculoDetalhe
  /** Algo que a pessoa precisa saber (ex.: já tem outro cliente com este CNPJ). */
  aviso: string | null
}

// --- Conciliação: as DUAS conciliações (05/10/2026) ---
// A) as notas foram pagas? (GET /conciliacao/notas)  B) o extrato está todo
// classificado? (GET /conciliacao). O estado das duas: GET /conciliacao/resumo.

export type StatusNotaConciliada = "paga" | "paga_a_menor" | "paga_a_maior" | "em_aberto" | "atrasada"

/** Linha do extrato que pode ser o pagamento de uma nota. */
export interface CandidatoDoExtrato {
  lancamento_id: string
  motivos: string[]
  /** Valor da linha menos o da nota (0 = mesmo valor). */
  diferenca: number
}

export interface NotaConciliada {
  /** "nota:<id>" ou "lote:<vinculo>:<AAAA-MM>" (notas de vendedores somadas por mês). */
  chave: string
  tipo: "nota" | "lote"
  vinculo_id: string
  competencia: string
  emissao_id: string | null
  n_dps: number | null
  estado: string | null
  /** Quantas notas a linha junta (1, ou centenas no lote). */
  quantidade: number
  valor: number
  /** null = paga, mas sem como saber o valor (histórico do mês, baixa sem valor, paga junto). */
  recebido: number | null
  diferenca: number | null
  em_aberto: number
  status: StatusNotaConciliada
  /** Por onde veio a baixa. */
  como: "extrato" | "manual" | "planilha" | "historico" | "sem_valor" | "junto" | "conciliacao" | null
  pago_em: string | null
  emitida_em: string
  vencimento: string | null
  dias_em_aberto: number
  dias_atraso: number
  /** O tomador não tem "dias para recebimento": vale o prazo geral. */
  sem_prazo: boolean
  valor_incerto: boolean
  /** O depósito desta nota pagou também as notas de vendedores do mês (Shopee). */
  cobre_lote?: { quantidade: number; valor: number } | null
  /** Histórico: quanto entrou do tomador no mês inteiro. */
  recebido_mes: number | null
  /** Diferença que a pessoa já disse que está certa. */
  conferida: boolean
  /** Mais antiga que o período escolhido, mas ainda sem resolver. */
  antiga: boolean
  pagamentos: { id: string; valor: number; data: string | null; origem: string }[]
  sugestao: (CandidatoDoExtrato & { confianca: "alta" | "media" }) | null
  candidatos: CandidatoDoExtrato[]
}

export interface TotaisNotasConciliadas {
  notas: number
  pagas: number
  faturado: number
  recebido: number
  em_aberto: number
  notas_em_aberto: number
  atrasado: number
  notas_atrasadas: number
  no_prazo: number
  notas_no_prazo: number
  diferenca: number
  notas_com_diferenca: number
  diferencas_a_conferir: number
  notas_sem_valor: number
}

export interface EstadoConciliacaoNotas {
  ok: boolean
  pendencias: number
  atrasadas: number
  diferencas: number
  sugestoes: number
  sem_nota: number
  no_prazo: number
}

export interface TomadorConciliado {
  vinculo_id: string
  apelido: string
  prazo_dias: number | null
  resumo: TotaisNotasConciliadas
  pendencias: number
  itens: NotaConciliada[]
}

export interface EntradaDoExtrato {
  id: string
  data: string | null
  descricao: string
  valor: number
}

export interface PainelConciliacaoNotas {
  /** "recebimentos": empresa só com o Financeiro, sem nota nenhuma pra conferir. */
  modo: "notas" | "recebimentos"
  emissor: boolean
  periodo: { desde: string | null; ate: string | null; antigas: number }
  tolerancia: number
  resumo: TotaisNotasConciliadas
  estado: EstadoConciliacaoNotas
  tomadores: TomadorConciliado[]
  /** Entradas do extrato ainda sem classificar. */
  lancamentos: EntradaDoExtrato[]
  recebimentos_sem_nota: RecebimentoSemNota[]
  clientes: { vinculo_id: string; nome: string; recebido: number; recebimentos: number; ultimo: string | null }[]
}

export interface ResumoExtratoConciliacao {
  linhas: number
  classificadas: number
  pendentes: number
  pendentes_entradas: number
  pendentes_saidas: number
  ignoradas: number
  de: string | null
  ate: string | null
  ultimo_arquivo: string | null
  ultimo_importado_em: string | null
  ok: boolean
}

export interface FechamentoDoMes {
  competencia: string
  estado: "fechado" | "aguardando" | "pendente" | "vazio"
  em_andamento: boolean
  notas: number
  notas_pagas: number
  notas_atrasadas: number
  notas_no_prazo: number
  diferencas: number
  extrato_linhas: number
  extrato_pendentes: number
  /** Notas de vendedores dentro do grupo "em lote" do mês (que conta como 1 em `notas`). */
  notas_em_lote?: number
}

export interface ResumoConciliacao {
  notas: EstadoConciliacaoNotas & { aplica: boolean; notas?: number; pagas?: number; em_aberto?: number; atrasado?: number }
  extrato: ResumoExtratoConciliacao
  /** Soma das pendências das duas conciliações. */
  pendencias: number
  fechamentos: FechamentoDoMes[]
}

// --- Ajuda / FAQ (05/10/2026) ---
/** GET /ajuda — `ia_url`: endereço da IA gratuita carregada com o guia da Ana
 * (null = não configurada: a tela não mostra o botão "Perguntar pra IA"). */
export interface AjudaInfo {
  ia_url: string | null
  /** "Pergunte à Ana" (IA do Claude, 2026.10.7) ligado pra esta conta. */
  ia_ativa?: boolean
  ia_restantes?: number | null
  ia_limite?: number | null
}

export interface RespostaPergunteAna {
  situacao: "ok" | "nao_sei" | "contador" | "limite" | "desligada" | "falha"
  texto: string | null
  restantes: number | null
}

export interface ExplicacaoRecusa {
  disponivel: boolean
  o_que: string | null
  passos: string[]
}

// --- Parceiras de indicação com comissão (06/10/2026) ---
export type StatusIndicadoParceira = "trial" | "ativa" | "inadimplente" | "cancelada"

/** GET /publico/parceira/{token} — o que a parceira vê pelo link secreto. */
export interface ParceiroResumo {
  nome: string
  codigo: string
  /** Link de cadastro com ?ref=CODIGO — é o que a parceira divulga. */
  link: string
  comissao_pct: number
  desconto_1_mes_pct: number
  ativo: boolean
  indicados_total: number
  indicados_ativos: number
  total_comissao: number
  /** O que a plataforma ainda deve repassar. */
  a_receber: number
  indicados: { nome: string; status: StatusIndicadoParceira; desde: string }[]
  meses: {
    competencia: string
    pagamentos: number
    /** Soma do que os indicados pagaram no mês. */
    base: number
    comissao: number
    a_pagar: number
    pago_em: string | null
  }[]
}

/** GET /parceiros — a mesma coisa, pra administração (nomes inteiros + link do painel). */
export interface ParceiroAdmin extends ParceiroResumo {
  id: string
  email: string | null
  /** URL completa do painel secreto da parceira. */
  painel: string
  criado_em: string
}

// --- Painel de gestão da plataforma (06/10/2026) — backend/app/services/gestao.py ---
/** GET /gestao/acesso. `configurado=false`: falta definir ADMIN_EMAILS no servidor. */
export interface AcessoGestao {
  gestor: boolean
  configurado: boolean
}

export type AssinaturaGestao = "trial" | "ativa" | "inadimplente" | "cancelada" | "cortesia"

export interface LoginGestao {
  email: string
  nome: string | null
  confirmado: boolean
  ativo: boolean
  ultimo_acesso: string | null
}

/** Uma ferramenta e quantas contas reais usam. */
export interface FerramentaGestao {
  id: string
  nome: string
  /** Quantas contas usam. */
  contas: number
  volume: number
  /** true = o volume é do mês; false = é o total desde o começo. */
  do_mes: boolean
}

/** Uma empresa na Gestão: só números de uso, nunca o conteúdo. */
export interface ContaGestao {
  id: string
  razao_social: string | null
  cnpj: string | null
  cod_municipio: string | null
  criada_em: string | null
  /** Conta de simulação (apagada em 24h). */
  demo: boolean
  modo_teste: boolean
  modulos: string[]
  assinatura: AssinaturaGestao | null
  plano: string | null
  trial_termina_em: string | null
  certificado: "ok" | "falta" | "vencido"
  logins: LoginGestao[]
  /** Pelo menos um login confirmou o e-mail. */
  email_confirmado: boolean
  ultimo_acesso: string | null
  dias_sem_acesso: number | null
  ultima_nota: string | null
  tomadores: number
  notas_total: number
  /** Notas avulsas (uma a uma) no mês — as de lote vêm em `notas_lote_mes`. */
  notas_mes: number
  notas_lote_mes: number
  notas_importadas: number
  emails_mes: number
  emails_total: number
  emails_lote_mes: number
  emails_falha_mes: number
  lancamentos_financeiros_mes: number
  linhas_extrato_mes: number
  anotacoes: number
  lotes_mes: number
  drive: 0 | 1
  indicou: number
  indicou_ativos: number
  veio_por: string | null
  /** Pode usar tudo? (teste, assinatura, liberação da Gestão...) */
  acesso: SituacaoAcesso
  liberado_obs: string | null
  /** Bloqueio manual pela Gestão (vale mesmo com o bloqueio geral desligado). */
  bloqueada_em?: string | null
  bloqueada_obs?: string | null
  /** Contato que está no cadastro da empresa. */
  telefone?: string | null
/** De onde veio o telefone: o WhatsApp do cadastro ou o telefone da empresa (Receita). */
  telefone_origem?: "cadastro" | "empresa" | null
  /** A pessoa pediu pra continuar usando depois do teste. */
  liberacao_pedida_em?: string | null
    email_empresa?: string | null
  /** Conta só de contador: não é cliente (sem notas, sem assinatura). */
  so_contador?: boolean
  /** Contadores com acesso ativo a esta empresa. */
  contadores: number
}

export interface ResumoGestao {
  /** Contas reais (sem as de simulação). */
  contas: number
  contas_simulacao: number
  contas_teste: number
  email_confirmado: number
  com_certificado: number
  ativas_30_dias: number
  emitiram_no_mes: number
  /** Situação da assinatura -> quantas contas ("sem assinatura" quando não há). */
  assinaturas: Record<string, number>
  /** Sem assinatura e sem liberação: quem o bloqueio trava. */
  sem_acesso: number
  liberadas_na_mao: number
  bloqueio_ativo: boolean
  /** Avulsas + lote. */
  notas_mes: number
  notas_total: number
  emails_mes: number
  emails_lote_mes: number
  emails_falha_mes: number
}

/** GET /gestao */
export interface PainelGestao {
  gerado_em: string
  /** "AAAA-MM" */
  competencia: string
  resumo: ResumoGestao
  ferramentas: FerramentaGestao[]
  contas: ContaGestao[]
}

/** GET /nbs — item da Nomenclatura Brasileira de Serviços (NBS 2.0). */
export interface ItemNbs {
  codigo: string
  descricao: string
  grupo: string
  /** 1.1406.11.00 */
  formatado: string
}
