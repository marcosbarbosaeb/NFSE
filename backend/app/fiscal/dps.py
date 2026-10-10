"""
Montagem da DPS (Declaração de Prestação de Serviços) — porta de
integracao/build_dps.py para a biblioteca importável do Marco 3.

Diferença deliberada em relação ao original: lá, `build_dps_xml` recebia uma
`fornecedor_key` e ia buscar os dados em FORNECEDORES (dict hardcoded no
próprio arquivo). Aqui, `montar_dps_xml` recebe os dados já prontos (prest/
toma/serv como dicts simples) — é assim que fica "importável" de verdade: o
Marco 6 (motor de emissão) monta esses dicts a partir das linhas reais do
Postgres (Prestador/PrestadorTomador/Tomador, migradas no Marco 1), sem essa
função precisar saber que um banco existe. Os scripts antigos em
integracao/ continuam funcionando exatamente como estão — ninguém mexeu
neles, é o que a Raiana usa hoje pra emitir de verdade.

Nenhuma regra fiscal mudou na tradução: layout do XML, cálculo do Id da DPS,
formatação de valores e a lógica de descrição (inclusive o
`{ordem}`/`dados_bancarios`) são idênticos ao original — conferido por um
teste de equivalência campo-a-campo contra o output de build_dps.py
(backend/tests/test_dps.py).
"""
import datetime

import re

from lxml import etree

from app.fiscal.xmldsig import assinar_elemento
from app.tempo import agora as agora_br, hoje as hoje_br

NS = "http://www.sped.fazenda.gov.br/nfse"
NSMAP = {None: NS}

_MESES_PT = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]


class DescricaoIncompletaError(ValueError):
    """O template de descrição precisa de `ordem` (número da ordem de
    pagamento) e ele não foi informado — mesmo caso que o `ValueError`
    original de build_dps.py, só que com um tipo próprio pra quem for
    tratar isso na camada de API (Marco 5/6) poder distinguir de outros
    ValueError."""


class RegimeNaoInformadoError(DescricaoIncompletaError):
    """A empresa não tem o regime tributário (opção pelo Simples) cadastrado.
    Antes a nota saía com o texto "None" e a Receita recusava; agora para
    antes, com a mesma resposta 422 de "falta dado" (2026.10.7)."""


def renderizar_descricao(template: str, competencia: str, ordem: str | None = None,
                          dados_bancarios: str | None = None) -> str:
    """competencia: 'AAAA-MM'. Substitui os placeholders que os 5
    fornecedores reais usam hoje: {competencia_mm_aaaa}, {mes_nome_upper},
    {ano}, {mes}, {ordem}. Levanta DescricaoIncompletaError se o template
    pede {ordem} e nenhuma foi passada — mesma trava que o original tinha."""
    ano, mes = competencia.split("-")
    if "{ordem}" in template and not ordem:
        raise DescricaoIncompletaError(
            "Template de descrição usa {ordem} mas nenhuma foi informada "
            "(número da ordem de pagamento — obrigatório para AWIN/AWIN Rchlo)."
        )
    # Substituição tolerante (antes era str.format): o modelo é editado pela
    # pessoa, e um "{cliente}" ou "{" solto derrubava a geração com 500.
    # Códigos desconhecidos ficam como estão.
    valores = {
        "competencia_mm_aaaa": f"{mes}/{ano}",
        "mes_nome_upper": _MESES_PT[int(mes)],
        "ano": ano,
        "mes": mes,
        "ordem": ordem or "",
    }
    descricao = re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), template)
    if dados_bancarios:
        # Sem quebra de linha: a API normaliza quebras antes de conferir a
        # assinatura, o que invalida o digest (E0714) — mesma regra do
        # build_dps.py original.
        descricao = descricao + " - " + dados_bancarios
    return descricao


def montar_id_dps(cod_municipio_prestador: str, cnpj_prestador: str, serie: str, n_dps: int) -> str:
    """Id = 'DPS' + cMun(7) + tipoInscFederal(1, sempre '2'=CNPJ) +
    inscFederal(14) + serie(5) + numDPS(15)."""
    return (
        "DPS"
        + cod_municipio_prestador.zfill(7)
        + "2"
        + cnpj_prestador.zfill(14)
        + serie.zfill(5)
        + str(n_dps).zfill(15)
    )


def _el(tag, children=(), attrs=None, text=None):
    e = etree.Element(f"{{{NS}}}{tag}", nsmap=NSMAP)
    if attrs:
        for k, v in attrs.items():
            e.set(k, v)
    if text is not None:
        e.text = text
    for c in children:
        if c is not None:
            e.append(c)
    return e


def _leaf(tag, text):
    e = etree.Element(f"{{{NS}}}{tag}", nsmap=NSMAP)
    e.text = str(text)
    return e


def _vazio(valor) -> bool:
    return valor is None or str(valor).strip() in ("", "None")


def _opcional(tag, valor):
    """Campo opcional: sem valor não vai (antes ia o texto "None" — 2026.10.7)."""
    return None if _vazio(valor) else _leaf(tag, str(valor).strip())


# Situação perante o Simples (opSimpNac): 1 não optante, 2 MEI, 3 ME/EPP.
MEI = "2"
ME_EPP = "3"


def regras_do_regime(prest: dict) -> dict:
    """O que o regime do prestador permite na DPS (Anexo VI da NT 009, lido em
    10/10/2026 — ver claude/raio-x-tecnico.md seção 15):

    - MEI: sem regApTribSN (E0162), regEspTrib sempre 0 (E0174), sem
      pTotTribSN (E0710 — vai indTotTrib=0), sem retenção de ISS (E0583) e sem
      alíquota (E0600).
    - ME/EPP: regApTribSN quando informado; indTotTrib proibido (E0712).
    - Não optante: sem regApTribSN (E0162).
    """
    op = str(prest.get("opSimpNac") or "").strip()
    return {
        "op": op,
        "mei": op == MEI,
        "me_epp": op == ME_EPP,
        "regApTribSN": None if op != ME_EPP or _vazio(prest.get("regApTribSN")) else str(prest["regApTribSN"]).strip(),
        "regEspTrib": "0" if op == MEI or _vazio(prest.get("regEspTrib")) else str(prest["regEspTrib"]).strip(),
    }


def _pessoa(tag: str, dados: dict):
    """<toma>/<interm>: documento (CNPJ, CPF ou NIF), nome e endereço
    nacional quando houver município."""
    if dados.get("CNPJ"):
        doc = _leaf("CNPJ", dados["CNPJ"])
    elif dados.get("CPF"):
        doc = _leaf("CPF", dados["CPF"])
    elif dados.get("NIF"):
        doc = _leaf("NIF", dados["NIF"])
    else:
        # De fora do Brasil e sem número fiscal (08/10/2026): o schema pede o
        # motivo no lugar — "1" dispensado do NIF, "2" o país não exige.
        doc = _leaf("cNaoNIF", dados["cNaoNIF"])
    end = None
    if not dados.get("CNPJ") and not dados.get("CPF") and dados.get("cPais"):
        # Estrangeiro (NIF): endereço no exterior. Só o país é conhecido — o
        # resto vai com "-", do jeito que a Receita já autorizou em notas
        # emitidas pra vendedores de fora (conferido em 05/10/2026).
        end = _el("end", [
            _el("endExt", [
                _leaf("cPais", str(dados["cPais"]).upper()[:2]), _leaf("cEndPost", dados.get("cEndPost") or "-"),
                _leaf("xCidade", dados.get("xCidade") or "-"), _leaf("xEstProvReg", dados.get("xEstProvReg") or "-"),
            ]),
            _leaf("xLgr", dados.get("xLgr") or "-"), _leaf("nro", dados.get("nro") or "-"), _leaf("xBairro", dados.get("xBairro") or "-"),
        ])
    elif dados.get("cMun"):
        filhos = [_el("endNac", [_leaf("cMun", dados["cMun"]), _leaf("CEP", dados["CEP"])]), _leaf("xLgr", dados["xLgr"]), _leaf("nro", dados["nro"])]
        if dados.get("xCpl"):
            filhos.append(_leaf("xCpl", dados["xCpl"]))
        filhos.append(_leaf("xBairro", dados["xBairro"]))
        end = _el("end", filhos)
    return _el(tag, [doc, _leaf("xNome", dados["xNome"]), end])


def montar_dps_xml(
    *,
    prest: dict,
    toma: dict,
    serv: dict,
    serie: str,
    n_dps: int,
    valor: float,
    tpAmb: str = "2",
    aliq_sn: float | None = None,
    dcompet: str | None = None,
    interm: dict | None = None,
    iss_retido: bool = False,
    aliq_iss: float | None = None,
) -> etree._Element:
    """Monta o elemento <DPS> (não assinado).

    prest: {CNPJ, IM, cMun, opSimpNac, regApTribSN, regEspTrib} — só isso
        vai pro XML; nome/endereço do prestador NÃO são enviados de
        propósito (a Sefin preenche a partir do cadastro/CNC e REJEITA se
        vierem na DPS — erro E0121, descoberto em produção 09/09/2026).
    toma: {CNPJ | CPF | NIF, xNome, cMun?, CEP, xLgr, nro, xCpl?, xBairro}.
    serv: {cLocPrestacao, cTribNac, cTribMun, descricao} — `descricao` já
        deve vir renderizada (ver `renderizar_descricao` acima); esta
        função não sabe nada sobre templates/placeholders.
    tpAmb: '1' produção, '2' homologação.
    aliq_sn: alíquota do Simples Nacional em % (-> pTotTribSN). None ->
        indTotTrib=0 (mesma regra do original — Marcos ajusta manualmente
        todo mês).
    dcompet: 'AAAA-MM-DD'; None = hoje.
    iss_retido / aliq_iss: ISS retido pelo tomador e a alíquota do ISS (%) que
        vai junto quando a regra exige (ver `regras_do_regime` e abaixo).
    """
    dCompet = dcompet or hoje_br().isoformat()
    cnpj_prest = prest["CNPJ"]

    # Hora de Brasília (-03:00), nunca a do servidor (UTC): a Sefin compara o
    # dhEmi com o relógio dela SEM converter o fuso — "12:15+00:00" era lido
    # como 12:15 de Brasília e a nota enviada na hora era recusada (E0008,
    # "data de emissão posterior à do processamento", 05/10/2026). Dois
    # minutos de folga cobrem diferença de relógio entre os servidores.
    now = agora_br() - datetime.timedelta(minutes=2)
    dhEmi = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    dhEmi = dhEmi[:-2] + ":" + dhEmi[-2:]

    id_dps = montar_id_dps(prest["cMun"], cnpj_prest, serie, n_dps)

    end_nac_prest = _el("endNac", [_leaf("cMun", prest["cMun"]), _leaf("CEP", prest.get("CEP", ""))])
    regime = regras_do_regime(prest)
    if not regime["op"]:
        raise RegimeNaoInformadoError("Informe o regime tributário da empresa (Simples Nacional, MEI...) em Empresa antes de gerar a nota.")
    regTrib = _el("regTrib", [
        _leaf("opSimpNac", regime["op"]),
        _opcional("regApTribSN", regime["regApTribSN"]),
        _leaf("regEspTrib", regime["regEspTrib"]),
    ])
    prest_el = _el("prest", [
        _leaf("CNPJ", cnpj_prest),
        _opcional("IM", prest.get("IM")),
        regTrib,
    ])

    # Tomador: CNPJ (o caso de sempre), CPF ou NIF (estrangeiro) — os dois
    # últimos entraram com o relatório da Shopee (28/09/2026), onde a nota
    # vai pra cada vendedor. O endereço do tomador é opcional na DPS: sem
    # cMun (endereço não reconhecido / estrangeiro) o <end> não é enviado.
    toma_el = _pessoa("toma", toma)
    # Intermediário (29/09/2026): nas notas pra vendedores da Shopee, o
    # marketplace pode ser declarado como intermediário do serviço.
    interm_el = _pessoa("interm", interm) if interm else None

    locPrest = _el("locPrest", [_leaf("cLocPrestacao", serv["cLocPrestacao"])])
    # cTribMun é opcional (antes ia "None" no XML quando vazio); cNBS
    # (Nomenclatura Brasileira de Serviços, 9 dígitos) entrou com a reforma
    # tributária.
    cnbs = "".join(c for c in str(serv.get("cNBS") or "") if c.isdigit())
    cServ = _el("cServ", [
        _leaf("cTribNac", serv["cTribNac"]),
        _leaf("cTribMun", serv["cTribMun"]) if serv.get("cTribMun") else None,
        _leaf("xDescServ", serv["descricao"]),
        _leaf("cNBS", cnbs) if len(cnbs) == 9 else None,
    ])
    # Tomador no exterior: o grupo de comércio exterior é obrigatório. O
    # serviço é prestado daqui, em reais, sem vínculo nem benefício — os
    # mesmos valores das notas pra vendedores estrangeiros já autorizadas
    # (o ISS continua tributável aqui: tribISSQN=1).
    com_ext = None
    if (toma.get("NIF") or toma.get("cNaoNIF")) and toma.get("cPais"):
        com_ext = _el("comExt", [
            _leaf("mdPrestacao", "1"), _leaf("vincPrest", "0"), _leaf("tpMoeda", "986"), _leaf("vServMoeda", f"{valor:.2f}"),
            _leaf("mecAFComexP", "01"), _leaf("mecAFComexT", "01"), _leaf("movTempBens", "1"), _leaf("mdic", "0"),
        ])
    serv_el = _el("serv", [locPrest, cServ, com_ext])

    vServPrest = _el("vServPrest", [_leaf("vServ", f"{valor:.2f}")])
    # ISS retido pelo tomador (2026.10.7): tpRetISSQN=2. Nunca pra MEI (E0583).
    # ME/EPP apurando pelo Simples (regApTribSN=1): com retenção a alíquota do
    # ISS é obrigatória (E0621/E0628, de 1,8% a 5%); sem retenção é proibida
    # (E0625/E0631). Fora do Simples pro ISS (2 ou 3), em cidade com convênio
    # ativo, a alíquota é proibida (E0635) — a Sefin usa a do município.
    retido = bool(iss_retido) and not regime["mei"]
    pAliq = None
    if retido and regime["me_epp"] and regime["regApTribSN"] in (None, "1") and aliq_iss is not None:
        pAliq = _leaf("pAliq", f"{float(aliq_iss):.2f}")
    # Ordem do esquema 1.00: pAliq ANTES de tpRetISSQN (no 1.01 a ordem inverte).
    tribMun = _el("tribMun", [_leaf("tribISSQN", "1"), pAliq, _leaf("tpRetISSQN", "2" if retido else "1")])
    if aliq_sn is not None and not regime["mei"]:
        totTrib = _el("totTrib", [_leaf("pTotTribSN", f"{aliq_sn:.2f}")])
    else:
        # MEI nunca manda pTotTribSN (E0710): vai "não informo" (indTotTrib=0).
        totTrib = _el("totTrib", [_leaf("indTotTrib", "0")])
    trib = _el("trib", [tribMun, totTrib])
    valores_el = _el("valores", [vServPrest, trib])

    infDPS = _el(
        "infDPS",
        [
            _leaf("tpAmb", tpAmb),
            _leaf("dhEmi", dhEmi),
            _leaf("verAplic", "ClaudeNFSe-0.1"),
            _leaf("serie", serie),
            _leaf("nDPS", str(n_dps)),
            _leaf("dCompet", dCompet),
            _leaf("tpEmit", "1"),
            _leaf("cLocEmi", prest["cMun"]),
            prest_el,
            toma_el,
            interm_el,
            serv_el,
            valores_el,
        ],
        attrs={"Id": id_dps},
    )

    dps = _el("DPS", [infDPS], attrs={"versao": "1.00"})
    etree.cleanup_namespaces(dps)
    return dps


def assinar_dps(dps_el, private_key, cert):
    """Assina o infDPS de um elemento <DPS> e retorna a árvore assinada
    (mesma árvore, mutada in place — `dps_el` já sai com <Signature>)."""
    infDPS = dps_el.find(f"{{{NS}}}infDPS")
    if infDPS is None:
        raise ValueError("Elemento <DPS> sem infDPS")
    return assinar_elemento(dps_el, infDPS, private_key, cert)
