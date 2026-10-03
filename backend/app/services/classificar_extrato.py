"""Classificação das linhas do extrato (03/10/2026) — pedido do Marcos depois
de importar o primeiro extrato de verdade: "depois que relacionar uma vez as
próximas já venham relacionando", "o Awin está sem categoria", "tenho que
poder escolher entre receita e despesa".

Pra cada transação lida do extrato (app/services/extrato_pdf.py) devolve uma
SUGESTÃO — a pessoa sempre revisa na tela antes de gravar:

1. regra lembrada: a mesma descrição já foi classificada antes (tabela
   `regra_extrato`, gravada na confirmação);
2. nome/CNPJ do tomador na descrição — e, quando dois tomadores batem (AWIN e
   AWIN Rchlo têm o mesmo CNPJ), desempata pela nota em aberto do mesmo valor;
3. sem nome nenhum: uma única nota em aberto com exatamente aquele valor.

A competência sugerida é a da nota que o dinheiro está pagando (é assim que o
"a receber" dá baixa), não o mês em que caiu.
"""
import re
import unicodedata
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Despesa, DespesaRecorrente, PagamentoRecebido, Prestador, PrestadorTomador, RegraExtrato
from app.services import a_receber
from app.services.importar_adn import _apelido_livre, criar_tomador_interno

CATEGORIAS_PADRAO = (
    "Tarifas bancárias", "Simples Nacional", "INSS", "Pró-labore", "Contador", "Ferramentas e anúncios", "Outras despesas",
)

# Palavras que aparecem em qualquer linha de extrato e não identificam ninguém.
_GENERICAS = {
    "pix", "ted", "doc", "tef", "transferencia", "transf", "recebida", "recebido", "recebimento", "enviada", "enviado",
    "pagamento", "pagto", "pgto", "pago", "compra", "debito", "credito", "boleto", "titulo", "cobranca", "conta",
    "para", "por", "com", "dos", "das", "ltda", "eireli", "mei", "epp", "banco", "the", "and",
}


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def chave_da_descricao(descricao: str) -> str:
    """O que identifica "o mesmo lançamento do mês que vem": só as palavras
    (números mudam — data, protocolo, valor), sem as genéricas. Vazia quando
    a descrição não diz de quem é ("Pix recebido" puro): aí não há o que
    lembrar."""
    palavras = [p for p in re.findall(r"[a-z]{3,}", _sem_acento(descricao)) if p not in _GENERICAS]
    return " ".join(palavras[:8])[:160]


def categoria_sugerida(descricao: str) -> str:
    d = _sem_acento(descricao)
    if re.search(r"tarifa|pacote de servico|anuidade|manutencao conta|\biof\b", d):
        return "Tarifas bancárias"
    if re.search(r"\bdas\b|simples nacional|receita federal|darf", d):
        return "Simples Nacional"
    if re.search(r"\binss\b|\bgps\b", d):
        return "INSS"
    if re.search(r"pro.?labore", d):
        return "Pró-labore"
    if re.search(r"contab|contador", d):
        return "Contador"
    if re.search(r"google|meta\b|facebook|\bads\b|hotmart|canva|chatgpt|openai", d):
        return "Ferramentas e anúncios"
    return "Outras despesas"


def categorias(db: Session) -> dict:
    """Categorias que a conta já usa (despesas lançadas e contas fixas) mais
    as de fábrica — pra tela oferecer numa lista em vez de texto solto."""
    usadas: dict[str, set[str]] = {"despesa": set(), "retirada": set()}
    for tipo, categoria in db.query(Despesa.tipo, Despesa.categoria).distinct():
        usadas.setdefault(tipo, set()).add(categoria)
    for tipo, categoria in db.query(DespesaRecorrente.tipo, DespesaRecorrente.categoria).distinct():
        usadas.setdefault(tipo, set()).add(categoria)
    despesas = sorted(usadas["despesa"] | set(CATEGORIAS_PADRAO) - usadas["retirada"], key=_sem_acento)
    return {"despesas": despesas, "retiradas": sorted(usadas["retirada"], key=_sem_acento)}


def _candidatos_por_nome(descricao: str, vinculos: list[PrestadorTomador]) -> list[PrestadorTomador]:
    alvo = _sem_acento(descricao)
    digitos = re.sub(r"\D", "", descricao)
    por_cnpj = [
        v for v in vinculos
        if v.tomador is not None and v.tomador.cnpj.isdigit() and len(v.tomador.cnpj) == 14 and v.tomador.cnpj in digitos
    ]
    if por_cnpj:
        return por_cnpj
    achados = []
    for v in vinculos:
        apelido = _sem_acento(v.apelido)
        # "Magalu (Magazine Luiza)": o apelido inteiro quase nunca aparece no
        # extrato — vale cada pedaço (fora e dentro dos parênteses).
        pedacos = [p.strip() for p in re.split(r"[()/,]", apelido) if len(p.strip()) >= 4]
        if any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", alvo) for p in pedacos):
            achados.append(v)
            continue
        razao = _sem_acento(v.tomador.razao_social) if v.tomador is not None else ""
        forte = next((p for p in re.findall(r"[a-z]{4,}", razao) if p not in _GENERICAS), None)
        if forte and re.search(rf"(?<![a-z]){re.escape(forte)}(?![a-z])", alvo):
            achados.append(v)
    return achados


def sugerir(db: Session, transacoes: list) -> list[dict]:
    """Uma sugestão por transação, na mesma ordem. Não grava nada."""
    vinculos = (
        db.query(PrestadorTomador)
        .filter(PrestadorTomador.ativo.is_(True), PrestadorTomador.excluido_em.is_(None))
        .all()
    )
    por_id = {v.id: v for v in vinculos}
    regras = {r.chave: r for r in db.query(RegraExtrato)}
    abertas = a_receber.notas_em_aberto(db)
    abertas_por_vinculo: dict[uuid.UUID, list[dict]] = {}
    for g in abertas:
        abertas_por_vinculo.setdefault(g["vinculo_id"], []).append(g)

    # Reimportar o mesmo extrato não deve dobrar nada: o que já existe com o
    # mesmo valor na mesma data vem desmarcado.
    datas = [t.data for t in transacoes if t.data]
    recebidos, pagos = set(), set()
    if datas:
        recebidos = {
            (d, Decimal(v)) for d, v in db.query(PagamentoRecebido.data_recebimento, PagamentoRecebido.valor)
            .filter(PagamentoRecebido.data_recebimento.between(min(datas), max(datas)))
        }
        pagos = {
            (d, Decimal(v)) for d, v in db.query(Despesa.pago_em, Despesa.valor)
            .filter(Despesa.origem == "extrato", Despesa.pago_em.between(min(datas), max(datas)))
        }

    saida = []
    sugeridas: set[uuid.UUID] = set()
    for t in transacoes:
        valor = Decimal(t.valor).quantize(Decimal("0.01"))
        mes = f"{t.data.year:04d}-{t.data.month:02d}" if t.data else None
        credito, vinculo, origem = t.credito, None, None
        categoria, tipo_despesa = categoria_sugerida(t.descricao), "despesa"

        chave = chave_da_descricao(t.descricao)
        regra = regras.get(chave) if chave else None
        if regra is not None:
            credito, origem = regra.credito, "lembrado"
            if regra.credito:
                vinculo = por_id.get(regra.prestador_tomador_id)
            elif regra.categoria:
                categoria, tipo_despesa = regra.categoria, regra.tipo
        if vinculo is None and credito:
            candidatos = _candidatos_por_nome(t.descricao, vinculos)
            if len(candidatos) > 1:
                exatos = [v for v in candidatos if any(abs(Decimal(str(g["valor"])) - valor) < Decimal("0.005") for g in abertas_por_vinculo.get(v.id, []))]
                candidatos = exatos if len(exatos) == 1 else []
            if len(candidatos) == 1:
                vinculo, origem = candidatos[0], origem or "nome"
            elif not candidatos:
                exatas = [g for g in abertas if abs(Decimal(str(g["valor"])) - valor) < Decimal("0.005") and g["vinculo_id"] in por_id]
                if len(exatas) == 1:
                    vinculo, origem = por_id[exatas[0]["vinculo_id"]], origem or "valor"

        competencia, nota = mes, None
        if vinculo is not None:
            # Cada nota em aberto só é sugerida pra UMA linha do extrato.
            do_vinculo = [
                g for g in abertas_por_vinculo.get(vinculo.id, [])
                if (mes is None or g["competencia"] <= mes) and g["emissao_id"] not in sugeridas
            ]
            exata = next((g for g in do_vinculo if abs(Decimal(str(g["valor"])) - valor) < Decimal("0.005")), None)
            alvo = exata or (do_vinculo[0] if len(do_vinculo) == 1 else None)
            if alvo is not None:
                sugeridas.add(alvo["emissao_id"])
                competencia = alvo["competencia"]
                nota = {
                    "emissao_id": alvo["emissao_id"], "competencia": alvo["competencia"], "valor": float(alvo["valor"]),
                    "exata": exata is not None,
                }

        saida.append({
            "chave": chave,
            "credito": credito,
            "vinculo_id": vinculo.id if vinculo is not None else None,
            "competencia": competencia,
            "emissao_id": nota["emissao_id"] if nota else None,
            "categoria": categoria,
            "tipo_despesa": tipo_despesa,
            "origem_sugestao": origem,
            "nota": nota,
            "ja_lancado": bool(t.data) and (t.data, valor) in (recebidos if credito else pagos),
        })
    return saida


def notas_para_escolher(db: Session) -> list[dict]:
    """Notas em aberto, pra tela do extrato oferecer "qual nota esse dinheiro
    paga" depois que a pessoa escolhe o tomador."""
    return [
        {"emissao_id": g["emissao_id"], "vinculo_id": g["vinculo_id"], "competencia": g["competencia"],
         "valor": g["valor"], "n_dps": g["n_dps"]}
        for g in a_receber.notas_em_aberto(db)
    ]


def lembrar(
    db: Session, prestador_id: uuid.UUID, descricao: str | None, *, credito: bool,
    vinculo_id: uuid.UUID | None = None, categoria: str | None = None, tipo: str = "despesa",
) -> None:
    chave = chave_da_descricao(descricao or "")
    if not chave:
        return
    regra = db.query(RegraExtrato).filter(RegraExtrato.chave == chave).one_or_none()
    if regra is None:
        regra = RegraExtrato(id=uuid.uuid4(), prestador_id=prestador_id, chave=chave, credito=credito)
        db.add(regra)
    regra.credito = credito
    regra.prestador_tomador_id = vinculo_id if credito else None
    regra.categoria = None if credito else (categoria or "")[:100] or None
    regra.tipo = "despesa" if credito else tipo
    regra.atualizado_em = func.now()
    db.flush()


def criar_fonte(db: Session, prestador: Prestador, nome: str) -> PrestadorTomador:
    """Tomador criado direto da tela do extrato: entra só pra controle (sem
    nota) — pra emitir nota pra ele, o cadastro completo é em Tomadores."""
    nome = re.sub(r"\s+", " ", nome).strip()
    existente = (
        db.query(PrestadorTomador)
        .filter(func.lower(PrestadorTomador.apelido) == nome.lower(), PrestadorTomador.excluido_em.is_(None))
        .first()
    )
    if existente is not None:
        return existente
    tomador = criar_tomador_interno(db, nome, prestador.cod_municipio)
    vinculo = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador.id, tomador_id=tomador.id, apelido=_apelido_livre(db, prestador.id, nome),
        cod_local_prestacao=prestador.cod_municipio, cod_trib_nacional="000000", template_descricao=nome[:200],
        ativo=True, sem_nota=True,
    )
    db.add(vinculo)
    db.flush()
    return vinculo


def registrar_saida(
    db: Session, prestador_id: uuid.UUID, *, categoria: str, competencia: str, valor: float,
    descricao: str | None = None, data: date | None = None, tipo: str = "despesa",
) -> Despesa:
    despesa = Despesa(
        id=uuid.uuid4(), prestador_id=prestador_id, categoria=categoria.strip()[:100], competencia=competencia, valor=valor,
        descricao=(descricao or "").strip()[:200] or None, tipo=tipo, pago=True, pago_em=data, origem="extrato",
    )
    db.add(despesa)
    db.flush()
    return despesa
