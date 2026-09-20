"""
Canais de envio — Marco 9 do plano. Usa o modelo `Envio` (já desenhado no
Marco 1, nunca usado até agora): registra TENTATIVAS de entregar a nota ao
fornecedor, deliberadamente independente da máquina de estados fiscal do
motor de emissão — "falha de envio nunca invalida uma nota já confirmada"
(docstring de `Envio` em app/models.py).

Duas categorias bem diferentes de canal, e importa não confundir:

- 'download' e 'mensagem_pronta': o próprio app GERA o conteúdo (o XML pra
  baixar, ou um texto pronto pra copiar/colar) — não fazem chamada de rede
  nenhuma, então "enviar" aqui só significa "entreguei pra Raiana usar como
  quiser". Por isso entram já como status='enviado' no momento em que o
  registro é criado.
- 'email', 'whatsapp', 'direto_fornecedor': este sandbox não tem rede
  liberada pra internet (mesma limitação de sempre — ver ClienteSefin) nem
  credenciais de e-mail/WhatsApp configuradas, então NENHUM desses envia de
  verdade. O registro fica 'pendente' até a Raiana confirmar manualmente
  (marcar_enviado) que enviou por fora, ou marcar_falha se não conseguiu.
  Automatizar isso de verdade (SMTP, API do WhatsApp Business, ...) é um
  próximo passo natural, não construído aqui de propósito — mesma decisão
  que já foi tomada pra submissão à Sefin.

IMPORTANTE sobre RLS: `envio` NÃO tem prestador_id próprio nem policy de
RLS (ver comentário na migração do Marco 1 — "no direct prestador_id
column"). A única barreira de tenant é o JOIN com `emissao`, que TEM RLS.
Por isso toda função aqui ou recebe um objeto `Emissao` já carregado (e
portanto já filtrado por RLS) ou, pra buscar um Envio direto pelo id
(`buscar_envio`), faz o JOIN explícito com `emissao` — nunca uma query
direta em `Envio` por id sozinha, que vazaria entre tenants.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Emissao, Envio

CANAIS_VALIDOS = {"download", "email", "whatsapp", "direto_fornecedor", "mensagem_pronta"}
CANAIS_AUTO_ENVIADOS = {"download", "mensagem_pronta"}  # gerar o conteúdo JÁ é a entrega


class EmissaoSemConteudoError(Exception):
    """Emissão ainda em rascunho — não há XML nem dados pra gerar
    mensagem/download/envio."""


class CanalInvalidoError(Exception):
    pass


def _exigir_conteudo_disponivel(emissao: Emissao) -> None:
    if emissao.estado == "rascunho":
        raise EmissaoSemConteudoError(
            "Emissão ainda em rascunho — monte a nota (POST /api/dps) antes de gerar mensagem, download ou envio."
        )


def gerar_mensagem_pronta(emissao: Emissao) -> str:
    """Texto pronto pra copiar/colar (WhatsApp, e-mail, o que for) — usa o
    snapshot congelado no rascunho (Marco 6), não o catálogo ao vivo, mesma
    garantia anti-edição-retroativa das outras partes do sistema."""
    _exigir_conteudo_disponivel(emissao)
    snap = emissao.tomador_snapshot
    valor_fmt = f"{float(emissao.valor):.2f}".replace(".", ",")

    linhas = [
        f"Olá! Segue a nota fiscal referente a: {snap.get('descricao_renderizada', emissao.competencia)}",
        f"Fornecedor: {snap.get('apelido', '')}",
        f"Competência: {emissao.competencia}",
        f"Valor: R$ {valor_fmt}",
    ]
    if emissao.chave_acesso:
        linhas.append(f"Chave de acesso da NFS-e: {emissao.chave_acesso}")
    else:
        linhas.append("(Nota ainda não confirmada pela prefeitura — a chave de acesso sai depois da submissão.)")
    return "\n".join(linhas)


def melhor_xml_disponivel(emissao: Emissao) -> tuple[str, str]:
    """O XML mais 'avançado' disponível pro estado atual da emissão — NÃO é
    o DANFSE oficial da prefeitura (isso só existe depois de uma submissão
    real à Sefin, nunca validada por este sistema, ver motor_emissao.py):
    é o XML da DPS (rascunho/assinado) ou, se já confirmado, a resposta
    real da Sefin."""
    _exigir_conteudo_disponivel(emissao)
    if emissao.xml_resposta:
        return f"nfse_ndps{emissao.n_dps}_confirmada.xml", emissao.xml_resposta
    if emissao.xml_assinado:
        return f"dps_ndps{emissao.n_dps}_assinada.xml", emissao.xml_assinado
    return f"dps_ndps{emissao.n_dps}_montada.xml", emissao.xml_dps


def registrar_envio(db: Session, emissao: Emissao, canal: str) -> Envio:
    if canal not in CANAIS_VALIDOS:
        raise CanalInvalidoError(f"Canal inválido: '{canal}'. Válidos: {', '.join(sorted(CANAIS_VALIDOS))}")
    _exigir_conteudo_disponivel(emissao)

    envio = Envio(id=uuid.uuid4(), emissao_id=emissao.id, canal=canal, tentativas=1)
    if canal in CANAIS_AUTO_ENVIADOS:
        envio.status = "enviado"
        envio.enviado_em = datetime.now(timezone.utc)
    else:
        envio.status = "pendente"
    db.add(envio)
    db.flush()
    return envio


def buscar_envio(db: Session, envio_id: uuid.UUID) -> Envio | None:
    """JOIN com `emissao` de propósito — é isso que aplica RLS aqui (ver
    docstring do módulo). Nunca troque por uma query direta em Envio."""
    return db.query(Envio).join(Emissao, Envio.emissao_id == Emissao.id).filter(Envio.id == envio_id).one_or_none()


def listar_envios(db: Session, emissao: Emissao) -> list[Envio]:
    return db.query(Envio).filter_by(emissao_id=emissao.id).order_by(Envio.criado_em.desc()).all()


def marcar_enviado(db: Session, envio: Envio) -> Envio:
    envio.status = "enviado"
    envio.enviado_em = datetime.now(timezone.utc)
    db.flush()
    return envio


def marcar_falha(db: Session, envio: Envio) -> Envio:
    envio.status = "falha"
    envio.tentativas += 1
    db.flush()
    return envio
