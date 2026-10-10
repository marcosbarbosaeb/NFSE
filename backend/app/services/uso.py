"""Uso da plataforma (08/10/2026).

Pergunta do Marcos: "você conseguiria rastrear a atividade do usuário na
plataforma, de forma futura sugerir melhorias?". O sistema anota, sem
conteúdo nenhum:

- **tela**: a página que a pessoa abriu (o painel avisa em `POST /api/uso/tela`);
- **acao**: toda chamada que muda algo e deu certo (anotada sozinha no
  middleware de `app/main.py` — "POST /api/dps/{emissao_id}/assinar");
- **erro**: toda chamada recusada (4xx/5xx), com o código.

Identificadores (id de nota, de tomador...) nunca entram: o nome é o MODELO
da rota. A Gestão lê os números em `painel()`; `sugestoes()` aponta onde
olhar primeiro. Contas de simulação não são anotadas. Guarda 180 dias.
"""
from __future__ import annotations

import datetime
import logging
import re
import uuid

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import EventoUso, Usuario

logger = logging.getLogger("agenteana.uso")

DIAS_GUARDADOS = 180
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_NUMERO_LONGO = re.compile(r"/\d{3,}(?=/|$)")
# Rotas que não dizem nada sobre o uso (ou são o próprio registro).
_FORA = re.compile(r"/api/(uso/|auth/|webhooks/|conta/(novidades-vistas|preferencias)|cep/buscar|versao)")

# Como a Gestão chama cada tela.
TELAS = {
    "/app": "Visão geral", "/app/nfse": "NFS-e (lista)", "/app/nfse/lote": "Notas em lote", "/app/nfse/:id": "Nota (detalhe)",
    "/app/tomadores": "Tomadores", "/app/tomadores/novo": "Novo tomador", "/app/tomadores/:id": "Tomador (cadastro)",
    "/app/calendario": "Calendário", "/app/financeiro": "Financeiro (painel)", "/app/financeiro/conciliacao": "Conciliação",
    "/app/financeiro/clientes": "Clientes do financeiro", "/app/empresa": "Empresa", "/app/conta": "Minha conta",
    "/app/atendimentos": "Painel do contador", "/app/ajuda": "Ajuda", "/app/documentos": "Documentos da empresa", "/app/pasta": "Pasta do mês", "/app/novidades": "Novidades", "/app/gestao": "Gestão",
}


def normalizar_tela(caminho: str) -> str | None:
    """"/app/nfse/<uuid>?x=1" -> "/app/nfse/:id". Mantém só `?aba=` (qual aba
    da tela) — o resto da consulta pode carregar dado."""
    caminho = (caminho or "").strip()
    if not caminho.startswith("/app") or len(caminho) > 300:
        return None
    base, _, consulta = caminho.partition("?")
    base = _NUMERO_LONGO.sub("/:id", _UUID.sub(":id", base)).rstrip("/") or "/app"
    aba = re.search(r"(?:^|&)aba=([a-z0-9_-]{1,30})(?:&|$)", consulta)
    return (f"{base}?aba={aba.group(1)}" if aba else base)[:120]


def interessa(metodo: str, caminho: str, status: int) -> str | None:
    """"acao", "erro" ou None (não anota). GET que deu certo é leitura: não
    entra (as telas já contam isso); 401 é sessão vencida, não erro de uso."""
    if not caminho.startswith("/api/") or _FORA.match(caminho):
        return None
    if status >= 400:
        return None if status == 401 else "erro"
    return None if metodo.upper() in ("GET", "HEAD", "OPTIONS") else "acao"


def gravar(usuario_id: str | uuid.UUID | None, prestador_id: str | uuid.UUID | None, tipo: str, nome: str, detalhe: str | None = None) -> None:
    """Anota um evento numa transação própria. Nunca levanta: estatística não
    pode derrubar a ação da pessoa."""
    from app.database import SessionLocal
    from app.services.demo import eh_email_demo

    if not usuario_id:
        return
    try:
        with SessionLocal() as db:
            uid = uuid.UUID(str(usuario_id))
            email = db.query(Usuario.email).filter(Usuario.id == uid).scalar()
            if email is None or eh_email_demo(email):
                return
            db.add(EventoUso(
                id=uuid.uuid4(), usuario_id=uid, prestador_id=uuid.UUID(str(prestador_id)) if prestador_id else None,
                tipo=tipo, nome=nome[:120], detalhe=(detalhe or None) and str(detalhe)[:60],
            ))
            db.commit()
    except Exception:  # noqa: BLE001
        logger.debug("Não deu pra anotar o uso (%s %s)", tipo, nome, exc_info=True)


def limpar_antigos(db: Session) -> int:
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DIAS_GUARDADOS)
    return db.query(EventoUso).filter(EventoUso.criado_em < limite).delete(synchronize_session=False)


def _nome_da_acao(nome: str) -> str:
    """"POST /api/dps/{emissao_id}/assinar" -> "Assinou uma nota" (o mesmo
    título que o histórico do contador usa), ou o próprio nome."""
    from app.services import acesso

    metodo, _, caminho = nome.partition(" ")
    rotulo = acesso.classificar(metodo, re.sub(r"\{[^}]+\}", "x", caminho))[1]
    return rotulo or nome.replace("/api", "")


def _nome_da_tela(nome: str) -> str:
    base, _, aba = nome.partition("?aba=")
    titulo = TELAS.get(base, base)
    return f"{titulo} › aba {aba}" if aba else titulo


def painel(db: Session, dias: int = 30) -> dict:
    """O que a Gestão vê: telas, ações e erros dos últimos `dias`, com
    quantas vezes e por quantas pessoas."""
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
    linhas = db.execute(text("""
        SELECT tipo, nome, coalesce(detalhe, '') AS detalhe, count(*) AS vezes, count(DISTINCT usuario_id) AS pessoas,
               count(DISTINCT prestador_id) AS empresas, max(criado_em) AS ultima
        FROM evento_uso WHERE criado_em >= :desde
        GROUP BY tipo, nome, coalesce(detalhe, '') ORDER BY vezes DESC
    """), {"desde": desde}).mappings().all()
    telas, acoes, erros, ia = [], {}, [], []
    for l in linhas:
        if l["tipo"] == "ia":
            ia.append({"titulo": l["nome"], "vezes": l["vezes"], "pessoas": l["pessoas"]})
        elif l["tipo"] == "tela":
            telas.append({"nome": l["nome"], "titulo": _nome_da_tela(l["nome"]), "vezes": l["vezes"], "pessoas": l["pessoas"]})
        elif l["tipo"] == "acao":
            # rotas diferentes com o mesmo título ("Enviou uma nota por e-mail") somam
            titulo = _nome_da_acao(l["nome"])
            a = acoes.setdefault(titulo, {"titulo": titulo, "vezes": 0, "pessoas": 0, "rotas": []})
            a["vezes"] += l["vezes"]
            a["pessoas"] = max(a["pessoas"], l["pessoas"])
            a["rotas"].append(l["nome"])
        else:
            erros.append({
                "nome": l["nome"], "titulo": _nome_da_acao(l["nome"]), "status": l["detalhe"], "vezes": l["vezes"],
                "pessoas": l["pessoas"], "ultima": l["ultima"].isoformat() if l["ultima"] else None,
            })
    total, pessoas = db.query(func.count(EventoUso.id), func.count(func.distinct(EventoUso.usuario_id))).filter(EventoUso.criado_em >= desde).one()
    return {
        "dias": dias, "eventos": int(total or 0), "pessoas": int(pessoas or 0),
        "telas": telas[:40], "acoes": sorted(acoes.values(), key=lambda a: -a["vezes"])[:40], "erros": erros[:30], "ia_eventos": ia[:20],
        "telas_sem_visita": [{"nome": n, "titulo": t} for n, t in TELAS.items() if n not in {x["nome"].partition("?")[0] for x in telas} and ":id" not in n and n != "/app/gestao"],
    }


def funil(contas: list[dict]) -> list[dict]:
    """Da conta criada até a primeira nota: onde as pessoas param. Sai das
    contas que a Gestão já lista (não precisa de evento nenhum)."""
    reais = [c for c in contas if not c["demo"] and not c.get("so_contador") and "emissor" in (c.get("modulos") or [])]
    etapas = [
        ("Criaram a conta", lambda c: True),
        ("Confirmaram o e-mail", lambda c: c["email_confirmado"]),
        ("Entraram no painel", lambda c: c["ultimo_acesso"] is not None),
        ("Enviaram o certificado", lambda c: c["certificado"] != "falta"),
        ("Cadastraram um tomador", lambda c: c["tomadores"] > 0),
        ("Emitiram a primeira nota", lambda c: c["notas_total"] > 0),
    ]
    saida, restantes = [], reais
    for titulo, vale in etapas:
        restantes = [c for c in restantes if vale(c)]
        saida.append({"etapa": titulo, "contas": len(restantes)})
    return saida


def sugestoes(uso: dict, etapas: list[dict]) -> list[dict]:
    """Onde olhar primeiro — regras simples em cima dos números."""
    dicas: list[dict] = []
    # a maior queda do funil
    quedas = [(etapas[i - 1]["contas"] - etapas[i]["contas"], i) for i in range(1, len(etapas)) if etapas[i - 1]["contas"] > 0]
    if quedas:
        perdeu, i = max(quedas)
        if perdeu > 0:
            antes = etapas[i - 1]["contas"]
            dicas.append({
                "tipo": "funil", "titulo": f"{perdeu} de {antes} conta{'s' if antes != 1 else ''} param antes de “{etapas[i]['etapa'].lower()}”",
                "texto": "É a maior perda no caminho até a primeira nota. Vale olhar o que essa etapa pede e simplificar, ou chamar essas pessoas no WhatsApp.",
            })
    for e in uso["erros"][:3]:
        if e["vezes"] >= 3:
            dicas.append({
                "tipo": "erro", "titulo": f"“{e['titulo']}” foi recusado {e['vezes']} vezes ({e['pessoas']} pessoa{'s' if e['pessoas'] != 1 else ''})",
                "texto": f"Código {e['status'] or '?'}. Se a mesma recusa se repete, a tela provavelmente não está deixando claro o que falta.",
            })
    if uso["pessoas"] >= 3 and uso["telas_sem_visita"]:
        nomes = ", ".join(t["titulo"] for t in uso["telas_sem_visita"][:4])
        dicas.append({
            "tipo": "tela", "titulo": f"Ninguém abriu nos últimos {uso['dias']} dias: {nomes}",
            "texto": "Ou a tela não é necessária, ou o caminho até ela está escondido.",
        })
    if uso["eventos"] == 0:
        dicas.append({"tipo": "vazio", "titulo": "Ainda sem registro de uso", "texto": "As telas e ações passam a ser anotadas a partir desta versão. Volte em alguns dias."})
    return dicas
