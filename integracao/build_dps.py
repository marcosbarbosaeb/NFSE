#!/usr/bin/env python3
"""
Gerador de DPS (Declaração de Prestação de Serviços) - Sistema Nacional NFS-e
Baseado no leiaute oficial (Anexo I v1.01, estruturalmente idêntico ao XSD v1.00
usado aqui para validação estrutural).

Uso:
    python3 build_dps.py --fornecedor squad_epoca --competencia 2026-08 --valor 17654.40

Isso gera um XML de DPS (NÃO assinado, NÃO enviado) em ./output/.
A assinatura (XMLDSig com o certificado A1) e o envio para a API do ADN
precisam rodar de um ambiente com acesso direto à rede do gov.br e mTLS
(não funciona a partir deste sandbox de nuvem - ver signing.py e SUBMIT_README.md).
"""
import argparse
import datetime
import os
from lxml import etree

NS = "http://www.sped.fazenda.gov.br/nfse"
NSMAP = {None: NS}

FORNECEDORES = {
    "squad_epoca": {
        "nome_curto": "Squad Época (Campos Floridos)",
        "prest": {
            "CNPJ": "45172374000122",
            "IM": "13665300010",
            "xNome": "RAIANA DINIZ REMORINI",
            "cMun": "3106200",  # Belo Horizonte/MG
            "CEP": "30580353",
            "xLgr": "Rua Ursula Paulino - de 1153 ao fim - lado impar",
            "nro": "1321",
            "xBairro": "Estrela do Oriente",
            "fone": "31983767096",
            "email": "raianadinizremorinni@gmail.com",
            "opSimpNac": "3",       # Optante ME/EPP
            "regApTribSN": "1",     # Regime de apuracao dos tributos federais e municipal pelo SN
            "regEspTrib": "0",      # Nenhum
        },
        "toma": {
            "CNPJ": "01239313000160",
            "xNome": "CAMPOS FLORIDOS COMERCIO DE COSMETICOS LTDA",
            "cMun": "3304557",  # Rio de Janeiro/RJ
            "CEP": "20011000",
            "xLgr": "Da Assembleia",
            "nro": "00100",
            "xCpl": "Sal 2701 Sal 2801",
            "xBairro": "Centro",
        },
        "serv": {
            "cLocPrestacao": "3106200",  # Belo Horizonte (local da prestacao)
            "cTribNac": "170601",
            "cTribMun": "001",
            "descricao_template": "Comissão recebida pela promoção de vendas no Programa Squad Época - {competencia_mm_aaaa}",
        },
        # Dados bancarios vao dentro da descricao do servico, como no modelo original
        "dados_bancarios": "Dados bancários: Compartilhando Promoções, Banco Inter, agência 0001, conta corrente 29218862-5",
        # Serie da DPS. Faixas oficiais (leiaute): 00001-49999 = aplicativo proprio
        # (nosso caso, via API); 70000-79999 = Emissor Web (a nota-modelo era do
        # Emissor Web, serie 70000 - NAO reutilizar: faixa reservada). A numeracao
        # (nDPS) e por serie, entao a serie 1 comeca do 1, independente das notas
        # emitidas pelo portal.
        "serie": "1",
        # ATENCAO: pAliq / aliquota do ISSQN fica de fora aqui de proposito.
        # Marcos atualiza isso manualmente todo mes no Emissor Nacional.
        # Ver nota no rodape do script.
    },
    "elausa": {
        "nome_curto": "ElaUsa (Exi Brasil)",
        # Prestador e sempre a Raiana - mesmo cadastro do squad_epoca.
        "prest": {
            "CNPJ": "45172374000122",
            "IM": "13665300010",
            "xNome": "RAIANA DINIZ REMORINI",
            "cMun": "3106200",  # Belo Horizonte/MG
            "CEP": "30580353",
            "xLgr": "Rua Ursula Paulino - de 1153 ao fim - lado impar",
            "nro": "1321",
            "xBairro": "Estrela do Oriente",
            "fone": "31983767096",
            "email": "raianadinizremorinni@gmail.com",
            "opSimpNac": "3",
            "regApTribSN": "1",
            "regEspTrib": "0",
        },
        "toma": {
            # EXI IMPORTACAO,EXPORTACAO E COMERCIALIZACAO DE PRODUTOS DE BELEZA LTDA
            # (dados extraidos da nota-modelo n. 144, emitida via portal em 16/08/2026)
            "CNPJ": "12232213000128",
            "xNome": "EXI IMPORTACAO,EXPORTACAO E COMERCIALIZACAO DE PRODUTOS DE BELEZA LTDA",
            "cMun": "5300108",  # Brasilia/DF
            "CEP": "70770536",
            "xLgr": "SHCGN CLR QD 716 BLOCO F",
            "nro": "LJ 19",
            "xCpl": "PARTE B",
            "xBairro": "ASA NORTE",
        },
        "serv": {
            "cLocPrestacao": "3106200",  # Belo Horizonte (local da prestacao)
            "cTribNac": "170601",
            "cTribMun": "001",
            # Modelo (nota 144): "Comissão referente aos serviços prestados de
            # propaganda e promoção de vendas do mês de JULHO/2026." - SEM dados
            # bancarios na descricao (diferente do squad_epoca).
            "descricao_template": "Comissão referente aos serviços prestados de propaganda e promoção de vendas do mês de {mes_nome_upper}/{ano}.",
        },
        "serie": "1",
    },
    "magalu": {
        "nome_curto": "Magalu (Magazine Luiza)",
        # Prestador e sempre a Raiana - mesmo cadastro dos demais.
        "prest": {
            "CNPJ": "45172374000122",
            "IM": "13665300010",
            "xNome": "RAIANA DINIZ REMORINI",
            "cMun": "3106200",  # Belo Horizonte/MG
            "CEP": "30580353",
            "xLgr": "Rua Ursula Paulino - de 1153 ao fim - lado impar",
            "nro": "1321",
            "xBairro": "Estrela do Oriente",
            "fone": "31983767096",
            "email": "raianadinizremorinni@gmail.com",
            "opSimpNac": "3",
            "regApTribSN": "1",
            "regEspTrib": "0",
        },
        "toma": {
            # MAGAZINE LUIZA S/A (dados extraidos da nota-modelo n. 145, emitida
            # via portal em 16/08/2026).
            "CNPJ": "47960950000121",
            "xNome": "MAGAZINE LUIZA S/A",
            "cMun": "3516200",  # Franca/SP
            "CEP": "14400490",
            "xLgr": "VOLUNTARIOS DA FRANCA",
            "nro": "1465",
            "xBairro": "CENTRO",
        },
        "serv": {
            "cLocPrestacao": "3106200",  # Belo Horizonte (local da prestacao)
            "cTribNac": "170601",
            "cTribMun": "001",
            # Modelo (nota 145): "Canal Influenciador Magalu Ref 07_2026" - o mes
            # da referencia acompanha o mes ATUAL da emissao (nao o mes anterior
            # como no squad_epoca/elausa).
            "descricao_template": "Canal Influenciador Magalu Ref {mes}_{ano}",
        },
        "serie": "1",
    },
    "awin": {
        "nome_curto": "AWIN",
        "prest": {
            "CNPJ": "45172374000122",
            "IM": "13665300010",
            "xNome": "RAIANA DINIZ REMORINI",
            "cMun": "3106200",  # Belo Horizonte/MG
            "CEP": "30580353",
            "xLgr": "Rua Ursula Paulino - de 1153 ao fim - lado impar",
            "nro": "1321",
            "xBairro": "Estrela do Oriente",
            "fone": "31983767096",
            "email": "raianadinizremorinni@gmail.com",
            "opSimpNac": "3",
            "regApTribSN": "1",
            "regEspTrib": "0",
        },
        "toma": {
            # AWIN VEICULACAO DE PUBLICIDADE NA INTERNET LTDA. (dados extraidos
            # da nota-modelo n. 147, emitida via portal em 17/08/2026).
            "CNPJ": "14182871000188",
            "xNome": "AWIN VEICULACAO DE PUBLICIDADE NA INTERNET LTDA.",
            "cMun": "3550308",  # Sao Paulo/SP
            "CEP": "01311000",
            "xLgr": "PAULISTA",
            "nro": "37",
            "xCpl": "CONJ 131",
            "xBairro": "BELA VISTA",
        },
        "serv": {
            "cLocPrestacao": "3106200",  # Belo Horizonte (local da prestacao)
            "cTribNac": "170601",
            "cTribMun": "001",
            # A ordem de pagamento muda a cada nota - passada via --ordem.
            "descricao_template": "Locação de espaço virtual realizada até a data deste documento. Ordem de pagamento número: {ordem}",
        },
        "serie": "1",
    },
    "awin_rchlo": {
        "nome_curto": "AWIN Rchlo",
        # Mesmo tomador/prestador do "awin" - e o mesmo programa AWIN, apenas
        # controlado separadamente na planilha do Marcos (valores bem menores).
        "prest": {
            "CNPJ": "45172374000122",
            "IM": "13665300010",
            "xNome": "RAIANA DINIZ REMORINI",
            "cMun": "3106200",  # Belo Horizonte/MG
            "CEP": "30580353",
            "xLgr": "Rua Ursula Paulino - de 1153 ao fim - lado impar",
            "nro": "1321",
            "xBairro": "Estrela do Oriente",
            "fone": "31983767096",
            "email": "raianadinizremorinni@gmail.com",
            "opSimpNac": "3",
            "regApTribSN": "1",
            "regEspTrib": "0",
        },
        "toma": {
            # AWIN VEICULACAO DE PUBLICIDADE NA INTERNET LTDA. (dados extraidos
            # da nota-modelo n. 146, emitida via portal em 17/08/2026).
            "CNPJ": "14182871000188",
            "xNome": "AWIN VEICULACAO DE PUBLICIDADE NA INTERNET LTDA.",
            "cMun": "3550308",  # Sao Paulo/SP
            "CEP": "01311000",
            "xLgr": "PAULISTA",
            "nro": "37",
            "xCpl": "CONJ 131",
            "xBairro": "BELA VISTA",
        },
        "serv": {
            "cLocPrestacao": "3106200",  # Belo Horizonte (local da prestacao)
            "cTribNac": "170601",
            "cTribMun": "001",
            "descricao_template": "Locação de espaço virtual realizada até a data deste documento. Ordem de pagamento número: {ordem}",
        },
        "serie": "1",
    },
}


def only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def build_dps_xml(fornecedor_key: str, competencia: str, valor: float,
                   n_dps: int, tpAmb: str = "2", aliq_sn: float = None,
                   dcompet: str = None, ordem: str = None) -> etree._Element:
    """
    competencia: 'AAAA-MM' (mes de competencia do servico)
    valor: valor do servico em R$
    n_dps: numero sequencial da DPS (controle do prestador)
    tpAmb: '1' = Producao, '2' = Homologacao (produção restrita). Usar '2' ate validar.
    aliq_sn: aliquota do Simples Nacional em % (ex.: 12.5) -> pTotTribSN. None = indTotTrib=0.
    dcompet: 'AAAA-MM-DD' para forcar a data de competencia; None = hoje.
    ordem: numero da ordem de pagamento (fornecedores AWIN/AWIN Rchlo - vai na descricao).
    """
    cfg = FORNECEDORES[fornecedor_key]
    prest = cfg["prest"]
    toma = cfg["toma"]
    serv = cfg["serv"]

    MESES_PT = ["", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
                "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    ano, mes = competencia.split("-")
    competencia_mm_aaaa = f"{mes}/{ano}"
    mes_nome_upper = MESES_PT[int(mes)]
    # dCompet = DATA DO DIA da emissao (regra do Marcos: "a competencia da nota e
    # o dia atual"). O mes/ano que vai na DESCRICAO e outra coisa: e o mes de
    # referencia da comissao (mes anterior), passado em --competencia.
    dCompet = dcompet or datetime.date.today().isoformat()

    cnpj_prest = prest["CNPJ"]
    serie = cfg["serie"]
    nDPS = str(n_dps)

    # Id da DPS: "DPS" + Cod.Mun(7) + TipoInscFederal(1) + InscFederal(14) + Serie(5) + NumDPS(15)
    tipo_insc = "2"  # 2 = CNPJ
    id_dps = (
        "DPS"
        + prest["cMun"].zfill(7)
        + tipo_insc
        + cnpj_prest.zfill(14)
        + serie.zfill(5)
        + nDPS.zfill(15)
    )

    now = datetime.datetime.now().astimezone()
    dhEmi = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    dhEmi = dhEmi[:-2] + ":" + dhEmi[-2:]  # formata timezone com ':'

    E = lambda tag, *children, **attrs: _el(tag, children, attrs)

    def _el(tag, children=(), attrs=None, text=None):
        # nsmap={None: NS} => namespace PADRAO (sem prefixo). Sem isso o lxml
        # inventa o prefixo "ns0:" e a API Sefin rejeita (erro E1235:
        # "O elemento raiz do XML deve ser 'DPS', mas foi encontrado 'ns0:DPS'").
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

    def leaf(tag, text):
        e = etree.Element(f"{{{NS}}}{tag}", nsmap=NSMAP)
        e.text = str(text)
        return e

    if "{ordem}" in serv["descricao_template"] and not ordem:
        raise ValueError(f"Fornecedor '{fornecedor_key}' precisa de --ordem (numero da ordem de pagamento).")
    descricao = serv["descricao_template"].format(
        competencia_mm_aaaa=competencia_mm_aaaa, mes_nome_upper=mes_nome_upper, ano=ano, mes=mes,
        ordem=ordem or ""
    )
    if cfg.get("dados_bancarios"):
        # SEM quebra de linha: o padrao NF-e/NFS-e nao admite quebras de linha no
        # XML, e a API pode normaliza-las antes de conferir a assinatura (o que
        # invalida o digest -> E0714). Separador " - " no lugar do "\n".
        descricao = descricao + " - " + cfg["dados_bancarios"]

    # --- prest ---
    end_prest = leaf("end", None)
    end_prest.tag = f"{{{NS}}}end"
    end_nac_prest = _el("endNac", [leaf("cMun", prest["cMun"]), leaf("CEP", prest["CEP"])])
    end_prest_children = [end_nac_prest, leaf("xLgr", prest["xLgr"]), leaf("nro", prest["nro"])]
    if prest.get("xCpl"):
        end_prest_children.append(leaf("xCpl", prest["xCpl"]))
    end_prest_children.append(leaf("xBairro", prest["xBairro"]))
    end_prest = _el("end", end_prest_children)

    regTrib = _el("regTrib", [
        leaf("opSimpNac", prest["opSimpNac"]),
        leaf("regApTribSN", prest["regApTribSN"]),
        leaf("regEspTrib", prest["regEspTrib"]),
    ])

    # Emitente = proprio prestador (tpEmit=1): a Sefin preenche nome, endereco,
    # fone e e-mail a partir do cadastro (CNC) e REJEITA se vierem na DPS
    # (E0121 "O nome ou razao social do prestador nao deve ser informado quando
    # o emitente da DPS for o proprio prestador" - producao, 09/09/2026).
    # Vai so: CNPJ, IM e regime tributario. Os demais dados ficam em FORNECEDORES
    # apenas como referencia.
    prest_el = _el("prest", [
        leaf("CNPJ", cnpj_prest),
        leaf("IM", prest["IM"]),
        regTrib,
    ])

    # --- toma ---
    end_nac_toma = _el("endNac", [leaf("cMun", toma["cMun"]), leaf("CEP", toma["CEP"])])
    toma_end_children = [end_nac_toma, leaf("xLgr", toma["xLgr"]), leaf("nro", toma["nro"])]
    if toma.get("xCpl"):
        toma_end_children.append(leaf("xCpl", toma["xCpl"]))
    toma_end_children.append(leaf("xBairro", toma["xBairro"]))
    end_toma = _el("end", toma_end_children)

    toma_el = _el("toma", [
        leaf("CNPJ", toma["CNPJ"]),
        leaf("xNome", toma["xNome"]),
        end_toma,
    ])

    # --- serv ---
    locPrest = _el("locPrest", [leaf("cLocPrestacao", serv["cLocPrestacao"])])
    cServ = _el("cServ", [
        leaf("cTribNac", serv["cTribNac"]),
        leaf("cTribMun", serv["cTribMun"]),
        leaf("xDescServ", descricao),
    ])
    serv_el = _el("serv", [locPrest, cServ])

    # --- valores ---
    vServPrest = _el("vServPrest", [leaf("vServ", f"{valor:.2f}")])
    # pAliq / demais campos de aliquota ficam de fora: Marcos preenche/ajusta
    # manualmente no Emissor Nacional todo mes (ver README).
    tribMun = _el("tribMun", [
        leaf("tribISSQN", "1"),   # Operacao tributavel
        leaf("tpRetISSQN", "1"),  # Nao retido
    ])
    # totTrib e um "choice": vTotTrib OU pTotTrib OU indTotTrib OU pTotTribSN.
    # pTotTribSN = "percentual aproximado do total dos tributos da aliquota do
    # Simples Nacional (%)" - e a aliquota que o Marcos informa todo mes no
    # portal (ex.: 12,5). Se nao for informada, cai em indTotTrib=0 (emitente
    # opta por nao informar). O ISSQN (pAliq) NAO vai: BH e conveniado e a
    # Sefin aplica a aliquota parametrizada do municipio.
    if aliq_sn is not None:
        totTrib = _el("totTrib", [leaf("pTotTribSN", f"{aliq_sn:.2f}")])
    else:
        totTrib = _el("totTrib", [leaf("indTotTrib", "0")])
    trib = _el("trib", [tribMun, totTrib])
    valores_el = _el("valores", [vServPrest, trib])

    infDPS = _el(
        "infDPS",
        [
            leaf("tpAmb", tpAmb),
            leaf("dhEmi", dhEmi),
            leaf("verAplic", "ClaudeNFSe-0.1"),
            leaf("serie", serie),
            leaf("nDPS", nDPS),
            leaf("dCompet", dCompet),
            leaf("tpEmit", "1"),  # 1 = Prestador
            leaf("cLocEmi", prest["cMun"]),  # municipio emissor (onde o prestador esta cadastrado)
            prest_el,
            toma_el,
            serv_el,
            valores_el,
        ],
        attrs={"Id": id_dps},
    )

    dps = _el("DPS", [infDPS], attrs={"versao": "1.00"})
    # Remove declaracoes xmlns redundantes nos filhos: fica so uma, na raiz.
    etree.cleanup_namespaces(dps)
    return dps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fornecedor", default="squad_epoca")
    ap.add_argument("--competencia", required=True, help="AAAA-MM do mes de referencia da comissao (vai na descricao), ex: 2026-08")
    ap.add_argument("--valor", required=True, type=float)
    ap.add_argument("--n-dps", type=int, default=1, help="numero sequencial da DPS")
    ap.add_argument("--tpAmb", default="2", choices=["1", "2"], help="1=Producao 2=Homologacao")
    ap.add_argument("--aliq-sn", type=float, default=None,
                    help="aliquota do Simples Nacional em %% (ex: 12.5) -> pTotTribSN")
    ap.add_argument("--dcompet", default=None, help="data de competencia AAAA-MM-DD (padrao: hoje)")
    ap.add_argument("--ordem", default=None, help="numero da ordem de pagamento (fornecedores AWIN/AWIN Rchlo)")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    dps_el = build_dps_xml(args.fornecedor, args.competencia, args.valor, args.n_dps, args.tpAmb, args.aliq_sn, args.dcompet, args.ordem)
    tree = etree.ElementTree(dps_el)
    fname = os.path.join(args.outdir, f"DPS_{args.fornecedor}_{args.competencia}.xml")
    tree.write(fname, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    print(f"DPS (nao assinada) gerada em: {fname}")


if __name__ == "__main__":
    main()
