"""
Biblioteca fiscal importável — Marco 3 do plano.

Porta de integracao/{build_dps,sign_dps,submit_dps,consultar_dps,
consultar_nfse,cancelar_nfse}.py, decouplada do dict FORNECEDORES hardcoded
(agora recebe dados prontos — o Marco 6 monta esses dados a partir do
Postgres) e com a duplicação de código de assinatura/HTTP consolidada. Os
scripts originais em integracao/ continuam intactos e são o que roda de
verdade hoje.
"""
from app.fiscal.cliente_sefin import BASES, ClienteSefin, RespostaSefin
from app.fiscal.dps import (
    DescricaoIncompletaError,
    assinar_dps,
    montar_dps_xml,
    montar_id_dps,
    renderizar_descricao,
)
from app.fiscal.eventos import (
    CODIGO_EVENTO_CANCELAMENTO,
    MOTIVOS_CANCELAMENTO,
    assinar_evento,
    montar_evento_cancelamento,
)
from app.fiscal.certificado import carregar_pfx, pem_temporario

__all__ = [
    "BASES",
    "ClienteSefin",
    "RespostaSefin",
    "DescricaoIncompletaError",
    "assinar_dps",
    "montar_dps_xml",
    "montar_id_dps",
    "renderizar_descricao",
    "CODIGO_EVENTO_CANCELAMENTO",
    "MOTIVOS_CANCELAMENTO",
    "assinar_evento",
    "montar_evento_cancelamento",
    "carregar_pfx",
    "pem_temporario",
]
