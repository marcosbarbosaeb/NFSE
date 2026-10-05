"""
Listagens por linha (com id) — Marco 14 do plano: as telas novas de
NFS-e/Recebimentos/Despesas precisam de uma lista navegável (uma linha por
nota/pagamento/despesa, com id pra abrir o detalhe), diferente de
app/services/painel_status.py (agrega o ano inteiro, fornecedor×mês, sem
id nenhum — bom pro resumo, ruim pra abrir um registro específico) e de
app/services/dashboard.py (só a competência corrente).

Mesma disciplina de RLS das demais consultas: toda query aqui presume que
`definir_prestador_atual` já rodou na sessão (ver db_sessao em app/main.py)
— os filtros de prestador vêm de graça da RLS, nunca de um WHERE explícito
nestas tabelas.
"""
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models import Emissao, Envio, PrestadorTomador
from app.services.dashboard import ESTADO_NFSE_LABEL
from app.services.motor_emissao import motivo_da_recusa


def listar_emissoes(
    db: Session,
    *,
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    estado: str | None = None,
    grupo: str | None = None,
) -> list[dict]:
    """Notas da empresa, da mais nova pra mais antiga. Só o que é do emissor:
    situação da nota e do envio — nada de pagamento (isso é do módulo
    financeiro, desde a separação de 05/10/2026)."""
    query = (
        db.query(Emissao)
        .options(joinedload(Emissao.vinculo).joinedload(PrestadorTomador.tomador))
        # Desempate por n_dps (sequencial por prestador+série, ver
        # motor_emissao._proximo_ndps) além de criado_em: dentro de uma
        # MESMA transação — o caso comum é a importação de CSV, que gera
        # várias emissões em lote — `criado_em` (server_default=now())
        # fica CONGELADO no início da transação no Postgres, então todas as
        # linhas do lote nascem com o mesmo timestamp; sem o desempate, a
        # ordem dentro do lote ficaria arbitrária.
        .order_by(Emissao.criado_em.desc(), Emissao.n_dps.desc())
    )
    if ano:
        query = query.filter(Emissao.competencia.like(f"{ano}-%"))
    if vinculo_id:
        query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    if estado:
        query = query.filter(Emissao.estado == estado)
    # "notas" = as normais; "vendedores" = as dos vendedores da Shopee
    # (centenas de notas pequenas, numa aba própria — 01/10/2026).
    if grupo == "notas":
        query = query.filter(Emissao.tomador_documento.is_(None))
    elif grupo == "vendedores":
        query = query.filter(Emissao.tomador_documento.isnot(None))

    emissoes = query.all()
    # Último envio de cada nota (e-mail/WhatsApp/...) numa query só.
    ultimo_envio: dict[uuid.UUID, str] = {}
    if emissoes:
        for emissao_id, status in (
            db.query(Envio.emissao_id, Envio.status)
            .filter(Envio.emissao_id.in_([e.id for e in emissoes]), Envio.canal.in_(("email", "whatsapp", "direto_fornecedor")))
            .order_by(Envio.criado_em)
        ):
            if ultimo_envio.get(emissao_id) != "enviado":
                ultimo_envio[emissao_id] = status
    linhas = [
        {
            "id": e.id,
            "vinculo_id": e.prestador_tomador_id,
            "apelido": e.vinculo.apelido,
            # Shopee: o tomador é o vendedor da nota, não o do vínculo.
            "tomador_razao_social": (
                ((e.tomador_snapshot or {}).get("razao_social") or "(tomador sem nome)") if e.tomador_documento
                else e.vinculo.tomador.razao_social
            ),
            "competencia": e.competencia,
            "valor": float(e.valor),
            "serie": e.serie,
            "n_dps": e.n_dps,
            "estado": e.estado,
            "estado_label": ESTADO_NFSE_LABEL.get(e.estado, e.estado),
            "criado_em": e.criado_em,
            "envio_status": ultimo_envio.get(e.id),
            "tem_pdf": e.estado == "confirmado" and bool(e.chave_acesso),
            "tem_email": bool((e.tomador_snapshot or {}).get("email") if e.tomador_documento else (e.vinculo.email_para or e.vinculo.email_contato)),
            "homologacao": (e.tomador_snapshot or {}).get("tpAmb") == "2",
            "avulsa": bool(e.tomador_documento),
            "envio_forma": "email" if e.tomador_documento else e.vinculo.envio_canal,
            # Por que a prefeitura recusou — a lista mostra junto do selo.
            "erro_detalhe": motivo_da_recusa(e.erro_detalhe) if e.estado == "erro" else None,
        }
        for e in emissoes
    ]
    return linhas
