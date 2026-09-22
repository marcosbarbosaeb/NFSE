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
import hashlib
import uuid
from datetime import datetime, timezone

from lxml import etree
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.fiscal.cliente_sefin import ClienteSefin
from app.fiscal.dps import assinar_dps, montar_dps_xml, montar_id_dps, renderizar_descricao
from app.fiscal.eventos import assinar_evento, montar_evento_cancelamento
from app.models import Emissao, PrestadorTomador

NS = "http://www.sped.fazenda.gov.br/nfse"

ESTADOS_ATIVOS_PARA_IDEMPOTENCIA = "estado != 'cancelada'"  # espelha o índice parcial do Marco 1


class TransicaoInvalidaError(Exception):
    """A Emissao não está no estado que essa transição exige."""

    def __init__(self, esperado: str, atual: str):
        super().__init__(f"esperava estado '{esperado}' (ou compatível), mas emissão está em '{atual}'")
        self.esperado = esperado
        self.atual = atual


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


def buscar_emissao_ativa(db: Session, vinculo_id: uuid.UUID, competencia: str) -> Emissao | None:
    """Emissão ATIVA (não cancelada) pra esse vínculo+competência, se
    existir — mesma regra do índice único parcial
    `uq_emissao_vinculo_competencia_ativa`. Reaproveitada por
    `criar_rascunho` (bloqueia de verdade) e por um endpoint só-leitura que a
    tela de 'Nova emissão' consulta ANTES do usuário tentar submeter, pra
    avisar de duplicata de forma proativa em vez de só depois de um erro
    (pedido do Marcos no Marco 16 — 'o sistema tem que avisar pra não ter
    nota repetida')."""
    return (
        db.query(Emissao)
        .filter(Emissao.prestador_tomador_id == vinculo_id, Emissao.competencia == competencia, Emissao.estado != "cancelada")
        .first()
    )


def criar_rascunho(
    db: Session,
    vinculo: PrestadorTomador,
    *,
    competencia: str,
    valor: float,
    ordem: str | None = None,
    aliq_sn: float | None = None,
    tpAmb: str = "2",
) -> Emissao:
    """rascunho — atribui nDPS, congela o snapshot do tomador+descrição, e
    checa a idempotência mensal ANTES de tentar gravar (o índice único
    parcial é quem garante de verdade; isto aqui só dá um erro mais claro
    no caso comum, em vez de deixar estourar IntegrityError genérico)."""
    ja_existe = buscar_emissao_ativa(db, vinculo.id, competencia)
    if ja_existe is not None:
        raise EmissaoJaExisteError(
            f"Já existe uma emissão ativa para '{vinculo.apelido}' na competência {competencia} "
            f"(id={ja_existe.id}, estado={ja_existe.estado}). Cancele-a antes de criar outra."
        )

    descricao = renderizar_descricao(vinculo.template_descricao, competencia, ordem=ordem)
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
        },
        "ordem": ordem,
        "aliq_sn": aliq_sn,
        "tpAmb": tpAmb,
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
    )
    db.add(emissao)
    db.flush()
    return emissao


def _exigir_estado(emissao: Emissao, *permitidos: str) -> None:
    if emissao.estado not in permitidos:
        raise TransicaoInvalidaError("/".join(permitidos), emissao.estado)


def montar(db: Session, emissao: Emissao) -> Emissao:
    """rascunho -> montado. Usa o snapshot congelado (tomador/descrição),
    não o catálogo ao vivo — é essa a garantia contra edição retroativa."""
    _exigir_estado(emissao, "rascunho")
    prestador = emissao.vinculo.prestador
    snap = emissao.tomador_snapshot

    prest = {
        "CNPJ": prestador.cpf_cnpj, "IM": prestador.inscricao_municipal, "cMun": prestador.cod_municipio,
        "opSimpNac": prestador.op_simples_nacional, "regApTribSN": prestador.regime_apuracao_sn,
        "regEspTrib": prestador.regime_especial_trib,
    }
    toma = {
        "CNPJ": snap["cnpj"], "xNome": snap["razao_social"],
        "cMun": snap["endereco"]["cMun"], "CEP": snap["endereco"]["CEP"],
        "xLgr": snap["endereco"]["xLgr"], "nro": snap["endereco"]["nro"],
        "xCpl": snap["endereco"].get("xCpl"), "xBairro": snap["endereco"]["xBairro"],
    }
    serv = {**snap["codigo_servico_usado"], "descricao": snap["descricao_renderizada"]}

    dps_el = montar_dps_xml(
        prest=prest, toma=toma, serv=serv, serie=emissao.serie, n_dps=emissao.n_dps,
        valor=float(emissao.valor), tpAmb=snap["tpAmb"], aliq_sn=snap["aliq_sn"],
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


def submeter(db: Session, emissao: Emissao, cliente: ClienteSefin) -> Emissao:
    """assinado -> submetido -> confirmado, ou -> erro (retentável: chamar
    de novo a partir de 'erro' tenta de novo, não precisa remontar/reassinar
    — o XML assinado não muda)."""
    _exigir_estado(emissao, "assinado", "erro")
    emissao.estado = "submetido"
    emissao.erro_detalhe = None
    db.flush()  # marca a tentativa ANTES do request de rede — se cair no meio, fica visível como 'submetido', não como 'assinado' silenciosamente reenviável sem rastro

    resposta = cliente.submeter_dps(emissao.xml_assinado.encode("utf-8"))
    if not resposta.ok:
        emissao.estado = "erro"
        emissao.erro_detalhe = str(resposta.dados or resposta.texto_bruto or f"HTTP {resposta.status_code}")
        db.flush()
        return emissao

    emissao.chave_acesso = (resposta.dados or {}).get("chaveAcesso")
    nfse_xml = ClienteSefin.extrair_nfse_xml(resposta)
    emissao.xml_resposta = nfse_xml.decode("utf-8") if nfse_xml else None
    emissao.estado = "confirmado"
    emissao.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    return emissao


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
