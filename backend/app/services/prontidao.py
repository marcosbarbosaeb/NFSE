"""A empresa está pronta pra emitir? (06/10/2026)

"Quando a pessoa criar uma conta ela deve ser orientada a cadastrar o
certificado A1; senão não deve ser possível fazer as atividades
relacionadas à emissão das notas. Guie ela pra página da empresa pra
colocar os dados que faltam." Aqui fica a lista do que falta, na ordem em
que a pessoa resolve — a Visão geral mostra como "Primeiros passos" e as
telas de nota usam pra travar a emissão.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.tempo import hoje as hoje_br
from app.models import Certificado, Prestador, PrestadorTomador

SEM_CERTIFICADO = (
    "Antes de emitir, envie o certificado digital A1 da empresa em Empresa › Certificado. "
    "É com ele que eu assino a nota e falo com a prefeitura."
)
CERTIFICADO_VENCIDO = "O certificado digital da empresa venceu. Envie o novo em Empresa › Certificado pra voltar a emitir."


def motivo_que_trava(db: Session, prestador_id: uuid.UUID) -> str | None:
    """Por que esta empresa não pode gerar nota agora (None = pode).
    Simulação nunca assina nem envia nada: não precisa de certificado."""
    prestador = db.get(Prestador, prestador_id)
    if prestador is None or prestador.demo:
        return None
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        return SEM_CERTIFICADO
    if registro.validade is not None and registro.validade < hoje_br():
        return CERTIFICADO_VENCIDO
    return None


def _dados_que_faltam(prestador: Prestador) -> list[dict]:
    faltam: list[dict] = []
    endereco = [
        rotulo for campo, rotulo in (("cep", "CEP"), ("logradouro", "rua"), ("numero", "número"), ("bairro", "bairro"))
        if not str(getattr(prestador, campo) or "").strip()
    ]
    if endereco:
        faltam.append({"campo": "endereco", "rotulo": f"Endereço da empresa ({', '.join(endereco)})", "link": "/app/empresa?aba=emitente"})
    if not prestador.op_simples_nacional:
        faltam.append({"campo": "regime", "rotulo": "Regime tributário (Simples Nacional, MEI...)", "link": "/app/empresa?aba=emitente"})
    # "3" = ME/EPP do Simples: é quem informa a alíquota na nota.
    if prestador.op_simples_nacional == "3" and prestador.aliquota_atual is None:
        faltam.append({"campo": "aliquota", "rotulo": "Alíquota do Simples Nacional", "link": "/app/empresa?aba=aliquotas"})
    return faltam


def prontidao(db: Session, prestador_id: uuid.UUID) -> dict:
    prestador = db.get(Prestador, prestador_id)
    if prestador is None or prestador.demo:
        return {"aplica": False, "pode_emitir": True, "motivo": None, "certificado": "ok", "dados_faltando": [], "tomadores": 0, "pronta": True}
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        certificado = "falta"
    elif registro.validade is not None and registro.validade < hoje_br():
        certificado = "vencido"
    else:
        certificado = "ok"
    faltam = _dados_que_faltam(prestador)
    tomadores = (
        db.query(PrestadorTomador.id)
        .filter(PrestadorTomador.excluido_em.is_(None), PrestadorTomador.sem_nota.is_(False)).count()
    )
    motivo = SEM_CERTIFICADO if certificado == "falta" else CERTIFICADO_VENCIDO if certificado == "vencido" else None
    return {
        "aplica": True, "pode_emitir": motivo is None, "motivo": motivo, "certificado": certificado,
        "dados_faltando": faltam, "tomadores": tomadores,
        "pronta": motivo is None and not faltam and tomadores > 0,
    }
