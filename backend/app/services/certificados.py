"""
Serviço de armazenamento seguro do certificado A1 — Marco 4 do plano.

Junta duas peças que já existiam separadas: app.crypto (cifra/decifra
bytes) e app.fiscal.certificado (abre um .pfx e devolve private_key/cert
utilizáveis). Este módulo é a única porta de entrada/saída do certificado
guardado no Postgres — nada fora daqui deveria tocar
`Certificado.pfx_criptografado`/`senha_criptografada` diretamente.

Toda função aqui assume que `db` já está numa transação com
`definir_prestador_atual` chamado (a RLS da tabela `certificado` depende
disso — ver app/database.py e a migração de RLS). Isso não é feito aqui
dentro de propósito: quem chama é a camada de requisição (Marco 5/6), que
sabe qual prestador está autenticado; este serviço não deveria decidir isso
sozinho.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.crypto import REF_CHAVE_LOCAL_DEV, criptografar, descriptografar
from app.fiscal.certificado import carregar_pfx
from app.models import Certificado


class CertificadoNaoEncontradoError(LookupError):
    """Nenhum certificado cadastrado para este prestador (ou a RLS não deixou
    ver — checar se `definir_prestador_atual` foi chamado)."""


def salvar_certificado(
    db: Session,
    prestador_id: uuid.UUID,
    pfx_bytes: bytes,
    senha: str,
    chave_mestra: str,
) -> Certificado:
    """Valida o .pfx (abre de verdade, com a senha informada — falha cedo e
    com mensagem clara se a senha estiver errada ou o arquivo corrompido),
    extrai a validade do certificado X.509, cifra pfx+senha e faz upsert na
    tabela `certificado` (um por prestador, ver unique constraint).

    Nunca loga pfx_bytes/senha/chave_mestra nem os deixa em disco — tudo em
    memória, do início ao fim.
    """
    # Falha cedo: se a senha estiver errada, é melhor saber agora do que na
    # hora de assinar uma DPS de verdade (ver Contingências no plano).
    _private_key, cert = carregar_pfx(pfx_bytes, senha)
    validade: date = cert.not_valid_after_utc.date() if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.date()

    pfx_cifrado = criptografar(pfx_bytes, chave_mestra)
    senha_cifrada = criptografar(senha.encode("utf-8"), chave_mestra)

    existente = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if existente is not None:
        existente.pfx_criptografado = pfx_cifrado
        existente.senha_criptografada = senha_cifrada
        existente.chave_kms_ref = REF_CHAVE_LOCAL_DEV
        existente.validade = validade
        existente.atualizado_em = datetime.now(timezone.utc)
        db.flush()
        return existente

    registro = Certificado(
        id=uuid.uuid4(),
        prestador_id=prestador_id,
        pfx_criptografado=pfx_cifrado,
        senha_criptografada=senha_cifrada,
        chave_kms_ref=REF_CHAVE_LOCAL_DEV,
        validade=validade,
    )
    db.add(registro)
    db.flush()
    return registro


def carregar_certificado(db: Session, prestador_id: uuid.UUID, chave_mestra: str):
    """Devolve (private_key, cert) prontos pra assinar — mesmo formato que
    app.fiscal.certificado.carregar_pfx devolve direto de um arquivo, só que
    lendo do banco em vez de disco."""
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        raise CertificadoNaoEncontradoError(f"Nenhum certificado cadastrado para prestador_id={prestador_id}")

    pfx_bytes = descriptografar(registro.pfx_criptografado, chave_mestra)
    senha = descriptografar(registro.senha_criptografada, chave_mestra).decode("utf-8")
    return carregar_pfx(pfx_bytes, senha)


def certificado_vencido(certificado: Certificado, referencia: date | None = None) -> bool:
    """Ajuda a implementar o alerta de 'certificado vencido' do plano
    (Contingências) sem cada chamador reimplementar a comparação de data."""
    if certificado.validade is None:
        return False
    return certificado.validade < (referencia or date.today())
