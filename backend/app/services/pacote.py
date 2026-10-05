"""Pacote de notas (05/10/2026): os PDFs e/ou XMLs de várias notas num
.zip — pra baixar, mandar num e-mail só pro contador ou subir no Drive.
É o fim do passo a passo de Notas em lote."""
import io
import uuid
import zipfile

from sqlalchemy.orm import Session

from app.models import Emissao
from app.services.envio_direto import nome_pdf, obter_danfse
from app.services.envios import EmissaoSemConteudoError, melhor_xml_disponivel

CONTEUDOS = ("pdf", "xml", "ambos")
MAXIMO = 3000
# O serviço de e-mail aceita até ~40 MB por mensagem (já contando a
# codificação do anexo): acima disto o pacote vai por download ou Drive.
LIMITE_EMAIL_BYTES = 24 * 1024 * 1024


def arquivos_da_nota(db: Session, emissao: Emissao, conteudo: str) -> list[tuple[str, bytes, str]]:
    """[(nome, bytes, tipo)] do que existe desta nota. PDF só de nota autorizada."""
    arquivos: list[tuple[str, bytes, str]] = []
    if conteudo in ("pdf", "ambos") and emissao.estado == "confirmado":
        pdf = obter_danfse(db, emissao, emissao.prestador_id)
        if pdf:
            arquivos.append((nome_pdf(emissao), pdf, "application/pdf"))
    if conteudo in ("xml", "ambos"):
        try:
            nome, xml = melhor_xml_disponivel(emissao)
            arquivos.append((nome, xml.encode("utf-8"), "application/xml"))
        except EmissaoSemConteudoError:
            pass
    return arquivos


def selecionar(
    db: Session, *, ids: list[uuid.UUID] | None = None, competencia: str | None = None,
    vinculo_id: uuid.UUID | None = None, so_autorizadas: bool = False,
) -> list[Emissao]:
    query = db.query(Emissao).filter(Emissao.estado != "cancelada")
    if ids:
        query = query.filter(Emissao.id.in_(ids[:MAXIMO]))
    else:
        query = query.filter(Emissao.competencia == competencia)
        if vinculo_id:
            query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    if so_autorizadas:
        query = query.filter(Emissao.estado == "confirmado")
    return query.order_by(Emissao.n_dps).limit(MAXIMO).all()


def montar_zip(db: Session, emissoes: list[Emissao], conteudo: str = "ambos") -> tuple[bytes, int]:
    """(.zip, quantas notas entraram). Com os dois tipos, vão em pastas
    pdf/ e xml/; com um só, os arquivos ficam soltos."""
    buffer = io.BytesIO()
    quantas = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for emissao in emissoes:
            arquivos = arquivos_da_nota(db, emissao, conteudo)
            for nome, dados, _tipo in arquivos:
                pasta = ("pdf/" if nome.endswith(".pdf") else "xml/") if conteudo == "ambos" else ""
                zf.writestr(f"{pasta}{nome}", dados)
            quantas += 1 if arquivos else 0
    return buffer.getvalue(), quantas
