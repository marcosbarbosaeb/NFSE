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
import secrets
import uuid

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
)
from app.services.motor_emissao import criar_rascunho, montar
from app.services.pagamentos import registrar_pagamento
from app.tempo import hoje as hoje_br

DOMINIO_EMAIL_DEMO = "simulacao.agenteana.com.br"
VALIDADE = datetime.timedelta(hours=24)
# São Paulo (IBGE) — só pra ter uma cidade válida nas notas de exemplo.
_MUNICIPIO_DEMO = "3550308"

# CNPJs com dígito verificador inválido de propósito: não podem pertencer
# a nenhuma empresa real.
_TOMADORES_DEMO = [
    {"cnpj": "11222333000100", "razao_social": "Rede de Afiliados Exemplo LTDA (fictícia)", "apelido": "Rede Exemplo",
     "dia": 5, "dias_receber": 30, "template": "Comissão de vendas - {mes_nome_upper}/{ano}", "base": 1850.0},
    {"cnpj": "22333444000100", "razao_social": "Loja Parceira Modelo S.A. (fictícia)", "apelido": "Loja Modelo",
     "dia": 10, "dias_receber": 15, "template": "Divulgação de produtos - {mes_nome_upper}/{ano}", "base": 920.0},
    {"cnpj": "33444555000100", "razao_social": "Plataforma de Cursos Teste LTDA (fictícia)", "apelido": "Cursos Teste",
     "dia": 20, "dias_receber": 45, "template": "Comissão sobre vendas de cursos - {mes_nome_upper}/{ano}", "base": 2430.0},
    {"cnpj": "44555666000100", "razao_social": "Marketplace Simulado LTDA (fictícia)", "apelido": "Marketplace Simulado",
     "dia": None, "dias_receber": None, "template": "Comissão de vendas - {mes_nome_upper}/{ano}", "base": 400.0,
     "inativo": True},
]


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
            id=uuid.uuid4(), cnpj=dados["cnpj"], razao_social=dados["razao_social"], cod_municipio=_MUNICIPIO_DEMO,
            logradouro="Rua de Exemplo", numero="100", bairro="Centro", cep="01000000", status="pendente",
        )
        db.add(tomador)
        db.flush()
    return tomador


def criar_conta_demo(db: Session) -> Usuario:
    """Não dá commit. Deixa a variável de RLS apontando pro prestador novo."""
    apagar_demos_expiradas(db)

    hoje = hoje_br()
    prestador_id = uuid.uuid4()
    definir_prestador_atual(db, prestador_id)
    prestador = Prestador(
        id=prestador_id, cpf_cnpj=_cnpj_ficticio(), razao_social="Sua Empresa de Exemplo LTDA",
        cod_municipio=_MUNICIPIO_DEMO, logradouro="Avenida Simulação", numero="1", bairro="Centro", cep="01000000",
        op_simples_nacional="3", regime_apuracao_sn="1", regime_especial_trib="0",
        aliquota_atual=6, aliquota_atualizada_em=hoje, demo=True,
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

    for indice, dados in enumerate(_TOMADORES_DEMO):
        tomador = _tomador_demo(db, dados)
        vinculo = PrestadorTomador(
            id=uuid.uuid4(), prestador_id=prestador_id, tomador_id=tomador.id, apelido=dados["apelido"],
            cod_local_prestacao=_MUNICIPIO_DEMO, cod_trib_nacional="170601", template_descricao=dados["template"],
            serie="1", requer_revisao=True, ativo=not dados.get("inativo", False),
            dia_limite_emissao=dados["dia"], dias_para_recebimento=dados["dias_receber"],
            email_contato="financeiro@exemplo.com.br",
        )
        db.add(vinculo)
        db.flush()
        db.refresh(vinculo)
        if dados.get("inativo"):
            continue

        # Notas dos 3 meses anteriores (e a do mês atual pra quem já passou
        # do dia de emitir), recebimentos das mais antigas.
        for delta in (-3, -2, -1, 0):
            # Mês atual: uma fica de propósito sem gerar, pra lista de
            # Tomadores mostrar o "falta gerar" e o botão Gerar.
            if delta == 0 and ((dados["dia"] or 31) > hoje.day or indice == 1):
                continue
            competencia = _competencia(delta, hoje)
            valor = round(dados["base"] * (1 + 0.07 * (delta + indice)), 2)
            emissao = criar_rascunho(db, vinculo, competencia=competencia, valor=valor, aliq_sn=6.0, tpAmb="2")
            montar(db, emissao)
            if delta <= -2 or (delta == -1 and indice == 0):
                ano, mes = (int(p) for p in competencia.split("-"))
                recebido_em = datetime.date(ano, mes, min(28, (dados["dia"] or 1) + 3)) + datetime.timedelta(days=dados["dias_receber"] or 30)
                registrar_pagamento(db, vinculo, competencia=competencia, valor=valor, data_recebimento=min(recebido_em, hoje))

    for delta, categoria, valor in ((-2, "Contador", 350.0), (-1, "Contador", 350.0), (-1, "Ferramentas de marketing", 189.9), (0, "Contador", 350.0)):
        db.add(Despesa(id=uuid.uuid4(), prestador_id=prestador_id, categoria=categoria, competencia=_competencia(delta, hoje), valor=valor))

    db.add(EventoManual(
        id=uuid.uuid4(), prestador_id=prestador_id, data=hoje + datetime.timedelta(days=3), categoria="lembrete",
        titulo="Conferir comissões do mês (exemplo)", descricao="Evento criado à mão — dá pra editar ou apagar.",
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
