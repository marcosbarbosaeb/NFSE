"""A Ana funciona na cidade desta empresa? (05/10/2026 — "na página de
cadastro, um campo pra pessoa preencher o CNPJ e verificarmos se o nosso
sistema é compatível").

A Ana emite pela API do Emissor Nacional da NFS-e. Toda prefeitura já
manda as notas pro ambiente nacional, mas só parte delas USA o emissor
nacional — as outras continuam com sistema próprio de nota, e nelas não dá
pra emitir por aqui. A Receita publica a situação de cada município
(coluna "AderenteEmissorNacional" da planilha de monitoramento das
adesões); a lista dos que usam o emissor fica em app/data/emissor_nacional.json
— pra atualizar, baixe a planilha nova em
https://www.gov.br/nfse/pt-br/municipios/monitoramento-adesoes e rode
scripts/atualizar_emissor_nacional.py.

O módulo Financeiro não depende disso: funciona em qualquer cidade.
"""
import json
from functools import lru_cache
from pathlib import Path

from app.services.municipios import municipio_por_codigo

_ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "emissor_nacional.json"


@lru_cache(maxsize=1)
def _dados() -> dict:
    bruto = json.loads(_ARQUIVO.read_text(encoding="utf-8"))
    return {"codigos": frozenset(bruto["codigos"]), "atualizado_em": bruto.get("atualizado_em")}


def lista_atualizada_em() -> str | None:
    return _dados()["atualizado_em"]


def usa_emissor_nacional(cod_municipio: str | None) -> bool | None:
    """True/False pela lista da Receita; None se não reconhecemos a cidade."""
    if municipio_por_codigo(cod_municipio) is None:
        return None
    return cod_municipio in _dados()["codigos"]


def verificar(cod_municipio: str | None, situacao_cadastral: str | None = None) -> dict:
    """Resposta pronta pra tela: `emissor` = "sim" | "nao" | "indefinido"."""
    municipio = municipio_por_codigo(cod_municipio)
    cidade = f"{municipio['nome']}/{municipio['uf']}" if municipio else None
    usa = usa_emissor_nacional(cod_municipio)
    avisos: list[str] = []
    if situacao_cadastral and situacao_cadastral.strip().upper() != "ATIVA":
        avisos.append(f"Na Receita, este CNPJ está como “{situacao_cadastral}”. Com o CNPJ irregular a prefeitura pode recusar as notas.")
    if usa is True:
        emissor, mensagem = "sim", (
            f"Boa notícia: a prefeitura de {cidade} usa o Emissor Nacional, então a Ana emite as suas notas. "
            "Você só vai precisar do certificado digital A1 da empresa (o mesmo que o contador usa)."
        )
    elif usa is False:
        emissor, mensagem = "nao", (
            f"A prefeitura de {cidade} ainda emite nota pelo sistema próprio dela, não pelo Emissor Nacional — "
            "por isso a Ana ainda não consegue emitir as suas notas. O controle financeiro funciona normalmente."
        )
    else:
        emissor, mensagem = "indefinido", "Não consegui identificar a cidade deste CNPJ pra conferir. Escolha a cidade abaixo."
    return {
        "emissor": emissor, "financeiro": "sim", "cidade": cidade, "cod_municipio": cod_municipio if municipio else None,
        "mensagem": mensagem, "avisos": avisos, "lista_atualizada_em": lista_atualizada_em(),
    }
