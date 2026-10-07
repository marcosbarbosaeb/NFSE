"""Completar os dados da empresa pelo CNPJ (07/10/2026).

Pedido do Marcos: "sobre o completar os dados da empresa, falei para
puxarmos pelo CNPJ". Em vez de mandar a pessoa preencher endereço e regime
na tela da empresa, a Ana consulta a Receita e preenche o que estiver em
branco. Nunca troca o que a pessoa já escreveu — só completa.

O que a Receita não sabe (a alíquota do Simples) continua sendo informado
pela pessoa ou pelo contador.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Prestador
from app.services import prontidao
from app.services.cnpj_lookup import DadosCnpj, consultar_cnpj


class SemCnpjError(Exception):
    """Empresa cadastrada com CPF (ou conta só de contador): não há o que
    consultar."""


def _vazio(valor) -> bool:
    return not str(valor or "").strip()


def aplicar(prestador: Prestador, dados: DadosCnpj) -> list[str]:
    """Preenche só o que está em branco. Devolve o que foi preenchido, em
    palavras de gente."""
    feitos: list[str] = []

    endereco = False
    for campo, valor, tamanho in (
        ("cep", "".join(c for c in (dados.cep or "") if c.isdigit()), 8),
        ("logradouro", dados.logradouro, 200), ("numero", dados.numero, 20),
        ("complemento", dados.complemento, 100), ("bairro", dados.bairro, 100),
    ):
        if _vazio(getattr(prestador, campo)) and not _vazio(valor):
            setattr(prestador, campo, str(valor).strip()[:tamanho])
            endereco = True
    if endereco:
        feitos.append("endereço")

    if _vazio(prestador.cod_municipio) or prestador.cod_municipio == "0000000":
        if dados.cod_municipio_sugerido:
            prestador.cod_municipio = dados.cod_municipio_sugerido
            feitos.append("cidade")

    if _vazio(prestador.op_simples_nacional) and dados.regime:
        prestador.op_simples_nacional = dados.regime
        if dados.regime == "3" and _vazio(prestador.regime_apuracao_sn):
            # O caso de quase todo mundo: federais e ISS dentro do Simples.
            prestador.regime_apuracao_sn = "1"
        feitos.append("regime tributário")

    if _vazio(prestador.nome_fantasia) and dados.nome_fantasia:
        prestador.nome_fantasia = dados.nome_fantasia[:200]
        feitos.append("nome fantasia")
    if _vazio(prestador.telefone) and dados.telefone:
        prestador.telefone = dados.telefone[:20]
        feitos.append("telefone")
    if _vazio(prestador.email) and dados.email:
        prestador.email = dados.email[:200]
        feitos.append("e-mail da empresa")
    return feitos


def completar(db: Session, prestador: Prestador) -> dict:
    cnpj = "".join(c for c in (prestador.cpf_cnpj or "") if c.isdigit())
    if prestador.so_contador or len(cnpj) != 14:
        raise SemCnpjError("Esta empresa não tem CNPJ: preencha os dados à mão.")
    feitos = aplicar(prestador, consultar_cnpj(cnpj))
    db.flush()
    return {"preenchidos": feitos, "faltam": prontidao._dados_que_faltam(prestador)}
