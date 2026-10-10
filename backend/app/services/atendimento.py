"""A Ana atende esta empresa? (2026.10.7 — item B do roteiro de lançamento).

A verificação acontece quando a pessoa informa o CNPJ, antes de criar a
conta: ninguém se cadastra pra só depois descobrir que não é atendido.

| O que a consulta mostra                         | Resultado      | Conta? | Lista de espera? |
| ----------------------------------------------- | -------------- | ------ | ---------------- |
| MEI ou Simples, ativo, cidade no Emissor Nacional | `atende`     | sim    | —                |
| MEI, ativo, cidade fora da lista                | `atende`       | sim    | — (a Sefin aceita MEI em qualquer município, regras E0037–E0039) |
| Simples ME/EPP, ativo, cidade fora da lista     | `cidade_fora`  | não    | sim              |
| Não optante (Lucro Presumido/Real)              | `regime`       | não    | sim              |
| CNPJ não ativo                                  | `inativo`      | não    | não              |
| Consulta fora do ar                             | `sem_consulta` | sim (preenchimento à mão; a Gestão marca depois) | — |
| Regime ou cidade que a consulta não trouxe      | `indefinido`   | sim    | —                |

Só vale pra conta com o emissor de notas: quem cria conta só com o Financeiro
passa (o Financeiro funciona em qualquer cidade e regime), menos CNPJ inativo.
Contas que já existem não são barradas: a Gestão mostra quais estão fora
(`fora_do_atendimento`). CNAE fica de fora.
"""
from __future__ import annotations

from app.services import compatibilidade
from app.services.cnpj_lookup import (
    CnpjInvalidoError,
    CnpjNaoEncontradoError,
    ConsultaCnpjIndisponivelError,
    consultar_cnpj,
)
from app.services.municipios import municipio_por_codigo

ROTULO_REGIME = {"1": "Não optante do Simples (Lucro Presumido ou Real)", "2": "MEI", "3": "Simples Nacional (ME/EPP)"}


def _consultar(cnpj: str):
    """Ponto único da consulta (os testes trocam isto: nada de rede)."""
    return consultar_cnpj(cnpj)


def _cidade(cod_municipio: str | None) -> str | None:
    m = municipio_por_codigo(cod_municipio)
    return f"{m['nome']}/{m['uf']}" if m else None


def avaliar(*, regime: str | None, situacao: str | None, cod_municipio: str | None, so_financeiro: bool = False) -> dict:
    """O veredito a partir do que a consulta trouxe."""
    cidade = _cidade(cod_municipio)
    base = {
        "regime": regime, "regime_rotulo": ROTULO_REGIME.get(regime or ""), "cidade": cidade,
        "cod_municipio": cod_municipio if cidade else None, "situacao_cadastral": situacao,
    }
    if situacao and situacao.strip().upper() != "ATIVA":
        return {**base, "codigo": "inativo", "pode_criar": False, "lista_espera": False,
                "titulo": "Não é possível cadastrar",
                "mensagem": f"Na Receita, este CNPJ está como “{situacao.strip().title()}”. Só dá pra usar a Ana com o CNPJ ativo."}
    if so_financeiro:
        return {**base, "codigo": "atende", "pode_criar": True, "lista_espera": False,
                "titulo": "Tudo certo", "mensagem": "O controle financeiro funciona pra qualquer empresa."}
    if regime == "1":
        return {**base, "codigo": "regime", "pode_criar": False, "lista_espera": True,
                "titulo": "Ainda não atendemos",
                "mensagem": ("Por enquanto a Ana emite notas só pra MEI e empresas do Simples Nacional, e este CNPJ está como "
                             "não optante (Lucro Presumido ou Real). Deixe seu contato: eu aviso quando passar a atender.")}
    usa = compatibilidade.usa_emissor_nacional(cod_municipio)
    if regime == "3" and usa is False:
        return {**base, "codigo": "cidade_fora", "pode_criar": False, "lista_espera": True,
                "titulo": "Sua cidade ainda não está no Emissor Nacional",
                "mensagem": (f"A prefeitura de {cidade} ainda emite nota pelo sistema próprio dela, não pelo Emissor Nacional — "
                             "por isso eu ainda não consigo emitir as suas notas. Deixe seu contato: eu aviso assim que a cidade entrar.")}
    if regime in ("2", "3") and (usa is True or regime == "2"):
        onde = f" em {cidade}" if cidade else ""
        return {**base, "codigo": "atende", "pode_criar": True, "lista_espera": False,
                "titulo": "A Ana atende você",
                "mensagem": f"{ROTULO_REGIME[regime]}{onde}: eu emito as suas notas pelo Emissor Nacional. Você só vai precisar do certificado digital A1."}
    return {**base, "codigo": "indefinido", "pode_criar": True, "lista_espera": False, "titulo": None, "mensagem": None}


def avaliar_cnpj(cnpj: str, *, so_financeiro: bool = False) -> dict:
    """Consulta a Receita e devolve o veredito. CNPJ inválido ou não
    encontrado levantam (a rota responde 422/404 como sempre); consulta fora
    do ar devolve `sem_consulta` (segue o cadastro à mão)."""
    try:
        dados = _consultar(cnpj)
    except (CnpjInvalidoError, CnpjNaoEncontradoError):
        raise
    except ConsultaCnpjIndisponivelError:
        return {"codigo": "sem_consulta", "pode_criar": True, "lista_espera": False, "titulo": None, "mensagem": None,
                "regime": None, "regime_rotulo": None, "cidade": None, "cod_municipio": None, "situacao_cadastral": None,
                "razao_social": None}
    veredito = avaliar(regime=dados.regime, situacao=dados.situacao_cadastral, cod_municipio=dados.cod_municipio_sugerido,
                       so_financeiro=so_financeiro)
    return {**veredito, "razao_social": dados.razao_social or None}


def fora_do_atendimento(*, regime: str | None, cod_municipio: str | None, modulos: list[str] | None) -> str | None:
    """Pra Gestão marcar contas que já existem: "regime", "cidade_fora" ou None."""
    if "emissor" not in (modulos or ["emissor"]):
        return None
    if regime == "1":
        return "regime"
    if regime == "3" and compatibilidade.usa_emissor_nacional(cod_municipio) is False:
        return "cidade_fora"
    return None
