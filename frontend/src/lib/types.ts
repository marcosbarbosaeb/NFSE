export interface Usuario {
  email: string
  prestador_id: string
}

export interface VinculoResumo {
  id: string
  apelido: string
  tomador_razao_social: string
  tomador_cnpj: string
  serie: string
  template_descricao: string
  requer_revisao: boolean
}

export interface EmissaoResumoLinha {
  emissao_id: string
  apelido: string
  tomador_razao_social: string
  competencia: string
  valor: number
  estado: string
  estado_label: string
  envio_status: string | null
  pagamento_recebido: boolean
}

export interface AtencaoItem {
  tipo: string
  titulo: string
  mensagem: string
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
}

export type VinculoAtualizarRequest = Partial<Omit<VinculoCriarRequest, "tomador_id" | "novo_tomador">> & {
  ativo?: boolean
}

export type TipoEventoCalendario = "prazo_emissao" | "recebimento_previsto" | "recebimento_confirmado"

export interface EventoCalendario {
  data: string
  tipo: TipoEventoCalendario
  titulo: string
  vinculo_id: string | null
  apelido: string | null
  valor: number | null
}

export interface Calendario {
  inicio: string
  fim: string
  eventos: EventoCalendario[]
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
}
