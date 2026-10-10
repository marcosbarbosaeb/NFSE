"""Documentos da empresa (2026.10.7 — `ideias/documentos-da-empresa.md`).

Guarda permanente, separada da pasta do mês: contrato social, cartão CNPJ,
documentos dos sócios, certidões, alvará... Regras:

- **Quem enxerga:** o dono e o contador com a permissão "documentos" (a
  exceção ao "ver é sempre livre" do contador: aqui tem documento pessoal de
  sócio). Ninguém mais — nem a Gestão, que vê no máximo quantidade e espaço.
- O dono envia, baixa, substitui e apaga. O contador com a permissão vê,
  envia e substitui; **só o dono apaga**.
- Substituir troca o arquivo e guarda a data (sem histórico de versões).
- Validade (opcional): aparece em "Precisa da sua atenção" e no painel do
  contador 30 dias antes e depois de vencido.
- Cada abertura/baixa fica registrada (`documento_acesso`); o dono vê.
- Limites: 15 MB por arquivo, 100 MB por empresa (separado da pasta do mês).
- No banco, sem cifragem nesta fase. Some com a empresa (CASCADE).
"""
from __future__ import annotations

import datetime
import mimetypes
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AcessoContador, DocumentoAcesso, DocumentoEmpresa, Usuario
from app.tempo import hoje as hoje_br

LIMITE_ARQUIVO_MB = 15
LIMITE_EMPRESA_MB = 100
DIAS_AVISO = 30
PERMISSAO = "documentos"

TIPOS = {
    "contrato_social": "Contrato social e alterações",
    "cartao_cnpj": "Cartão CNPJ",
    "socios": "Documentos dos sócios",
    "certidoes": "Certidões",
    "alvara": "Alvará e licenças",
    "outros": "Outros",
}


class DocumentoError(Exception):
    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


def pode_ver(papel: str, permissoes: list[str]) -> bool:
    return papel == "dono" or PERMISSAO in (permissoes or [])


def situacao(validade: datetime.date | None, hoje: datetime.date | None = None) -> str:
    if validade is None:
        return "sem_validade"
    dias = (validade - (hoje or hoje_br())).days
    return "vencido" if dias < 0 else ("vence_em_breve" if dias <= DIAS_AVISO else "ok")


def uso(db: Session, prestador_id: uuid.UUID) -> int:
    return int(db.query(func.coalesce(func.sum(DocumentoEmpresa.tamanho), 0)).filter(DocumentoEmpresa.prestador_id == prestador_id).scalar() or 0)


def _conferir_arquivo(db: Session, prestador_id: uuid.UUID, dados: bytes, substituindo: DocumentoEmpresa | None = None) -> None:
    if not dados:
        raise DocumentoError("O arquivo está vazio.")
    if len(dados) > LIMITE_ARQUIVO_MB * 1024 * 1024:
        raise DocumentoError(f"Arquivo grande demais: o limite é {LIMITE_ARQUIVO_MB} MB por arquivo.", 413)
    ocupado = uso(db, prestador_id) - (substituindo.tamanho if substituindo else 0)
    if ocupado + len(dados) > LIMITE_EMPRESA_MB * 1024 * 1024:
        livre = max(0, LIMITE_EMPRESA_MB * 1024 * 1024 - ocupado) / (1024 * 1024)
        raise DocumentoError(
            f"Os documentos da empresa chegaram ao limite de {LIMITE_EMPRESA_MB} MB (sobram {livre:.1f} MB). Apague algum que não precisa mais.", 413)


def _mime(nome: str, informado: str | None) -> str:
    return (informado or "").strip() or mimetypes.guess_type(nome)[0] or "application/octet-stream"


def _registrar(db: Session, doc: DocumentoEmpresa, usuario: Usuario, papel: str, acao: str) -> None:
    db.add(DocumentoAcesso(id=uuid.uuid4(), prestador_id=doc.prestador_id, documento_id=doc.id, usuario_id=usuario.id,
                           email=usuario.email, papel=papel, acao=acao))


def enviar(db: Session, prestador_id: uuid.UUID, usuario: Usuario, papel: str, *, tipo: str, nome: str | None,
           nome_arquivo: str, tipo_mime: str | None, dados: bytes, validade: datetime.date | None) -> DocumentoEmpresa:
    if tipo not in TIPOS:
        raise DocumentoError("Tipo de documento desconhecido.")
    _conferir_arquivo(db, prestador_id, dados)
    nome_arquivo = (nome_arquivo or "documento").strip()[-200:]
    doc = DocumentoEmpresa(
        id=uuid.uuid4(), prestador_id=prestador_id, tipo=tipo, nome=((nome or "").strip() or TIPOS[tipo])[:200],
        nome_arquivo=nome_arquivo, tipo_mime=_mime(nome_arquivo, tipo_mime)[:100], tamanho=len(dados), conteudo=dados,
        validade=validade, enviado_por=usuario.id, enviado_por_email=usuario.email, papel=papel,
    )
    db.add(doc)
    db.flush()
    _registrar(db, doc, usuario, papel, "enviou")
    db.flush()
    return doc


def _do_id(db: Session, documento_id: uuid.UUID) -> DocumentoEmpresa:
    doc = db.get(DocumentoEmpresa, documento_id)
    if doc is None:
        raise DocumentoError("Documento não encontrado.", 404)
    return doc


def substituir(db: Session, documento_id: uuid.UUID, usuario: Usuario, papel: str, *, nome_arquivo: str, tipo_mime: str | None,
               dados: bytes, validade: datetime.date | None, manter_validade: bool) -> DocumentoEmpresa:
    doc = _do_id(db, documento_id)
    _conferir_arquivo(db, doc.prestador_id, dados, substituindo=doc)
    doc.nome_arquivo = (nome_arquivo or doc.nome_arquivo).strip()[-200:]
    doc.tipo_mime = _mime(doc.nome_arquivo, tipo_mime)[:100]
    doc.tamanho = len(dados)
    doc.conteudo = dados
    if not manter_validade:
        doc.validade = validade
    doc.enviado_por, doc.enviado_por_email, doc.papel = usuario.id, usuario.email, papel
    doc.substituido_em = datetime.datetime.now(datetime.timezone.utc)
    _registrar(db, doc, usuario, papel, "substituiu")
    db.flush()
    return doc


def editar(db: Session, documento_id: uuid.UUID, *, tipo: str | None, nome: str | None, validade: datetime.date | None, limpar_validade: bool) -> DocumentoEmpresa:
    doc = _do_id(db, documento_id)
    if tipo is not None:
        if tipo not in TIPOS:
            raise DocumentoError("Tipo de documento desconhecido.")
        doc.tipo = tipo
    if nome is not None and nome.strip():
        doc.nome = nome.strip()[:200]
    if limpar_validade:
        doc.validade = None
    elif validade is not None:
        doc.validade = validade
    db.flush()
    return doc


def apagar(db: Session, documento_id: uuid.UUID) -> None:
    db.delete(_do_id(db, documento_id))
    db.flush()


def abrir(db: Session, documento_id: uuid.UUID, usuario: Usuario, papel: str, baixar: bool) -> DocumentoEmpresa:
    doc = _do_id(db, documento_id)
    _registrar(db, doc, usuario, papel, "baixou" if baixar else "abriu")
    db.flush()
    return doc


def _para_dict(doc: DocumentoEmpresa) -> dict:
    return {
        "id": str(doc.id), "tipo": doc.tipo, "tipo_rotulo": TIPOS.get(doc.tipo, doc.tipo), "nome": doc.nome,
        "nome_arquivo": doc.nome_arquivo, "tamanho": doc.tamanho, "validade": doc.validade.isoformat() if doc.validade else None,
        "situacao": situacao(doc.validade), "enviado_por": doc.enviado_por_email, "papel": doc.papel,
        "enviado_em": doc.criado_em.isoformat() if doc.criado_em else None,
        "substituido_em": doc.substituido_em.isoformat() if doc.substituido_em else None,
    }


def listar(db: Session, prestador_id: uuid.UUID) -> list[dict]:
    docs = db.query(DocumentoEmpresa).filter(DocumentoEmpresa.prestador_id == prestador_id).order_by(DocumentoEmpresa.tipo, DocumentoEmpresa.nome).all()
    return [_para_dict(d) for d in docs]


def acessos(db: Session, documento_id: uuid.UUID) -> list[dict]:
    _do_id(db, documento_id)
    linhas = db.query(DocumentoAcesso).filter(DocumentoAcesso.documento_id == documento_id).order_by(DocumentoAcesso.criado_em.desc()).limit(200).all()
    return [{"email": a.email, "papel": a.papel, "acao": a.acao, "em": a.criado_em.isoformat() if a.criado_em else None} for a in linhas]


def contadores_sem_permissao(db: Session, prestador_id: uuid.UUID) -> list[str]:
    """Pro dono: contadores ativos que ainda não podem ver os documentos (os de
    antes desta versão começam sem a permissão)."""
    return [a.email for a in db.query(AcessoContador).filter_by(prestador_id=prestador_id, status="ativo").all()
            if PERMISSAO not in (a.permissoes or [])]


def avisos_de_validade(db: Session, prestador_id: uuid.UUID, hoje: datetime.date | None = None) -> list[dict]:
    """Documentos vencendo (30 dias) ou vencidos — "Precisa da sua atenção" e painel do contador."""
    hoje = hoje or hoje_br()
    limite = hoje + datetime.timedelta(days=DIAS_AVISO)
    docs = db.query(DocumentoEmpresa.nome, DocumentoEmpresa.validade).filter(
        DocumentoEmpresa.prestador_id == prestador_id, DocumentoEmpresa.validade.isnot(None), DocumentoEmpresa.validade <= limite,
    ).order_by(DocumentoEmpresa.validade).all()
    saida = []
    for nome, validade in docs:
        dias = (validade - hoje).days
        saida.append({"nome": nome, "validade": validade.isoformat(), "vencido": dias < 0, "dias": dias})
    return saida


def resumo_gestao(db: Session, prestador_id: uuid.UUID) -> dict:
    """O máximo que a Gestão vê: quantos e quanto espaço (nunca o conteúdo)."""
    n, total = db.query(func.count(DocumentoEmpresa.id), func.coalesce(func.sum(DocumentoEmpresa.tamanho), 0)).filter(
        DocumentoEmpresa.prestador_id == prestador_id).one()
    return {"quantidade": int(n or 0), "bytes": int(total or 0)}
