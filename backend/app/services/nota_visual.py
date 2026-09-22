"""
Máscara visual da nota — Marco 11 do plano, motivado por um teste real da
Raiana: ela não conseguiu conferir uma nota olhando só o "Resumo" (um bloco
de JSON) e o XML cru que o painel mostrava desde o Marco 5 (ver
`mostrarEmissao` em app/main.py) — não é assim que ela reconhece uma nota
fiscal. Este módulo entrega os MESMOS dados já lidos e rotulados em
português, prontos pra o painel desenhar algo parecido com uma nota de
verdade (cabeçalho, PRESTADOR/TOMADOR lado a lado, serviço, valores) em vez
de estrutura de depuração. O XML cru continua disponível — só deixou de ser
a visão padrão (ver `NotaVisualResponse.xml_disponivel` e o `<details>` de
"dados técnicos" no painel).

Porta a mesma leitura de campos que integracao/resumo_dps.py já fazia em
linha de comando (funções `t`/`brl`/`cnpj` daquele script) pra dentro do
backend — mas devolvendo um dict estruturado (pronto pro schema
`NotaVisualResponse`) em vez de linhas de texto pra imprimir no terminal.

Duas fontes por baixo, combinadas — nenhuma das duas cobre tudo sozinha, e
isso é proposital, não uma lacuna:

1. Banco (Prestador + `Emissao.tomador_snapshot`) — sempre disponível,
   mesmo antes de existir XML (estado 'rascunho'). É daqui que vem
   nome/CNPJ/endereço do PRESTADOR: a partir do Marco 9 (erro E0121 visto em
   produção em 09/09/2026), `montar_dps_xml` propositalmente NÃO manda
   nome/endereço do prestador no XML — a Sefin preenche a partir do
   cadastro/CNC e rejeita se vier (ver app/fiscal/dps.py) — então montar a
   nota só a partir do XML deixaria o prestador em branco. `tomador_snapshot`
   cobre o tomador pelo mesmo motivo que já cobre a descrição renderizada: é
   o que foi congelado no rascunho (Marco 6), não uma releitura do catálogo
   ao vivo — a mesma garantia anti-edição-retroativa vale aqui.
2. XML (xml_resposta > xml_assinado > xml_dps, mesma prioridade de
   `melhor_xml_disponivel` em app/services/envios.py) — só existe a partir
   de 'montado'. Cobre o que só nasce na montagem: Id da DPS, dhEmi, códigos
   de tributação/local de prestação (aqui já tem fallback pro snapshot,
   preenchido no rascunho) e os tributos/ISSQN.
"""
from lxml import etree

from app.models import Emissao

NS = "http://www.sped.fazenda.gov.br/nfse"

AMBIENTE_LABEL = {
    "1": "Produção — nota fiscal real",
    "2": "Homologação — ambiente de teste, não vale como nota fiscal real",
}

ESTADO_LABEL = {
    "rascunho": "Rascunho — ainda não montada",
    "montado": "Montada — pronta para assinar",
    "assinado": "Assinada — pronta para enviar/conferir (ainda não submetida à prefeitura)",
    "submetido": "Submetida à prefeitura — aguardando confirmação",
    "confirmado": "Confirmada pela prefeitura — nota fiscal válida",
    "cancelada": "Cancelada",
    "substituida": "Substituída por outra nota",
    "erro": "Erro na última tentativa de submissão",
}


def _t(inf, path: str) -> str | None:
    """Mesmo helper do resumo_dps.py original, só que devolve None em vez
    de '-' — quem decide como mostrar 'campo ausente' é o chamador (aqui,
    normalmente cai num fallback do snapshot; no painel, a linha some)."""
    el = inf.find("/".join(f"{{{NS}}}{p}" for p in path.split("/")))
    return el.text if el is not None and el.text is not None else None


def _fmt_cnpj(valor: str | None) -> str | None:
    if not valor:
        return valor
    digitos = "".join(c for c in valor if c.isdigit())
    if len(digitos) != 14:
        return valor
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def _fmt_endereco(logradouro, numero, complemento, bairro, cod_municipio, cep) -> str | None:
    """Sem tabela de municípios neste sistema (só o código IBGE é guardado
    — ver Prestador/Tomador em app/models.py), então o código aparece cru,
    rotulado como 'mun.' — mesma escolha que integracao/resumo_dps.py já
    fazia ('mun {cMun}'), não uma lacuna nova desta tela."""
    via = ", ".join(p for p in [logradouro, numero] if p)
    if complemento:
        via = f"{via} - {complemento}" if via else complemento
    resto = " - ".join(
        p for p in [bairro, f"mun. {cod_municipio}" if cod_municipio else None, f"CEP {cep}" if cep else None] if p
    )
    endereco = " - ".join(p for p in [via, resto] if p)
    return endereco or None


def _melhor_xml(emissao: Emissao) -> str | None:
    """Mesma prioridade de app/services/envios.py:melhor_xml_disponivel —
    mas aqui pode devolver None (rascunho), que o resto da função trata."""
    return emissao.xml_resposta or emissao.xml_assinado or emissao.xml_dps


def montar_nota_visual(emissao: Emissao) -> dict:
    """Devolve os campos da nota já combinados/rotulados — ver docstring do
    módulo pra origem de cada um. Não muda estado nem faz I/O de rede;
    só lê `emissao` (com `vinculo.prestador` carregado via lazy load, mesma
    sessão/RLS de quem chamou)."""
    prestador = emissao.vinculo.prestador
    snap = emissao.tomador_snapshot or {}
    xml_bruto = _melhor_xml(emissao)

    inf = None
    if xml_bruto:
        root = etree.fromstring(xml_bruto.encode("utf-8"))
        inf = root.find(f"{{{NS}}}infDPS")

    def _xml(path: str) -> str | None:
        return _t(inf, path) if inf is not None else None

    endereco_toma = snap.get("endereco") or {}
    servico_codigos = snap.get("codigo_servico_usado") or {}

    tot_trib = None
    issqn_retido = None
    if inf is not None:
        tot = inf.find(f"{{{NS}}}valores/{{{NS}}}trib/{{{NS}}}totTrib")
        if tot is not None and len(tot):
            filho = tot[0]
            nome = etree.QName(filho).localname
            if nome == "pTotTribSN":
                tot_trib = f"Alíquota do Simples Nacional: {filho.text}%"
            elif nome == "indTotTrib":
                tot_trib = "Não informado (tributos aproximados não parametrizados nesta nota)"
            else:
                tot_trib = f"{nome} = {filho.text}"

        trib_issqn = _xml("valores/trib/tribMun/tribISSQN")
        ret_issqn = _xml("valores/trib/tribMun/tpRetISSQN")
        if trib_issqn is not None:
            issqn_retido = "Retido pelo tomador" if ret_issqn == "2" else "Não retido (recolhido pelo prestador)"

    ambiente = _xml("tpAmb") or snap.get("tpAmb")

    return {
        "estado": emissao.estado,
        "estado_label": ESTADO_LABEL.get(emissao.estado, emissao.estado),
        "ambiente": ambiente,
        "ambiente_label": AMBIENTE_LABEL.get(ambiente, ambiente),
        "id_dps": inf.get("Id") if inf is not None else None,
        "serie": emissao.serie,
        "n_dps": emissao.n_dps,
        "competencia": emissao.competencia,
        "dh_emissao": _xml("dhEmi"),
        "chave_acesso": emissao.chave_acesso,
        # Marco 16, item 7 — só faz sentido quando estado='erro' (recusa da
        # Sefin ao submeter, ver app/services/motor_emissao.submeter): é o
        # que explica NA TELA por que ficou em erro, em vez da pessoa só
        # ver o badge vermelho sem saber o motivo pra corrigir e tentar de
        # novo.
        "erro_detalhe": emissao.erro_detalhe,
        "prestador": {
            "razao_social": prestador.razao_social,
            "cnpj": _fmt_cnpj(prestador.cpf_cnpj),
            "inscricao_municipal": prestador.inscricao_municipal,
            "endereco": _fmt_endereco(
                prestador.logradouro, prestador.numero, prestador.complemento,
                prestador.bairro, prestador.cod_municipio, prestador.cep,
            ),
            "telefone": prestador.telefone,
            "email": prestador.email,
        },
        "tomador": {
            "razao_social": snap.get("razao_social"),
            "cnpj": _fmt_cnpj(snap.get("cnpj")),
            "endereco": _fmt_endereco(
                endereco_toma.get("xLgr"), endereco_toma.get("nro"), endereco_toma.get("xCpl"),
                endereco_toma.get("xBairro"), endereco_toma.get("cMun"), endereco_toma.get("CEP"),
            ),
        },
        "servico": {
            "descricao": snap.get("descricao_renderizada"),
            "codigo_tributacao_nacional": _xml("serv/cServ/cTribNac") or servico_codigos.get("cTribNac"),
            "codigo_tributacao_municipal": _xml("serv/cServ/cTribMun") or servico_codigos.get("cTribMun"),
            "codigo_local_prestacao": _xml("serv/locPrest/cLocPrestacao") or servico_codigos.get("cLocPrestacao"),
        },
        "valores": {
            "valor_servico": float(emissao.valor),
            "issqn": issqn_retido,
            "total_tributos": tot_trib,
        },
        "xml_disponivel": xml_bruto is not None,
    }
