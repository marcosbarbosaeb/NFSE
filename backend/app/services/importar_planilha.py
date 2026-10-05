"""Importar a planilha de controle financeiro (.xlsx) — 28/09/2026.

Formato da planilha "Controle CP" (uma aba, meses em colunas JAN..DEZ):

- bloco "Pagamentos recebidos": uma linha por fonte de receita;
- bloco "NF Geradas": uma linha por tomador (só usado pra descobrir quem
  paga antes da nota — no Mercado Livre e na Amazon o dinheiro cai sem nota
  e a nota do que caiu em janeiro sai em fevereiro);
- bloco "Despesas": uma linha por conta (pró-labore, Simples, ferramentas);
- "Distribuição de lucros ..." / conta: as retiradas;
- um quadro de conferências com X em cada mês (extrato do banco, PayPal...).

A leitura procura os blocos pelo nome da primeira coluna, então aguenta
linhas a mais ou a menos. Nada é gravado na prévia; a importação recebe o
mesmo arquivo de novo junto com as escolhas da tela (qual tomador é cada
linha de receita).
"""
import datetime
import difflib
import io
import re
import unicodedata
import uuid
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import Despesa, DespesaRecorrente, PagamentoRecebido, Prestador, PrestadorTomador, RotinaMensal, RotinaMensalFeita
from app.services.importar_adn import criar_tomador_interno

MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


class PlanilhaInvalidaError(Exception):
    pass


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _chave_nome(texto: str) -> str:
    base = texto.split("(")[0] if "(" in texto and texto.split("(")[0].strip() else texto
    return re.sub(r"[^a-z0-9]", "", _sem_acento(base.lower()))


def _numero(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto or texto in {"-", "–"} or texto.startswith("#"):
        return None
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(Decimal(texto))
    except InvalidOperation:
        return None


def _rotulo(valor) -> str:
    return re.sub(r"\s+", " ", str(valor)).strip() if valor is not None else ""


def _cabecalho_meses(linha) -> dict[int, int] | None:
    """{índice da coluna: mês 1..12} se a linha tiver JAN..DEZ."""
    mapa = {}
    for i, v in enumerate(linha):
        if isinstance(v, str) and v.strip().upper()[:3] in MESES_ABREV:
            mapa[i] = MESES_ABREV.index(v.strip().upper()[:3]) + 1
    return mapa if len(mapa) >= 6 else None


def _valores(linha, colunas: dict[int, int]) -> list[float | None]:
    out: list[float | None] = [None] * 12
    for i, mes in colunas.items():
        out[mes - 1] = _numero(linha[i]) if i < len(linha) else None
    return out


def ler(conteudo: bytes) -> dict:
    try:
        wb = load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 — qualquer arquivo inválido vira a mesma mensagem
        raise PlanilhaInvalidaError("Não consegui abrir o arquivo — envie a planilha em .xlsx.") from exc
    ws = wb.worksheets[0]
    linhas = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()

    blocos: dict[str, list] = {"recebidos": [], "nf": [], "despesas": [], "retiradas": [], "rotinas": []}
    atual, colunas = None, None
    depois_da_margem = False
    for linha in linhas:
        if not any(v is not None for v in linha):
            continue
        rotulo = _rotulo(linha[0])
        chave = _sem_acento(rotulo.lower())
        cab = _cabecalho_meses(linha)
        if cab:
            colunas = cab
            if chave.startswith("pagamen") or "recebid" in chave:
                atual = "recebidos"
            elif chave.startswith("nf") or "nota" in chave:
                atual = "nf"
            elif chave.startswith("despesa"):
                atual = "despesas"
            elif not rotulo:
                atual = "rotinas"
            else:
                atual = None
            continue
        if colunas is None:
            continue
        if chave.startswith("lucro") or chave.startswith("margem"):
            depois_da_margem = chave.startswith("margem") or depois_da_margem
            atual = None
            continue
        if depois_da_margem and atual is None and rotulo and not chave.startswith("total"):
            if "distribui" in chave or "retirada" in chave or len(blocos["retiradas"]) > 0:
                conta = re.sub(r"(?i)distribui[cç][aã]o de lucros?", "", rotulo).strip() or rotulo
                blocos["retiradas"].append({"nome": rotulo, "conta": conta, "valores": _valores(linha, colunas)})
                continue
        if chave.startswith("total"):
            depois_da_margem = False
            continue
        if atual in ("recebidos", "nf", "despesas"):
            if not rotulo:  # linha de total do bloco
                atual = None
                continue
            if rotulo in {"-", "–"}:
                continue
            blocos[atual].append({"nome": rotulo, "valores": _valores(linha, colunas)})
        elif atual == "rotinas":
            if not rotulo or chave.startswith(("dia da", "legenda")):
                atual = None
                continue
            marcas = [
                bool(isinstance(linha[i], str) and linha[i].strip().lower() == "x") if i < len(linha) else False
                for i in sorted(colunas, key=colunas.get)
            ]
            blocos["rotinas"].append({"nome": rotulo, "feitos": [m for m, ok in zip(range(1, 13), marcas) if ok]})
    if not blocos["recebidos"] and not blocos["despesas"]:
        raise PlanilhaInvalidaError("Não achei os blocos de 'Pagamentos recebidos' e 'Despesas' (com os meses JAN..DEZ nas colunas).")
    return blocos


def _parecidos(a: list[float | None], b: list[float | None]) -> bool:
    return a is not None and b is not None and abs(a - b) < 0.02 and abs(a) > 0.009


def deslocamento(pagos: list[float | None], notas: list[float | None]) -> int:
    """0 = nota e pagamento no mesmo mês; 1 = paga antes, nota no mês seguinte."""
    mesmo = sum(1 for m in range(12) if _parecidos(pagos[m], notas[m]))
    seguinte = sum(1 for m in range(11) if _parecidos(pagos[m], notas[m + 1]))
    return 1 if seguinte > mesmo else 0


def _achar_nf(nome: str, nfs: list[dict]) -> dict | None:
    k = _chave_nome(nome)
    completo = re.sub(r"[^a-z0-9]", "", _sem_acento(nome.lower()))
    for nf in nfs:  # igual primeiro ("AWIN Rchlo" não pode cair em "AWIN")
        if re.sub(r"[^a-z0-9]", "", _sem_acento(nf["nome"].lower())) == completo or _chave_nome(nf["nome"]) == k:
            return nf
    candidatos = [nf for nf in nfs if (kn := _chave_nome(nf["nome"])) and k and (kn.startswith(k) or k.startswith(kn))]
    return max(candidatos, key=lambda nf: len(_chave_nome(nf["nome"])), default=None)


def _sugerir_vinculo(nome: str, vinculos: list[PrestadorTomador]) -> PrestadorTomador | None:
    k = _chave_nome(nome)
    completo = re.sub(r"[^a-z0-9]", "", _sem_acento(nome.lower()))
    melhor, nota = None, 0.0
    for v in vinculos:
        for alvo in (v.apelido, v.tomador.razao_social):
            ka = re.sub(r"[^a-z0-9]", "", _sem_acento((alvo or "").lower()))
            if not ka:
                continue
            if ka == completo or ka == k:
                return v
            pontos = difflib.SequenceMatcher(None, k, ka).ratio()
            if k and (ka.startswith(k) or k in ka):
                pontos = max(pontos, 0.85)
            if pontos > nota:
                melhor, nota = v, pontos
    return melhor if nota >= 0.72 else None


def _competencia(ano: int, mes: int) -> str:
    ano += (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return f"{ano:04d}-{mes:02d}"


def _categoria(nome: str) -> str:
    base = nome.split("(")[0].strip() if "(" in nome and nome.split("(")[0].strip() else nome
    return base[:100]


def _recorrente(valores: list[float | None], mes_atual: int) -> tuple[bool, float | None]:
    """Conta fixa = tem valor em pelo menos 3 dos 4 últimos meses até agora.
    Valor padrão só quando os 3 últimos valores são iguais."""
    ate_agora = [v for v in valores[:mes_atual] if v]
    ultimos = [v for v in valores[max(0, mes_atual - 4):mes_atual]]
    fixa = sum(1 for v in ultimos if v) >= 3
    recentes = ate_agora[-3:]
    estavel = len(recentes) >= 2 and max(recentes) <= min(recentes) * 1.1
    return fixa, (ate_agora[-1] if fixa and estavel else None)


def previa(db: Session, conteudo: bytes, ano: int, hoje: datetime.date) -> dict:
    blocos = ler(conteudo)
    vinculos = db.query(PrestadorTomador).all()
    mes_atual = hoje.month if hoje.year == ano else (12 if ano < hoje.year else 0)
    receitas = []
    for i, r in enumerate(blocos["recebidos"]):
        nf = _achar_nf(r["nome"], blocos["nf"])
        desl = deslocamento(r["valores"], nf["valores"]) if nf else 0
        sug = _sugerir_vinculo(r["nome"], vinculos)
        receitas.append({
            "linha": i, "nome": r["nome"], "valores": r["valores"], "total": round(sum(v or 0 for v in r["valores"]), 2),
            "deslocamento": desl, "nf_nome": nf["nome"] if nf else None,
            "acao": "vinculo" if sug else "novo", "vinculo_id": sug.id if sug else None,
        })
    despesas = []
    for r in blocos["despesas"]:
        fixa, padrao = _recorrente(r["valores"], mes_atual)
        despesas.append({
            "nome": r["nome"], "categoria": _categoria(r["nome"]), "valores": r["valores"],
            "total": round(sum(v or 0 for v in r["valores"]), 2), "recorrente": fixa, "valor_padrao": padrao,
        })
    return {
        "ano": ano,
        "receitas": receitas,
        "despesas": despesas,
        "retiradas": [{**r, "total": round(sum(v or 0 for v in r["valores"]), 2)} for r in blocos["retiradas"]],
        "rotinas": blocos["rotinas"],
        "notas_na_planilha": len(blocos["nf"]),
    }


def importar(db: Session, prestador: Prestador, conteudo: bytes, ano: int, escolhas: dict, hoje: datetime.date) -> dict:
    """`escolhas`: {receitas: [{linha, acao: vinculo|novo|ignorar, vinculo_id?, deslocamento}],
    despesas: bool, recorrentes: bool, retiradas: bool, rotinas: bool}."""
    dados = previa(db, conteudo, ano, hoje)
    competencia_hoje = f"{hoje.year:04d}-{hoje.month:02d}"
    res = {"pagamentos": 0, "pagamentos_existentes": 0, "tomadores_criados": 0, "despesas": 0, "contas_fixas": 0,
           "retiradas": 0, "rotinas": 0, "avisos": []}
    por_linha = {int(e["linha"]): e for e in escolhas.get("receitas", [])}
    # O que já existia antes desta importação (reimportar não duplica). Várias
    # linhas da planilha podem ir pro mesmo tomador (Lancôme, Kérastase e YSL
    # são todas da +Tec): aí os valores do mês se somam.
    preexistentes = {(v, c) for v, c in db.query(PagamentoRecebido.prestador_tomador_id, PagamentoRecebido.competencia)}

    for r in dados["receitas"]:
        e = por_linha.get(r["linha"])
        if e is None or e.get("acao") == "ignorar":
            continue
        existente = (
            db.query(PrestadorTomador).filter(PrestadorTomador.apelido == r["nome"][:100], PrestadorTomador.sem_nota.is_(True)).first()
            if e["acao"] == "novo" else None
        )
        if existente is not None:
            vinculo = existente
        elif e["acao"] == "novo":
            tomador = criar_tomador_interno(db, r["nome"], prestador.cod_municipio)
            vinculo = PrestadorTomador(
                id=uuid.uuid4(), prestador_id=prestador.id, tomador_id=tomador.id, apelido=_apelido_livre(db, prestador.id, r["nome"]),
                cod_local_prestacao=prestador.cod_municipio, cod_trib_nacional="000000", template_descricao=r["nome"],
                ativo=True, sem_nota=True,
            )
            db.add(vinculo)
            db.flush()
            res["tomadores_criados"] += 1
        else:
            vinculo = db.get(PrestadorTomador, uuid.UUID(str(e.get("vinculo_id"))))
            if vinculo is None:
                res["avisos"].append(f"{r['nome']}: tomador escolhido não existe — linha pulada.")
                continue
        # 1 = paga antes da nota (Mercado Livre, Amazon): o que caiu em janeiro
        # é a nota de fevereiro — o pagamento entra no mês da nota, pra bater.
        desl = int(e.get("deslocamento", r["deslocamento"]) or 0)
        for mes, valor in enumerate(r["valores"], start=1):
            if not valor or valor <= 0:
                continue
            competencia = _competencia(ano, mes + desl)
            if (vinculo.id, competencia) in preexistentes:
                res["pagamentos_existentes"] += 1
                continue
            db.add(PagamentoRecebido(
                id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=prestador.id, competencia=competencia,
                valor=Decimal(str(round(valor, 2))), origem="planilha", mes_inteiro=True,
            ))
            res["pagamentos"] += 1
    db.flush()

    if escolhas.get("despesas", True):
        existentes = {
            (c, comp, round(float(v), 2)) for c, comp, v in
            db.query(Despesa.categoria, Despesa.competencia, Despesa.valor).filter(Despesa.competencia.like(f"{ano}-%"))
        }
        for d in dados["despesas"]:
            recorrente = None
            if escolhas.get("recorrentes", True) and d["recorrente"]:
                recorrente = db.query(DespesaRecorrente).filter(DespesaRecorrente.nome == d["nome"][:120]).one_or_none()
                if recorrente is None:
                    recorrente = DespesaRecorrente(
                        id=uuid.uuid4(), prestador_id=prestador.id, nome=d["nome"][:120], categoria=d["categoria"],
                        valor_padrao=Decimal(str(d["valor_padrao"])) if d["valor_padrao"] else None, ordem=res["contas_fixas"],
                    )
                    db.add(recorrente)
                    db.flush()
                    res["contas_fixas"] += 1
            for mes, valor in enumerate(d["valores"], start=1):
                if not valor or valor <= 0:
                    continue
                competencia = _competencia(ano, mes)
                if (d["categoria"], competencia, round(valor, 2)) in existentes:
                    continue
                if recorrente is not None and db.query(Despesa.id).filter_by(recorrente_id=recorrente.id, competencia=competencia).first():
                    continue
                futura = competencia > competencia_hoje
                db.add(Despesa(
                    id=uuid.uuid4(), prestador_id=prestador.id, categoria=d["categoria"], descricao=d["nome"][:200],
                    competencia=competencia, valor=Decimal(str(round(valor, 2))), tipo="despesa",
                    pago=not futura, recorrente_id=recorrente.id if recorrente else None, origem="planilha",
                ))
                existentes.add((d["categoria"], competencia, round(valor, 2)))
                res["despesas"] += 1
        db.flush()

    if escolhas.get("retiradas", True):
        for r in dados["retiradas"]:
            for mes, valor in enumerate(r["valores"], start=1):
                if not valor or valor <= 0:
                    continue
                competencia = _competencia(ano, mes)
                if db.query(Despesa.id).filter_by(tipo="retirada", competencia=competencia, conta=r["conta"][:60], valor=Decimal(str(round(valor, 2)))).first():
                    continue
                db.add(Despesa(
                    id=uuid.uuid4(), prestador_id=prestador.id, categoria="Distribuição de lucros", descricao=r["nome"][:200],
                    competencia=competencia, valor=Decimal(str(round(valor, 2))), tipo="retirada", conta=r["conta"][:60],
                    pago=True, origem="planilha",
                ))
                res["retiradas"] += 1
        db.flush()

    if escolhas.get("rotinas", True):
        for r in dados["rotinas"]:
            rotina = db.query(RotinaMensal).filter(RotinaMensal.nome == r["nome"][:120]).one_or_none()
            if rotina is None:
                rotina = RotinaMensal(id=uuid.uuid4(), prestador_id=prestador.id, nome=r["nome"][:120], ordem=res["rotinas"])
                db.add(rotina)
                db.flush()
                res["rotinas"] += 1
            feitas = {c for (c,) in db.query(RotinaMensalFeita.competencia).filter_by(rotina_id=rotina.id)}
            for mes in r["feitos"]:
                competencia = _competencia(ano, mes)
                if competencia not in feitas:
                    db.add(RotinaMensalFeita(id=uuid.uuid4(), prestador_id=prestador.id, rotina_id=rotina.id, competencia=competencia))
        db.flush()
    return res


def _apelido_livre(db: Session, prestador_id: uuid.UUID, nome: str) -> str:
    from app.services.importar_adn import _apelido_livre as livre

    return livre(db, prestador_id, nome)
