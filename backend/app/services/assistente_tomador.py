"""Cadastro assistido de tomador (05/10/2026).

"A pessoa carrega os dados da nota anterior, informa o que deve alterar
todo mês e com isso cadastramos o tomador de forma mais fácil — está um
pouco confuso pra quem é leigo." Daqui sai tudo o que dá pra tirar de uma
nota já emitida: quem é o tomador, os códigos do serviço e a descrição —
com o que muda todo mês (mês/ano, número da ordem) já trocado por um
campo automático.
"""
import io
import re

from sqlalchemy.orm import Session

from app.models import Emissao
from app.services import importar_adn

_MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
_MES_RE = "|".join(_MESES + ["MARCO"])


class NotaIlegivelError(Exception):
    pass


def sugerir_modelo(descricao: str) -> dict:
    """Descrição de uma nota antiga -> modelo pras próximas, com o que muda
    todo mês trocado por um campo automático. `partes` conta o que foi
    trocado, pra pessoa conferir."""
    modelo = re.sub(r"\s+", " ", descricao or "").strip()
    partes: list[dict] = []

    def trocar(padrao: str, novo, rotulo: str, flags=re.IGNORECASE):
        nonlocal modelo
        achado = re.search(padrao, modelo, flags)
        if achado:
            partes.append({"trecho": achado.group(0), "rotulo": rotulo})
            modelo = re.sub(padrao, novo, modelo, count=1, flags=flags)

    trocar(rf"\b({_MES_RE})\s*/\s*20\d\d\b", "{mes_nome_upper}/{ano}", "mês e ano da nota (ex.: OUTUBRO/2026)")
    trocar(rf"\b({_MES_RE})\s+de\s+20\d\d\b", "{mes_nome_upper} de {ano}", "mês e ano da nota (ex.: OUTUBRO de 2026)")
    trocar(r"\b(0[1-9]|1[0-2])\s*/\s*20\d\d\b", "{competencia_mm_aaaa}", "mês e ano da nota (ex.: 10/2026)")
    if not partes:
        trocar(rf"\b({_MES_RE})\b", "{mes_nome_upper}", "mês da nota (ex.: OUTUBRO)")
    trocar(
        r"(ordem(?:\s+de\s+pagamento)?(?:\s*n[ºo°.]*)?\s*[:\-]?\s*)\d{3,}",
        lambda m: m.group(1) + "{ordem}",
        "número da ordem de pagamento (você informa ao gerar)",
    )
    return {"modelo": modelo[:1000], "partes": partes}


def dados_da_nota(nota: dict) -> dict:
    """Resultado de `importar_adn.ler_nfse` -> o que o cadastro precisa."""
    toma = nota.get("toma") or {}
    sugestao = sugerir_modelo(nota.get("descricao") or "")
    return {
        "tomador": {
            "tipo_documento": toma.get("tipo"), "documento": toma.get("documento"), "razao_social": toma.get("nome"),
            "cod_municipio": toma.get("cMun"), "cep": toma.get("CEP"), "logradouro": toma.get("xLgr"),
            "numero": toma.get("nro"), "complemento": toma.get("xCpl"), "bairro": toma.get("xBairro"), "email": toma.get("email"),
        },
        "cod_trib_nacional": nota.get("cTribNac"),
        "cod_trib_municipal": nota.get("cTribMun"),
        "cod_nbs": nota.get("cNBS"),
        "cod_local_prestacao": nota.get("cLocPrestacao"),
        "serie": nota.get("serie"),
        "descricao_original": nota.get("descricao"),
        "modelo_sugerido": sugestao["modelo"],
        "partes": sugestao["partes"],
        "valor": float(nota["valor"]) if nota.get("valor") else None,
        "competencia": (nota.get("dcompet") or "")[:7] or None,
    }


def chave_no_pdf(conteudo: bytes) -> str | None:
    """Chave de acesso (50 dígitos) impressa no DANFSe."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            texto = " ".join((p.extract_text() or "") for p in pdf.pages[:2])
    except Exception:  # noqa: BLE001 — PDF estragado/protegido
        return None
    # A chave pode vir quebrada em blocos ("3106 2002 ..."): junta os dígitos.
    for achado in re.finditer(r"(?<!\d)\d[\d .\-]{48,75}\d(?!\d)", texto):
        digitos = re.sub(r"\D", "", achado.group(0))
        if len(digitos) == 50:
            return digitos
    return None


def ler_xml(conteudo: bytes) -> dict:
    nota = importar_adn.ler_nfse(conteudo)
    if nota is None:
        raise NotaIlegivelError("Esse arquivo não é o XML de uma NFS-e do padrão nacional.")
    return dados_da_nota(nota)


def ultima_nota_do_vinculo(db: Session, vinculo_id) -> dict | None:
    """A nota mais recente deste tomador que tem XML (emitida aqui ou
    importada) — base pra configurar a emissão de quem só tinha controle."""
    emissoes = (
        db.query(Emissao)
        .filter(Emissao.prestador_tomador_id == vinculo_id, Emissao.tomador_documento.is_(None), Emissao.estado != "cancelada")
        .order_by(Emissao.competencia.desc(), Emissao.criado_em.desc())
        .limit(5)
    )
    for e in emissoes:
        bruto = e.xml_resposta or e.xml_assinado or e.xml_dps
        if not bruto:
            continue
        nota = importar_adn.ler_nfse(bruto.encode("utf-8"))
        if nota is not None:
            return dados_da_nota(nota)
    return None


_CAMPO = {
    "municipais": (re.compile(r"<cTribMun>([^<]+)</cTribMun>"), re.compile(r"<xTribMun>([^<]+)</xTribMun>")),
    "nbs": (re.compile(r"<cNBS>([^<]+)</cNBS>"), re.compile(r"<xNBS>([^<]+)</xNBS>")),
}
_TRIB_NAC = re.compile(r"<cTribNac>([^<]+)</cTribNac>")


def codigos_usados(db: Session, cod_trib_nacional: str | None = None) -> dict:
    """Códigos de tributação municipal e NBS que já apareceram nas notas
    desta empresa, com a descrição que a própria Receita devolveu — pra
    pessoa escolher numa lista, como no emissor nacional, em vez de digitar
    número. Olha as notas mais recentes (com XML da NFS-e)."""
    contagem: dict[str, dict[str, dict]] = {"municipais": {}, "nbs": {}}
    consulta = (
        db.query(Emissao.xml_resposta)
        .filter(Emissao.xml_resposta.isnot(None), Emissao.estado == "confirmado")
        .order_by(Emissao.criado_em.desc())
        .limit(300)
    )
    for (xml,) in consulta:
        nacional = _TRIB_NAC.search(xml)
        if cod_trib_nacional and (not nacional or nacional.group(1) != cod_trib_nacional):
            continue
        for campo, (re_codigo, re_descricao) in _CAMPO.items():
            codigo = re_codigo.search(xml)
            if not codigo:
                continue
            descricao = re_descricao.search(xml)
            item = contagem[campo].setdefault(codigo.group(1), {"codigo": codigo.group(1), "descricao": None, "vezes": 0})
            item["vezes"] += 1
            if descricao and not item["descricao"]:
                item["descricao"] = descricao.group(1).strip()
    return {campo: sorted(itens.values(), key=lambda i: -i["vezes"]) for campo, itens in contagem.items()}
