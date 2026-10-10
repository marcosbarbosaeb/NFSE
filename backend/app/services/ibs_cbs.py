"""IBS e CBS na nota — parte da tela e da memória (2026.10.7).

Leitura do leiaute no raio-x técnico, seção 15: o esquema publicado (1.01,
dez/2025) é anterior à NT 009 e não tem `regApIBSCBSSN` nem `cAtvSN`, então
nesta versão NADA disso vai para o XML. O que existe:

- a ME/EPP do Simples diz como recolhe IBS e CBS (`regime_ibs_cbs`, padrão
  "tudo pelo Simples") e desde quando; MEI e não optante não escolhem;
- a classificação tributária (`cClassTrib`) e o código da operação
  (`cIndOp`) ficam guardados no tomador como memória;
- a conferência avisa, em nota de competência de 2027 em diante, quando a
  classificação falta;
- "Precisa da sua atenção" pede a confirmação antes da virada do semestre
  (a opção pelo regime regular vale por semestre);
- o PDF mostra IBS e CBS quando a nota autorizada trouxer os valores (quem
  calcula é a Sefin, não a Ana).
"""
from __future__ import annotations

import datetime
import re

from app.tempo import hoje as hoje_br

OPCOES = {
    "1": "IBS e CBS pelo Simples Nacional",
    "2": "CBS pelo Simples e IBS pelo regime regular",
    "3": "IBS e CBS pelo regime regular",
}
PADRAO = "1"
INICIO = "2027-01"  # Simples: o grupo IBS/CBS passa a ser obrigatório em 2027
_SEIS_DIGITOS = re.compile(r"^\d{6}$")


def escolhe(prestador) -> bool:
    """Só a ME/EPP optante do Simples escolhe (MEI não tem a opção)."""
    return prestador is not None and (prestador.op_simples_nacional or "") == "3"


def regime(prestador) -> str | None:
    if not escolhe(prestador):
        return None
    return prestador.regime_ibs_cbs if prestador.regime_ibs_cbs in OPCOES else PADRAO


def limpar_codigo(valor: str | None) -> str | None:
    """cClassTrib / cIndOp: 6 dígitos (aceita pontos e espaços na digitação)."""
    so = re.sub(r"\D", "", valor or "")
    if not so:
        return None
    if not _SEIS_DIGITOS.match(so):
        raise ValueError("O código tem 6 números.")
    return so


def semestre_seguinte(hoje: datetime.date) -> str:
    return f"{hoje.year + 1:04d}-01" if hoje.month >= 7 else f"{hoje.year:04d}-07"


def _inicio_da_janela(hoje: datetime.date) -> datetime.date | None:
    """Os dois meses antes da virada do semestre: maio-junho e novembro-dezembro."""
    if hoje.month in (5, 6):
        return datetime.date(hoje.year, 5, 1)
    if hoje.month in (11, 12):
        return datetime.date(hoje.year, 11, 1)
    return None


def precisa_confirmar(prestador, hoje: datetime.date | None = None) -> bool:
    hoje = hoje or hoje_br()
    if not escolhe(prestador):
        return False
    janela = _inicio_da_janela(hoje)
    if janela is None:
        return False
    return prestador.ibs_cbs_confirmado_em is None or prestador.ibs_cbs_confirmado_em < janela


def aviso_de_atencao(prestador, hoje: datetime.date | None = None) -> dict | None:
    hoje = hoje or hoje_br()
    if not precisa_confirmar(prestador, hoje):
        return None
    sem = semestre_seguinte(hoje)
    quando = f"{'janeiro' if sem.endswith('-01') else 'julho'} de {sem[:4]}"
    return {
        "titulo": "IBS e CBS: confirme como a empresa recolhe",
        "mensagem": (
            f"Com a reforma tributária, a partir de {quando} a nota leva IBS e CBS. Hoje está marcado: "
            f"{OPCOES[regime(prestador)].lower()}. Confirme com o seu contador e salve em Empresa."
        ),
        "link": "/app/empresa?aba=emitente#ibs-cbs",
    }


def confere_classificacao(prestador, vinculo, competencia: str | None) -> bool:
    """True quando a nota deveria avisar que falta a classificação."""
    if not escolhe(prestador) or vinculo is None or getattr(vinculo, "sem_nota", False):
        return False
    if not competencia or competencia[:7] < INICIO:
        return False
    return not (vinculo.cclass_trib or "").strip()


def valores_da_nota(inf_nfse) -> list[tuple[str, str]] | None:
    """Lê o grupo IBSCBS da NFS-e autorizada (valores calculados pela Sefin).
    Devolve pares (rótulo, valor em texto cru) ou None quando a nota não tem."""
    if inf_nfse is None:
        return None
    from lxml import etree

    grupo = None
    for filho in inf_nfse:
        if isinstance(filho.tag, str) and etree.QName(filho).localname == "IBSCBS":
            grupo = filho
            break
    if grupo is None:
        return None

    def achar(nome):
        for el in grupo.iter():
            if isinstance(el.tag, str) and etree.QName(el).localname == nome and (el.text or "").strip():
                return el.text.strip()
        return None

    pares = [
        ("Base de cálculo", achar("vBC"), "brl"),
        ("IBS", achar("vIBSTot"), "brl"),
        ("CBS", achar("vCBS"), "brl"),
        ("IBS no Simples", achar("vIBSSN"), "brl"),
        ("Alíquota IBS no Simples", achar("pIBSSN"), "pct"),
        ("CBS no Simples", achar("vCBSSN"), "brl"),
        ("Alíquota CBS no Simples", achar("pCBSSN"), "pct"),
        ("Total da nota com IBS e CBS", achar("vTotNF"), "brl"),
    ]
    saida = [(r, v, t) for r, v, t in pares if v is not None]
    return saida or None
