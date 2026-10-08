"""
Ambiente de simulação — pedido do Marcos (28/09/2026): "crie um ambiente
de simulação para as pessoas que quiserem testar a plataforma de forma
gratuita".

Um clique em "Testar sem cadastro" cria uma conta descartável, já logada,
com uma empresa fictícia e dados de exemplo (tomadores, notas dos últimos
meses, recebimentos, despesas e um lembrete no calendário) — dá pra mexer
em tudo sem cadastrar CNPJ, sem certificado e sem risco:

- `Prestador.demo = True` marca a conta. As rotas que falam com o mundo de
  fora (enviar à Receita, cancelar na Receita, subir certificado, mandar
  e-mail, assinatura/cobrança, trocar senha) recusam contas demo — ver
  `exigir_conta_real` em app/main.py.
- Os tomadores de exemplo são empresas FICTÍCIAS, com CNPJ de dígito
  verificador inválido de propósito (não existe na Receita), e nascem com
  status 'pendente' — o catálogo compartilhado só lista 'aprovado', então
  eles nunca aparecem pra contas de verdade.
- Cada conta demo vive `VALIDADE` e depois é apagada inteira na próxima
  vez que alguém abre uma simulação (`apagar_demos_expiradas`). Como a
  tabela `prestador` tem RLS por id, a busca das contas vencidas parte de
  `usuario` (sem RLS), pelo domínio fixo de e-mail das contas demo.
"""
import datetime
import json
import re
import secrets
import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_senha
from app.database import definir_prestador_atual
from app.models import (
    AjusteEvento,
    Assinatura,
    Certificado,
    Despesa,
    Emissao,
    Envio,
    EventoManual,
    PagamentoRecebido,
    Prestador,
    PrestadorTomador,
    Tomador,
    Usuario,
    UsuarioPrestador,
)
from app.services.motor_emissao import criar_rascunho, montar
from app.tempo import hoje as hoje_br

DOMINIO_EMAIL_DEMO = "simulacao.agenteana.com.br"
VALIDADE = datetime.timedelta(hours=24)
# São Paulo (IBGE) — só pra ter uma cidade válida nas notas de exemplo.
_MUNICIPIO_DEMO = "3550308"

# Cenários (08/10/2026, modo demonstração): os dados de exemplo moram em
# app/data/cenarios/<nome>.json — empresa, tomadores, valores, meses — pra
# trocar o nicho sem mexer em código nem em cadastro. Ver o LEIA-ME de lá.
# Os CNPJs dos tomadores de lá têm dígito verificador inválido de propósito:
# não podem pertencer a nenhuma empresa real.
PASTA_CENARIOS = Path(__file__).resolve().parents[1] / "data" / "cenarios"
CENARIO_PADRAO = "afiliados"
_NOME_CENARIO = re.compile(r"^[a-z0-9_-]{1,40}$")


class CenarioInexistenteError(Exception):
    pass


def cenarios() -> list[str]:
    return sorted(p.stem for p in PASTA_CENARIOS.glob("*.json"))


def carregar_cenario(nome: str | None) -> dict:
    nome = (nome or CENARIO_PADRAO).strip().lower()
    if not _NOME_CENARIO.match(nome) or not (PASTA_CENARIOS / f"{nome}.json").is_file():
        raise CenarioInexistenteError(f"Cenário “{nome}” não existe. Os que existem: {', '.join(cenarios())}.")
    return json.loads((PASTA_CENARIOS / f"{nome}.json").read_text(encoding="utf-8"))


def eh_email_demo(email: str | None) -> bool:
    return bool(email) and email.endswith("@" + DOMINIO_EMAIL_DEMO)


def _cnpj_ficticio() -> str:
    """14 dígitos com os dois verificadores errados (sempre "00" depois de
    uma base que não gera 00) — nunca colide com empresa real."""
    while True:
        base = "9" + "".join(secrets.choice("0123456789") for _ in range(11))
        if _dv_cnpj(base) != "00":
            return base + "00"


def _dv_cnpj(base12: str) -> str:
    def dv(numeros: str, pesos: list[int]) -> str:
        soma = sum(int(n) * p for n, p in zip(numeros, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = dv(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = dv(base12 + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d1 + d2


def _competencia(delta_meses: int, hoje: datetime.date) -> str:
    indice = hoje.year * 12 + hoje.month - 1 + delta_meses
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _tomador_demo(db: Session, dados: dict) -> Tomador:
    tomador = db.query(Tomador).filter_by(cnpj=dados["cnpj"]).one_or_none()
    if tomador is None:
        tomador = Tomador(
            id=uuid.uuid4(), cnpj=dados["cnpj"], razao_social=dados["razao_social"],
            cod_municipio=dados.get("cod_municipio") or _MUNICIPIO_DEMO,
            logradouro=dados.get("logradouro") or "Rua de Exemplo", numero=dados.get("numero") or "100",
            bairro=dados.get("bairro") or "Centro", cep=dados.get("cep") or "01000000", status="pendente",
        )
        db.add(tomador)
        db.flush()
    return tomador


def _valores_do_tomador(cenario: dict, dados: dict, indice: int, hoje: datetime.date) -> dict[int, float]:
    """{mês relativo: valor} das notas que este tomador já tem."""
    if dados.get("valores"):
        return {int(k): float(v) for k, v in dados["valores"].items()}
    variacao = float(cenario.get("variacao_por_mes", 0.07))
    meses = list(range(-int(cenario.get("meses_passados", 3)), 0))
    # Mês atual: só pra quem já passou do dia de gerar (e não pediu pra ficar sem).
    if not dados.get("sem_nota_no_mes") and (dados.get("dia") or 31) <= hoje.day:
        meses.append(0)
    return {d: round(float(dados["base"]) * (1 + variacao * (d + indice)), 2) for d in meses}


def criar_conta_demo(db: Session, cenario: str | None = None) -> Usuario:
    """Não dá commit. Deixa a variável de RLS apontando pro prestador novo.
    `cenario`: nome de um arquivo de app/data/cenarios (padrão: afiliados)."""
    from app.services import demo_emissao

    dados_cenario = carregar_cenario(cenario)
    apagar_demos_expiradas(db)

    hoje = hoje_br()
    empresa = dados_cenario.get("empresa") or {}
    municipio = empresa.get("cod_municipio") or _MUNICIPIO_DEMO
    prestador_id = uuid.uuid4()
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        modulos=["emissor", "financeiro"],  # a simulação mostra os dois produtos
        id=prestador_id, cpf_cnpj=_cnpj_ficticio(), razao_social=empresa.get("razao_social") or "Sua Empresa de Exemplo LTDA",
        nome_fantasia=empresa.get("nome_fantasia") or None,
        cod_municipio=municipio, logradouro=empresa.get("logradouro") or "Avenida Simulação", numero=empresa.get("numero") or "1",
        bairro=empresa.get("bairro") or "Centro", cep=empresa.get("cep") or "01000000",
        op_simples_nacional="3", regime_apuracao_sn="1", regime_especial_trib="0",
        aliquota_atual=empresa.get("aliquota", 6), aliquota_atualizada_em=hoje, demo=True,
    )
    db.add(prestador)
    db.flush()
    db.add(Assinatura(
        id=uuid.uuid4(), prestador_id=prestador_id, status="trial",
        trial_termina_em=datetime.datetime.now(datetime.timezone.utc) + VALIDADE,
    ))

    usuario = Usuario(
        id=uuid.uuid4(), prestador_id=prestador_id,
        email=f"demo-{uuid.uuid4().hex[:12]}@{DOMINIO_EMAIL_DEMO}",
        senha_hash=hash_senha(secrets.token_urlsafe(24)), email_confirmado=True,
    )
    db.add(usuario)
    db.flush()
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador_id))
    db.flush()

    aliquota = float(empresa.get("aliquota", 6))
    for indice, dados in enumerate(dados_cenario.get("tomadores") or []):
        tomador = _tomador_demo(db, dados)
        email = dados.get("email") or "financeiro@exemplo.com.br"
        vinculo = PrestadorTomador(
            id=uuid.uuid4(), prestador_id=prestador_id, tomador_id=tomador.id, apelido=dados["apelido"],
            cod_local_prestacao=municipio, cod_trib_nacional=dados.get("cod_trib_nacional") or "170601",
            template_descricao=dados["template"], serie="1", requer_revisao=True, ativo=not dados.get("inativo", False),
            dia_limite_emissao=dados.get("dia"), dias_para_recebimento=dados.get("dias_receber"),
            email_contato=email,
        )
        db.add(vinculo)
        db.flush()
        db.refresh(vinculo)
        if dados.get("inativo"):
            continue

        recebidos = {int(m) for m in dados.get("recebidos") or []}
        for delta, valor in sorted(_valores_do_tomador(dados_cenario, dados, indice, hoje).items()):
            competencia = _competencia(delta, hoje)
            emissao = criar_rascunho(db, vinculo, competencia=competencia, valor=valor, aliq_sn=aliquota, tpAmb="2")
            montar(db, emissao)
            # Já autorizada e entregue (de mentira — conta de simulação, nota de homologação).
            demo_emissao.fazer_tudo(db, emissao, email)
            if delta in recebidos:
                ano, mes = (int(p) for p in competencia.split("-"))
                recebido_em = datetime.date(ano, mes, min(28, (dados.get("dia") or 1) + 3)) + datetime.timedelta(days=dados.get("dias_receber") or 30)
                # (dados de exemplo dos dois produtos, gravados direto — a
                # simulação não depende do código de nenhum dos módulos)
                db.add(PagamentoRecebido(
                    id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=prestador_id, competencia=competencia,
                    valor=valor, data_recebimento=min(recebido_em, hoje), emissao_id=emissao.id,
                ))

    for d in dados_cenario.get("despesas") or []:
        db.add(Despesa(
            id=uuid.uuid4(), prestador_id=prestador_id, categoria=d["categoria"],
            competencia=_competencia(int(d["mes"]), hoje), valor=float(d["valor"]),
        ))

    for ev in dados_cenario.get("eventos") or []:
        db.add(EventoManual(
            id=uuid.uuid4(), prestador_id=prestador_id, data=hoje + datetime.timedelta(days=int(ev.get("daqui_a_dias", 3))),
            categoria=ev.get("categoria") or "lembrete", titulo=ev["titulo"], descricao=ev.get("descricao"),
        ))
    db.flush()
    return usuario


def apagar_conta_demo(db: Session, prestador_id: uuid.UUID) -> None:
    """Apaga TUDO de uma conta demo (nunca de uma conta real: confere a
    marca `demo` antes). Não dá commit."""
    definir_prestador_atual(db, prestador_id)
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is None or not prestador.demo:
        return
    tomadores = [t for (t,) in db.query(PrestadorTomador.tomador_id).filter(PrestadorTomador.prestador_id == prestador_id)]
    emissoes = [e.id for e in db.query(Emissao.id).filter(Emissao.prestador_id == prestador_id)]
    if emissoes:
        db.query(Envio).filter(Envio.emissao_id.in_(emissoes)).delete(synchronize_session=False)
    for modelo in (Emissao, PagamentoRecebido, Despesa, EventoManual, AjusteEvento, PrestadorTomador, Certificado, Assinatura, Usuario):
        db.query(modelo).filter(modelo.prestador_id == prestador_id).delete(synchronize_session=False)
    db.query(Prestador).filter(Prestador.id == prestador_id).delete(synchronize_session=False)
    db.flush()
    # Tomadores que a simulação criou (nunca aprovados no catálogo) saem
    # junto — se algum outro vínculo ainda apontar pra ele, a FK impede e
    # ele fica.
    for tomador_id in set(tomadores):
        try:
            with db.begin_nested():
                db.query(Tomador).filter(Tomador.id == tomador_id, Tomador.status != "aprovado").delete(synchronize_session=False)
        except IntegrityError:
            pass


def apagar_demos_expiradas(db: Session) -> int:
    limite = datetime.datetime.now(datetime.timezone.utc) - VALIDADE
    vencidas = (
        db.query(Usuario.prestador_id)
        .filter(Usuario.email.like(f"%@{DOMINIO_EMAIL_DEMO}"), Usuario.criado_em < limite)
        .limit(50)
        .all()
    )
    for (prestador_id,) in vencidas:
        apagar_conta_demo(db, prestador_id)
    return len(vencidas)
