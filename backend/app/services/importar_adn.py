"""Importar do Emissor Nacional as notas já emitidas (28/09/2026).

"Você consegue importar do emissor nacional?" — sim: o Ambiente de Dados
Nacional (ADN) tem a distribuição de documentos pro contribuinte, lida com o
próprio certificado da empresa, por NSU (número sequencial). Vêm todas as
NFS-e em que o CNPJ aparece — as que ele emitiu (por qualquer emissor: o
portal, o MandaNotas, a Ana) e as que recebeu — e os eventos
(cancelamentos).

Fluxo em duas etapas, porque quem decide pra qual tomador cada nota vai é a
pessoa:

1. `buscar` — lê páginas do ADN a partir do último NSU importado e guarda
   as notas emitidas pela empresa num cache em memória (o app roda num
   processo só). Devolve a prévia agrupada por tomador, com uma sugestão
   (tomador já cadastrado, nota avulsa de marketplace pelo intermediário, ou
   tomador novo).
2. `importar` — grava as notas escolhidas como emissões confirmadas
   (`origem='importada'`), criando tomadores/vínculos novos quando pedido.
   Notas importadas já foram entregues por fora: entram com o envio ao
   fornecedor marcado, pra não virar pendência.
"""
import base64
import datetime
import difflib
import gzip
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import requests
from lxml import etree
from sqlalchemy.orm import Session

from app.fiscal.cliente_sefin import ADN_BASES, ClienteSefin
from app.services.vinculos import apelido_livre as _apelido_livre, criar_tomador_interno  # noqa: F401
from app.models import Emissao, Envio, Prestador, PrestadorTomador, Tomador

PAGINAS_POR_CHAMADA = 15
PAUSA_S = 0.3
CACHE_TTL_S = 3600


class ImportacaoAdnError(Exception):
    pass


# --- leitura do XML -----------------------------------------------------


def _local(el) -> str:
    return etree.QName(el).localname


def _filho(el, *caminho):
    atual = el
    for nome in caminho:
        if atual is None:
            return None
        atual = next((c for c in atual if isinstance(c.tag, str) and _local(c) == nome), None)
    return atual


def _texto(el, *caminho) -> str | None:
    alvo = _filho(el, *caminho)
    return alvo.text.strip() if alvo is not None and alvo.text else None


def _achar(raiz, nome):
    return next((e for e in raiz.iter() if isinstance(e.tag, str) and _local(e) == nome), None)


def ler_nfse(xml: bytes) -> dict | None:
    """Campos que a importação usa, de um XML de NFS-e do padrão nacional.
    None se não for uma NFS-e."""
    try:
        raiz = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        return None
    inf = _achar(raiz, "infNFSe")
    dps = _achar(raiz, "infDPS")
    if inf is None or dps is None:
        return None
    chave = re.sub(r"\D", "", inf.get("Id") or "")
    toma = _filho(dps, "toma")
    tipo_doc, documento = None, None
    if toma is not None:
        for tipo in ("CNPJ", "CPF", "NIF"):
            valor = _texto(toma, tipo)
            if valor:
                tipo_doc, documento = tipo, valor
                break
    end_nac = _filho(toma, "end", "endNac") if toma is not None else None
    end_ext = _filho(toma, "end", "endExt") if toma is not None else None
    end = _filho(toma, "end") if toma is not None else None
    interm = _filho(dps, "interm")
    cserv = _filho(dps, "serv", "cServ")
    valor = _texto(dps, "valores", "vServPrest", "vServ") or _texto(inf, "valores", "vLiq") or "0"
    dcompet = _texto(dps, "dCompet") or (_texto(dps, "dhEmi") or "")[:10]
    return {
        "chave": chave or None,
        "n_nfse": _texto(inf, "nNFSe"),
        "dh_proc": _texto(inf, "dhProc"),
        "tp_amb": _texto(dps, "tpAmb"),
        "dh_emi": _texto(dps, "dhEmi"),
        "serie": (_texto(dps, "serie") or "1").lstrip("0") or "0",
        "n_dps": int(_texto(dps, "nDPS") or 0),
        "dcompet": dcompet,
        "prestador_cnpj": _texto(dps, "prest", "CNPJ") or _texto(inf, "emit", "CNPJ"),
        "toma": {
            "tipo": tipo_doc, "documento": documento, "nome": _texto(toma, "xNome") if toma is not None else None,
            "email": _texto(toma, "email") if toma is not None else None,
            "cMun": _texto(end_nac, "cMun") if end_nac is not None else None,
            "CEP": _texto(end_nac, "CEP") if end_nac is not None else None,
            "pais": _texto(end_ext, "cPais") if end_ext is not None else "BR",
            "xLgr": _texto(end, "xLgr") if end is not None else None,
            "nro": _texto(end, "nro") if end is not None else None,
            "xCpl": _texto(end, "xCpl") if end is not None else None,
            "xBairro": _texto(end, "xBairro") if end is not None else None,
        },
        "interm": {"CNPJ": _texto(interm, "CNPJ"), "xNome": _texto(interm, "xNome")} if interm is not None else None,
        "cLocPrestacao": _texto(dps, "serv", "locPrest", "cLocPrestacao"),
        "cTribNac": _texto(cserv, "cTribNac") if cserv is not None else None,
        "cTribMun": _texto(cserv, "cTribMun") if cserv is not None else None,
        "cNBS": _texto(cserv, "cNBS") if cserv is not None else None,
        "descricao": _texto(cserv, "xDescServ") if cserv is not None else None,
        "valor": str(Decimal(valor)),
    }


def ler_cancelamento(xml: bytes) -> str | None:
    """Chave da NFS-e cancelada (ou substituída), se o XML for um evento
    desses."""
    try:
        raiz = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        return None
    if not any(isinstance(e.tag, str) and _local(e) in ("e101101", "e105102") for e in raiz.iter()):
        return None
    ch = _achar(raiz, "chNFSe")
    return re.sub(r"\D", "", ch.text) if ch is not None and ch.text else None


# --- conversa com o ADN -------------------------------------------------


def _chave_ci(d: dict, *nomes):
    baixo = {k.lower(): v for k, v in d.items()} if isinstance(d, dict) else {}
    for n in nomes:
        if n.lower() in baixo:
            return baixo[n.lower()]
    return None


def _decodificar(arquivo: str) -> bytes:
    bruto = base64.b64decode(arquivo)
    return gzip.decompress(bruto) if bruto[:2] == b"\x1f\x8b" else bruto


def ler_pagina(cliente: ClienteSefin, cnpj: str, nsu: int) -> tuple[list[dict], int | None]:
    """Uma página da distribuição: [(nsu, tipo, xml)], maior NSU visto.
    Lista vazia = não há mais documentos."""
    base = ADN_BASES[cliente.tpAmb]
    ultimo_erro = None
    for url in (f"{base}/contribuintes/DFe/{nsu}", f"{base}/DFe/{nsu}"):
        try:
            resp = cliente._get(f"{url}?cnpjConsulta={cnpj}&lote=true", headers={"Accept": "application/json"})
        except requests.RequestException as exc:
            raise ImportacaoAdnError("Não consegui falar com o Emissor Nacional agora. Tente de novo em alguns minutos.") from exc
        if resp.status_code == 404 and "json" not in (resp.headers.get("content-type") or ""):
            ultimo_erro = resp.status_code
            continue
        try:
            dados = resp.json()
        except ValueError:
            dados = None
        if resp.status_code in (401, 403):
            raise ImportacaoAdnError("O Emissor Nacional recusou o certificado. Confira se o certificado carregado é o desta empresa e está válido.")
        if resp.status_code == 429:
            raise ImportacaoAdnError("O Emissor Nacional pediu pra esperar um pouco (muitas consultas). Tente de novo em alguns minutos.")
        if dados is None:
            ultimo_erro = resp.status_code
            continue
        status = str(_chave_ci(dados, "StatusProcessamento") or "")
        lote = _chave_ci(dados, "LoteDFe") or []
        if "NENHUM" in status.upper() or not lote:
            return [], None
        docs, maior = [], None
        for item in lote:
            arquivo = _chave_ci(item, "ArquivoXml")
            n = _chave_ci(item, "NSU")
            if not arquivo or n is None:
                continue
            n = int(n)
            maior = n if maior is None else max(maior, n)
            docs.append({"nsu": n, "tipo": str(_chave_ci(item, "TipoDocumento") or ""), "xml": _decodificar(arquivo)})
        return docs, maior
    raise ImportacaoAdnError(f"O Emissor Nacional respondeu de um jeito inesperado (HTTP {ultimo_erro}). Tente de novo mais tarde.")


# --- cache da prévia ------------------------------------------------------


@dataclass
class _Busca:
    nsu: int
    notas: dict[str, dict] = field(default_factory=dict)  # chave -> nota lida (+ "xml")
    canceladas: set[str] = field(default_factory=set)
    recebidas: int = 0
    terminou: bool = False
    # Só notas com competência a partir daqui (01/10/2026: histórico longo
    # pesa e o controle começa no ano atual).
    desde: str | None = None
    atualizado: float = field(default_factory=time.time)


_buscas: dict[uuid.UUID, _Busca] = {}
_lock = threading.Lock()


def _busca(prestador_id: uuid.UUID, nsu_inicial: int, recomecar: bool, desde: str | None = None) -> _Busca:
    with _lock:
        for chave in [k for k, v in _buscas.items() if time.time() - v.atualizado > CACHE_TTL_S]:
            _buscas.pop(chave, None)
        b = _buscas.get(prestador_id)
        if b is None or recomecar:
            b = _Busca(nsu=nsu_inicial, desde=desde)
            _buscas[prestador_id] = b
        elif desde is not None:
            b.desde = desde
        return b


def buscar(
    db: Session, prestador: Prestador, cliente: ClienteSefin, *, recomecar: bool = False, desde_inicio: bool = False,
    ler_pagina_fn=None, desde: str | None = None,
) -> dict:
    """Lê mais algumas páginas do ADN e devolve a prévia até aqui."""
    inicio = 0 if desde_inicio else (prestador.adn_ultimo_nsu or 0)
    b = _busca(prestador.id, inicio, recomecar or desde_inicio, desde)
    cnpj = re.sub(r"\D", "", prestador.cpf_cnpj)
    for _ in range(PAGINAS_POR_CHAMADA):
        if b.terminou:
            break
        docs, maior = (ler_pagina_fn or ler_pagina)(cliente, cnpj, b.nsu)
        if not docs:
            b.terminou = True
            break
        for doc in docs:
            chave_cancelada = ler_cancelamento(doc["xml"])
            if chave_cancelada:
                b.canceladas.add(chave_cancelada)
                continue
            nota = ler_nfse(doc["xml"])
            if nota is None:
                continue
            if re.sub(r"\D", "", nota["prestador_cnpj"] or "") != cnpj:
                b.recebidas += 1  # nota que a empresa RECEBEU (serviço comprado)
                continue
            if nota["tp_amb"] not in (None, "1"):
                continue
            if b.desde and (nota["dcompet"] or "")[:7] < b.desde:
                continue
            nota["xml"] = doc["xml"]
            nota["nsu"] = doc["nsu"]
            b.notas[nota["chave"]] = nota
        b.nsu = maior if maior is not None and maior > b.nsu else b.nsu + len(docs)
        b.atualizado = time.time()
        time.sleep(PAUSA_S)
    return previa(db, prestador, b)


def _vinculos_por_documento(db: Session) -> dict[str, list[PrestadorTomador]]:
    mapa: dict[str, list[PrestadorTomador]] = {}
    for v in db.query(PrestadorTomador).join(Tomador).order_by(PrestadorTomador.apelido):
        mapa.setdefault(v.tomador.cnpj, []).append(v)
        # Tomador de fora do Brasil: a nota dele vem com o NIF no lugar do CNPJ.
        if v.tomador.de_fora and (v.tomador.nif or "").strip():
            mapa.setdefault(v.tomador.nif.strip(), []).append(v)
    return mapa


def previa(db: Session, prestador: Prestador, b: _Busca | None = None) -> dict:
    b = b or _buscas.get(prestador.id)
    if b is None:
        return {"terminou": False, "nsu": prestador.adn_ultimo_nsu or 0, "total_notas": 0, "ja_importadas": 0, "recebidas": 0, "grupos": []}
    existentes = {
        c for (c,) in db.query(Emissao.chave_acesso).filter(Emissao.chave_acesso.in_(list(b.notas) or ["-"]))
    }
    por_doc = _vinculos_por_documento(db)
    grupos: dict[str, dict] = {}
    for nota in b.notas.values():
        if nota["chave"] in existentes:
            continue
        toma = nota["toma"]
        doc = toma["documento"] or "sem-documento"
        g = grupos.setdefault(doc, {
            "documento": doc, "tipo": toma["tipo"], "nome": toma["nome"] or "(sem nome)", "quantidade": 0, "total": 0.0,
            "canceladas": 0, "competencias": set(), "descricao_exemplo": nota["descricao"], "intermediario": None,
            "sugestao": "novo", "vinculo_id": None,
        })
        g["quantidade"] += 1
        g["total"] += float(nota["valor"])
        g["canceladas"] += 1 if nota["chave"] in b.canceladas else 0
        g["competencias"].add(nota["dcompet"][:7])
        interm = (nota.get("interm") or {}).get("CNPJ")
        if interm:
            g["intermediario"] = (nota["interm"] or {}).get("xNome") or interm
            if interm in por_doc and g["sugestao"] == "novo":
                g["sugestao"], g["vinculo_id"] = "avulsa", por_doc[interm][0].id
    for g in grupos.values():
        if g["documento"] in por_doc:
            g["sugestao"], g["vinculo_id"] = "vinculo", por_doc[g["documento"]][0].id
        g["competencias"] = sorted(g["competencias"])
        g["total"] = round(g["total"], 2)
    lista = sorted(grupos.values(), key=lambda g: (-g["total"]))
    return {
        "terminou": b.terminou, "nsu": b.nsu, "total_notas": sum(g["quantidade"] for g in lista),
        "ja_importadas": len(existentes), "recebidas": b.recebidas, "grupos": lista,
    }


# --- gravação ---------------------------------------------------------------


def _novo_vinculo(db: Session, prestador: Prestador, nota: dict) -> PrestadorTomador:
    toma = nota["toma"]
    if toma["tipo"] == "CNPJ" and toma["documento"]:
        tomador = db.query(Tomador).filter_by(cnpj=toma["documento"]).one_or_none()
        if tomador is None:
            tomador = Tomador(
                id=uuid.uuid4(), cnpj=toma["documento"], razao_social=(toma["nome"] or toma["documento"])[:200],
                cod_municipio=(toma["cMun"] or prestador.cod_municipio)[:7], cep=_corta(toma["CEP"], 8),
                logradouro=_corta(toma["xLgr"], 200), numero=_corta(toma["nro"], 20), complemento=_corta(toma["xCpl"], 100),
                bairro=_corta(toma["xBairro"], 100), status="aprovado",
            )
            db.add(tomador)
            db.flush()
        sem_nota = False
    else:
        tomador = criar_tomador_interno(db, toma["nome"] or "Tomador", toma["cMun"] or prestador.cod_municipio)
        if toma["tipo"] == "NIF" and toma["documento"] and (toma.get("pais") or "BR").upper() != "BR":
            # Empresa de fora: já fica identificada (país + NIF da nota) — a
            # pessoa só precisa ligar a emissão pra gerar as próximas.
            tomador.nif, tomador.pais = toma["documento"][:40], str(toma["pais"]).upper()[:2]
            db.flush()
        sem_nota = True
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador.id, tomador_id=tomador.id,
        apelido=_apelido_livre(db, prestador.id, toma["nome"] or "Tomador"),
        cod_local_prestacao=(nota["cLocPrestacao"] or prestador.cod_municipio)[:7],
        cod_trib_nacional=(nota["cTribNac"] or "000000")[:6], cod_trib_municipal=_corta(nota["cTribMun"], 5),
        cod_nbs=_corta(nota["cNBS"], 12), template_descricao=nota["descricao"] or "Serviço prestado",
        serie="1", ativo=True, sem_nota=sem_nota,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def _parecido(a: str | None, b: str | None) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def importar(db: Session, prestador: Prestador, mapeamento: list[dict], *, ajustar_modelos: bool = False) -> dict:
    """`mapeamento`: [{documento, acao: vinculo|avulsa|novo|ignorar, vinculo_id?}].

    `ajustar_modelos` ("Importar emissor", 05/10/2026): os tomadores novos
    já saem prontos pra próxima nota — códigos e descrição da nota mais
    recente, com o mês/ano trocado por campo automático (o mesmo que o
    cadastro assistido faz). O resultado traz `tomadores`: os que foram
    criados agora e o que ainda falta em cada um."""
    b = _buscas.get(prestador.id)
    if b is None or not b.notas:
        raise ImportacaoAdnError("Busque as notas no Emissor Nacional antes de importar (a prévia expirou).")
    regras = {m["documento"]: m for m in mapeamento}
    existentes = {c for (c,) in db.query(Emissao.chave_acesso).filter(Emissao.chave_acesso.in_(list(b.notas)))}
    ocupados: set[tuple] = {
        (v, c, d or "") for v, c, d in db.query(Emissao.prestador_tomador_id, Emissao.competencia, Emissao.tomador_documento)
        .filter(Emissao.estado != "cancelada")
    }
    numeros = {(s, n) for s, n in db.query(Emissao.serie, Emissao.n_dps).filter(Emissao.n_dps.isnot(None))}
    por_doc = _vinculos_por_documento(db)
    novos: dict[str, PrestadorTomador] = {}
    notas_por_vinculo: dict[uuid.UUID, int] = {}
    importadas, puladas, vinculos_criados = 0, [], 0
    agora = datetime.datetime.now(datetime.timezone.utc)

    for nota in sorted(b.notas.values(), key=lambda n: (n["dh_emi"] or "", n["n_dps"])):
        if nota["chave"] in existentes:
            continue
        doc = nota["toma"]["documento"] or "sem-documento"
        regra = regras.get(doc)
        if regra is None or regra.get("acao") == "ignorar":
            continue
        acao = regra["acao"]
        competencia = (nota["dcompet"] or "")[:7]
        if not re.fullmatch(r"\d{4}-\d{2}", competencia):
            puladas.append({"chave": nota["chave"], "motivo": "Nota sem data de competência."})
            continue
        # Número de DPS já usado aqui (ex.: por uma nota de teste em
        # homologação): a nota entra sem o número — a chave de acesso
        # continua identificando ela.
        n_dps = None if (nota["serie"], nota["n_dps"]) in numeros else nota["n_dps"]
        cancelada = nota["chave"] in b.canceladas
        documento_avulso = None
        if acao == "novo":
            if doc not in novos:
                novos[doc] = _novo_vinculo(db, prestador, nota)
                vinculos_criados += 1
            candidatos = [novos[doc]]
        else:
            vinculo = db.get(PrestadorTomador, uuid.UUID(str(regra.get("vinculo_id"))))
            if vinculo is None:
                puladas.append({"chave": nota["chave"], "motivo": "Tomador escolhido não existe."})
                continue
            if acao == "avulsa":
                documento_avulso = doc
                candidatos = [vinculo]
            else:
                # Mesmo CNPJ faturado em programas diferentes (ex.: AWIN e
                # AWIN Rchlo): vai pro vínculo livre no mês com a descrição
                # mais parecida.
                do_vinculo = vinculo.tomador.nif.strip() if vinculo.tomador.de_fora and vinculo.tomador.nif else vinculo.tomador.cnpj
                irmaos = por_doc.get(do_vinculo, [vinculo]) if do_vinculo == doc else [vinculo]
                candidatos = sorted(
                    irmaos, key=lambda v: (-round(_parecido(v.template_descricao, nota["descricao"]), 2), v.id != vinculo.id)
                )
        # Prefere o vínculo ainda sem nota no mês; se todos já têm (histórico
        # com duas notas no mês), vai pro mais parecido mesmo — importadas
        # não entram na regra de uma nota por mês.
        destino = next(
            (v for v in candidatos if cancelada or (v.id, competencia, documento_avulso or "") not in ocupados), candidatos[0]
        )
        toma = nota["toma"]
        snapshot = {
            "razao_social": toma["nome"], "cnpj": toma["documento"], "tipo_documento": toma["tipo"],
            "endereco": {k: toma[k] for k in ("cMun", "CEP", "xLgr", "nro", "xCpl", "xBairro")},
            "email": toma["email"], "pais": toma["pais"], "apelido": destino.apelido,
            "descricao_renderizada": nota["descricao"],
            "codigo_servico_usado": {
                "cLocPrestacao": nota["cLocPrestacao"], "cTribNac": nota["cTribNac"], "cTribMun": nota["cTribMun"], "cNBS": nota["cNBS"],
            },
            "dcompet": nota["dcompet"], "tpAmb": "1", "importada": True, "n_nfse": nota["n_nfse"],
        }
        if documento_avulso:
            snapshot["avulso"] = True
        if nota.get("interm"):
            snapshot["intermediario"] = nota["interm"]
        emitida = _data_hora(nota["dh_emi"]) or agora
        emissao = Emissao(
            id=uuid.uuid4(), prestador_tomador_id=destino.id, prestador_id=prestador.id, competencia=competencia,
            valor=Decimal(nota["valor"]), serie=nota["serie"][:5], n_dps=n_dps, chave_acesso=nota["chave"],
            estado="cancelada" if cancelada else "confirmado", tomador_snapshot=snapshot,
            tomador_documento=documento_avulso, xml_resposta=nota["xml"].decode("utf-8"), origem="importada",
            criado_em=emitida, atualizado_em=emitida,
        )
        db.add(emissao)
        db.flush()
        if not cancelada:
            ocupados.add((destino.id, competencia, documento_avulso or ""))
            db.add(Envio(
                id=uuid.uuid4(), emissao_id=emissao.id, canal="direto_fornecedor", status="enviado", tentativas=1,
                enviado_em=emitida, destino="emitida fora da Ana",
            ))
        numeros.add((nota["serie"], nota["n_dps"]))
        existentes.add(nota["chave"])
        notas_por_vinculo[destino.id] = notas_por_vinculo.get(destino.id, 0) + 1
        importadas += 1

    # Tomador novo que não recebe nota há mais de um mês entra como inativo
    # (histórico), pra não virar pendência "gerar a nota" todo mês.
    if novos:
        ultimas = [n["dcompet"][:7] for n in b.notas.values() if n.get("dcompet")]
        referencia = max(ultimas) if ultimas else None
        for v in novos.values():
            meses = [c for (c,) in db.query(Emissao.competencia).filter(Emissao.prestador_tomador_id == v.id)]
            if referencia and (not meses or _meses_entre(max(meses), referencia) > 1):
                v.ativo = False
    ajustados = _ajustar_modelos(b, novos) if ajustar_modelos else set()
    if b.terminou:
        prestador.adn_ultimo_nsu = max(b.nsu, prestador.adn_ultimo_nsu or 0)
    db.flush()
    return {
        "importadas": importadas, "vinculos_criados": vinculos_criados, "puladas": puladas[:200],
        "tomadores": [_resumo_do_novo(doc, v, notas_por_vinculo.get(v.id, 0), doc in ajustados) for doc, v in novos.items()][:500],
    }


def _ajustar_modelos(b: _Busca, novos: dict[str, PrestadorTomador]) -> set[str]:
    """Configura cada tomador novo (com CNPJ) pela nota mais recente dele:
    códigos do serviço e descrição com o que muda todo mês trocado por campo
    automático. Devolve os documentos em que a descrição foi trocada."""
    from app.services.assistente_tomador import sugerir_modelo  # import tardio: ele importa este módulo

    ajustados: set[str] = set()
    for doc, vinculo in novos.items():
        if vinculo.sem_nota:
            continue
        notas = [n for n in b.notas.values() if (n["toma"]["documento"] or "sem-documento") == doc]
        validas = [n for n in notas if n["chave"] not in b.canceladas] or notas
        if not validas:
            continue
        ultima = max(validas, key=lambda n: (n["dcompet"] or "", n["dh_emi"] or "", n["n_dps"]))
        if ultima["cTribNac"]:
            vinculo.cod_trib_nacional = ultima["cTribNac"][:6]
            vinculo.cod_trib_municipal = _corta(ultima["cTribMun"], 5)
            vinculo.cod_nbs = _corta(ultima["cNBS"], 12)
        if ultima["cLocPrestacao"]:
            vinculo.cod_local_prestacao = ultima["cLocPrestacao"][:7]
        if ultima["descricao"]:
            sugestao = sugerir_modelo(ultima["descricao"])
            if sugestao["modelo"]:
                vinculo.template_descricao = sugestao["modelo"]
                if sugestao["partes"]:
                    ajustados.add(doc)
    return ajustados


def _resumo_do_novo(doc: str, vinculo: PrestadorTomador, notas: int, modelo_ajustado: bool) -> dict:
    """Um tomador criado pela importação, em palavras de tela. `pendencia`:
    o que ainda falta pra gerar a próxima nota dele (None = pronto)."""
    pendencia = None
    if not vinculo.sem_nota and (vinculo.cod_trib_nacional or "000000") == "000000":
        pendencia = "Falta escolher o código do serviço."
    return {
        "id": vinculo.id, "apelido": vinculo.apelido, "documento": None if doc == "sem-documento" else doc,
        "notas": notas, "ativo": bool(vinculo.ativo), "sem_nota": bool(vinculo.sem_nota),
        "modelo_ajustado": modelo_ajustado, "pendencia": pendencia,
    }


def _data_hora(texto: str | None) -> datetime.datetime | None:
    if not texto:
        return None
    try:
        return datetime.datetime.fromisoformat(texto)
    except ValueError:
        return None


def _meses_entre(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def _corta(valor: str | None, tamanho: int) -> str | None:
    return valor[:tamanho] if valor else None


def remover_importadas(db: Session, antes: str) -> dict:
    """Tira as notas importadas com competência antes de `antes` (AAAA-MM)
    e os tomadores que só existiam por causa delas (sem nota, sem pagamento,
    inativos). Notas geradas pela Ana nunca são tocadas."""
    ids = [i for (i,) in db.query(Emissao.id).filter(Emissao.origem == "importada", Emissao.competencia < antes)]
    if ids:
        db.query(Envio).filter(Envio.emissao_id.in_(ids)).delete(synchronize_session=False)
        db.query(Emissao).filter(Emissao.id.in_(ids)).delete(synchronize_session=False)
    from app import eventos

    vinculos = 0
    for v in db.query(PrestadorTomador).filter(PrestadorTomador.ativo.is_(False), PrestadorTomador.excluido_em.is_(None)):
        tem_nota = db.query(Emissao.id).filter(Emissao.prestador_tomador_id == v.id).first()
        # Outro módulo (o financeiro) pode ter dados desse tomador.
        if not tem_nota and not eventos.perguntar("tomador_em_uso", db, vinculo_id=v.id):
            db.delete(v)
            vinculos += 1
    db.flush()
    return {"notas": len(ids), "tomadores": vinculos}
