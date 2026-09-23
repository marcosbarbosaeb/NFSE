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
    LargeBinary,
    Numeric,
    SmallInteger,
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
    # Marco 16, item 5 — depois da pesquisa de viabilidade de uma "aba de
    # impostos" (DAS-MEI), Marcos decidiu não construir cálculo/boleto por
    # enquanto (exigiria integração paga com a SERPRO): só quer poder
    # registrar essa alíquota de referência e ser lembrado mensalmente de
    # revisá-la. Esta data marca a última vez que `aliquota_atual` foi
    # confirmada/alterada (ver PATCH /api/prestador/aliquota) — separada de
    # `atualizado_em` de propósito, porque esse campo muda com QUALQUER
    # edição do prestador, não só a alíquota. É o que permite ao dashboard
    # e ao calendário saberem se ela já foi revisada NESTE mês (ver
    # app/services/dashboard.py e app/services/calendario.py).
    aliquota_atualizada_em: Mapped[date | None] = mapped_column(Date)
    # Regra do lembrete mensal de alíquota no calendário (dia do mês).
    # Nulo = dia 1 (padrão). Ver app/services/calendario.py.
    dia_lembrete_aliquota: Mapped[int | None] = mapped_column(SmallInteger)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    certificado: Mapped["Certificado | None"] = relationship(back_populates="prestador", uselist=False)
    vinculos: Mapped[list["PrestadorTomador"]] = relationship(back_populates="prestador")
    despesas: Mapped[list["Despesa"]] = relationship(back_populates="prestador")
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="prestador")
    eventos_manuais: Mapped[list["EventoManual"]] = relationship(back_populates="prestador")
    assinatura: Mapped["Assinatura | None"] = relationship(back_populates="prestador", uselist=False)


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

    # Marco 15 — cadastro público self-service (ver app/services/cadastro.py).
    # default=False no lado Python de propósito: um cadastro novo nasce NÃO
    # confirmado; usuários criados administrativamente (scripts/criar_usuario.py)
    # setam True explicitamente. `autenticar`/`api_login` bloqueiam login
    # enquanto isto for False (ver app/main.py).
    email_confirmado: Mapped[bool] = mapped_column(nullable=False, default=False)
    token_confirmacao: Mapped[str | None] = mapped_column(String(64), unique=True)
    token_confirmacao_expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Marco 16, item 1 — login/cadastro via Google (ver app/services/
    # google_oauth.py). Nullable: a maioria das contas continua só
    # e-mail+senha. Guarda o `sub` (identificador estável do Google, nunca
    # o e-mail — e-mail pode mudar) da PRIMEIRA vez que este usuário loga
    # com Google, seja porque o cadastro nasceu assim (login novo, sem
    # conta ainda — cai no formulário de cadastro público normal, que
    # ainda pede CNPJ/razão social; só depois disso vincula) ou porque uma
    # conta já existente (e-mail+senha) se vinculou depois. Nunca é o
    # único jeito de entrar: `senha_hash` continua obrigatório pra toda
    # conta, então uma conta vinculada ao Google sempre pode entrar pelos
    # dois jeitos.
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)

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

    # Curadoria: o plano original previa que cadastro/edição de um tomador
    # compartilhado não seria gravação direta de qualquer conta — nunca
    # chegou a ser implementado, e Marcos confirmou (22/09/2026, Marco 13)
    # que o caminho é self-service mesmo: a Raiana usa um tomador já no
    # catálogo OU cadastra um novo na hora (igual ao Emissor Nacional
    # permite), sem fila de aprovação — ver app/services/tomadores.py, que
    # sempre cria com status='aprovado'. A coluna continua aqui porque não
    # custa nada manter — dá pra ligar uma curadoria de verdade depois, se
    # isto deixar de ser single-tenant, sem precisar de nova migração.
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

    # Marco 13 — calendário de prazos (ver migração 4e44be09cfe3 e
    # app/services/calendario.py). Os dois são opcionais de propósito: nem
    # todo vínculo tem prazo/previsão conhecidos, e um vínculo sem eles
    # simplesmente não gera evento nenhum no calendário, sem quebrar nada.
    dia_limite_emissao: Mapped[int | None] = mapped_column(
        comment="Dia do mês (1-31) até o qual a nota precisa ser gerada pra não cair pro ciclo do mês seguinte."
    )
    dias_para_recebimento: Mapped[int | None] = mapped_column(
        comment="Dias corridos após a EMISSÃO em que o pagamento costuma cair (não é um dia fixo do mês)."
    )
    # Marco 17 — pra onde mandar as notas deste fornecedor (envio direto).
    email_contato: Mapped[str | None] = mapped_column(String(200))
    whatsapp_contato: Mapped[str | None] = mapped_column(String(20))

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
        CheckConstraint(
            "dia_limite_emissao IS NULL OR (dia_limite_emissao BETWEEN 1 AND 31)",
            name="ck_prestador_tomador_dia_limite_emissao",
        ),
        CheckConstraint(
            "dias_para_recebimento IS NULL OR dias_para_recebimento >= 0",
            name="ck_prestador_tomador_dias_para_recebimento",
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
    # Marco 17 — cache do DANFSe (PDF oficial do ADN) depois da confirmação;
    # anexado no e-mail ao fornecedor e servido pelo link público.
    danfse_pdf: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
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


class EventoManual(Base):
    """Marco 15 — eventos de calendário criados manualmente pelo usuário
    (reunião, lembrete, prazo específico que não é nenhum dos 3 tipos
    computados). Diferente de 'prazo_emissao'/'recebimento_previsto'/
    'recebimento_confirmado' (ver app/services/calendario.py), que são
    derivados na hora a partir de Emissao/PagamentoRecebido/
    PrestadorTomador e não têm linha própria no banco — este tipo É dado
    de verdade, por isso tem tabela e RLS por prestador_id igual ao resto."""

    __tablename__ = "evento_manual"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )

    data: Mapped[date] = mapped_column(Date, nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    # Marco 17 — tipo do evento manual: 'lembrete' (genérico),
    # 'recebimento_previsto' (com valor e fornecedor opcionais) ou
    # 'prazo_emissao'. Ver migração a81c2e5d7f30.
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, default="lembrete", server_default="lembrete")
    valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    prestador_tomador_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador_tomador.id", ondelete="SET NULL")
    )

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prestador: Mapped["Prestador"] = relationship(back_populates="eventos_manuais")


class AjusteEvento(Base):
    """Marco 17 — ajuste de UMA ocorrência de um alerta calculado do
    calendário (mover pra outra data ou ocultar), sem mudar a regra que o
    gera. `chave` identifica a ocorrência: 'vinculo_id:AAAA-MM' pro prazo
    de emissão, o id da emissão pra previsão de recebimento, 'AAAA-MM' pro
    lembrete de alíquota (ver app/services/calendario.py)."""

    __tablename__ = "ajuste_evento"
    __table_args__ = (UniqueConstraint("prestador_id", "tipo", "chave", name="uq_ajuste_evento_ocorrencia"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    chave: Mapped[str] = mapped_column(String(100), nullable=False)
    nova_data: Mapped[date | None] = mapped_column(Date)
    oculto: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assinatura(Base):
    """Marco 15 (item 4) — assinatura/cobrança (Marcos confirmou "cobrança
    real (Stripe ou similar)", mas ainda não tem conta criada: ver
    app/services/billing.py e o racional em app/config.py). Uma linha por
    prestador (não por usuário — o mesmo padrão de `certificado`), criada
    automaticamente:

    - "cortesia": contas administrativas (scripts/criar_usuario.py) — nunca
      passam por Stripe, nunca expiram. É o caso da Raiana hoje.
    - "trial": contas que nascem por /api/cadastro (self-service) — acesso
      liberado até `trial_termina_em` sem precisar de cartão.
    - "ativa"/"inadimplente"/"cancelada": espelham o status de uma
      assinatura Stripe de verdade, sincronizado via webhook
      (checkout.session.completed / customer.subscription.*, ver
      app/services/billing.py). Só existe depois que o prestador passa pelo
      Checkout.

    De propósito, esta versão NÃO bloqueia acesso ao painel com base no
    status (ver docstring de `assinatura_esta_ativa` em billing.py) — a
    estrutura de cobrança está pronta, mas ligar o bloqueio de verdade
    depende de ter uma conta Stripe real pra validar contra ela primeiro."""

    __tablename__ = "assinatura"

    id: Mapped[uuid.UUID] = _uuid_pk()
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestador.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
    trial_termina_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('cortesia', 'trial', 'ativa', 'inadimplente', 'cancelada')",
            name="ck_assinatura_status_valido",
        ),
    )

    prestador: Mapped["Prestador"] = relationship(back_populates="assinatura")


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
    # Marco 17 — e-mail/telefone usado e motivo da falha (envio direto).
    destino: Mapped[str | None] = mapped_column(String(200))
    erro: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    emissao: Mapped["Emissao"] = relationship(back_populates="envios")

    __table_args__ = (
        CheckConstraint(
            "canal IN ('download','email','whatsapp','direto_fornecedor','mensagem_pronta')",
            name="ck_envio_canal",
        ),
        CheckConstraint("status IN ('pendente','enviado','falha')", name="ck_envio_status"),
    )
