"""
Modelo de dados — implementa a seção "Modelo de dados" do plano do projeto,
já com as correções que entraram nas revisões (ChatGPT, Gemini, Opus):

- `tomador` guarda só identidade (CNPJ, razão social, endereço). Nenhuma regra
  fiscal/de negócio mora nele.
- `prestador_tomador` é onde fica COMO aquele prestador fatura aquele tomador
  (código de serviço, tributação, template de descrição, método de captura de
  valor). Isso pode mudar de prestador pra prestador mesmo faturando o mesmo
  tomador.
- ACHADO ao ler os dados reais (FORNECEDORES em integracao/build_dps.py): AWIN
  e AWIN Rchlo são o MESMO tomador (mesmo CNPJ), mas a Raiana precisa faturar
  os dois separadamente porque são programas/linhas de receita distintos na
  planilha de controle dela. Ou seja, um par (prestador, tomador) pode
  legitimamente ter MAIS DE UM vínculo — por isso não há UNIQUE(prestador_id,
  tomador_id) aqui; o que precisa ser único é (prestador_id, apelido).
- `emissao.tomador_snapshot` congela os dados do tomador usados naquela nota
  no momento da emissão — uma correção posterior no catálogo central não pode
  reescrever silenciosamente o que uma nota antiga "deveria" ter dito.
- RLS (Row-Level Security) é ativado na migração (ver alembic/versions), não
  aqui — mas as tabelas sensíveis carregam `prestador_id` diretamente
  (denormalizado, inclusive em `emissao`/`pagamento_recebido`) pra a policy
  não depender de subquery/join.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Prestador(Base):
    """Quem emite. Um prestador por conta no MVP (multi-CNPJ fica pra depois,
    de propósito — ver Escopo do MVP no plano)."""

    __tablename__ = "prestador"

    id: Mapped[uuid.UUID] = _uuid_pk()
    cpf_cnpj: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    inscricao_municipal: Mapped[str | None] = mapped_column(String(30))
    razao_social: Mapped[str] = mapped_column(String(200), nullable=False)

    cod_municipio: Mapped[str] = mapped_column(String(7), nullable=False)
    cep: Mapped[str | None] = mapped_column(String(8))
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str | None] = mapped_column(String(100))

    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))

    # Campos exigidos pela DPS (ver build_dps_xml existente) — nomes mantidos
    # próximos do leiaute oficial de propósito, pra ficar óbvio de onde vêm
    # quando a biblioteca de emissão for plugada aqui (Marco 3).
    op_simples_nacional: Mapped[str | None] = mapped_column(String(1))
    regime_apuracao_sn: Mapped[str | None] = mapped_column(String(1))
    regime_especial_trib: Mapped[str | None] = mapped_column(String(1))

    # Muda mês a mês (Marcos ajusta isso manualmente hoje) — fica aqui como o
    # valor "atual" pra pré-preencher, mas a confirmação antes de emitir é
    # sempre obrigatória (ver Contingências: "Alíquota errada" no plano).
    aliquota_atual: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    certificado: Mapped["Certificado | None"] = relationship(back_populates="prestador", uselist=False)
    vinculos: Mapped[list["PrestadorTomador"]] = relationship(back_populates="prestador")
    despesas: Mapped[list["Despesa"]] = relationship(back_populates="prestador")
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="prestador")


class Usuario(Base):
    """Login multiusuário — Marco 10 (Fase 2). Antes disso, o painel operava
    sempre como o `prestador_ativo_id` fixo em app/config.py (Fase 1, sem
    login, ver docstring antiga em Settings). Um usuário pertence a UM
    prestador (mesma limitação de 'um prestador por conta' do MVP — ver
    docstring de Prestador); múltiplos usuários podem logar como o MESMO
    prestador (ex.: Marcos e a Raiana operando o mesmo negócio).

    Esta tabela NÃO tem RLS (ao contrário de certificado/emissao/...):
    login precisa achar o usuário pelo e-mail ANTES de sabermos qual
    prestador_id usar pra `definir_prestador_atual` — não dá pra exigir a
    variável de sessão de RLS pra descobrir ela mesma. Isso é seguro porque
    `usuario` só guarda dado de CONTA (e-mail, hash de senha, qual
    prestador), não dado de negócio do prestador — o isolamento de negócio
    continua 100% garantido pela RLS nas tabelas de sempre, alcançada só
    depois que o login resolve prestador_id no servidor (nunca a partir de
    entrada do cliente — ver prestador_atual_id em app/main.py).
    """

    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )

    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    # Formato: "scrypt$<salt hex>$<hash hex>" (ver app/auth.py) — nunca
    # texto puro, nunca um hash sem salt.
    senha_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    ativo: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prestador: Mapped["Prestador"] = relationship(back_populates="usuarios")


class Certificado(Base):
    """Certificado A1 do prestador. Um por prestador no MVP.

    `pfx_criptografado`/`senha_criptografada` NUNCA guardam texto puro (ver
    Riscos/Integrações no plano — é a integração mais urgente). O esquema já
    carrega `chave_kms_ref` pra quando a criptografia local (Fernet, ver
    app/crypto.py) for trocada por envelope encryption via KMS de verdade —
    essa troca não precisa mexer nesta tabela.
    """

    __tablename__ = "certificado"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    pfx_criptografado: Mapped[bytes] = mapped_column(nullable=False)
    senha_criptografada: Mapped[bytes] = mapped_column(nullable=False)
    chave_kms_ref: Mapped[str | None] = mapped_column(
        String(200), comment="Identifica qual chave/versão do KMS cifrou este registro. Nulo = chave local de dev."
    )
    validade: Mapped[date | None] = mapped_column(Date, comment="Vencimento do certificado A1 — ver Contingências.")

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prestador: Mapped["Prestador"] = relationship(back_populates="certificado")


class Tomador(Base):
    """Catálogo CENTRAL — compartilhado entre prestadores. Só identidade.

    Restrito a pessoa jurídica de propósito (ver Modelo de dados no plano):
    tomador pessoa física compartilhado entre contas seria dado pessoal sem
    base legal clara.
    """

    __tablename__ = "tomador"

    id: Mapped[uuid.UUID] = _uuid_pk()
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    razao_social: Mapped[str] = mapped_column(String(200), nullable=False)

    cod_municipio: Mapped[str] = mapped_column(String(7), nullable=False)
    cep: Mapped[str | None] = mapped_column(String(8))
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str | None] = mapped_column(String(100))

    # Curadoria (ver Modelo de dados no plano): cadastro/edição de um tomador
    # compartilhado não pode ser gravação direta de qualquer conta.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="aprovado")

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('pendente', 'aprovado')", name="ck_tomador_status"),
    )


class PrestadorTomador(Base):
    """O vínculo: COMO um prestador fatura um tomador do catálogo.

    Mais de um vínculo pode existir para o mesmo par (prestador, tomador) —
    caso real: AWIN e AWIN Rchlo são o mesmo tomador, faturados como dois
    programas separados. O que precisa ser único é o apelido dentro de um
    mesmo prestador, não o par em si.
    """

    __tablename__ = "prestador_tomador"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )
    tomador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tomador.id", ondelete="RESTRICT"), nullable=False
    )

    apelido: Mapped[str] = mapped_column(String(100), nullable=False, comment='Ex.: "AWIN", "AWIN Rchlo", "Squad Época"')

    cod_local_prestacao: Mapped[str] = mapped_column(String(7), nullable=False)
    cod_trib_nacional: Mapped[str] = mapped_column(String(6), nullable=False)
    cod_trib_municipal: Mapped[str | None] = mapped_column(String(5))
    template_descricao: Mapped[str] = mapped_column(Text, nullable=False)

    metodo_captura_valor: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    serie: Mapped[str] = mapped_column(String(5), nullable=False, server_default="1")
    requer_revisao: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    ativo: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prestador: Mapped["Prestador"] = relationship(back_populates="vinculos")
    tomador: Mapped["Tomador"] = relationship()
    emissoes: Mapped[list["Emissao"]] = relationship(back_populates="vinculo")

    __table_args__ = (
        UniqueConstraint("prestador_id", "apelido", name="uq_prestador_tomador_apelido"),
        CheckConstraint(
            "metodo_captura_valor IN ('manual', 'pdf', 'csv', 'chat')",
            name="ck_prestador_tomador_metodo",
        ),
    )


class Emissao(Base):
    """Uma linha por nota. `estado` é a máquina de estados do plano:

    rascunho -> montado -> assinado -> submetido -> confirmado
                                                   -> cancelada / substituida
    (qualquer etapa) -> erro

    `prestador_id` é denormalizado (também dá pra chegar nele via
    `vinculo.prestador_id`) só pra permitir a policy de RLS e a constraint de
    unicidade do nDPS sem subquery.
    """

    __tablename__ = "emissao"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_tomador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador_tomador.id", ondelete="RESTRICT"), nullable=False
    )
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="RESTRICT"), nullable=False
    )

    competencia: Mapped[str] = mapped_column(String(7), nullable=False, comment="AAAA-MM")
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    serie: Mapped[str] = mapped_column(String(5), nullable=False)
    n_dps: Mapped[int | None] = mapped_column()
    chave_acesso: Mapped[str | None] = mapped_column(String(50), unique=True)

    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="rascunho")

    # Congelamento dos dados do tomador no momento da emissão (achado do
    # Opus): {"razao_social": ..., "cnpj": ..., "endereco": {...}, "apelido":
    # ..., "template_descricao_usado": ..., "codigo_servico_usado": ...}
    tomador_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    xml_dps: Mapped[str | None] = mapped_column(Text)
    xml_assinado: Mapped[str | None] = mapped_column(Text)
    xml_resposta: Mapped[str | None] = mapped_column(Text)
    danfse_path: Mapped[str | None] = mapped_column(Text)
    erro_detalhe: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vinculo: Mapped["PrestadorTomador"] = relationship(back_populates="emissoes")
    envios: Mapped[list["Envio"]] = relationship(back_populates="emissao")

    __table_args__ = (
        CheckConstraint(
            "estado IN ('rascunho','montado','assinado','submetido','confirmado',"
            "'cancelada','substituida','erro')",
            name="ck_emissao_estado",
        ),
        # Fonte de verdade do sequencial: por prestador + série. O Sefin só
        # rejeita duplicidade quando ela chega; quem impede de tentar duas
        # vezes o mesmo número somos nós (ver Motor de emissão no plano).
        UniqueConstraint("prestador_id", "serie", "n_dps", name="uq_emissao_prestador_serie_ndps"),
    )


# Índice parcial: chave de idempotência de negócio — não permite duas
# emissões ATIVAS (não canceladas) pro mesmo vínculo+competência. Uma
# substituição precisa cancelar a anterior antes de criar a nova.
Index(
    "uq_emissao_vinculo_competencia_ativa",
    Emissao.prestador_tomador_id,
    Emissao.competencia,
    unique=True,
    postgresql_where=(Emissao.estado != "cancelada"),
)


class PagamentoRecebido(Base):
    """O lado 'recebi' do painel de status."""

    __tablename__ = "pagamento_recebido"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_tomador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador_tomador.id", ondelete="CASCADE"), nullable=False
    )
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )

    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    confirmado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("origem IN ('manual', 'extrato')", name="ck_pagamento_origem"),
    )


class Despesa(Base):
    __tablename__ = "despesa"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )

    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prestador: Mapped["Prestador"] = relationship(back_populates="despesas")


class Envio(Base):
    """Independente da emissão fiscal de propósito (ver Contingências no
    plano): falha de envio nunca invalida uma nota já confirmada."""

    __tablename__ = "envio"

    id: Mapped[uuid.UUID] = _uuid_pk()
    emissao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emissao.id", ondelete="CASCADE"), nullable=False
    )

    canal: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendente")
    tentativas: Mapped[int] = mapped_column(nullable=False, server_default="0")
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    emissao: Mapped["Emissao"] = relationship(back_populates="envios")

    __table_args__ = (
        CheckConstraint(
            "canal IN ('download','email','whatsapp','direto_fornecedor','mensagem_pronta')",
            name="ck_envio_canal",
        ),
        CheckConstraint("status IN ('pendente','enviado','falha')", name="ck_envio_status"),
    )
