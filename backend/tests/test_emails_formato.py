"""Formato de e-mail (09/10/2026): em 05/10 o aviso de fim de lote não saiu —
o serviço de e-mail recusou com 422 "Invalid `to` field". Agora o formato é
conferido na entrada e antes do envio; inválido vira aviso, não exceção."""
import uuid
from decimal import Decimal

import pytest
import requests

from app.models import LoteAcao, Usuario, UsuarioPrestador
from app.services import lotes
from app.services.email import EmailDestinoInvalidoError, EmailSenderResend, preparar_destinos
from app.services.emails import email_valido, normalizar, separar
from app.services.relatorio_shopee import VendedorShopee, tomador_avulso


@pytest.mark.parametrize("bom", ["a@x.com", "Fulano.Silva+nf@empresa.com.br", " A@X.COM ", "Maria <maria@gmail.com>", "mailto:fin@loja.com"])
def test_aceita(bom):
    assert email_valido(bom)


@pytest.mark.parametrize("ruim", [
    "", "sem-arroba", "a@x", "a@x.c", "joão@x.com", "a b@x.com", "a@@x.com", "a@x..com", ".a@x.com", "a.@x.com",
    "a@-x.com", "a@x.com,b@y.com", "a@x.com;", "(a)@x.com",
])
def test_recusa(ruim):
    assert not email_valido(ruim)


def test_separar_lista_digitada():
    assert separar("A@x.com; b@y.com.br, errado  a@x.com") == (["a@x.com", "b@y.com.br"], ["errado"])
    assert normalizar(" Maria <MARIA@GMAIL.COM> ") == "maria@gmail.com"


def test_antes_de_enviar_tira_o_invalido_e_sem_nenhum_valido_e_erro_claro():
    assert preparar_destinos(["a@x.com", "lixo"], ["c@x.com", "nada", "a@x.com"]) == (["a@x.com"], ["c@x.com"])
    with pytest.raises(EmailDestinoInvalidoError, match="não é um e-mail válido"):
        preparar_destinos("maria@gmail", None)


def test_resend_nunca_recebe_destinatario_invalido(monkeypatch):
    chamadas = []
    monkeypatch.setattr(requests, "post", lambda *a, **kw: chamadas.append(kw) or None)
    with pytest.raises(EmailDestinoInvalidoError):
        EmailSenderResend("chave-falsa", "Ana <ana@x.com>").enviar(destinatario=["maria@gmail"], assunto="x", corpo_texto="x", corpo_html="x")
    assert chamadas == []


def test_vendedor_com_email_invalido_vira_aviso_no_lote():
    v = VendedorShopee(
        competencia="2026-09", documento="12345678000195", tipo_documento="CNPJ", razao_social="LOJA X", lojas=["x"],
        valor=Decimal("10"), pais="BR", email="vendas@lojax", endereco=None, endereco_bruto="",
    )
    t = tomador_avulso(v)
    assert t["email"] is None and t["email_invalido"] == "vendas@lojax"

    class _Nota:
        tomador_documento = "12345678000195"
        tomador_snapshot = {"email": None, "email_invalido": "vendas@lojax"}
        vinculo = None

    assert "(“vendas@lojax”) não é válido" in lotes._motivo_sem_email(_Nota())


def test_fim_do_lote_com_email_da_conta_invalido_vira_aviso_na_tela(db, prestador_teste, monkeypatch):
    usuario = Usuario(id=uuid.uuid4(), prestador_id=prestador_teste.id, email="dona@gmail", senha_hash="x", email_confirmado=True)
    db.add(usuario)
    db.flush()
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador_teste.id))
    lote = LoteAcao(id=uuid.uuid4(), prestador_id=prestador_teste.id, acao="completo", status="concluido", total=1, feitos=1, emissao_ids=[])
    db.add(lote)
    db.flush()
    monkeypatch.setattr(db, "commit", db.flush)

    enviados = []
    monkeypatch.setattr("app.services.email.get_email_sender", lambda: type("S", (), {"enviar": lambda self, **kw: enviados.append(kw)})())
    lotes._avisar_por_email(db, lote, prestador_teste.id, "https://x")

    assert enviados == []
    aviso = lotes.resumo(lote)["aviso_conta"]
    assert aviso and "“dona@gmail”" in aviso and "Minha conta" in aviso
