"""
Motor de emissão — Marco 6 do plano: formaliza como serviço a máquina de
estados desenhada em "Planejamento detalhado de construção > Motor de
emissão":

    rascunho -> montado -> assinado -> submetido -> confirmado
                                                   -> cancelada / substituida
    (qualquer etapa) -> erro

Cada função abaixo é UMA transição — recebe uma Emissao num estado e a
devolve no próximo, ou levanta TransicaoInvalidaError se o estado atual não
permite aquela transição. Nada aqui pula etapa.

Duas decisões que vêm direto das correções da revisão do Opus:

1. nDPS é sequencial POR (prestador, série) e o Postgres é a fonte de
   verdade — NÃO a Sefin ("reserva" de nDPS pela Sefin era um entendimento
   errado, corrigido no plano). `_proximo_ndps` serializa a atribuição com
   um advisory lock transacional, então duas emissões criadas ao mesmo
   tempo nunca disputam o mesmo número — e o índice único
   `uq_emissao_prestador_serie_ndps` (Marco 1) é o cinto-e-suspensório caso
   algo escape disso.

   IMPORTANTE pra quem for ligar isto a submissões de verdade: até agora
   NENHUMA nota foi submetida com sucesso pela série "1" (a que os 5
   fornecedores usam) — o único envio real testado foi um CANCELAMENTO de
   nota emitida pelo Emissor Web, que usa série 70000-79999, faixa
   completamente separada (ver integracao/build_dps.py). Então começar do
   nDPS=1 aqui é seguro HOJE. Se algum dia uma DPS for emitida pela série 1
   por fora deste sistema (manualmente, por exemplo), o contador daqui
   precisa ser sincronizado antes de confiar nele — é pra isso que existe
   `ClienteSefin.proximo_ndps_livre_por_varredura` (Marco 3), como checagem
   de reconciliação, não como fonte de verdade.

2. `tomador_snapshot` congela os dados do tomador (e a descrição já
   renderizada) no momento do rascunho — uma edição posterior no catálogo
   central não reescreve o que uma nota antiga "deveria" ter dito. Dados do
   PRESTADOR (CNPJ/IM/regime) são lidos ao vivo em `montar()`: só existe um
   prestador na Fase 1 e esses campos não são compartilhados/editáveis por
   terceiros como o catálogo de tomadores é — não precisam do mesmo
   congelamento.

Submissão de verdade (`submeter`/`cancelar`) usa app.fiscal.cliente_sefin,
que continua com a mesma ressalva do Marco 3: a submissão de DPS nunca foi
testada contra a API real (rede bloqueada neste sandbox); cancelamento tem
uma receita já validada em produção, mas cada envio aqui é uma chamada de
rede de verdade — os testes deste módulo usam ClienteSefin mockado.
"""
import logging
import hashlib
import re
import uuid
from datetime import datetime, timezone

import requests
from lxml import etree
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.fiscal.cliente_sefin import ClienteSefin
from app.fiscal.dps import assinar_dps, montar_dps_xml, montar_id_dps, renderizar_descricao
from app.fiscal.eventos import assinar_evento, montar_evento_cancelamento
from app.models import Emissao, PrestadorTomador
from app.services.cep import RECUSAS_DE_CEP, corrigir_endereco

NS = "http://www.sped.fazenda.gov.br/nfse"

ESTADOS_ATIVOS_PARA_IDEMPOTENCIA = "estado != 'cancelada'"  # espelha o índice parcial do Marco 1


logger = logging.getLogger("agenteana.motor")


class TransicaoInvalidaError(Exception):
    """A Emissao não está no estado que essa transição exige."""

    def __init__(self, esperado: str, atual: str):
        super().__init__(f"esperava estado '{esperado}' (ou compatível), mas emissão está em '{atual}'")
        self.esperado = esperado
        self.atual = atual


class ReenvioPrecisaConferirError(TransicaoInvalidaError):
    """A última tentativa caiu no meio (rede): não se remonta, se confere."""

    def __init__(self):
        Exception.__init__(self, "A última tentativa caiu no meio: envie de novo que a Ana confere com a Receita antes.")
        self.esperado, self.atual = "erro", "erro"


class LimiteDoPlanoError(TransicaoInvalidaError):
    """Limite de notas do plano (app/services/planos.py). Não é erro da
    nota: ela fica como está, pronta pra ir quando houver espaço."""

    def __init__(self, mensagem: str):
        Exception.__init__(self, mensagem)


class SoHomologacaoError(TransicaoInvalidaError):
    """Ambiente de teste da plataforma: nota de produção não é enviada."""

    def __init__(self):
        Exception.__init__(self, "Este é o ambiente de teste: só saem notas de homologação (sem valor fiscal).")
        self.esperado, self.atual = "homologação", "produção"


class EmissaoJaExisteError(Exception):
    """Já existe uma emissão ativa (não cancelada) pra esse vínculo+competência
    — mesma regra do índice único parcial `uq_emissao_vinculo_competencia_ativa`."""


def _chave_advisory(prestador_id: uuid.UUID, serie: str) -> int:
    """Deriva uma chave estável (não o hash() nativo do Python — é
    randomizado por processo, PYTHONHASHSEED) pra pg_advisory_xact_lock."""
    digest = hashlib.sha256(f"{prestador_id}:{serie}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _proximo_ndps(db: Session, prestador_id: uuid.UUID, serie: str) -> int:
    """Trava consultiva transacional (liberada sozinha no fim da
    transação) serializando a atribuição do próximo nDPS pra esse
    prestador+série — evita corrida entre duas emissões concorrentes sem
    precisar de um lock de tabela inteira."""
    db.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": _chave_advisory(prestador_id, serie)})
    maximo = db.query(func.max(Emissao.n_dps)).filter_by(prestador_id=prestador_id, serie=serie).scalar()
    return (maximo or 0) + 1


def buscar_emissao_ativa(
    db: Session, vinculo_id: uuid.UUID, competencia: str, tomador_documento: str | None = None
) -> Emissao | None:
    """Emissão ATIVA (não cancelada) pra esse vínculo+competência, se
    existir — mesma regra do índice único parcial
    `uq_emissao_vinculo_competencia_ativa`. Reaproveitada por
    `criar_rascunho` (bloqueia de verdade) e por um endpoint só-leitura que a
    tela de 'Nova emissão' consulta ANTES do usuário tentar submeter, pra
    avisar de duplicata de forma proativa em vez de só depois de um erro
    (pedido do Marcos no Marco 16 — 'o sistema tem que avisar pra não ter
    nota repetida')."""
    query = db.query(Emissao).filter(
        Emissao.prestador_tomador_id == vinculo_id, Emissao.competencia == competencia, Emissao.estado != "cancelada"
    )
    if tomador_documento is None:
        query = query.filter(Emissao.tomador_documento.is_(None))
    else:
        query = query.filter(Emissao.tomador_documento == tomador_documento)
    return query.first()


def mes_anterior(competencia: str, meses: int) -> str:
    """'2026-01' menos 2 meses -> '2025-11'."""
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    total = ano * 12 + (mes - 1) - meses
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def criar_rascunho(
    db: Session,
    vinculo: PrestadorTomador,
    *,
    competencia: str,
    valor: float,
    ordem: str | None = None,
    aliq_sn: float | None = None,
    tpAmb: str = "2",
    tomador_avulso: dict | None = None,
    dcompet: str | None = None,
    referencia: str | None = None,
    iss_retido: bool | None = None,
    aliq_iss: float | None = None,
) -> Emissao:
    """rascunho — atribui nDPS, congela o snapshot do tomador+descrição, e
    checa a idempotência mensal ANTES de tentar gravar (o índice único
    parcial é quem garante de verdade; isto aqui só dá um erro mais claro
    no caso comum, em vez de deixar estourar IntegrityError genérico)."""
    documento_avulso = tomador_avulso["documento"] if tomador_avulso else None
    ja_existe = buscar_emissao_ativa(db, vinculo.id, competencia, documento_avulso)
    if ja_existe is not None:
        quem = f"{tomador_avulso['razao_social']} ({vinculo.apelido})" if tomador_avulso else f"'{vinculo.apelido}'"
        raise EmissaoJaExisteError(
            f"Já existe uma emissão ativa para {quem} na competência {competencia} "
            f"(id={ja_existe.id}, estado={ja_existe.estado}). Cancele-a antes de criar outra."
        )

    # `referencia` (AAAA-MM): o mês a que o serviço se refere quando ele não é
    # o da competência da nota — a comissão de setembro da Shopee sai numa
    # nota de outubro, e a descrição tem que falar de setembro (05/10/2026).
    if referencia is None and (vinculo.descricao_meses_atras or 0) > 0:
        # Tomador cuja nota fala de um mês anterior ao dela (a comissão de
        # setembro faturada em outubro): configurado no cadastro.
        referencia = mes_anterior(competencia, vinculo.descricao_meses_atras)
    descricao = renderizar_descricao(vinculo.template_descricao, referencia or competencia, ordem=ordem)
    snapshot = {
        "razao_social": vinculo.tomador.razao_social,
        "cnpj": vinculo.tomador.cnpj,
        "endereco": {
            "cMun": vinculo.tomador.cod_municipio, "CEP": vinculo.tomador.cep,
            "xLgr": vinculo.tomador.logradouro, "nro": vinculo.tomador.numero,
            "xCpl": vinculo.tomador.complemento, "xBairro": vinculo.tomador.bairro,
        },
        "apelido": vinculo.apelido,
        "template_descricao_usado": vinculo.template_descricao,
        "descricao_renderizada": descricao,
        "codigo_servico_usado": {
            "cLocPrestacao": vinculo.cod_local_prestacao,
            "cTribNac": vinculo.cod_trib_nacional,
            "cTribMun": vinculo.cod_trib_municipal,
            "cNBS": vinculo.cod_nbs,
        },
        # Data de competência escolhida no calendário (29/09/2026); sem ela,
        # a DPS usa o dia em que for montada.
        "dcompet": dcompet,
        "referencia": referencia,
        "ordem": ordem,
        "aliq_sn": aliq_sn,
        "tpAmb": tpAmb,
    }
    # ISS retido (2026.10.7): o que veio na tela ou a memória do tomador/empresa.
    # Nota de vendedor da Shopee (avulsa) não herda a retenção do marketplace.
    from app.services.conferencia import retencao_da_nota

    retido, aliq = retencao_da_nota(vinculo, vinculo.prestador, False if tomador_avulso and iss_retido is None else iss_retido, aliq_iss)
    snapshot["iss_retido"] = retido
    snapshot["aliq_iss"] = aliq
    if not tomador_avulso and vinculo.tomador.estrangeiro:
        # Tomador de fora do Brasil (05/10/2026): sem CNPJ, a nota sai com a
        # identificação fiscal de lá (NIF) e o país — o mesmo retrato das
        # notas pra vendedores estrangeiros da Shopee, que a Receita já
        # autorizou (`_montar_xml` põe o endExt só com o país e o grupo
        # comExt). É uma nota normal do vínculo: não é avulsa.
        snapshot.update({
            # Sem número fiscal: `cnpj` fica vazio e vai o motivo (cNaoNIF na nota).
            "cnpj": (vinculo.tomador.nif or "").strip() or None,
            "motivo_sem_nif": vinculo.tomador.sem_nif,
            "tipo_documento": "NIF",
            "pais": vinculo.tomador.pais.strip().upper(),
            "endereco": {"cMun": None, "CEP": None, "xLgr": None, "nro": None, "xCpl": None, "xBairro": None},
        })
    if tomador_avulso:
        # Relatório da Shopee: a nota é pro VENDEDOR da linha, não pro
        # tomador do vínculo — e ele não vai pro catálogo, só fica aqui.
        endereco = tomador_avulso.get("endereco") or {}
        snapshot.update({
            "razao_social": tomador_avulso["razao_social"],
            "cnpj": tomador_avulso["documento"],
            "tipo_documento": tomador_avulso["tipo_documento"],
            "endereco": {
                "cMun": endereco.get("cMun"), "CEP": endereco.get("CEP"), "xLgr": endereco.get("xLgr"),
                "nro": endereco.get("nro"), "xCpl": endereco.get("xCpl"), "xBairro": endereco.get("xBairro"),
            },
            "pais": tomador_avulso.get("pais"),
            "email": tomador_avulso.get("email"),
            "email_invalido": tomador_avulso.get("email_invalido"),
            "lojas": tomador_avulso.get("lojas") or [],
            "avulso": True,
        })
        if vinculo.incluir_intermediario:
            # O marketplace (tomador do vínculo, ex.: Shopee) declarado como
            # intermediário da nota do vendedor.
            snapshot["intermediario"] = {
                "CNPJ": vinculo.tomador.cnpj, "xNome": vinculo.tomador.razao_social,
                "cMun": vinculo.tomador.cod_municipio, "CEP": vinculo.tomador.cep,
                "xLgr": vinculo.tomador.logradouro, "nro": vinculo.tomador.numero,
                "xCpl": vinculo.tomador.complemento, "xBairro": vinculo.tomador.bairro,
            }

    n_dps = _proximo_ndps(db, vinculo.prestador_id, vinculo.serie)

    emissao = Emissao(
        id=uuid.uuid4(),
        prestador_tomador_id=vinculo.id,
        prestador_id=vinculo.prestador_id,
        competencia=competencia,
        valor=valor,
        serie=vinculo.serie,
        n_dps=n_dps,
        estado="rascunho",
        tomador_snapshot=snapshot,
        tomador_documento=documento_avulso,
    )
    db.add(emissao)
    db.flush()
    return emissao


def _exigir_estado(emissao: Emissao, *permitidos: str) -> None:
    if emissao.estado not in permitidos:
        raise TransicaoInvalidaError("/".join(permitidos), emissao.estado)


def _interm_valido(interm: dict | None) -> dict | None:
    """Endereço do intermediário só vai se estiver completo (senão só o
    documento e o nome)."""
    if not interm:
        return None
    if not all(interm.get(c) for c in ("cMun", "CEP", "xLgr", "nro", "xBairro")):
        interm = {k: v for k, v in interm.items() if k in ("CNPJ", "CPF", "NIF", "xNome")}
    return interm


def montar(db: Session, emissao: Emissao) -> Emissao:
    """rascunho -> montado. Usa o snapshot congelado (tomador/descrição),
    não o catálogo ao vivo — é essa a garantia contra edição retroativa."""
    _exigir_estado(emissao, "rascunho")
    return _montar_xml(db, emissao)


def remontar(db: Session, emissao: Emissao) -> Emissao:
    """erro -> montado, com o MESMO número de DPS e os mesmos dados (o
    snapshot), só com a hora de emissão nova. É o conserto das recusas que
    não dependem dos dados da nota (E0008, hora à frente do relógio da
    Receita). Não vale pra falha de comunicação: ali a nota pode ter
    chegado, e `submeter` confere antes de reenviar."""
    _exigir_estado(emissao, "erro")
    if (emissao.erro_detalhe or "").startswith(MARCA_FALHA_COMUNICACAO):
        raise ReenvioPrecisaConferirError()
    emissao.xml_assinado = None
    return _montar_xml(db, emissao)


def recusa_corrigivel(erro_detalhe: str | None) -> bool:
    """A Ana consegue consertar sozinha? Hora à frente do relógio (remonta
    com a hora de agora) ou CEP que não bate com a cidade (procura o certo)."""
    return bool(erro_detalhe) and any(codigo in erro_detalhe for codigo in (*_RECUSAS_DE_HORA, *RECUSAS_DE_CEP))


def recusa_de_cep(erro_detalhe: str | None) -> bool:
    return bool(erro_detalhe) and any(codigo in erro_detalhe for codigo in RECUSAS_DE_CEP)


def corrigir_cep(db: Session, emissao: Emissao) -> str | None:
    """Conserta o endereço do tomador NA NOTA (o snapshot) com o CEP achado
    pelo endereço — ver app/services/cep.py. Devolve o que mudou, em texto,
    ou None se não havia o que consertar. Não reenvia: quem chama remonta."""
    snap = dict(emissao.tomador_snapshot or {})
    antes = dict(snap.get("endereco") or {})
    correcao = corrigir_endereco(antes)
    if correcao is None:
        return None
    snap["endereco"] = correcao.endereco or {c: None for c in ("cMun", "CEP", "xLgr", "nro", "xCpl", "xBairro")}
    snap["endereco_corrigido"] = {"antes": antes, "explicacao": correcao.explicacao}
    emissao.tomador_snapshot = snap
    db.flush()
    return correcao.explicacao


def _endereco_do_cadastro_mudou(db: Session, emissao: Emissao) -> bool:
    """A pessoa corrigiu o endereço no cadastro do tomador depois da recusa:
    a nota passa a usar o endereço novo (e não precisa adivinhar o CEP)."""
    if emissao.tomador_documento or emissao.vinculo is None or emissao.vinculo.tomador is None:
        return False
    t = emissao.vinculo.tomador
    if t.de_fora:
        return False  # de fora do Brasil: não tem CEP nem endereço daqui pra acertar
    do_cadastro = {"cMun": t.cod_municipio, "CEP": t.cep, "xLgr": t.logradouro, "nro": t.numero, "xCpl": t.complemento, "xBairro": t.bairro}
    snap = dict(emissao.tomador_snapshot or {})
    atual = snap.get("endereco") or {}
    if all((atual.get(c) or None) == (v or None) for c, v in do_cadastro.items()):
        return False
    snap["endereco"] = do_cadastro
    snap["razao_social"] = t.razao_social
    emissao.tomador_snapshot = snap
    db.flush()
    return True


def _levar_cep_pro_cadastro(db: Session, emissao: Emissao) -> None:
    """A nota passou com o endereço consertado: o cadastro do tomador fica
    igual, pras próximas não baterem na mesma recusa. Só pra tomador
    cadastrado (vendedor de relatório não tem cadastro) e só se o cadastro
    ainda está como estava quando a nota foi gerada."""
    snap = emissao.tomador_snapshot or {}
    correcao = snap.get("endereco_corrigido")
    if not correcao or emissao.tomador_documento or emissao.vinculo is None:
        return
    tomador, antes, agora = emissao.vinculo.tomador, correcao.get("antes") or {}, snap.get("endereco") or {}
    if tomador is None or not agora.get("cMun") or tomador.cep != antes.get("CEP") or tomador.cod_municipio != antes.get("cMun"):
        return
    tomador.cep, tomador.cod_municipio = agora.get("CEP"), agora.get("cMun")
    db.flush()


def corrigir_e_reenviar(db: Session, emissao: Emissao, private_key, cert, cliente: ClienteSefin) -> Emissao:
    """Nota recusada por algo que a Ana conserta sozinha: acerta (hora ou
    CEP), remonta com o mesmo número, assina e envia de novo."""
    if recusa_de_cep(emissao.erro_detalhe) and not _endereco_do_cadastro_mudou(db, emissao):
        if corrigir_cep(db, emissao) is None:
            return emissao  # nada a consertar (ou o serviço de CEP não respondeu): fica como está
    remontar(db, emissao)
    assinar(db, emissao, private_key, cert)
    emissao = submeter(db, emissao, cliente)
    if emissao.estado == "confirmado":
        _levar_cep_pro_cadastro(db, emissao)
    return emissao


def _montar_xml(db: Session, emissao: Emissao) -> Emissao:
    prestador = emissao.vinculo.prestador
    snap = emissao.tomador_snapshot

    prest = {
        "CNPJ": prestador.cpf_cnpj, "IM": prestador.inscricao_municipal, "cMun": prestador.cod_municipio,
        "opSimpNac": prestador.op_simples_nacional, "regApTribSN": prestador.regime_apuracao_sn,
        "regEspTrib": prestador.regime_especial_trib,
    }
    tipo_doc = snap.get("tipo_documento", "CNPJ")
    endereco = snap.get("endereco") or {}
    if not all(endereco.get(c) for c in ("cMun", "CEP", "xLgr", "nro", "xBairro")):
        # Endereço pela metade (tomador importado sem rua/CEP, CEP que não
        # deu pra consertar): a nota sai sem o endereço do tomador — ele é
        # opcional na NFS-e — em vez de ir com campo vazio e ser recusada.
        endereco = {}
    toma = {
        tipo_doc: snap["cnpj"], "xNome": snap["razao_social"],
        "cMun": endereco.get("cMun"), "CEP": endereco.get("CEP"),
        "xLgr": endereco.get("xLgr"), "nro": endereco.get("nro"),
        "xCpl": endereco.get("xCpl"), "xBairro": endereco.get("xBairro"),
    }
    if tipo_doc == "NIF" and snap.get("pais") and str(snap["pais"]).upper() != "BR":
        toma["cPais"] = snap["pais"]
        if not snap.get("cnpj") and str(snap.get("motivo_sem_nif") or "") in ("1", "2"):
            # Empresa de fora sem número fiscal: no lugar do NIF vai o motivo.
            toma.pop("NIF", None)
            toma["cNaoNIF"] = str(snap["motivo_sem_nif"])
    serv = {**snap["codigo_servico_usado"], "descricao": snap["descricao_renderizada"]}

    dps_el = montar_dps_xml(
        prest=prest, toma=toma, serv=serv, serie=emissao.serie, n_dps=emissao.n_dps,
        valor=float(emissao.valor), tpAmb=snap["tpAmb"], aliq_sn=snap["aliq_sn"],
        dcompet=snap.get("dcompet"), interm=_interm_valido(snap.get("intermediario")),
        iss_retido=bool(snap.get("iss_retido")), aliq_iss=snap.get("aliq_iss"),
    )
    emissao.xml_dps = etree.tostring(dps_el, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode()
    emissao.estado = "montado"
    emissao.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    return emissao


def assinar(db: Session, emissao: Emissao, private_key, cert) -> Emissao:
    """montado -> assinado."""
    _exigir_estado(emissao, "montado")
    dps_el = etree.fromstring(emissao.xml_dps.encode("utf-8"))
    assinar_dps(dps_el, private_key, cert)
    emissao.xml_assinado = etree.tostring(dps_el, xml_declaration=True, encoding="UTF-8", pretty_print=False).decode()
    emissao.estado = "assinado"
    emissao.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    return emissao


# Marca no erro_detalhe de uma falha de REDE (não de uma recusa da Receita):
# a DPS pode ter chegado lá mesmo sem resposta. Na próxima tentativa, antes
# de reenviar, consulta se a nota já existe — reenviar às cegas daria
# "DPS duplicada" e a nota ficaria presa em erro pra sempre.
MARCA_FALHA_COMUNICACAO = "[comunicacao]"


def _id_dps(emissao: Emissao) -> str | None:
    m = re.search(r'Id="(DPS\d+)"', emissao.xml_assinado or "")
    return m.group(1) if m else None


def _confirmar_com_resposta(db: Session, emissao: Emissao, resposta, cliente: ClienteSefin, buscar_xml: bool = False) -> Emissao:
    emissao.chave_acesso = (resposta.dados or {}).get("chaveAcesso")
    nfse_xml = ClienteSefin.extrair_nfse_xml(resposta)
    if nfse_xml is None and buscar_xml and emissao.chave_acesso:
        try:
            nfse_xml = ClienteSefin.extrair_nfse_xml(cliente.consultar_nfse(emissao.chave_acesso))
        except requests.RequestException:
            nfse_xml = None
    emissao.xml_resposta = nfse_xml.decode("utf-8") if nfse_xml else None
    emissao.estado = "confirmado"
    emissao.erro_detalhe = None
    emissao.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    # Tomador com "guardar no Google Drive" entre as formas de envio.
    from app.services import drive

    drive.guardar_se_configurado(db, emissao)
    # Nota acima do limite do plano (com o aceite da pessoa): entra na próxima fatura.
    try:
        from app.services import planos

        planos.cobrar_excedente(db, emissao.prestador_id)
    except Exception:  # noqa: BLE001 — cobrança nunca atrapalha a nota já autorizada
        logger.exception("Falha ao registrar a nota excedente da emissão %s", emissao.id)
    return emissao


_DICAS_DE_RECUSA = {
    # ISS retido (2026.10.7 — regras do Anexo VI, raio-x seção 15)
    "E0655": "A prefeitura do serviço não prevê retenção de ISS pra este tomador ou serviço. Se o tomador não retém, desmarque “retém o ISS” no cadastro dele e gere a nota de novo.",
    "E0621": "Nota com ISS retido precisa da alíquota do ISS (de 1,8% a 5%). Informe na nota ou em Empresa › Emitente e gere de novo.",
    "E0628": "Nota com ISS retido precisa da alíquota do ISS (de 1,8% a 5%). Informe na nota ou em Empresa › Emitente e gere de novo.",
    "E0583": "MEI não tem ISS retido. Desmarque a retenção no cadastro do tomador e gere a nota de novo.",
    "E0160": "O regime cadastrado na empresa não bate com o da Receita (MEI, Simples ou não optante) no mês da nota. Confira em Empresa › Emitente.",
    "E0240": "Clique em “Corrigir e reenviar”: a Ana procura o CEP certo pelo endereço e manda de novo.",
    "E0008": "A hora da nota ficou à frente do relógio da Receita. Clique em “Corrigir e reenviar”: a Ana acerta a hora e manda de novo.",
}
# Recusas que se resolvem remontando a nota com a hora de agora.
_RECUSAS_DE_HORA = ("E0008",)


def erro_legivel(resposta) -> str:
    """Recusa da Sefin em texto de gente: "E0008 — descrição", e o que
    fazer quando a gente sabe. Antes ia o dicionário cru da resposta."""
    dados = resposta.dados if isinstance(resposta.dados, dict) else None
    erros = (dados or {}).get("erros") or (dados or {}).get("Erros") or []
    linhas = []
    for erro in erros if isinstance(erros, list) else []:
        if not isinstance(erro, dict):
            continue
        codigo = str(erro.get("Codigo") or erro.get("codigo") or "").strip()
        descricao = str(erro.get("Descricao") or erro.get("descricao") or "").strip()
        complemento = str(erro.get("Complemento") or erro.get("complemento") or "").strip()
        texto = " — ".join(p for p in (codigo, descricao) if p)
        if complemento:
            texto += f" ({complemento})"
        if codigo in _DICAS_DE_RECUSA:
            texto += f" {_DICAS_DE_RECUSA[codigo]}"
        if texto:
            linhas.append(texto)
    if linhas:
        return "A Receita recusou a nota: " + " | ".join(linhas)
    return str(resposta.dados or resposta.texto_bruto or f"HTTP {resposta.status_code}")


def motivo_da_recusa(texto: str | None) -> str | None:
    """`erro_detalhe` pronto pra tela. As recusas gravadas antes de
    05/10/2026 ficaram como o dicionário cru da resposta — viram frase."""
    if not texto:
        return None
    if texto.lstrip().startswith("{"):
        import ast
        from types import SimpleNamespace

        try:
            dados = ast.literal_eval(texto)
        except (ValueError, SyntaxError):
            return texto
        if isinstance(dados, dict):
            return erro_legivel(SimpleNamespace(dados=dados, texto_bruto=texto, status_code=0))
    # Dica gravada antes do botão "Corrigir e reenviar" existir.
    return texto.replace(
        "Gere a nota de novo (marcando pra substituir esta) e envie.",
        "Clique em “Corrigir e reenviar”: a Ana acerta a hora e manda de novo.",
    )


def submeter(db: Session, emissao: Emissao, cliente: ClienteSefin) -> Emissao:
    """assinado -> submetido -> confirmado, ou -> erro (retentável: chamar
    de novo a partir de 'erro' tenta de novo, não precisa remontar/reassinar
    — o XML assinado não muda).

    Queda de rede no meio (timeout, conexão) não vira 500 nem perde o estado:
    a nota vai pra 'erro' com MARCA_FALHA_COMUNICACAO, e a próxima tentativa
    primeiro pergunta à Receita se a DPS já virou nota (recupera a chave)."""
    _exigir_estado(emissao, "assinado", "erro")
    # Última trava do ambiente de teste da plataforma: nota de produção não sai daqui.
    from app.config import get_settings

    if get_settings().ambiente_teste and str((emissao.tomador_snapshot or {}).get("tpAmb") or "1") != "2":
        raise SoHomologacaoError()
    tentativa_apos_queda = emissao.estado == "erro" and (emissao.erro_detalhe or "").startswith(MARCA_FALHA_COMUNICACAO)
    if not tentativa_apos_queda:
        # Limite de notas do plano (só trava com BLOQUEIO_ATIVO). Depois de
        # uma queda de rede a nota pode já existir na Receita: aí passa.
        from app.services import planos

        try:
            planos.conferir(db, emissao.prestador_id)
        except planos.LimiteDeNotasError as exc:
            raise LimiteDoPlanoError(str(exc)) from exc
    emissao.estado = "submetido"
    emissao.erro_detalhe = None
    db.flush()  # marca a tentativa ANTES do request de rede — se cair no meio, fica visível como 'submetido', não como 'assinado' silenciosamente reenviável sem rastro

    try:
        if tentativa_apos_queda and (id_dps := _id_dps(emissao)):
            existente = cliente.consultar_dps(id_dps)
            if existente.ok and (existente.dados or {}).get("chaveAcesso"):
                return _confirmar_com_resposta(db, emissao, existente, cliente, buscar_xml=True)
        resposta = cliente.submeter_dps(emissao.xml_assinado.encode("utf-8"))
    except requests.RequestException as exc:
        emissao.estado = "erro"
        emissao.erro_detalhe = (
            f"{MARCA_FALHA_COMUNICACAO} Não deu pra falar com a Receita agora ({type(exc).__name__}). "
            "A nota pode ter chegado lá — ao tentar de novo, a Ana confere antes de reenviar."
        )
        db.flush()
        return emissao

    if not resposta.ok:
        emissao.estado = "erro"
        emissao.erro_detalhe = erro_legivel(resposta)
        db.flush()
        return emissao

    return _confirmar_com_resposta(db, emissao, resposta, cliente)


def cancelar(
    db: Session, emissao: Emissao, private_key, cert, cliente: ClienteSefin,
    *, cnpj_autor: str, cmotivo: str, xmotivo: str,
) -> Emissao:
    """confirmado -> cancelada. Usa a mesma receita (app.fiscal.eventos) já
    validada em produção em integracao/cancelar_nfse.py."""
    _exigir_estado(emissao, "confirmado")
    if not emissao.chave_acesso:
        raise ValueError("Emissao confirmada sem chave_acesso — dado inconsistente, não dá pra cancelar")

    evento_el = montar_evento_cancelamento(emissao.chave_acesso, cnpj_autor, cmotivo, xmotivo, emissao.tomador_snapshot["tpAmb"])
    assinar_evento(evento_el, private_key, cert)
    xml_evento = etree.tostring(evento_el, xml_declaration=True, encoding="UTF-8", pretty_print=False)

    resposta = cliente.enviar_evento_cancelamento(emissao.chave_acesso, xml_evento)
    if not resposta.ok:
        emissao.erro_detalhe = str(resposta.dados or resposta.texto_bruto or f"HTTP {resposta.status_code}")
        db.flush()
        raise RuntimeError(f"Cancelamento recusado pela Sefin: {emissao.erro_detalhe}")

    emissao.estado = "cancelada"
    emissao.erro_detalhe = None
    emissao.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    return emissao
