"""Schemas Pydantic da API do painel interno (Marco 5/6)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


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
