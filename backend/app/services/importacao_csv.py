"""
Importação em lote (Marco 7 — "entrada multi-formato" do plano) — cobre os
pontos #2 e #6 da lista original do Marcos ("receber o arquivo CSV e gerar
as múltiplas notas", "trabalhar com múltiplos imput").

Formato aceito: uma linha por NOTA A GERAR (não é o formato "largo" da
planilha real do Marcos, que tem uma linha por FORNECEDOR e uma coluna por
mês — ver ressalva no painel/relatório). Colunas esperadas (nomes de
cabeçalho, sem acento/case-insensitive):

    apelido, competencia, valor[, ordem][, aliq_sn][, tpAmb]

- `apelido` casa com `PrestadorTomador.apelido` (ex.: "ML/Ebazar", "AWIN")
  — mais amigável que exigir o UUID do vínculo na mão.
- `competencia` no formato AAAA-MM.
- `valor` aceita tanto "1234.56" quanto "1234,56" (Excel pt-BR costuma
  salvar CSV com vírgula decimal e ; como separador — o parser detecta o
  delimitador automaticamente).
- `ordem` e `aliq_sn` são opcionais (só usados por alguns vínculos).

Cada linha roda dentro do seu próprio SAVEPOINT (`db.begin_nested()`): uma
linha com erro (fornecedor desconhecido, competência duplicada, descrição
incompleta, valor malformado, ...) é revertida e registrada como erro SEM
derrubar as linhas seguintes nem as que já deram certo — é assim que "um
fornecedor com nome errado no meio do CSV" não trava o lote inteiro.

Este módulo só faz criar_rascunho + montar (mesma "caixa de revisão" antes
de assinar que o painel usa pra uma nota só) — assinar/submeter continuam
manuais, um vínculo de cada vez, pelo painel.
"""
import csv
import io
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.fiscal.dps import DescricaoIncompletaError
from app.models import PrestadorTomador
from app.services.motor_emissao import EmissaoJaExisteError, criar_rascunho, montar
from app.services.vinculos import listar_vinculos_ativos

COLUNAS_OBRIGATORIAS = {"apelido", "competencia", "valor"}


@dataclass
class LinhaImportada:
    linha: int
    apelido: str
    ok: bool
    mensagem: str | None = None
    emissao_id: uuid.UUID | None = None
    n_dps: int | None = None


class CsvInvalidoError(Exception):
    """Erro estrutural do arquivo inteiro (cabeçalho faltando, arquivo
    vazio, ...) — diferente de erro de UMA linha, que vira um LinhaImportada
    com ok=False em vez de abortar a importação toda."""


def _detectar_delimitador(amostra: str) -> str:
    try:
        return csv.Sniffer().sniff(amostra, delimiters=",;").delimiter
    except csv.Error:
        return ","  # amostra pequena demais pro sniffer decidir — chute razoável


def _normalizar_cabecalho(nome: str) -> str:
    return nome.strip().lower().lstrip("﻿")  # BOM do Excel no primeiro cabeçalho


def _parsear_valor(bruto: str) -> float:
    bruto = bruto.strip()
    if not bruto:
        raise ValueError("valor vazio")
    if "," in bruto and "." in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")  # 1.234,56 (pt-BR)
    elif "," in bruto:
        bruto = bruto.replace(",", ".")  # 1234,56
    return float(bruto)


def _parsear_linhas(conteudo: str) -> list[dict]:
    amostra = conteudo[:2048]
    delimitador = _detectar_delimitador(amostra)
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=delimitador)
    if leitor.fieldnames is None:
        raise CsvInvalidoError("Arquivo vazio ou sem cabeçalho.")

    cabecalhos = {_normalizar_cabecalho(c): c for c in leitor.fieldnames if c is not None}
    faltando = COLUNAS_OBRIGATORIAS - cabecalhos.keys()
    if faltando:
        raise CsvInvalidoError(
            f"Cabeçalho sem as colunas obrigatórias: {', '.join(sorted(faltando))}. "
            f"Colunas esperadas: apelido, competencia, valor (+ ordem, aliq_sn opcionais)."
        )

    linhas = []
    for bruta in leitor:
        linhas.append({chave_norm: bruta.get(chave_orig) for chave_norm, chave_orig in cabecalhos.items()})
    return linhas


def importar_csv(db: Session, conteudo: str) -> list[LinhaImportada]:
    """Processa o CSV inteiro, uma linha por vez, cada uma no seu próprio
    savepoint. NÃO dá commit — quem chama decide (o endpoint do painel dá
    um único commit no fim, cobrindo só as linhas que deram certo; as com
    erro já foram revertidas pro savepoint delas mesmas).

    Não recebe prestador_id à toa: `db` já deve ter passado por
    `definir_prestador_atual` (RLS) — os vínculos vêm de
    `listar_vinculos_ativos`, que já é filtrado por RLS, não por um
    parâmetro explícito aqui."""
    linhas_brutas = _parsear_linhas(conteudo)

    vinculos_por_apelido: dict[str, PrestadorTomador] = {
        v.apelido.strip().lower(): v for v in listar_vinculos_ativos(db)
    }

    resultados: list[LinhaImportada] = []
    for numero, linha in enumerate(linhas_brutas, start=2):  # linha 1 = cabeçalho
        apelido_bruto = (linha.get("apelido") or "").strip()
        savepoint = db.begin_nested()
        try:
            if not apelido_bruto:
                raise ValueError("coluna 'apelido' vazia")
            vinculo = vinculos_por_apelido.get(apelido_bruto.lower())
            if vinculo is None:
                raise ValueError(f"vínculo/fornecedor '{apelido_bruto}' não encontrado (confira o apelido)")

            competencia = (linha.get("competencia") or "").strip()
            if not competencia:
                raise ValueError("coluna 'competencia' vazia")

            valor = _parsear_valor(linha.get("valor") or "")
            ordem = (linha.get("ordem") or "").strip() or None
            aliq_sn_bruto = (linha.get("aliq_sn") or "").strip()
            aliq_sn = _parsear_valor(aliq_sn_bruto) if aliq_sn_bruto else None
            tpAmb = (linha.get("tpamb") or "").strip() or "2"

            emissao = criar_rascunho(db, vinculo, competencia=competencia, valor=valor, ordem=ordem, aliq_sn=aliq_sn, tpAmb=tpAmb)
            emissao = montar(db, emissao)
        except EmissaoJaExisteError as exc:
            savepoint.rollback()
            resultados.append(LinhaImportada(linha=numero, apelido=apelido_bruto, ok=False, mensagem=str(exc)))
        except DescricaoIncompletaError as exc:
            savepoint.rollback()
            resultados.append(LinhaImportada(linha=numero, apelido=apelido_bruto, ok=False, mensagem=str(exc)))
        except (ValueError, KeyError) as exc:
            savepoint.rollback()
            resultados.append(LinhaImportada(linha=numero, apelido=apelido_bruto, ok=False, mensagem=str(exc)))
        else:
            savepoint.commit()  # libera o savepoint (não é commit real — ainda dentro da transação de fora)
            resultados.append(LinhaImportada(
                linha=numero, apelido=apelido_bruto, ok=True, emissao_id=emissao.id, n_dps=emissao.n_dps,
            ))
    return resultados
