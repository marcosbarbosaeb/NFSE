"""Padrões do catálogo (05/10/2026): "deixe essas configurações como a
configuração padrão dos tomadores pré-cadastrados" — só regras de nota,
nunca dados de contato; e a conta de um cliente não troca o que já está lá."""
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Assinatura, Tomador
from app.services import vinculos


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def test_registrar_so_preenche_o_que_falta_e_publicar_sobrescreve(db, prestador_teste, vinculo_teste):
    tomador = db.get(Tomador, vinculo_teste.tomador_id)
    tomador.status = "aprovado"
    tomador.sug_template_descricao = "Descrição que já estava no catálogo"
    tomador.sug_cod_nbs = None
    vinculo_teste.template_descricao = "Comissão ref. {mes}/{ano}"
    vinculo_teste.cod_nbs = "117019000"
    vinculo_teste.descricao_meses_atras = 1
    vinculo_teste.email_tomador = "financeiro@cliente.com"
    db.flush()

    assert vinculos.registrar_sugestoes(db, vinculo_teste) is True
    # preencheu o que estava vazio, não trocou o que já existia
    assert (tomador.sug_cod_nbs, tomador.sug_meses_atras) == ("117019000", 1)
    assert tomador.sug_template_descricao == "Descrição que já estava no catálogo"

    # curadoria: as regras desta empresa viram o padrão
    assert vinculos.publicar_sugestoes(db) == 1
    assert tomador.sug_template_descricao == "Comissão ref. {mes}/{ano}"
    # nada de contato vai pro catálogo
    assert not any("financeiro@cliente.com" in str(v) for v in vars(tomador).values())


def test_cliente_so_de_controle_nao_ensina_o_catalogo(db, vinculo_teste):
    tomador = db.get(Tomador, vinculo_teste.tomador_id)
    tomador.status = "aprovado"
    tomador.sug_cod_nbs = None
    vinculo_teste.sem_nota = True
    vinculo_teste.cod_nbs = "117019000"
    db.flush()
    assert vinculos.registrar_sugestoes(db, vinculo_teste, sobrescrever=True) is False and tomador.sug_cod_nbs is None


def test_so_a_conta_administradora_publica(client, db, prestador_teste, vinculo_teste):
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_teste.id).one_or_none()
    if assinatura is not None:
        assinatura.status = "ativa"
        db.flush()
    assert client.post("/api/vinculos/publicar-sugestoes").status_code == 403


def test_limpeza_tira_dado_pessoal_e_mantem_o_modelo():
    from app.services.sugestoes import limpar_texto

    # mês fixo vira variável
    assert limpar_texto("Mês de competência 06/2025") == "Mês de competência {competencia_mm_aaaa}"
    # conta bancária e ID de afiliado saem; o modelo fica
    assert limpar_texto("Comissão {mes} {ano}|ID de afiliado 18128100000|") == "Comissão {mes} {ano}"
    assert limpar_texto(
        "Comissão do Programa X {competencia_mm_aaaa}\n\n- Dados bancários: Empresa Y, Banco Z, agência 0001, conta corrente 12345678-5"
    ) == "Comissão do Programa X {competencia_mm_aaaa}"
    # texto de um trabalho específico (pedido, vencimento, valores, @) não vira sugestão
    for unico in (
        "Número de pedido de compra associado PO4500292143",
        "Prestação de serviços para o Job Marca - Ações de maio\nVencimento: 27/08/2026\nBanco 077\nAgência 0001",
        "Locação Janeiro 2024 R$ 40,31 |Dados bancários: Empresa|CNPJ 11.222.333/0001-81",
        "Conta pessoa jurídica - FULANA DE TAL 12345678901|Banco C6|Ag 0001|CC 12345678",
        "Promoção pela influenciadora @perfil no período de abril de 2026",
    ):
        assert limpar_texto(unico) is None, unico
    # texto sem nada pessoal passa igual
    limpo = "Comissão das Campanhas de Publicidade e Vendas do Programa Z"
    assert limpar_texto(limpo) == limpo
    # no e-mail, o nome da empresa vira a variável
    assert limpar_texto("Segue a nota emitida por Empresa Y Ltda.\n\nAtt,\nEmpresa Y", ("Empresa Y Ltda", "Empresa Y"), "{prestador}") == (
        "Segue a nota emitida por {prestador}.\n\nAtt,\n{prestador}"
    )


def test_catalogo_nunca_recebe_conta_bancaria_e_ganha_o_padrao_de_envio(db, prestador_teste, vinculo_teste):
    tomador = db.get(Tomador, vinculo_teste.tomador_id)
    tomador.status = "aprovado"
    tomador.sug_template_descricao = "Descrição antiga com Banco X agência 0001 conta 12345678-9"
    tomador.sug_cod_trib_municipal = "001"
    vinculo_teste.template_descricao = "Serviço único\nBanco X agência 0001 conta 12345678-9"
    vinculo_teste.envio_formas = ["email", "drive"]
    vinculo_teste.email_assunto = "Nota {competencia} — " + prestador_teste.razao_social
    vinculo_teste.email_anexos = "pdf"
    vinculo_teste.email_contato = "financeiro@cliente.com"
    db.flush()

    assert vinculos.publicar_sugestoes(db) == 1
    # a descrição não passou na limpeza: a sugestão antiga (com conta) é apagada
    assert tomador.sug_template_descricao is None
    assert tomador.sug_cod_trib_municipal is None  # muda de cidade pra cidade
    assert tomador.sug_envio_formas == ["email", "drive"] and tomador.sug_email_anexos == "pdf"
    assert tomador.sug_email_assunto == "Nota {competencia} — {prestador}"
    assert not any("financeiro@cliente.com" in str(v) or "12345678" in str(v) for v in vars(tomador).values())


def test_assinatura_com_nome_de_pessoa_e_cupom_nao_vao_pro_catalogo():
    """08/10/2026: o catálogo de produção tinha "Atenciosamente, <nome>" e um
    assunto com cupom de desconto."""
    from app.services.sugestoes import limpar_texto

    assert limpar_texto("Bom dia, seguem as NF.\nAtenciosamente, Maria Souza.", (), "{prestador}") == (
        "Bom dia, seguem as NF.\nAtenciosamente, {prestador}"
    )
    assert limpar_texto("NF Codigo do Cupom_ FULANA10", (), "{prestador}") is None
    # nome da pessoa (MEI) aparece pela metade no texto
    assert limpar_texto("Segue a nota da Maria Souza", ("MARIA SOUZA LIMA",), "{prestador}") == "Segue a nota da {prestador}"
    assert limpar_texto("Olá!\nAtt,\nMaria", ("MARIA SOUZA LIMA",), "{prestador}") == "Olá!\nAtt,\n{prestador}"
    # palavra de empresa não derruba texto comum
    assert limpar_texto("Comissão de vendas {mes}/{ano}", ("BELEZA COMERCIO LTDA",)) == "Comissão de vendas {mes}/{ano}"
