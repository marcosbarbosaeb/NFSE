"""Schemas Pydantic da API do painel interno (Marco 5/6)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class VinculoResumo(BaseModel):
    id: uuid.UUID
    apelido: str
    tomador_razao_social: str
    tomador_cnpj: str
    serie: str
    template_descricao: str
    requer_revisao: bool

    model_config = {"from_attributes": True}


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
    competencia: str = Field(pattern=r"^\d{4}-\d{2}$", description="AAAA-MM, mês de referência da comissão")
    valor: float = Field(gt=0)
    ordem: str | None = Field(default=None, description="Número da ordem de pagamento (AWIN/AWIN Rchlo)")
    aliq_sn: float | None = Field(default=None, description="Alíquota do Simples Nacional em %% (ex.: 12.5)")
    tpAmb: str = Field(default="2", pattern=r"^[12]$", description="1=Produção 2=Homologação")


class EmissaoResponse(BaseModel):
    id: uuid.UUID
    estado: str
    n_dps: int
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

    model_config = {"from_attributes": True}


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
    n_dps: int
    competencia: str
    dh_emissao: str | None = None
    chave_acesso: str | None = None
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
    competencia: str = Field(pattern=r"^\d{4}-\d{2}$", description="AAAA-MM, mês de referência")
    valor: float = Field(gt=0)
    data_recebimento: date | None = None


class PagamentoResponse(BaseModel):
    id: uuid.UUID
    apelido: str
    competencia: str
    valor: float
    data_recebimento: date | None

    model_config = {"from_attributes": True}


class RegistrarDespesaRequest(BaseModel):
    categoria: str = Field(min_length=1, max_length=100)
    competencia: str = Field(pattern=r"^\d{4}-\d{2}$")
    valor: float = Field(gt=0)


class DespesaResponse(BaseModel):
    id: uuid.UUID
    categoria: str
    competencia: str
    valor: float

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
    apelido: str
    tomador_razao_social: str
    competencia: str
    valor: float
    estado: str
    estado_label: str
    envio_status: str | None = None
    pagamento_recebido: bool


class AtencaoItem(BaseModel):
    tipo: str
    titulo: str
    mensagem: str


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


# --- Marco 9: canais de envio ---


class RegistrarEnvioRequest(BaseModel):
    canal: str = Field(pattern=r"^(download|email|whatsapp|direto_fornecedor|mensagem_pronta)$")


class EnvioResponse(BaseModel):
    id: uuid.UUID
    emissao_id: uuid.UUID
    canal: str
    status: str
    tentativas: int
    enviado_em: datetime | None

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

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


class VinculoCriarRequest(BaseModel):
    """Cobre os dois caminhos da tela de Tomadores com o MESMO request:
    'usar um tomador pré-cadastrado' manda `tomador_id`; 'cadastrar meu
    próprio tomador' manda `novo_tomador` — nunca os dois, nem nenhum."""
    tomador_id: uuid.UUID | None = None
    novo_tomador: TomadorCriarRequest | None = None

    apelido: str = Field(min_length=1, max_length=100)
    cod_local_prestacao: str = Field(pattern=r"^\d{7}$")
    cod_trib_nacional: str = Field(min_length=1, max_length=6)
    cod_trib_municipal: str | None = Field(default=None, max_length=5)
    template_descricao: str = Field(min_length=1)
    metodo_captura_valor: str = Field(default="manual", pattern=r"^(manual|pdf|csv|chat)$")
    serie: str = Field(default="1", max_length=5)
    requer_revisao: bool = True
    dia_limite_emissao: int | None = Field(default=None, ge=1, le=31)
    dias_para_recebimento: int | None = Field(default=None, ge=0)

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
    cod_trib_nacional: str | None = Field(default=None, min_length=1, max_length=6)
    cod_trib_municipal: str | None = Field(default=None, max_length=5)
    template_descricao: str | None = Field(default=None, min_length=1)
    metodo_captura_valor: str | None = Field(default=None, pattern=r"^(manual|pdf|csv|chat)$")
    serie: str | None = Field(default=None, max_length=5)
    requer_revisao: bool | None = None
    ativo: bool | None = None
    dia_limite_emissao: int | None = Field(default=None, ge=1, le=31)
    dias_para_recebimento: int | None = Field(default=None, ge=0)


class PrestadorResponse(BaseModel):
    """Marco 14 — tela de Configurações (dados básicos, somente leitura por
    enquanto: não existe endpoint de edição ainda, é administrativo via
    banco/scripts — ver DEPLOY.md)."""
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

    model_config = {"from_attributes": True}


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


class EventoCalendarioResponse(BaseModel):
    data: date
    tipo: str
    titulo: str
    vinculo_id: uuid.UUID | None = None
    apelido: str | None = None
    valor: float | None = None


class CalendarioResponse(BaseModel):
    inicio: date
    fim: date
    eventos: list[EventoCalendarioResponse]
