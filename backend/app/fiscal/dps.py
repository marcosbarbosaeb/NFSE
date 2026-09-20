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

from lxml import etree

from app.fiscal.xmldsig import assinar_elemento

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
    descricao = template.format(
        competencia_mm_aaaa=f"{mes}/{ano}",
        mes_nome_upper=_MESES_PT[int(mes)],
        ano=ano,
        mes=mes,
        ordem=ordem or "",
    )
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
) -> etree._Element:
    """Monta o elemento <DPS> (não assinado).

    prest: {CNPJ, IM, cMun, opSimpNac, regApTribSN, regEspTrib} — só isso
        vai pro XML; nome/endereço do prestador NÃO são enviados de
        propósito (a Sefin preenche a partir do cadastro/CNC e REJEITA se
        vierem na DPS — erro E0121, descoberto em produção 09/09/2026).
    toma: {CNPJ, xNome, cMun, CEP, xLgr, nro, xCpl?, xBairro}.
    serv: {cLocPrestacao, cTribNac, cTribMun, descricao} — `descricao` já
        deve vir renderizada (ver `renderizar_descricao` acima); esta
        função não sabe nada sobre templates/placeholders.
    tpAmb: '1' produção, '2' homologação.
    aliq_sn: alíquota do Simples Nacional em % (-> pTotTribSN). None ->
        indTotTrib=0 (mesma regra do original — Marcos ajusta manualmente
        todo mês).
    dcompet: 'AAAA-MM-DD'; None = hoje.
    """
    dCompet = dcompet or datetime.date.today().isoformat()
    cnpj_prest = prest["CNPJ"]

    now = datetime.datetime.now().astimezone()
    dhEmi = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    dhEmi = dhEmi[:-2] + ":" + dhEmi[-2:]

    id_dps = montar_id_dps(prest["cMun"], cnpj_prest, serie, n_dps)

    end_nac_prest = _el("endNac", [_leaf("cMun", prest["cMun"]), _leaf("CEP", prest.get("CEP", ""))])
    regTrib = _el("regTrib", [
        _leaf("opSimpNac", prest["opSimpNac"]),
        _leaf("regApTribSN", prest["regApTribSN"]),
        _leaf("regEspTrib", prest["regEspTrib"]),
    ])
    prest_el = _el("prest", [
        _leaf("CNPJ", cnpj_prest),
        _leaf("IM", prest["IM"]),
        regTrib,
    ])

    end_nac_toma = _el("endNac", [_leaf("cMun", toma["cMun"]), _leaf("CEP", toma["CEP"])])
    toma_end_children = [end_nac_toma, _leaf("xLgr", toma["xLgr"]), _leaf("nro", toma["nro"])]
    if toma.get("xCpl"):
        toma_end_children.append(_leaf("xCpl", toma["xCpl"]))
    toma_end_children.append(_leaf("xBairro", toma["xBairro"]))
    end_toma = _el("end", toma_end_children)
    toma_el = _el("toma", [
        _leaf("CNPJ", toma["CNPJ"]),
        _leaf("xNome", toma["xNome"]),
        end_toma,
    ])

    locPrest = _el("locPrest", [_leaf("cLocPrestacao", serv["cLocPrestacao"])])
    cServ = _el("cServ", [
        _leaf("cTribNac", serv["cTribNac"]),
        _leaf("cTribMun", serv["cTribMun"]),
        _leaf("xDescServ", serv["descricao"]),
    ])
    serv_el = _el("serv", [locPrest, cServ])

    vServPrest = _el("vServPrest", [_leaf("vServ", f"{valor:.2f}")])
    tribMun = _el("tribMun", [_leaf("tribISSQN", "1"), _leaf("tpRetISSQN", "1")])
    if aliq_sn is not None:
        totTrib = _el("totTrib", [_leaf("pTotTribSN", f"{aliq_sn:.2f}")])
    else:
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
