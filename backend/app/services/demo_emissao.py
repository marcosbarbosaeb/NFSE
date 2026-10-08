"""Caminho feliz SIMULADO da simulação (modo demonstração, 08/10/2026).

Pedido do Marcos: "na simulação, 'Gerar e fazer tudo' deve retornar sucesso
simulado em assinar, enviar à prefeitura e entregar ao tomador (hoje para em
'Nota gerada, mas não deu pra assinar'). Contadores e financeiro atualizam
como numa emissão real." E a trava: "o modo só funciona na simulação, nunca
em conta real".

Por isso `eh_simulacao` exige as DUAS marcas da conta de simulação — o
usuário da sessão com o e-mail do domínio da simulação E a empresa com
`Prestador.demo` — e as rotas de assinar/enviar/entregar só desviam pra cá
quando as duas batem. Nada aqui fala com o mundo de fora: não há certificado,
Receita nem e-mail. A nota fica como uma nota autorizada de homologação (o
PDF sai com "SEM VALIDADE JURÍDICA"), com chave e número inventados.
"""
from __future__ import annotations

import datetime
import secrets
import uuid

from lxml import etree
from sqlalchemy.orm import Session

from app.models import Emissao, Envio, Prestador, Usuario
from app.services.demo import eh_email_demo
from app.services.motor_emissao import TransicaoInvalidaError

_NS = "http://www.sped.fazenda.gov.br/nfse"


def eh_simulacao(db: Session, usuario_id: str | uuid.UUID | None, prestador_id: uuid.UUID | None) -> bool:
    if not usuario_id or prestador_id is None:
        return False
    usuario = db.get(Usuario, uuid.UUID(str(usuario_id)))
    if usuario is None or not eh_email_demo(usuario.email):
        return False
    prestador = db.get(Prestador, prestador_id)
    return prestador is not None and bool(prestador.demo)


def _exigir(emissao: Emissao, *estados: str) -> None:
    if emissao.estado not in estados:
        raise TransicaoInvalidaError(f"Emissão em estado '{emissao.estado}', esperado um de {estados}.")


def assinar(db: Session, emissao: Emissao) -> Emissao:
    """montado -> assinado, sem certificado (a "assinatura" é o próprio XML)."""
    _exigir(emissao, "montado")
    emissao.xml_assinado = emissao.xml_dps
    emissao.estado = "assinado"
    emissao.atualizado_em = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return emissao


def _chave(emissao: Emissao, prestador: Prestador | None) -> str:
    mun = (prestador.cod_municipio if prestador else None) or "3550308"
    return (mun + "2" + "".join(secrets.choice("0123456789") for _ in range(50)))[:50]


def _numero(db: Session, emissao: Emissao) -> int:
    ja = db.query(Emissao).filter(Emissao.prestador_id == emissao.prestador_id, Emissao.chave_acesso.isnot(None)).count()
    return ja + 1


def xml_nfse_simulada(emissao: Emissao, prestador: Prestador | None, numero: int, chave: str) -> str:
    """Um XML de NFS-e mínimo em volta da DPS — o bastante pro PDF (DANFSe)
    mostrar número, data de processamento e emitente."""
    agora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).replace(microsecond=0)
    nfse = etree.Element(f"{{{_NS}}}NFSe", nsmap={None: _NS})
    inf = etree.SubElement(nfse, f"{{{_NS}}}infNFSe", Id=f"NFS{chave}")
    etree.SubElement(inf, f"{{{_NS}}}xLocEmi").text = "Simulação Agente Ana"
    etree.SubElement(inf, f"{{{_NS}}}nNFSe").text = str(numero)
    etree.SubElement(inf, f"{{{_NS}}}dhProc").text = agora.isoformat()
    emit = etree.SubElement(inf, f"{{{_NS}}}emit")
    etree.SubElement(emit, f"{{{_NS}}}CNPJ").text = prestador.cpf_cnpj if prestador else ""
    etree.SubElement(emit, f"{{{_NS}}}xNome").text = prestador.razao_social if prestador else ""
    ender = etree.SubElement(emit, f"{{{_NS}}}enderNac")
    etree.SubElement(ender, f"{{{_NS}}}cMun").text = (prestador.cod_municipio if prestador else None) or "3550308"
    valores = etree.SubElement(inf, f"{{{_NS}}}valores")
    etree.SubElement(valores, f"{{{_NS}}}vLiq").text = f"{float(emissao.valor):.2f}"
    bruto = emissao.xml_assinado or emissao.xml_dps
    if bruto:
        inf.append(etree.fromstring(bruto.encode("utf-8")))
    return etree.tostring(nfse, xml_declaration=True, encoding="UTF-8").decode()


def autorizar(db: Session, emissao: Emissao) -> Emissao:
    """assinado (ou erro) -> confirmado, como se a prefeitura tivesse autorizado."""
    _exigir(emissao, "assinado", "erro")
    prestador = db.get(Prestador, emissao.prestador_id)
    chave = _chave(emissao, prestador)
    emissao.chave_acesso = chave
    emissao.xml_resposta = xml_nfse_simulada(emissao, prestador, _numero(db, emissao), chave)
    emissao.estado = "confirmado"
    emissao.erro_detalhe = None
    emissao.atualizado_em = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return emissao


def entregar(db: Session, emissao: Emissao, destino: str | None = None, canal: str = "email") -> Envio:
    """Envio ao tomador registrado como feito — nenhum e-mail sai."""
    if emissao.estado != "confirmado":
        raise TransicaoInvalidaError("Só dá pra entregar uma nota autorizada.")
    envio = Envio(
        id=uuid.uuid4(), emissao_id=emissao.id, canal=canal, tentativas=1, status="enviado",
        destino=(destino or "financeiro@exemplo.com.br")[:200], enviado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(envio)
    db.flush()
    return envio


def fazer_tudo(db: Session, emissao: Emissao, destino: str | None = None, entregue: bool = True) -> Emissao:
    """Pros dados do cenário: a nota passada já autorizada (e entregue)."""
    assinar(db, emissao)
    autorizar(db, emissao)
    if entregue:
        entregar(db, emissao, destino)
    return emissao
