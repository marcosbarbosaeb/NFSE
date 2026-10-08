"""Painel de gestão da plataforma (06/10/2026).

Pedido do Marcos: "precisávamos de uma conta que fizesse a gestão dos
usuários — como sabemos quem está com conta no site, quem está ativo ou
não, ver as comissões de indicação, mensurar as ferramentas que esse
pessoal mais tem utilizado, ver o uso dos e-mails em lote".

Só NÚMEROS de uso por conta. Nada do conteúdo: nem tomadores, nem
descrição ou valor de nota, nem lançamentos do financeiro.

As tabelas de dados têm RLS por empresa, então não existe "SELECT de
todo mundo": a função passa empresa por empresa (a lista sai de
`usuario`/`usuario_prestador`, que não têm RLS), troca o contexto, conta e
no fim devolve o contexto pra quem chamou. É leitura pura.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import definir_prestador_atual
from app.tempo import hoje as hoje_br

# O que conta como "usar" cada ferramenta (id, nome, campo de volume no mês).
FERRAMENTAS = (
    ("notas", "Emitir nota (uma a uma)", "notas_mes"),
    ("lote", "Notas em lote (relatório)", "notas_lote_mes"),
    ("email", "Envio de nota por e-mail", "emails_mes"),
    ("importacao", "Importar do Emissor Nacional", "notas_importadas"),
    ("financeiro", "Recebimentos e despesas", "lancamentos_financeiros_mes"),
    ("extrato", "Importar extrato do banco", "linhas_extrato_mes"),
    ("anotacoes", "Anotações", "anotacoes"),
    ("drive", "Google Drive", "drive"),
)

_CONTAGENS = text("""
    SELECT
      (SELECT count(*) FROM prestador_tomador WHERE excluido_em IS NULL) AS tomadores,
      (SELECT count(*) FROM emissao WHERE estado = 'confirmado' AND origem <> 'importada') AS notas_total,
      (SELECT count(*) FROM emissao WHERE estado = 'confirmado' AND origem <> 'importada' AND tomador_documento IS NULL AND criado_em >= :mes) AS notas_mes,
      (SELECT count(*) FROM emissao WHERE estado = 'confirmado' AND origem <> 'importada' AND tomador_documento IS NOT NULL AND criado_em >= :mes) AS notas_lote_mes,
      (SELECT count(*) FROM emissao WHERE origem = 'importada') AS notas_importadas,
      (SELECT max(criado_em) FROM emissao WHERE origem <> 'importada') AS ultima_nota,
      -- `envio` não tem RLS própria (não carrega prestador_id): sem passar pela
      -- nota, a contagem pegava os envios de TODAS as contas em cada conta (08/10/2026).
      (SELECT count(*) FROM envio e JOIN emissao n ON n.id = e.emissao_id
         WHERE e.canal IN ('email', 'email_geral') AND e.status = 'enviado' AND e.criado_em >= :mes) AS emails_mes,
      (SELECT count(*) FROM envio e JOIN emissao n ON n.id = e.emissao_id
         WHERE e.canal IN ('email', 'email_geral') AND e.status = 'enviado') AS emails_total,
      (SELECT count(*) FROM envio e JOIN emissao n ON n.id = e.emissao_id
         WHERE e.canal = 'email' AND e.status = 'enviado' AND e.criado_em >= :mes AND n.tomador_documento IS NOT NULL) AS emails_lote_mes,
      (SELECT count(*) FROM envio e JOIN emissao n ON n.id = e.emissao_id
         WHERE e.canal IN ('email', 'email_geral') AND e.status = 'falha' AND e.criado_em >= :mes) AS emails_falha_mes,
      (SELECT count(*) FROM pagamento_recebido WHERE criado_em >= :mes) + (SELECT count(*) FROM despesa WHERE criado_em >= :mes) AS lancamentos_financeiros_mes,
      (SELECT count(*) FROM lancamento_bancario WHERE criado_em >= :mes) AS linhas_extrato_mes,
      (SELECT count(*) FROM anotacao) AS anotacoes,
      (SELECT count(*) FROM lote_acao WHERE criado_em >= :mes) AS lotes_mes
""")


def _data(valor) -> str | None:
    return valor.isoformat() if valor is not None else None


def _acesso(empresa, agora: datetime.datetime) -> dict:
    """Mesma regra de billing.situacao_do_acesso, a partir da linha lida aqui."""
    from types import SimpleNamespace

    from app.services.billing import situacao_do_acesso

    assinatura = None if empresa["assinatura"] is None else SimpleNamespace(
        status=empresa["assinatura"], trial_termina_em=empresa["trial_termina_em"],
        liberado_ate=empresa["liberado_ate"], liberado_sempre=bool(empresa["liberado_sempre"]),
        bloqueada_em=empresa["bloqueada_em"],
    )
    s = situacao_do_acesso(assinatura, agora)
    return {**s, "ate": _data(s["ate"])}


def painel(db: Session, prestador_de_volta: uuid.UUID, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or hoje_br()
    # O mês começa à meia-noite de Brasília (UTC-3), não à meia-noite UTC.
    inicio_mes = datetime.datetime(hoje.year, hoje.month, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))

    # Logins (sem RLS): quem acessa cada empresa e quando entrou pela última vez.
    usuarios = db.execute(text("""
        SELECT u.id, u.email, u.nome, u.telefone, u.email_confirmado, u.ativo, u.prestador_id,
               (SELECT max(s.ultimo_acesso) FROM sessao s WHERE s.usuario_id = u.id) AS ultimo_acesso
        FROM usuario u
    """)).mappings().all()
    vinculos = db.execute(text("SELECT usuario_id, prestador_id FROM usuario_prestador")).all()
    por_usuario = {u["id"]: u for u in usuarios}
    logins: dict[uuid.UUID, list[dict]] = {}
    for u in usuarios:
        logins.setdefault(u["prestador_id"], []).append(u)
    for usuario_id, prestador_id in vinculos:
        u = por_usuario.get(usuario_id)
        if u is not None and u not in logins.setdefault(prestador_id, []):
            logins[prestador_id].append(u)

    parcerias = {
        indicado: nome for indicado, nome in db.execute(text(
            "SELECT i.indicado_id, p.nome FROM indicacao_parceiro i JOIN parceiro p ON p.id = i.parceiro_id"
        )).all()
    }

    contadores = dict(db.execute(text(
        "SELECT prestador_id, count(*) FROM acesso_contador WHERE status = 'ativo' GROUP BY prestador_id"
    )).all())
    agora = datetime.datetime.now(datetime.timezone.utc)

    contas: list[dict] = []
    try:
        for prestador_id, pessoas in logins.items():
            definir_prestador_atual(db, prestador_id)
            empresa = db.execute(text("""
                SELECT p.razao_social, p.cpf_cnpj, p.cod_municipio, p.criado_em, p.demo, p.modo_teste, p.modulos, p.so_contador,
                       (p.drive_token IS NOT NULL) AS drive,
                       a.status AS assinatura, a.plano, a.trial_termina_em, a.liberado_ate, a.liberado_sempre, a.liberado_obs, a.bloqueada_em, a.bloqueada_obs, a.liberacao_pedida_em,
                       p.telefone, p.email AS email_empresa,
                       c.validade AS certificado_validade, (c.id IS NOT NULL) AS tem_certificado,
                       (SELECT count(*) FROM indicacao i WHERE i.indicador_id = p.id) AS indicou,
                       (SELECT count(*) FROM indicacao i WHERE i.indicador_id = p.id AND i.status = 'ativa') AS indicou_ativos,
                       EXISTS (SELECT 1 FROM indicacao i WHERE i.indicado_id = p.id) AS veio_por_indicacao
                FROM prestador p
                LEFT JOIN assinatura a ON a.prestador_id = p.id
                LEFT JOIN certificado c ON c.prestador_id = p.id
                WHERE p.id = :id
            """), {"id": prestador_id}).mappings().one_or_none()
            if empresa is None:
                continue
            n = db.execute(_CONTAGENS, {"mes": inicio_mes}).mappings().one()
            acesso = _acesso(empresa, agora)
            if empresa["so_contador"]:
                acesso = {"liberado": True, "motivo": "contador", "ate": None, "dias_restantes": None}
            acessos = [u["ultimo_acesso"] for u in pessoas if u["ultimo_acesso"] is not None]
            ultimo_acesso = max(acessos) if acessos else None
            validade = empresa["certificado_validade"]
            contas.append({
                "id": str(prestador_id),
                "razao_social": empresa["razao_social"], "cnpj": empresa["cpf_cnpj"], "cod_municipio": empresa["cod_municipio"],
                "criada_em": _data(empresa["criado_em"]), "demo": bool(empresa["demo"]), "modo_teste": bool(empresa["modo_teste"]),
                # conta só de contador: não é cliente, não entra nos números
                "so_contador": bool(empresa["so_contador"]),
                "modulos": list(empresa["modulos"] or []),
                "assinatura": empresa["assinatura"], "plano": empresa["plano"], "trial_termina_em": _data(empresa["trial_termina_em"]),
                # liberado? por quê? (teste, assinatura, liberação da gestão...)
                "acesso": acesso, "liberado_obs": empresa["liberado_obs"],
                "bloqueada_em": _data(empresa["bloqueada_em"]), "bloqueada_obs": empresa["bloqueada_obs"],
                # contato da empresa (cadastro dela) — pra falar com o cliente
                # o WhatsApp de quem criou a conta (cadastro) vale mais que o telefone
                # da empresa, que vem da Receita e muitas vezes é o do contador
                "telefone": next((u["telefone"] for u in pessoas if u["telefone"]), None) or empresa["telefone"],
                "telefone_origem": "cadastro" if any(u["telefone"] for u in pessoas) else ("empresa" if empresa["telefone"] else None),
                "email_empresa": empresa["email_empresa"],
                "liberacao_pedida_em": _data(empresa["liberacao_pedida_em"]),
                "contadores": contadores.get(prestador_id, 0),
                "certificado": "falta" if not empresa["tem_certificado"] else ("vencido" if validade is not None and validade < hoje else "ok"),
                "logins": [
                    {"email": u["email"], "nome": u["nome"], "telefone": u["telefone"], "confirmado": bool(u["email_confirmado"]), "ativo": bool(u["ativo"]), "ultimo_acesso": _data(u["ultimo_acesso"])}
                    for u in pessoas
                ],
                "email_confirmado": any(u["email_confirmado"] for u in pessoas),
                "ultimo_acesso": _data(ultimo_acesso),
                "dias_sem_acesso": (hoje - ultimo_acesso.date()).days if ultimo_acesso is not None else None,
                "ultima_nota": _data(n["ultima_nota"]),
                "tomadores": n["tomadores"], "notas_total": n["notas_total"], "notas_mes": n["notas_mes"], "notas_lote_mes": n["notas_lote_mes"],
                "notas_importadas": n["notas_importadas"],
                "emails_mes": n["emails_mes"], "emails_total": n["emails_total"], "emails_lote_mes": n["emails_lote_mes"], "emails_falha_mes": n["emails_falha_mes"],
                "lancamentos_financeiros_mes": n["lancamentos_financeiros_mes"], "linhas_extrato_mes": n["linhas_extrato_mes"],
                "anotacoes": n["anotacoes"], "lotes_mes": n["lotes_mes"], "drive": 1 if empresa["drive"] else 0,
                "indicou": empresa["indicou"], "indicou_ativos": empresa["indicou_ativos"],
                "veio_por": "parceira: " + parcerias[prestador_id] if prestador_id in parcerias else ("indicação de cliente" if empresa["veio_por_indicacao"] else None),
            })
    finally:
        definir_prestador_atual(db, prestador_de_volta)

    contas.sort(key=lambda c: c["criada_em"] or "", reverse=True)
    reais = [c for c in contas if not c["demo"] and not c["so_contador"]]
    por_assinatura: dict[str, int] = {}
    for c in reais:
        chave = c["assinatura"] or "sem assinatura"
        por_assinatura[chave] = por_assinatura.get(chave, 0) + 1
    ferramentas = [
        {
            "id": chave, "nome": nome,
            "contas": sum(1 for c in reais if c[campo] > 0),
            "volume": sum(c[campo] for c in reais),
            # "drive", "anotacoes" e "importacao" são totais, não do mês
            "do_mes": campo.endswith("_mes"),
        }
        for chave, nome, campo in FERRAMENTAS
    ]
    return {
        "gerado_em": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "competencia": f"{hoje.year:04d}-{hoje.month:02d}",
        "resumo": {
            "contas": len(reais),
            "contas_simulacao": sum(1 for c in contas if c["demo"]),
            "contas_contador": sum(1 for c in contas if c["so_contador"]),
            "contas_teste": sum(1 for c in reais if c["modo_teste"]),
            "email_confirmado": sum(1 for c in reais if c["email_confirmado"]),
            "com_certificado": sum(1 for c in reais if c["certificado"] == "ok"),
            "ativas_30_dias": sum(1 for c in reais if c["dias_sem_acesso"] is not None and c["dias_sem_acesso"] <= 30),
            "emitiram_no_mes": sum(1 for c in reais if c["notas_mes"] + c["notas_lote_mes"] > 0),
            "assinaturas": por_assinatura,
            # sem assinatura e sem liberação: é quem o bloqueio trava
            "sem_acesso": sum(1 for c in reais if not c["acesso"]["liberado"]),
            "liberadas_na_mao": sum(1 for c in reais if c["acesso"]["motivo"] == "liberacao"),
            "bloqueio_ativo": get_settings().bloqueio_ativo,
            "notas_mes": sum(c["notas_mes"] + c["notas_lote_mes"] for c in reais),
            "notas_total": sum(c["notas_total"] for c in reais),
            "emails_mes": sum(c["emails_mes"] for c in reais),
            "emails_lote_mes": sum(c["emails_lote_mes"] for c in reais),
            "emails_falha_mes": sum(c["emails_falha_mes"] for c in reais),
        },
        "ferramentas": sorted(ferramentas, key=lambda f: (-f["contas"], -f["volume"])),
        "contas": contas,
    }
