"""Pasta do mês (08/10/2026): a empresa e o contador se organizam aqui.

"Como poderíamos fazer para o contador e o cliente se falarem e trocarem
arquivos — organizando arquivos que o contador precisa mensalmente, exemplo o
extrato que ele já vai carregar ou ainda as notas tomadas ou qualquer outra
coisa que o contador peça" + "seria interessante se tivesse tipo um chat".

- **Pedidos** (`PastaPedido`): a lista do que o contador precisa todo mês.
  Qualquer um dos dois monta; vale pra todos os meses até ser tirado.
- **Arquivos** (`PastaArquivo`): o que foi enviado em cada mês, ligado a um
  pedido ou avulso. Nesta fase de teste o arquivo fica no próprio banco
  (`LIMITE_ARQUIVO`, `LIMITE_EMPRESA`); se crescer, vai pra um armazenamento
  de arquivos (bucket) sem mudar a tela.
- **Marcas** (`PastaMarca`): "não teve neste mês" (empresa) e "conferido"
  (contador).
- **Conversa** (`PastaMensagem`): uma por empresa, cada mensagem lembra o mês.
- O pedido do tipo "extrato" conta como entregue sozinho quando o mês tem
  extrato importado no Financeiro (evento `extrato_do_mes`, app/eventos.py).

Tudo aqui supõe o contexto da RLS já na empresa certa.
"""
from __future__ import annotations

import datetime
import re
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import eventos
from app.models import PastaArquivo, PastaLeitura, PastaMarca, PastaMensagem, PastaPedido, Usuario
from app.tempo import hoje as hoje_br

LIMITE_ARQUIVO = 15 * 1024 * 1024  # 15 MB por arquivo
LIMITE_EMPRESA = 300 * 1024 * 1024  # 300 MB por empresa, nesta fase
LIMITE_TEXTO = 4000

EXTENSOES = {
    "pdf", "png", "jpg", "jpeg", "webp", "heic", "xml", "csv", "txt", "ofx", "xls", "xlsx", "ods", "doc", "docx", "odt", "zip",
}

SUGESTOES = [
    {"titulo": "Extrato do banco", "descricao": "O extrato do mês da conta da empresa (PDF ou OFX).", "tipo": "extrato"},
    {"titulo": "Notas fiscais de serviços tomados", "descricao": "As notas que a empresa recebeu de quem prestou serviço pra ela.", "tipo": "arquivo"},
    {"titulo": "Comprovantes de pagamento", "descricao": "DAS, guias e outros impostos pagos no mês.", "tipo": "arquivo"},
]


class PastaError(Exception):
    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


def competencia_padrao(hoje: datetime.date | None = None) -> str:
    """O mês que o contador está fechando: o anterior."""
    hoje = hoje or hoje_br()
    primeiro = hoje.replace(day=1) - datetime.timedelta(days=1)
    return f"{primeiro.year:04d}-{primeiro.month:02d}"


def validar_competencia(competencia: str | None) -> str:
    if not competencia:
        return competencia_padrao()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise PastaError("O mês tem que estar no formato AAAA-MM.")
    return competencia


def _limpo(texto: str | None, limite: int) -> str:
    return re.sub(r"\s+", " ", (texto or "")).strip()[:limite]


# --- pedidos -------------------------------------------------------------------


def pedidos(db: Session) -> list[PastaPedido]:
    return db.query(PastaPedido).filter(PastaPedido.ativo.is_(True)).order_by(PastaPedido.ordem, PastaPedido.criado_em).all()


def criar_pedido(db: Session, prestador_id: uuid.UUID, usuario: Usuario, *, titulo: str, descricao: str | None = None, tipo: str = "arquivo") -> PastaPedido:
    titulo = _limpo(titulo, 120)
    if len(titulo) < 2:
        raise PastaError("Escreva o que precisa ser enviado (ex.: “Extrato do banco”).")
    if tipo not in ("arquivo", "extrato"):
        tipo = "arquivo"
    if tipo == "extrato" and db.query(PastaPedido.id).filter(PastaPedido.ativo.is_(True), PastaPedido.tipo == "extrato").first():
        tipo = "arquivo"  # um só pedido de extrato conta sozinho
    proxima = (db.query(func.max(PastaPedido.ordem)).filter(PastaPedido.ativo.is_(True)).scalar() or 0) + 1
    pedido = PastaPedido(
        id=uuid.uuid4(), prestador_id=prestador_id, titulo=titulo, descricao=_limpo(descricao, 300) or None,
        tipo=tipo, ordem=proxima, criado_por=usuario.id,
    )
    db.add(pedido)
    db.flush()
    return pedido


def usar_sugestoes(db: Session, prestador_id: uuid.UUID, usuario: Usuario) -> list[PastaPedido]:
    ja = {p.titulo.lower() for p in pedidos(db)}
    for s in SUGESTOES:
        if s["titulo"].lower() not in ja:
            criar_pedido(db, prestador_id, usuario, **s)
    return pedidos(db)


def _pedido(db: Session, pedido_id: uuid.UUID) -> PastaPedido:
    pedido = db.get(PastaPedido, pedido_id)
    if pedido is None or not pedido.ativo:
        raise PastaError("Esse item não está mais na lista.", 404)
    return pedido


def editar_pedido(db: Session, pedido_id: uuid.UUID, *, titulo: str | None = None, descricao: str | None = None) -> PastaPedido:
    pedido = _pedido(db, pedido_id)
    if titulo is not None:
        novo = _limpo(titulo, 120)
        if len(novo) < 2:
            raise PastaError("Escreva o que precisa ser enviado.")
        pedido.titulo = novo
    if descricao is not None:
        pedido.descricao = _limpo(descricao, 300) or None
    db.flush()
    return pedido


def tirar_pedido(db: Session, pedido_id: uuid.UUID) -> None:
    """Sai da lista dos próximos meses; o que já foi enviado continua nos meses dele."""
    _pedido(db, pedido_id).ativo = False
    db.flush()


# --- o mês ---------------------------------------------------------------------


def _arquivo_para_dict(a: PastaArquivo, nomes: dict) -> dict:
    return {
        "id": a.id, "nome": a.nome, "tamanho": a.tamanho, "tipo_mime": a.tipo_mime, "pedido_id": a.pedido_id,
        "papel": a.papel, "enviado_por": nomes.get(a.enviado_por), "criado_em": a.criado_em,
    }


def _nomes(db: Session, ids: set) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: (u.nome or u.email) for u in db.query(Usuario).filter(Usuario.id.in_(ids))}


def _extrato_do_mes(db: Session, prestador_id: uuid.UUID, competencia: str) -> int:
    respostas = eventos.coletar("extrato_do_mes", db, prestador_id=prestador_id, competencia=competencia)
    return sum(int(r or 0) for r in respostas)


def do_mes(db: Session, prestador_id: uuid.UUID, competencia: str) -> dict:
    lista = pedidos(db)
    arquivos = (
        db.query(PastaArquivo).filter(PastaArquivo.competencia == competencia).order_by(PastaArquivo.criado_em).all()
    )
    marcas = {m.pedido_id: m for m in db.query(PastaMarca).filter(PastaMarca.competencia == competencia)}
    nomes = _nomes(db, {a.enviado_por for a in arquivos} | {m.por for m in marcas.values()})
    por_pedido: dict = {}
    for a in arquivos:
        por_pedido.setdefault(a.pedido_id, []).append(_arquivo_para_dict(a, nomes))
    linhas_extrato = _extrato_do_mes(db, prestador_id, competencia) if any(p.tipo == "extrato" for p in lista) else 0

    itens = []
    for p in lista:
        enviados = por_pedido.get(p.id, [])
        marca = marcas.get(p.id)
        if marca is not None and marca.situacao == "conferido":
            situacao = "conferido"
        elif enviados or (p.tipo == "extrato" and linhas_extrato > 0):
            situacao = "entregue"
        elif marca is not None and marca.situacao == "nao_tem":
            situacao = "nao_tem"
        else:
            situacao = "pendente"
        itens.append({
            "id": p.id, "titulo": p.titulo, "descricao": p.descricao, "tipo": p.tipo, "situacao": situacao,
            "arquivos": enviados, "extrato_linhas": linhas_extrato if p.tipo == "extrato" else None,
            "marcado_por": nomes.get(marca.por) if marca else None,
        })
    avulsos = [a for pid, lista_a in por_pedido.items() if pid is None or pid not in {p.id for p in lista} for a in lista_a]
    pendentes = sum(1 for i in itens if i["situacao"] == "pendente")
    return {
        "competencia": competencia,
        "itens": itens,
        "avulsos": avulsos,
        "resumo": {"itens": len(itens), "pendentes": pendentes, "prontos": len(itens) - pendentes},
        "limite_arquivo": LIMITE_ARQUIVO,
    }


def marcar(db: Session, prestador_id: uuid.UUID, usuario: Usuario, pedido_id: uuid.UUID, competencia: str, situacao: str | None) -> None:
    _pedido(db, pedido_id)
    atual = db.query(PastaMarca).filter_by(pedido_id=pedido_id, competencia=competencia).one_or_none()
    if situacao is None:
        if atual is not None:
            db.delete(atual)
    else:
        if situacao not in ("nao_tem", "conferido"):
            raise PastaError("Marcação desconhecida.")
        if atual is None:
            atual = PastaMarca(id=uuid.uuid4(), prestador_id=prestador_id, pedido_id=pedido_id, competencia=competencia, situacao=situacao)
            db.add(atual)
        atual.situacao, atual.por, atual.em = situacao, usuario.id, datetime.datetime.now(datetime.timezone.utc)
    db.flush()


# --- arquivos ------------------------------------------------------------------


def _nome_seguro(nome: str) -> str:
    base = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", (nome or "").strip()) or "arquivo"
    return base[-200:]


def enviar_arquivo(
    db: Session, prestador_id: uuid.UUID, usuario: Usuario, papel: str, *,
    competencia: str, pedido_id: uuid.UUID | None, nome: str, tipo_mime: str | None, conteudo: bytes,
) -> PastaArquivo:
    if pedido_id is not None:
        _pedido(db, pedido_id)
    nome = _nome_seguro(nome)
    extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if extensao not in EXTENSOES:
        raise PastaError("Esse tipo de arquivo não é aceito aqui. Use PDF, imagem, planilha, XML, OFX, documento ou ZIP.")
    if not conteudo:
        raise PastaError("O arquivo chegou vazio.")
    if len(conteudo) > LIMITE_ARQUIVO:
        raise PastaError(f"Arquivo grande demais: o limite é {LIMITE_ARQUIVO // (1024 * 1024)} MB por arquivo.", 413)
    usado = db.query(func.coalesce(func.sum(PastaArquivo.tamanho), 0)).scalar() or 0
    if usado + len(conteudo) > LIMITE_EMPRESA:
        raise PastaError("A pasta desta empresa está cheia nesta fase de teste. Apague arquivos antigos ou fale com o suporte.", 413)
    arquivo = PastaArquivo(
        id=uuid.uuid4(), prestador_id=prestador_id, competencia=competencia, pedido_id=pedido_id, nome=nome,
        tipo_mime=(tipo_mime or "application/octet-stream")[:100], tamanho=len(conteudo), conteudo=conteudo,
        enviado_por=usuario.id, papel=papel,
    )
    db.add(arquivo)
    db.flush()
    return arquivo


def arquivo(db: Session, arquivo_id: uuid.UUID) -> PastaArquivo:
    achado = db.get(PastaArquivo, arquivo_id)
    if achado is None:
        raise PastaError("Arquivo não encontrado.", 404)
    return achado


def apagar_arquivo(db: Session, arquivo_id: uuid.UUID) -> None:
    db.delete(arquivo(db, arquivo_id))
    db.flush()


# --- conversa ------------------------------------------------------------------


def mensagens(db: Session, limite: int = 300) -> list[dict]:
    lista = db.query(PastaMensagem).order_by(PastaMensagem.criado_em.desc()).limit(limite).all()
    return [
        {"id": m.id, "texto": m.texto, "papel": m.papel, "autor_nome": m.autor_nome, "competencia": m.competencia, "criado_em": m.criado_em}
        for m in reversed(lista)
    ]


def escrever(db: Session, prestador_id: uuid.UUID, usuario: Usuario, papel: str, texto: str, competencia: str | None) -> PastaMensagem:
    texto = (texto or "").strip()
    if not texto:
        raise PastaError("Escreva a mensagem.")
    if len(texto) > LIMITE_TEXTO:
        raise PastaError(f"Mensagem longa demais (até {LIMITE_TEXTO} letras).")
    msg = PastaMensagem(
        id=uuid.uuid4(), prestador_id=prestador_id, competencia=competencia, autor=usuario.id,
        autor_nome=(usuario.nome or usuario.email)[:200], papel=papel, texto=texto,
    )
    db.add(msg)
    db.flush()
    return msg


# --- o que é novo pra quem ------------------------------------------------------


def marcar_lido(db: Session, prestador_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
    agora = datetime.datetime.now(datetime.timezone.utc)
    atual = db.get(PastaLeitura, (prestador_id, usuario_id))
    if atual is None:
        db.add(PastaLeitura(prestador_id=prestador_id, usuario_id=usuario_id, lido_em=agora))
    else:
        atual.lido_em = agora
    db.flush()


def novidades(db: Session, prestador_id: uuid.UUID, usuario_id: uuid.UUID, papel: str) -> dict:
    """Mensagens e arquivos que o OUTRO lado mandou desde a última visita."""
    leitura = db.get(PastaLeitura, (prestador_id, usuario_id))
    desde = leitura.lido_em if leitura else datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    # quem é contador vê o que a empresa mandou, e vice-versa
    lado = "empresa" if papel == "contador" else "contador"
    msgs = db.query(func.count(PastaMensagem.id)).filter(PastaMensagem.papel == lado, PastaMensagem.criado_em > desde).scalar() or 0
    arqs = db.query(func.count(PastaArquivo.id)).filter(PastaArquivo.papel == lado, PastaArquivo.criado_em > desde).scalar() or 0
    return {"mensagens": int(msgs), "arquivos": int(arqs)}


def tem_contador(db: Session, prestador_id: uuid.UUID) -> bool:
    from app.models import AcessoContador

    return db.query(AcessoContador.id).filter_by(prestador_id=prestador_id, status="ativo").first() is not None
