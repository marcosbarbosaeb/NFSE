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
import re
import uuid
from datetime import date, datetime, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID
from sqlalchemy.orm import Session

from app.crypto import REF_CHAVE_LOCAL_DEV, criptografar, descriptografar
from app.fiscal.certificado import carregar_pfx
from app.models import Certificado
from app.tempo import hoje as hoje_br


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
    return certificado.validade < (referencia or hoje_br())


# --- "Importar emissor" (05/10/2026): ler o certificado sem guardar -----------

# ICP-Brasil: nos certificados de pessoa jurídica (e-CNPJ) o CNPJ vem num
# otherName do Subject Alternative Name com este OID, e o CN costuma ser
# "RAZAO SOCIAL:CNPJ". Nos de pessoa física (e-CPF) o CN é "NOME:CPF".
OID_ICP_CNPJ = "2.16.76.1.3.3"
_TAGS_TEXTO_DER = {0x04, 0x0C, 0x13, 0x14, 0x16, 0x1A, 0x1B, 0x1E, 0xA0}


class CertificadoIlegivelError(ValueError):
    """Não deu pra abrir o .pfx: senha errada ou arquivo que não é um A1.
    A mensagem é a que vai pra tela — nunca carrega a senha."""


def cnpj_valido(cnpj: str) -> bool:
    """Confere os dois dígitos verificadores (evita aceitar 14 números
    quaisquer que apareçam no certificado)."""
    if not re.fullmatch(r"\d{14}", cnpj or "") or len(set(cnpj)) == 1:
        return False

    def digito(base: str) -> str:
        pesos = list(range(len(base) - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = digito(cnpj[:12])
    return cnpj[12:] == d1 + digito(cnpj[:12] + d1)


def _conteudo_der(valor: bytes) -> bytes:
    """Tira o(s) cabeçalho(s) ASN.1 de um otherName (OCTET STRING,
    PrintableString, UTF8String... às vezes um dentro do outro). Se não
    parecer DER, devolve como veio."""
    for _ in range(3):
        if len(valor) >= 2 and valor[0] in _TAGS_TEXTO_DER and valor[1] < 0x80 and valor[1] == len(valor) - 2:
            valor = valor[2:]
        else:
            break
    return valor


def _cnpj_do_san(cert) -> str | None:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        outros = san.get_values_for_type(x509.OtherName)
    except Exception:  # noqa: BLE001 — sem SAN ou extensão fora do padrão: tenta o CN
        return None
    for outro in outros:
        if outro.type_id.dotted_string != OID_ICP_CNPJ:
            continue
        texto = _conteudo_der(bytes(outro.value)).decode("latin-1", errors="ignore")
        achado = re.search(r"(?<!\d)\d{14}(?!\d)", texto)
        if achado and cnpj_valido(achado.group(0)):
            return achado.group(0)
    return None


def dados_do_certificado(cert, referencia: date | None = None) -> dict:
    """O que dá pra saber de um certificado X.509 já aberto: de quem é
    (nome e CNPJ, quando é um e-CNPJ da ICP-Brasil) e a validade."""
    try:
        atributos = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        cn = str(atributos[0].value).strip() if atributos else ""
    except Exception:  # noqa: BLE001 — subject fora do padrão
        cn = ""
    nome, _, final = cn.rpartition(":")
    numeros = re.sub(r"\D", "", final) if nome else ""
    cnpj_cn = numeros if cnpj_valido(numeros) else None
    cnpj = _cnpj_do_san(cert) or cnpj_cn
    # "NOME:CPF" (11 números) e nenhum CNPJ = certificado de pessoa física.
    pessoa_fisica = cnpj is None and len(numeros) == 11
    titular = (nome.strip() if nome and numeros and len(numeros) in (11, 14) else cn) or None

    inicio = cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") else cert.not_valid_before
    fim = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after
    hoje = referencia or hoje_br()
    return {
        "titular": titular[:200] if titular else None,
        "cnpj": cnpj,
        "pessoa_fisica": pessoa_fisica,
        "valido_de": inicio.date(),
        "valido_ate": fim.date(),
        "vencido": fim.date() < hoje,
    }


def ler_certificado(pfx_bytes: bytes, senha: str) -> dict:
    """Abre o .pfx com a senha informada e devolve `dados_do_certificado` —
    SEM guardar nada (nem no banco, nem em disco, nem no log). É o primeiro
    passo de "Importar emissor": a pessoa confere de quem é o certificado
    antes de criar a empresa."""
    try:
        _private_key, cert = carregar_pfx(pfx_bytes, senha)
    except Exception as exc:  # noqa: BLE001 — senha errada ou arquivo que não é PKCS#12
        raise CertificadoIlegivelError(
            "Não consegui abrir o certificado. Confira se o arquivo é o .pfx ou .p12 do certificado A1 e se a senha está certa."
        ) from exc
    return dados_do_certificado(cert)
