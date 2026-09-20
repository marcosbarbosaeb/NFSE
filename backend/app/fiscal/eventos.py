"""
Evento de cancelamento (e101101) — porta de integracao/cancelar_nfse.py.

Igual à nota em dps.py: a função aqui recebe dados prontos em vez de ler de
um cadastro hardcoded, e usa app.fiscal.xmldsig (assinatura consolidada,
sem a cópia local de c14n/build_signature que o original tinha).
integracao/cancelar_nfse.py continua existindo e funcionando exatamente
como está — é o script que já foi usado pra cancelar uma nota de verdade
(ver output/CANCELAMENTO_..._112223684.xml).
"""
import datetime

from lxml import etree

from app.fiscal.xmldsig import assinar_elemento

NS = "http://www.sped.fazenda.gov.br/nfse"
NSMAP = {None: NS}

CODIGO_EVENTO_CANCELAMENTO = "101101"

MOTIVOS_CANCELAMENTO = {
    "1": "Erro na Emissão",
    "2": "Serviço não Prestado",
    "9": "Outros",
}


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


def montar_evento_cancelamento(chave: str, cnpj_autor: str, cmotivo: str, xmotivo: str, tpAmb: str):
    """chave: chave de acesso da NFS-e a cancelar (50 dígitos). cmotivo:
    '1'|'2'|'9' (ver MOTIVOS_CANCELAMENTO). xmotivo: 15-255 caracteres —
    mesma validação do script original."""
    if len(chave) != 50 or not chave.isdigit():
        raise ValueError(f"Chave de acesso inválida (precisa ter 50 dígitos): {chave!r}")
    if cmotivo not in MOTIVOS_CANCELAMENTO:
        raise ValueError(f"cMotivo inválido: {cmotivo!r} (esperado um de {sorted(MOTIVOS_CANCELAMENTO)})")
    if not (15 <= len(xmotivo) <= 255):
        raise ValueError("xMotivo precisa ter entre 15 e 255 caracteres (regra do schema)")

    now = datetime.datetime.now().astimezone()
    dhEvento = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    dhEvento = dhEvento[:-2] + ":" + dhEvento[-2:]

    id_pedreg = "PRE" + chave + CODIGO_EVENTO_CANCELAMENTO

    e101101 = _el("e101101", [
        _leaf("xDesc", "Cancelamento de NFS-e"),
        _leaf("cMotivo", cmotivo),
        _leaf("xMotivo", xmotivo),
    ])
    infPedReg = _el(
        "infPedReg",
        [
            _leaf("tpAmb", tpAmb),
            _leaf("verAplic", "ClaudeNFSe-0.1"),
            _leaf("dhEvento", dhEvento),
            _leaf("CNPJAutor", cnpj_autor),
            _leaf("chNFSe", chave),
            e101101,
        ],
        attrs={"Id": id_pedreg},
    )
    pedRegEvento = _el("pedRegEvento", [infPedReg], attrs={"versao": "1.00"})
    etree.cleanup_namespaces(pedRegEvento)
    return pedRegEvento


def assinar_evento(pedRegEvento_el, private_key, cert):
    infPedReg = pedRegEvento_el.find(f"{{{NS}}}infPedReg")
    if infPedReg is None:
        raise ValueError("Elemento <pedRegEvento> sem infPedReg")
    return assinar_elemento(pedRegEvento_el, infPedReg, private_key, cert)
