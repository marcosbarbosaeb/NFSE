"""
Motor de emissão (Marco 6) — integração real contra o Postgres local.
Cobre: atribuição de nDPS, congelamento do snapshot, disciplina de
transições de estado, idempotência mensal, e o fluxo de submissão/
cancelamento com ClienteSefin mockado (rede real nunca foi validada pra
submissão — ver módulo).
"""
import uuid
from unittest.mock import MagicMock

import pytest
from lxml import etree

from app.fiscal.cliente_sefin import RespostaSefin
from app.models import Emissao
from app.services.motor_emissao import (
    EmissaoJaExisteError,
    TransicaoInvalidaError,
    assinar,
    cancelar,
    criar_rascunho,
    montar,
    submeter,
)

NS = "http://www.sped.fazenda.gov.br/nfse"


def test_criar_rascunho_atribui_ndps_sequencial(db, vinculo_teste):
    e1 = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    e2 = criar_rascunho(db, vinculo_teste, competencia="2026-09", valor=200.0)
    assert e1.n_dps == 1
    assert e2.n_dps == 2
    assert e1.estado == e2.estado == "rascunho"


def test_ndps_e_por_prestador_serie_nao_por_vinculo(db, prestador_teste, vinculo_teste):
    """Dois vínculos DIFERENTES do mesmo prestador+série compartilham a
    mesma sequência de nDPS — replica o caso real AWIN/AWIN Rchlo."""
    from app.models import PrestadorTomador, Tomador

    tomador2 = Tomador(
        id=uuid.uuid4(), cnpj="22333444000199", razao_social="OUTRO TOMADOR",
        cod_municipio="3550308", cep="01311000", logradouro="Rua Y", numero="2", bairro="Centro",
    )
    db.add(tomador2)
    db.flush()
    vinculo2 = PrestadorTomador(
        id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=tomador2.id,
        apelido="Segundo Vínculo", cod_local_prestacao=prestador_teste.cod_municipio,
        cod_trib_nacional="170601", cod_trib_municipal="001",
        template_descricao="Comissão - {competencia_mm_aaaa}", serie="1", ativo=True,
    )
    db.add(vinculo2)
    db.flush()

    e1 = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    e2 = criar_rascunho(db, vinculo2, competencia="2026-08", valor=50.0)
    assert (e1.n_dps, e2.n_dps) == (1, 2)


def test_idempotencia_bloqueia_segunda_emissao_ativa_mesma_competencia(db, vinculo_teste):
    criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    with pytest.raises(EmissaoJaExisteError):
        criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=999.0)


def test_indice_unico_do_banco_e_quem_garante_de_verdade(db, vinculo_teste):
    """O check proativo em criar_rascunho não é a única linha de defesa —
    forçar duas linhas via o ORM direto (contornando o serviço) ainda tem
    que ser barrado pelo índice parcial do Marco 1."""
    from sqlalchemy.exc import IntegrityError

    criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    dup = Emissao(
        id=uuid.uuid4(), prestador_tomador_id=vinculo_teste.id, prestador_id=vinculo_teste.prestador_id,
        competencia="2026-08", valor=1.0, serie="1", n_dps=999, estado="rascunho", tomador_snapshot={},
    )
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.flush()


def test_idempotencia_permite_nova_emissao_apos_cancelar_anterior(db, vinculo_teste):
    e1 = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    e1.estado = "cancelada"
    db.flush()
    e2 = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=150.0)
    assert e2.id != e1.id


def test_montar_usa_snapshot_congelado_nao_dados_ao_vivo(db, vinculo_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0, aliq_sn=12.5)

    # edita o catálogo DEPOIS do rascunho — a nota já montada não pode mudar.
    vinculo_teste.tomador.razao_social = "NOME MUDOU DEPOIS, NÃO DEVERIA APARECER"
    db.flush()

    emissao = montar(db, rascunho)
    assert "NOME MUDOU DEPOIS" not in emissao.xml_dps
    assert "TOMADOR DE TESTE LTDA" in emissao.xml_dps
    assert emissao.estado == "montado"


def test_transicoes_fora_de_ordem_sao_recusadas(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    with pytest.raises(TransicaoInvalidaError):
        assinar(db, rascunho, certificado_teste["private_key"], certificado_teste["cert"])

    montado = montar(db, rascunho)
    cliente_fake = MagicMock()
    with pytest.raises(TransicaoInvalidaError):
        submeter(db, montado, cliente_fake)

    with pytest.raises(TransicaoInvalidaError):
        montar(db, montado)  # já montado, não pode montar de novo


def test_fluxo_ate_assinado_produz_assinatura_valida(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0, aliq_sn=12.5)
    montado = montar(db, rascunho)
    assinado = assinar(db, montado, certificado_teste["private_key"], certificado_teste["cert"])

    assert assinado.estado == "assinado"
    el = etree.fromstring(assinado.xml_assinado.encode())
    assert el.find("{http://www.w3.org/2000/09/xmldsig#}Signature") is not None


def test_submeter_sucesso_marca_confirmado(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    assinado = assinar(db, montar(db, rascunho), certificado_teste["private_key"], certificado_teste["cert"])

    cliente_fake = MagicMock()
    cliente_fake.submeter_dps.return_value = RespostaSefin(
        status_code=201, dados={"chaveAcesso": "31062002" + "0" * 42, "nfseXmlGZipB64": None}
    )
    confirmado = submeter(db, assinado, cliente_fake)

    assert confirmado.estado == "confirmado"
    assert confirmado.chave_acesso == "31062002" + "0" * 42
    cliente_fake.submeter_dps.assert_called_once()


def test_submeter_falha_marca_erro_e_permite_retentativa(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    assinado = assinar(db, montar(db, rascunho), certificado_teste["private_key"], certificado_teste["cert"])

    cliente_fake = MagicMock()
    cliente_fake.submeter_dps.side_effect = [
        RespostaSefin(status_code=400, dados={"erros": [{"mensagem": "falha simulada"}]}),
        RespostaSefin(status_code=201, dados={"chaveAcesso": "chave-ok", "nfseXmlGZipB64": None}),
    ]

    com_erro = submeter(db, assinado, cliente_fake)
    assert com_erro.estado == "erro"
    assert "falha simulada" in com_erro.erro_detalhe

    retry = submeter(db, com_erro, cliente_fake)  # 'erro' é retentável
    assert retry.estado == "confirmado"
    assert cliente_fake.submeter_dps.call_count == 2


def test_cancelar_requer_confirmado(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    with pytest.raises(TransicaoInvalidaError):
        cancelar(
            db, rascunho, certificado_teste["private_key"], certificado_teste["cert"], MagicMock(),
            cnpj_autor="45172374000122", cmotivo="1", xmotivo="Motivo de teste com mais de 15 caracteres",
        )


def test_cancelar_fluxo_completo(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    assinado = assinar(db, montar(db, rascunho), certificado_teste["private_key"], certificado_teste["cert"])

    cliente_fake = MagicMock()
    cliente_fake.submeter_dps.return_value = RespostaSefin(status_code=201, dados={"chaveAcesso": "3" * 50, "nfseXmlGZipB64": None})
    confirmado = submeter(db, assinado, cliente_fake)

    cliente_fake.enviar_evento_cancelamento.return_value = RespostaSefin(status_code=201, dados={"alertas": []})
    cancelado = cancelar(
        db, confirmado, certificado_teste["private_key"], certificado_teste["cert"], cliente_fake,
        cnpj_autor="45172374000122", cmotivo="1", xmotivo="Emissao duplicada, motivo com mais de 15 caracteres",
    )
    assert cancelado.estado == "cancelada"
    cliente_fake.enviar_evento_cancelamento.assert_called_once()
    chave_chamada, xml_evento_bytes = cliente_fake.enviar_evento_cancelamento.call_args.args
    assert chave_chamada == confirmado.chave_acesso
    assert b"<pedRegEvento" in xml_evento_bytes
    assert confirmado.chave_acesso.encode() in xml_evento_bytes


def test_cancelar_recusado_pela_sefin_nao_muda_estado(db, vinculo_teste, certificado_teste):
    rascunho = criar_rascunho(db, vinculo_teste, competencia="2026-08", valor=100.0)
    assinado = assinar(db, montar(db, rascunho), certificado_teste["private_key"], certificado_teste["cert"])
    cliente_fake = MagicMock()
    cliente_fake.submeter_dps.return_value = RespostaSefin(status_code=201, dados={"chaveAcesso": "4" * 50, "nfseXmlGZipB64": None})
    confirmado = submeter(db, assinado, cliente_fake)

    cliente_fake.enviar_evento_cancelamento.return_value = RespostaSefin(status_code=400, dados={"erros": ["recusado"]})
    with pytest.raises(RuntimeError):
        cancelar(
            db, confirmado, certificado_teste["private_key"], certificado_teste["cert"], cliente_fake,
            cnpj_autor="45172374000122", cmotivo="1", xmotivo="Motivo de teste com mais de 15 caracteres",
        )
    assert confirmado.estado == "confirmado"  # não avançou pra cancelada
