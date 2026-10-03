"""Schemas Pydantic da API do painel interno (Marco 5/6)."""
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.services.municipios import rotulo_municipio


class VinculoResumo(BaseModel):
    id: uuid.UUID
    apelido: str
    tomador_razao_social: str
    tomador_cnpj: str
    serie: str
    template_descricao: str
    requer_revisao: bool
    # Aba Tomadores (28/09/2026) — dia de emissão, ativo/inativo e se a
    # nota da competência pedida já foi gerada.
    ativo: bool = True
    tomador_id: uuid.UUID | None = None
    cod_trib_nacional: str | None = None
    cod_local_prestacao: str | None = None
    dia_limite_emissao: int | None = None
    dias_para_recebimento: int | None = None
    emissao_id: uuid.UUID | None = None
    emissao_estado: str | None = None
    emissao_valor: float | None = None
    # Shopee: várias notas no mês (uma por vendedor).
    emissao_quantidade: int = 0
    metodo_captura_valor: str = "manual"
    sem_nota: bool = False

    model_config = {"from_attributes": True}


class ServicoNacionalResponse(BaseModel):
    codigo: str
    descricao: str
    grupo: str


class ExclusaoVinculoResponse(BaseModel):
    resultado: str  # 'apagado' | 'arquivado'
    mensagem: str


class LimparDadosRequest(BaseModel):
    categorias: list[str] = Field(min_length=1)
    confirmacao: str


class LimparDadosResponse(BaseModel):
    removidos: dict[str, int]


class CertificadoStatus(BaseModel):
    carregado: bool
    validade: date | None = None
    vencido: bool = False


class GerarDpsRequest(BaseModel):
    """Cria e monta uma emissão (rascunho -> montado). `n_dps` NÃO entra
    aqui — é atribuído automaticamente pelo motor de emissão (Marco 6),
    que é a fonte de verdade do sequencial (ver app/services/
    motor_emissao.py)."""
    vinculo_id: uuid.UUID
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM, mês de referência da comissão")
    valor: float = Field(gt=0)
    ordem: str | None = Field(default=None, description="Número da ordem de pagamento (AWIN/AWIN Rchlo)")
    aliq_sn: float | None = Field(default=None, description="Alíquota do Simples Nacional em %% (ex.: 12.5)")
    # Sem valor = ambiente configurado na conta (prestador.tp_amb_padrao) —
    # a escolha saiu da tela de gerar nota em 28/09/2026.
    tpAmb: str | None = Field(default=None, pattern=r"^[12]$", description="1=Produção 2=Homologação")
    # Dia de competência escolhido no calendário (29/09/2026). Quando vem,
    # a competência (AAAA-MM) passa a ser o mês dele.
    data_competencia: date | None = None
    # Gerar a nota de um recebimento que chegou sem nota: a nota fica no mês
    # do recebimento (01/10/2026).
    pagamento_id: uuid.UUID | None = None


class EmissaoResponse(BaseModel):
    id: uuid.UUID
    estado: str
    n_dps: int | None = None
    serie: str
    competencia: str
    valor: float
    apelido: str
    tomador: str
    descricao: str
    xml: str | None
    chave_acesso: str | None = None
    erro_detalhe: str | None = None
    atualizado_em: datetime
    origem: str = "ana"
    vinculo_id: uuid.UUID | None = None
    avulsa: bool = False

    model_config = {"from_attributes": True}


class CancelarDpsRequest(BaseModel):
    """Marco 16, item 7 — cancelamento real na Sefin (ver
    app/services/motor_emissao.cancelar). `cmotivo`: '1' (Erro na
    Emissão) | '2' (Serviço não Prestado) | '9' (Outros) — ver
    app/fiscal/eventos.MOTIVOS_CANCELAMENTO. `xmotivo`: 15-255 caracteres,
    mesma regra do schema oficial."""
    cmotivo: str
    xmotivo: str = Field(min_length=15, max_length=255)


class MunicipioResponse(BaseModel):
    """Cidade da tabela oficial (ver app/services/municipios.py) — a tela
    mostra `rotulo` ('Belo Horizonte/MG') e guarda `codigo` por trás."""
    codigo: str
    nome: str
    uf: str
    rotulo: str


class ConsultaCnpjResponse(BaseModel):
    """Marco 16 — autopreenchimento do cadastro a partir do CNPJ (ver
    app/services/cnpj_lookup.py). `cod_municipio_sugerido` é só uma
    SUGESTÃO editável — nunca aceita cegamente, ver docstring do serviço."""
    razao_social: str
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cep: str | None = None
    municipio: str
    uf: str
    cod_municipio_sugerido: str | None = None
    situacao_cadastral: str | None = None


class VerificarDuplicataResponse(BaseModel):
    """Marco 16 — aviso proativo de nota duplicada: a tela de 'Nova emissão'
    consulta isso assim que fornecedor+competência ficam preenchidos, ANTES
    do usuário tentar submeter (ver GET /api/dps/verificar-duplicata)."""
    existe: bool
    emissao_id: uuid.UUID | None = None
    estado: str | None = None


class ErroResponse(BaseModel):
    detalhe: str


# --- Marco 11: máscara visual da nota (ver app/services/nota_visual.py) ---


class PrestadorVisual(BaseModel):
    razao_social: str
    cnpj: str | None = None
    inscricao_municipal: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    email: str | None = None


class TomadorVisual(BaseModel):
    razao_social: str | None = None
    cnpj: str | None = None
    endereco: str | None = None


class ServicoVisual(BaseModel):
    descricao: str | None = None
    codigo_tributacao_nacional: str | None = None
    codigo_tributacao_municipal: str | None = None
    codigo_local_prestacao: str | None = None


class ValoresVisual(BaseModel):
    valor_servico: float
    issqn: str | None = None
    total_tributos: str | None = None


class NotaVisualResponse(BaseModel):
    """Mesma nota de `EmissaoResponse`, já lida/rotulada em português pra
    desenhar uma 'nota' de verdade no painel (ver app/services/nota_visual.py
    pra origem de cada campo — banco vs. XML)."""
    estado: str
    estado_label: str
    ambiente: str | None = None
    ambiente_label: str | None = None
    id_dps: str | None = None
    serie: str
    n_dps: int | None = None
    competencia: str
    dh_emissao: str | None = None
    chave_acesso: str | None = None
    erro_detalhe: str | None = None
    prestador: PrestadorVisual
    tomador: TomadorVisual
    servico: ServicoVisual
    valores: ValoresVisual
    xml_disponivel: bool


class ImportacaoLinhaResponse(BaseModel):
    """Resultado de UMA linha do CSV importado (Marco 7) — `ok=False` não
    aborta o restante do lote, ver app/services/importacao_csv.py."""
    linha: int
    apelido: str
    ok: bool
    mensagem: str | None = None
    emissao_id: uuid.UUID | None = None
    n_dps: int | None = None


class ImportacaoCsvResponse(BaseModel):
    total: int
    sucesso: int
    erro: int
    linhas: list[ImportacaoLinhaResponse]


# --- Marco 8: painel de status completo (notas geradas / recebidas / despesas,
# no mesmo formato fornecedor×mês da planilha real do Marcos) ---


class RegistrarPagamentoRequest(BaseModel):
    vinculo_id: uuid.UUID
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM, mês de referência")
    valor: float = Field(gt=0)
    data_recebimento: date | None = None


class PagamentoResponse(BaseModel):
    id: uuid.UUID
    apelido: str
    competencia: str
    valor: float
    data_recebimento: date | None
    # Caiu sem nota emitida pra esse tomador nesse mês — a tela oferece gerar.
    sem_nota: bool = False
    vinculo_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class RegistrarDespesaRequest(BaseModel):
    categoria: str = Field(min_length=1, max_length=100)
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    valor: float = Field(gt=0)
    descricao: str | None = Field(default=None, max_length=200)
    tipo: str = Field(default="despesa", pattern=r"^(despesa|retirada)$")
    conta: str | None = Field(default=None, max_length=60)
    vencimento: date | None = None
    pago: bool = True
    pago_em: date | None = None


class AtualizarDespesaRequest(BaseModel):
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    competencia: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    valor: float | None = Field(default=None, ge=0)
    descricao: str | None = Field(default=None, max_length=200)
    tipo: str | None = Field(default=None, pattern=r"^(despesa|retirada)$")
    conta: str | None = Field(default=None, max_length=60)
    vencimento: date | None = None
    pago: bool | None = None
    pago_em: date | None = None


class DespesaResponse(BaseModel):
    id: uuid.UUID
    categoria: str
    competencia: str
    valor: float
    descricao: str | None = None
    tipo: str = "despesa"
    conta: str | None = None
    vencimento: date | None = None
    pago: bool = True
    pago_em: date | None = None
    recorrente_id: uuid.UUID | None = None
    valor_a_definir: bool = False

    model_config = {"from_attributes": True}


class StatusLinhaResponse(BaseModel):
    """Uma linha do painel de status: um fornecedor (notas/pagamentos) ou
    uma categoria (despesas), com os 12 meses do ano + total — mesmo
    layout fornecedor×mês da planilha real (Controle_CP)."""
    rotulo: str
    meses: list[float] = Field(min_length=12, max_length=12)
    total: float


class PainelStatusResponse(BaseModel):
    ano: str
    notas_geradas: list[StatusLinhaResponse]
    pagamentos_recebidos: list[StatusLinhaResponse]
    despesas: list[StatusLinhaResponse]


# --- Marco 12: dashboard do novo frontend (ver app/services/dashboard.py) ---


class EmissaoResumoLinha(BaseModel):
    emissao_id: uuid.UUID
    vinculo_id: uuid.UUID | None = None
    quantidade: int = 1
    apelido: str
    tomador_razao_social: str
    competencia: str
    valor: float
    estado: str
    estado_label: str
    envio_status: str | None = None
    pagamento_recebido: bool
    tem_pdf: bool = False
    tem_email: bool = False
    homologacao: bool = False
    envio_forma: str | None = None
    # Linha das notas de vendedores da Shopee (pagamento indireto).
    vendedores: bool = False


class AtencaoItem(BaseModel):
    tipo: str
    titulo: str
    mensagem: str
    # Onde resolver (rota do painel) + rótulo do botão — o card "Precisa da
    # sua atenção" vira um atalho, não só um aviso (pedido do Marcos).
    link: str | None = None
    link_label: str | None = None


class PontoSerieMensal(BaseModel):
    competencia: str
    valor: float


class DashboardResumoResponse(BaseModel):
    competencia: str
    total_vinculos: int
    emitidas: int
    aguardando: int
    a_receber: float
    pagamentos_pendentes: int
    recebido_no_mes: float
    recebido_mes_anterior: float
    delta_recebimentos_pct: float | None = None
    serie_recebimentos: list[PontoSerieMensal]
    emissoes: list[EmissaoResumoLinha]
    atencao: list[AtencaoItem]
    # Todos os meses (28/09/2026) — ver app/services/a_receber.py.
    a_receber_total: float = 0
    notas_a_receber: int = 0
    recebido_total: float = 0
    notas_recebidas: int = 0


class PendenciaItem(BaseModel):
    tipo: str
    titulo: str
    acao: str
    link: str
    emissao_id: uuid.UUID | None = None
    vinculo_id: uuid.UUID | None = None
    valor: float | None = None
    competencia: str | None = None
    # Pra "ignorar este aviso" (POST /api/painel/pendencias/ignorar).
    chave: str | None = None


class AgendaItem(BaseModel):
    data: date
    tipo: str
    titulo: str
    detalhe: str | None = None
    valor: float | None = None


class ProximosResponse(BaseModel):
    pendencias: list[PendenciaItem]
    total_pendencias: int
    agenda: list[AgendaItem]


class NotaAbertaResponse(BaseModel):
    vinculo_id: uuid.UUID
    apelido: str
    competencia: str
    emissao_id: uuid.UUID
    estado: str
    valor: float
    quantidade: int
    emitida_em: date
    dias_em_aberto: int


# --- Marco 9: canais de envio ---


class RegistrarEnvioRequest(BaseModel):
    canal: str = Field(pattern=r"^(download|email|whatsapp|direto_fornecedor|mensagem_pronta)$")


class OpcoesEnvioResponse(BaseModel):
    """Marco 17 — o que a tela 'Envio ao fornecedor' pode oferecer pra esta
    nota: e-mail direto (se o domínio/Resend estiver configurado e o
    fornecedor tiver e-mail), WhatsApp e o link público da nota."""
    email_habilitado: bool
    email_motivo_desabilitado: str | None = None
    email_destino: str | None = None
    whatsapp_destino: str | None = None
    link_publico: str
    tem_pdf: bool
    vinculo_id: uuid.UUID | None = None


class WhatsappLinkResponse(BaseModel):
    url: str
    envio: "EnvioResponse"


class EnvioResponse(BaseModel):
    id: uuid.UUID
    emissao_id: uuid.UUID
    canal: str
    status: str
    tentativas: int
    enviado_em: datetime | None
    destino: str | None = None
    erro: str | None = None

    model_config = {"from_attributes": True}


class MensagemProntaResponse(BaseModel):
    mensagem: str


# --- Marco 10: login multiusuário ---


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioResponse(BaseModel):
    email: str
    prestador_id: uuid.UUID
    # Conta do ambiente de simulação (ver app/services/demo.py).
    demo: bool = False
    nome: str | None = None
    # Empresa ativa é conta de teste (notas só em homologação).
    teste: bool = False


class GoogleOAuthUrlResponse(BaseModel):
    """Marco 16, item 1 — URL de autorização da Google pra POST
    /api/auth/google/iniciar (ver app/services/google_oauth.py)."""
    url: str


class CadastroRequest(BaseModel):
    """Marco 15 — formulário público de cadastro (/cadastro no frontend).
    O mínimo pra já existir um Prestador+Usuario utilizáveis: o resto
    (endereço, inscrição municipal, certificado...) se configura depois em
    Configurações, como já é hoje pra contas criadas administrativamente."""
    email: str
    senha: str = Field(min_length=8)
    razao_social: str = Field(min_length=1, max_length=200)
    cpf_cnpj: str = Field(pattern=r"^\d{14}$", description="CNPJ, só dígitos, 14 caracteres")
    cod_municipio: str = Field(pattern=r"^\d{7}$", description="Código IBGE do município, 7 dígitos")
    # Programa de indicação: código do link /cadastro?ref=CODIGO (opcional).
    codigo_indicacao: str | None = Field(default=None, max_length=20)

    # Marco 16 — opcionais, preenchidos pelo autopreenchimento via CNPJ no
    # frontend (ver app/services/cnpj_lookup.py); quem cadastra sem usar o
    # autopreenchimento simplesmente não manda esses campos, exatamente como
    # antes. Guardados aqui só pra a pessoa não ter que digitar de novo em
    # Configurações depois — nada disso é exigido pra emitir nota.
    cep: str | None = Field(default=None, max_length=8)
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    # Conta de teste (link /cadastro?teste=1): notas só em homologação.
    modo_teste: bool = False


class CadastroResponse(BaseModel):
    mensagem: str
    email: str


class ConfirmarEmailRequest(BaseModel):
    token: str


class ReenviarConfirmacaoRequest(BaseModel):
    email: str


class TrocarSenhaRequest(BaseModel):
    """Marco 15 — troca de senha pelo próprio usuário logado (antes disso,
    só existia via scripts/criar_usuario.py, administrativo). Exige a senha
    atual pra confirmar identidade (ver app/services/usuarios.trocar_senha)
    — mesma regra de tamanho mínimo do script (>= 8 caracteres)."""
    senha_atual: str
    senha_nova: str = Field(min_length=8)


# --- Marco 13: catálogo de tomadores + vínculo self-service, e calendário
# de prazos/previsão de recebimento (ver app/services/tomadores.py,
# app/services/vinculos.py e app/services/calendario.py) ---


class TomadorResponse(BaseModel):
    id: uuid.UUID
    cnpj: str
    razao_social: str
    cod_municipio: str
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    # Sugestões de preenchimento (o que já foi usado com este tomador).
    sug_cod_trib_nacional: str | None = None
    sug_template_descricao: str | None = None
    sug_dia_emissao: int | None = None
    sug_dias_recebimento: int | None = None
    # 'interno' = só desta conta (sem CNPJ: parceria, pessoa física, exterior).
    status: str = "aprovado"

    model_config = {"from_attributes": True}

    @field_validator("cnpj")
    @classmethod
    def _sem_cnpj_interno(cls, v: str) -> str:
        return "" if v.startswith("X") else v


class TomadorCriarRequest(BaseModel):
    cnpj: str = Field(pattern=r"^\d{14}$", description="Só dígitos, 14 caracteres")
    razao_social: str = Field(min_length=1, max_length=200)
    cod_municipio: str = Field(pattern=r"^\d{7}$", description="Código IBGE do município, 7 dígitos")
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None


class VinculoDetalheResponse(BaseModel):
    """A tela de detalhe do tomador ('Regras de emissão') usa isto —
    diferente de VinculoResumo (usado pelo dropdown 'Nova DPS' do painel
    antigo), que não muda de forma pra não afetar quem já depende dela."""
    id: uuid.UUID
    apelido: str
    tomador: TomadorResponse
    cod_local_prestacao: str
    cod_trib_nacional: str
    cod_trib_municipal: str | None = None
    template_descricao: str
    metodo_captura_valor: str
    serie: str
    requer_revisao: bool
    ativo: bool
    dia_limite_emissao: int | None = None
    dias_para_recebimento: int | None = None
    email_contato: str | None = None
    whatsapp_contato: str | None = None
    email_assunto: str | None = None
    email_mensagem: str | None = None
    email_anexos: str | None = None
    email_copia: str | None = None
    email_para: str | None = None
    cod_nbs: str | None = None
    incluir_intermediario: bool = False
    envio_canal: str | None = None
    portal_url: str | None = None
    sem_nota: bool = False

    model_config = {"from_attributes": True}


class VinculoCriarRequest(BaseModel):
    """Cobre os dois caminhos da tela de Tomadores com o MESMO request:
    'usar um tomador pré-cadastrado' manda `tomador_id`; 'cadastrar meu
    próprio tomador' manda `novo_tomador` — nunca os dois, nem nenhum."""
    tomador_id: uuid.UUID | None = None
    novo_tomador: TomadorCriarRequest | None = None

    apelido: str = Field(min_length=1, max_length=100)
    cod_local_prestacao: str = Field(pattern=r"^\d{7}$")
    cod_trib_nacional: str = Field(min_length=1, max_length=10)
    cod_trib_municipal: str | None = Field(default=None, max_length=5)
    template_descricao: str = Field(min_length=1)
    metodo_captura_valor: str = Field(default="manual", pattern=r"^(manual|pdf|csv|chat)$")
    serie: str = Field(default="1", max_length=5)
    requer_revisao: bool = True
    dia_limite_emissao: int | None = Field(default=None, ge=1, le=31)
    dias_para_recebimento: int | None = Field(default=None, ge=0)
    email_contato: str | None = Field(default=None, max_length=200)
    whatsapp_contato: str | None = Field(default=None, max_length=20)
    # Modelo do e-mail da nota só pra este tomador (28/09/2026). Nulo = padrão.
    email_assunto: str | None = Field(default=None, max_length=300)
    email_mensagem: str | None = Field(default=None, max_length=5000)
    email_anexos: str | None = Field(default=None, pattern=r"^(pdf_xml|pdf|xml)$")
    email_copia: str | None = Field(default=None, max_length=400)
    email_para: str | None = Field(default=None, max_length=400)
    cod_nbs: str | None = Field(default=None, max_length=14, pattern=r"^[\d.\s]*$")
    incluir_intermediario: bool | None = None
    envio_canal: str | None = Field(default=None, pattern=r"^(email|whatsapp|portal|nenhum)$")
    portal_url: str | None = Field(default=None, max_length=400)
    sem_nota: bool | None = None

    @model_validator(mode="after")
    def _exatamente_um_tomador(self):
        if (self.tomador_id is None) == (self.novo_tomador is None):
            raise ValueError("Informe exatamente um dos dois: tomador_id (existente) ou novo_tomador (novo).")
        return self


class VinculoAtualizarRequest(BaseModel):
    """Todos os campos opcionais — PATCH parcial: só o que vier preenchido
    é alterado (ver atualizar_vinculo em app/services/vinculos.py)."""
    apelido: str | None = Field(default=None, min_length=1, max_length=100)
    cod_local_prestacao: str | None = Field(default=None, pattern=r"^\d{7}$")
    cod_trib_nacional: str | None = Field(default=None, min_length=1, max_length=10)
    cod_trib_municipal: str | None = Field(default=None, max_length=5)
    template_descricao: str | None = Field(default=None, min_length=1)
    metodo_captura_valor: str | None = Field(default=None, pattern=r"^(manual|pdf|csv|chat)$")
    serie: str | None = Field(default=None, max_length=5)
    requer_revisao: bool | None = None
    ativo: bool | None = None
    dia_limite_emissao: int | None = Field(default=None, ge=1, le=31)
    dias_para_recebimento: int | None = Field(default=None, ge=0)
    email_contato: str | None = Field(default=None, max_length=200)
    whatsapp_contato: str | None = Field(default=None, max_length=20)
    # Modelo do e-mail da nota só pra este tomador (28/09/2026). Nulo = padrão.
    email_assunto: str | None = Field(default=None, max_length=300)
    email_mensagem: str | None = Field(default=None, max_length=5000)
    email_anexos: str | None = Field(default=None, pattern=r"^(pdf_xml|pdf|xml)$")
    email_copia: str | None = Field(default=None, max_length=400)
    email_para: str | None = Field(default=None, max_length=400)
    cod_nbs: str | None = Field(default=None, max_length=14, pattern=r"^[\d.\s]*$")
    incluir_intermediario: bool | None = None
    envio_canal: str | None = Field(default=None, pattern=r"^(email|whatsapp|portal|nenhum)$")
    portal_url: str | None = Field(default=None, max_length=400)
    sem_nota: bool | None = None


class PrestadorResponse(BaseModel):
    """Marco 14 — tela de Configurações (dados básicos, somente leitura por
    enquanto: não existe endpoint de edição ainda, é administrativo via
    banco/scripts — ver DEPLOY.md). Exceção: `aliquota_atual` TEM edição
    própria (ver AliquotaAtualizarRequest / PATCH /api/prestador/aliquota),
    porque é o único dado aqui que muda mês a mês na operação normal."""
    razao_social: str
    cpf_cnpj: str
    inscricao_municipal: str | None = None
    cod_municipio: str
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    telefone: str | None = None
    email: str | None = None
    # Marco 16, item 5 — alíquota de referência do Simples Nacional (só pra
    # pré-preencher o campo aliq_sn na Nova emissão; nunca aplicada sozinha
    # sem confirmação, ver docstring de Prestador.aliquota_atual).
    aliquota_atual: float | None = None
    aliquota_atualizada_em: date | None = None
    dia_lembrete_aliquota: int | None = None
    tp_amb_padrao: str = "1"
    modo_teste: bool = False
    nome_fantasia: str | None = None
    op_simples_nacional: str | None = None
    regime_apuracao_sn: str | None = None
    regime_especial_trib: str | None = None
    email_assunto_padrao: str | None = None
    email_mensagem_padrao: str | None = None
    email_anexos_padrao: str | None = None
    email_copia_padrao: str | None = None
    email_geral_para: str | None = None
    email_geral_assunto: str | None = None
    email_geral_mensagem: str | None = None
    email_geral_anexos: str | None = None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def municipio_rotulo(self) -> str | None:
        """'Belo Horizonte/MG' em vez do código IBGE cru (pedido do Marcos)."""
        return rotulo_municipio(self.cod_municipio)


class PreferenciasPrestadorRequest(BaseModel):
    """PATCH /api/prestador/preferencias (28/09/2026): ambiente das notas
    novas e o modelo padrão do e-mail da nota. PATCH parcial; string vazia
    nos textos volta pro texto de sempre."""
    tp_amb_padrao: str | None = Field(default=None, pattern=r"^[12]$")
    email_assunto_padrao: str | None = Field(default=None, max_length=300)
    email_mensagem_padrao: str | None = Field(default=None, max_length=5000)
    email_anexos_padrao: str | None = Field(default=None, pattern=r"^(pdf_xml|pdf|xml)$")
    email_copia_padrao: str | None = Field(default=None, max_length=400)
    email_geral_para: str | None = Field(default=None, max_length=400)
    email_geral_assunto: str | None = Field(default=None, max_length=300)
    email_geral_mensagem: str | None = Field(default=None, max_length=5000)
    email_geral_anexos: str | None = Field(default=None, pattern=r"^(pdf_xml|pdf|xml)$")


class CodigoModeloResponse(BaseModel):
    codigo: str
    descricao: str
    exemplo: str


class ModeloEmailPadraoResponse(BaseModel):
    assunto: str
    mensagem: str
    codigos: list[CodigoModeloResponse]


class PreviaEmailResponse(BaseModel):
    destino: str | None
    destinos: list[str] = []
    whatsapp: str | None = None
    whatsapp_texto: str = ""
    canal_preferido: str = "email"
    portal_url: str | None = None
    avulsa: bool = False
    geral_destinos: list[str] = []
    geral_assunto: str = ""
    geral_texto: str = ""
    copia: list[str]
    assunto: str
    texto: str
    anexos: str
    arquivos: list[str]
    motivo_desabilitado: str | None = None


class AliquotaAtualizarRequest(BaseModel):
    """Marco 16, item 5 — PATCH /api/prestador/aliquota. Alíquota do Simples
    Nacional em %% (mesma unidade de GerarDpsRequest.aliq_sn, ex.: 12.5)."""
    aliquota: float = Field(ge=0, le=100)


class EmissaoListaLinha(BaseModel):
    """Marco 14 — uma linha da tela 'NFS-e' (lista completa, diferente de
    EmissaoResumoLinha do dashboard que é só o mês corrente). Mesmos rótulos
    de estado do dashboard (ver app/services/dashboard.ESTADO_NFSE_LABEL)."""
    id: uuid.UUID
    vinculo_id: uuid.UUID
    apelido: str
    tomador_razao_social: str
    competencia: str
    valor: float
    serie: str
    n_dps: int | None
    estado: str
    estado_label: str
    criado_em: datetime
    pagamento_recebido: bool
    envio_status: str | None = None
    tem_pdf: bool = False
    tem_email: bool = False
    homologacao: bool = False
    avulsa: bool = False  # nota de vendedor da Shopee (destinatário fixo)
    envio_forma: str | None = None  # como o tomador recebe: email|whatsapp|portal|nenhum


class EventoCalendarioResponse(BaseModel):
    data: date
    tipo: str
    titulo: str
    vinculo_id: uuid.UUID | None = None
    apelido: str | None = None
    valor: float | None = None
    # Marco 15 — só preenchidos pra tipo="manual" (os outros 3 tipos são
    # computados na hora, sem linha própria — ver app/services/calendario.py).
    # `id` é o que permite editar/excluir um evento manual pelo frontend.
    id: uuid.UUID | None = None
    descricao: str | None = None
    # Marco 17 — manual: categoria (lembrete | recebimento_previsto |
    # prazo_emissao). Calculados: `chave` da ocorrência (pra mover/ocultar
    # só ela), se já foi ajustada, a data original e o valor atual da regra.
    categoria: str | None = None
    chave: str | None = None
    ajustado: bool = False
    data_original: date | None = None
    regra_valor: int | None = None


class CalendarioResponse(BaseModel):
    inicio: date
    fim: date
    eventos: list[EventoCalendarioResponse]


CategoriaEventoManual = Literal["lembrete", "recebimento_previsto", "prazo_emissao"]


class EventoManualCriarRequest(BaseModel):
    data: date
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    categoria: CategoriaEventoManual = "lembrete"
    valor: float | None = Field(default=None, gt=0)
    vinculo_id: uuid.UUID | None = None


class EventoManualAtualizarRequest(BaseModel):
    data: date | None = None
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    categoria: CategoriaEventoManual | None = None
    valor: float | None = Field(default=None, gt=0)
    vinculo_id: uuid.UUID | None = None


class AjusteOcorrenciaRequest(BaseModel):
    """Marco 17 — mover (nova_data) ou ocultar UMA ocorrência de um alerta
    calculado, sem mudar a regra (ver app/services/calendario.py)."""
    tipo: Literal["prazo_emissao", "recebimento_previsto", "revisar_aliquota"]
    chave: str = Field(min_length=1, max_length=100)
    nova_data: date | None = None
    oculto: bool = False


class LembreteAliquotaRequest(BaseModel):
    """Regra do lembrete de alíquota: dia do mês (1-31; meses curtos caem
    no último dia)."""
    dia: int = Field(ge=1, le=31)


# --- Marco 15 (item 4): assinatura/cobrança (ver app/services/billing.py) ---


class AssinaturaResponse(BaseModel):
    status: str
    ativa: bool
    trial_termina_em: datetime | None = None
    tem_assinatura_stripe: bool


class CheckoutSessaoResponse(BaseModel):
    url: str


# --- Marco 15 (item 5): extrato bancário em PDF (ver app/services/extrato_pdf.py
# e app/services/importacao_extrato.py) ---


class TransacaoExtraidaResponse(BaseModel):
    linha: int
    data: date | None
    descricao: str
    valor: float
    credito: bool
    # Sugestões de classificação (03/10/2026, app/services/classificar_extrato.py).
    chave: str = ""  # linhas com a mesma chave são "o mesmo lançamento"
    vinculo_id: uuid.UUID | None = None
    competencia: str | None = None
    categoria: str | None = None
    tipo_despesa: str = "despesa"
    origem_sugestao: str | None = None  # lembrado | nome | valor
    nota: dict | None = None  # nota em aberto que o valor paga
    ja_lancado: bool = False


class ExtratoExtraidoResponse(BaseModel):
    total_transacoes: int
    transacoes: list[TransacaoExtraidaResponse]
    categorias: list[str] = []
    categorias_retirada: list[str] = []
    formato: str = "pdf"
    # Linhas de texto que o arquivo tinha: 0 num PDF = imagem escaneada.
    linhas_lidas: int = 0


class ItemConfirmarExtratoRequest(BaseModel):
    vinculo_id: uuid.UUID
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM, mês de referência")
    valor: float = Field(gt=0)
    data_recebimento: date | None = None
    # Texto da linha do extrato: guarda a escolha pra próxima importação.
    descricao: str | None = Field(default=None, max_length=500)


class DespesaExtratoRequest(BaseModel):
    """Saída do extrato que vira despesa (28/09/2026)."""
    categoria: str = Field(min_length=1, max_length=100)
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    valor: float = Field(gt=0)
    descricao: str | None = Field(default=None, max_length=500)
    data: date | None = None
    tipo: Literal["despesa", "retirada"] = "despesa"


class FonteReceitaRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=60)


class ConfirmarExtratoRequest(BaseModel):
    itens: list[ItemConfirmarExtratoRequest] = Field(default_factory=list)
    despesas: list[DespesaExtratoRequest] = Field(default_factory=list)


class ItemConfirmadoExtratoResponse(BaseModel):
    indice: int
    ok: bool
    mensagem: str | None = None
    pagamento_id: uuid.UUID | None = None


class RecebimentoSemNotaResponse(BaseModel):
    pagamento_id: uuid.UUID
    vinculo_id: uuid.UUID
    apelido: str
    competencia: str
    valor: float
    data_recebimento: date | None = None
    chave: str


class ConfirmarExtratoResponse(BaseModel):
    total: int
    sucesso: int
    erro: int
    itens: list[ItemConfirmadoExtratoResponse]
    despesas_registradas: int = 0
    # Recebimentos que caíram sem nota do tomador naquele mês (01/10/2026).
    sem_nota: list[RecebimentoSemNotaResponse] = []


class VendedorShopeeResponse(BaseModel):
    competencia: str
    documento: str
    tipo_documento: str
    razao_social: str
    lojas: list[str]
    valor: float
    cidade: str | None = None
    uf: str | None = None
    estrangeiro: bool
    avisos: list[str]
    ja_gerada: bool = False


class CompetenciaShopeeResponse(BaseModel):
    competencia: str
    vendedores: int
    total: float
    estrangeiros: int
    ja_geradas: int


class PreviaShopeeResponse(BaseModel):
    linhas_lidas: int
    linhas_ignoradas: list[str]
    competencias: list[CompetenciaShopeeResponse]
    vendedores: list[VendedorShopeeResponse]


class OrdemAwinUsadaResponse(BaseModel):
    emissao_id: uuid.UUID
    apelido: str
    competencia: str
    estado: str


class OrdemAwinResponse(BaseModel):
    """Leitura da ordem de pagamento da Awin em PDF (28/09/2026) — nada é
    gravado; a tela usa pra preencher competência, valor e número da ordem."""
    numero: str | None
    valor: float | None
    data: date | None
    moeda: str | None
    competencia_sugerida: str | None
    avisos: list[str]
    ja_usada: OrdemAwinUsadaResponse | None = None


class GeracaoShopeeResponse(BaseModel):
    geradas: int
    ja_existiam: int
    puladas: int
    total: float
    erros: list[str]


WhatsappLinkResponse.model_rebuild()


class CanaisSuporteResponse(BaseModel):
    email: str
    whatsapp: str | None = None
    formulario: bool


class MensagemSuporteRequest(BaseModel):
    """Formulário "Fale com o suporte" (28/09/2026) — o botão com mailto:
    não abria nada em quem não tem programa de e-mail configurado. Logado,
    o e-mail de resposta é o da conta; fora do painel, precisa informar."""
    assunto: str = Field(min_length=2, max_length=150)
    mensagem: str = Field(min_length=5, max_length=5000)
    nome: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    pagina: str | None = Field(default=None, max_length=300)
    # Campo escondido na tela: robô preenche, gente não.
    site: str | None = None


class IndicadoResponse(BaseModel):
    nome: str
    status: str
    desde: date


class IndicacaoResponse(BaseModel):
    codigo: str
    link: str
    ativos: int
    total: int
    desconto_pct: int
    desconto_aplicado_pct: int
    pct_por_indicado: int
    pct_maximo: int
    cobranca_ativa: bool
    indicados: list[IndicadoResponse]


class EnviarEmailRequest(BaseModel):
    """Opcional: trocar pra quem vai, o assunto e o texto SÓ neste envio (a
    tela pré-preenche com o configurado). `salvar_padrao`: guarda essas
    escolhas no tomador pra próxima vez."""
    para: list[str] | None = Field(default=None, max_length=20)
    copia: list[str] | None = Field(default=None, max_length=20)
    assunto: str | None = Field(default=None, max_length=300)
    texto: str | None = Field(default=None, max_length=5000)
    salvar_padrao: bool = False


class WhatsappRequest(BaseModel):
    numero: str | None = Field(default=None, max_length=30)
    texto: str | None = Field(default=None, max_length=3000)
    salvar_padrao: bool = False



class CriarLoteRequest(BaseModel):
    """Ação em lote (29/09/2026). Ou uma lista de notas (seleção na tela),
    ou um filtro (ex.: todas as notas da Shopee de um mês)."""
    acao: str = Field(pattern=r"^(email|email_geral|assinar|submeter)$")
    emissao_ids: list[uuid.UUID] | None = Field(default=None, max_length=3000)
    vinculo_id: uuid.UUID | None = None
    competencia: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    reenviar: bool = False


class ErroLoteItem(BaseModel):
    emissao_id: str
    nome: str = ""
    erro: str


class LoteResponse(BaseModel):
    id: uuid.UUID
    acao: str
    status: str
    total: int
    feitos: int
    falhas: int
    erros: list[ErroLoteItem]
    criado_em: datetime | None = None
    concluido_em: datetime | None = None


class PreviaLoteResponse(BaseModel):
    acao: str
    quantidade: int


class ResumoEnviosResponse(BaseModel):
    enviados: int
    falhas: int
    notas_sem_envio: int



# --- Conta e empresas (29/09/2026) ---


class SolicitarCodigoRequest(BaseModel):
    email: str = Field(max_length=200)


class EntrarComCodigoRequest(BaseModel):
    email: str = Field(max_length=200)
    codigo: str = Field(min_length=6, max_length=12)


class ContaResponse(BaseModel):
    nome: str | None
    email: str
    demo: bool
    tem_senha: bool
    google_conectado: bool


class ContaAtualizarRequest(BaseModel):
    nome: str | None = Field(default=None, max_length=120)


class SessaoResponse(BaseModel):
    id: uuid.UUID
    dispositivo: str
    ip: str | None
    criado_em: datetime | None
    ultimo_acesso: datetime | None
    atual: bool


class EmpresaResponse(BaseModel):
    id: uuid.UUID
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    ativa: bool = False


class EmpresaCriarRequest(BaseModel):
    cpf_cnpj: str = Field(pattern=r"^\d{14}$")
    razao_social: str = Field(min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cod_municipio: str = Field(pattern=r"^\d{7}$")
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None


class ExcluirRequest(BaseModel):
    confirmacao: str = Field(max_length=40)


class EmitenteAtualizarRequest(BaseModel):
    """Dados do emitente editáveis (antes eram só administrativos). CNPJ
    não muda — outro CNPJ é outra empresa."""
    razao_social: str | None = Field(default=None, min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cod_municipio: str | None = Field(default=None, pattern=r"^\d{7}$")
    inscricao_municipal: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=20)
    cep: str | None = Field(default=None, max_length=10)
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    op_simples_nacional: str | None = Field(default=None, pattern=r"^[123]$")
    regime_apuracao_sn: str | None = Field(default=None, pattern=r"^[123]$")
    regime_especial_trib: str | None = Field(default=None, pattern=r"^[0-6]$")



class EnviarGeralRequest(BaseModel):
    para: list[str] | None = Field(default=None, max_length=20)
    assunto: str | None = Field(default=None, max_length=300)
    texto: str | None = Field(default=None, max_length=5000)


class MarcarEnviadaRequest(BaseModel):
    forma: str = Field(default="portal", pattern=r"^(portal|outro)$")



# --- Importar do Emissor Nacional (28/09/2026) ---


class BuscarNacionalRequest(BaseModel):
    recomecar: bool = False
    desde_inicio: bool = False
    # Só notas a partir desta competência (AAAA-MM). Sem = janeiro do ano atual.
    desde: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class LimparImportadasRequest(BaseModel):
    antes: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class GrupoImportacaoResponse(BaseModel):
    documento: str
    tipo: str | None = None
    nome: str
    quantidade: int
    total: float
    canceladas: int = 0
    competencias: list[str]
    descricao_exemplo: str | None = None
    intermediario: str | None = None
    sugestao: str
    vinculo_id: uuid.UUID | None = None


class PreviaNacionalResponse(BaseModel):
    terminou: bool
    nsu: int
    total_notas: int
    ja_importadas: int
    recebidas: int
    grupos: list[GrupoImportacaoResponse]


class RegraImportacao(BaseModel):
    documento: str = Field(max_length=40)
    acao: str = Field(pattern=r"^(vinculo|avulsa|novo|ignorar)$")
    vinculo_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _precisa_vinculo(self):
        if self.acao in ("vinculo", "avulsa") and self.vinculo_id is None:
            raise ValueError("Escolha o tomador de destino.")
        return self


class ImportarNacionalRequest(BaseModel):
    mapeamento: list[RegraImportacao] = Field(max_length=5000)


class ImportarNacionalResponse(BaseModel):
    importadas: int
    vinculos_criados: int
    puladas: list[dict]



# --- Financeiro (28/09/2026) ---


class ContaFixaRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    categoria: str | None = Field(default=None, max_length=100)
    tipo: str = Field(default="despesa", pattern=r"^(despesa|retirada)$")
    valor_padrao: float | None = Field(default=None, ge=0)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    conta: str | None = Field(default=None, max_length=60)


class ContaFixaAtualizarRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    tipo: str | None = Field(default=None, pattern=r"^(despesa|retirada)$")
    valor_padrao: float | None = Field(default=None, ge=0)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    conta: str | None = Field(default=None, max_length=60)
    ativa: bool | None = None


class ContaFixaResponse(BaseModel):
    id: uuid.UUID
    nome: str
    categoria: str
    tipo: str
    valor_padrao: float | None
    dia_vencimento: int | None
    conta: str | None
    ativa: bool

    model_config = {"from_attributes": True}


class RotinaRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=120)


class RotinaAtualizarRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    ativa: bool | None = None


class RotinaCheckRequest(BaseModel):
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    feita: bool = True


class RotinaResponse(BaseModel):
    id: uuid.UUID
    nome: str
    ativa: bool = True

    model_config = {"from_attributes": True}


class RotinaDoMes(BaseModel):
    id: uuid.UUID
    nome: str
    feita: bool
    feita_em: datetime | None = None


class ContasDoMesResponse(BaseModel):
    competencia: str
    contas: list[DespesaResponse]
    rotinas: list[RotinaDoMes]
    total_previsto: float
    total_pago: float
    a_pagar: int
    rotinas_feitas: int


class ResumoFinanceiroResponse(BaseModel):
    ano: str
    meses: list[str]
    faturado: list[float]
    recebido: list[float]
    despesas: list[float]
    impostos: list[float]
    ferramentas: list[float]
    retiradas: list[float]
    lucro: list[float]
    margem: list[float | None]
    saldo_a_distribuir: list[float]
    totais: dict
    categorias: list[dict]


class ImportarPlanilhaResponse(BaseModel):
    pagamentos: int
    pagamentos_existentes: int
    tomadores_criados: int
    despesas: int
    contas_fixas: int
    retiradas: int
    rotinas: int
    avisos: list[str]


class IgnorarPendenciaRequest(BaseModel):
    chave: str = Field(min_length=3, max_length=100)
    ignorar: bool = True



class MoverNotaRequest(BaseModel):
    vinculo_id: uuid.UUID


class ConciliarItem(BaseModel):
    vinculo_id: uuid.UUID
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class ConciliarRequest(BaseModel):
    """Notas pra dar como recebidas sem lançar valor (histórico controlado em
    outra plataforma). `ate`: em vez da lista, todas as em aberto até esse
    mês (AAAA-MM)."""
    itens: list[ConciliarItem] = Field(default=[], max_length=2000)
    ate: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
