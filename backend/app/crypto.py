"""
Criptografia em repouso do certificado A1 — Marco 4 do plano ("KMS desde a
Fase 1", decisão tomada na revisão do Gemini: o esquema já nasce pronto pra
trocar chave local por KMS de verdade sem migração de schema).

HOJE (Fase 1, só a Raiana): uma única chave simétrica Fernet, lida de
`settings.cert_master_key` (env var / .env local — nunca hardcoded em
produção). Fernet já é autenticado (Reforço: detecta adulteração, não só
confidencialidade) e cuida de nonce/IV sozinho — não precisamos reinventar
isso.

QUANDO houver hospedagem escolhida (Marco 4 "de verdade" em produção): troca
por envelope encryption via AWS Secrets Manager / GCP Secret Manager. A
troca é só implementar `Descriptografador`/`Criptografador` com outro
backend — `Certificado.chave_kms_ref` já guarda qual chave/versão cifrou
cada linha, então dá pra ter linhas antigas (Fernet local) e novas (KMS)
convivendo durante a migração, sem downtime nem reprocessar tudo de uma vez.

Nunca logar `pfx_criptografado`/`senha_criptografada` nem os valores
decriptografados — só passam por memória, nunca por disco fora do
certificado original do usuário.
"""
from cryptography.fernet import Fernet, InvalidToken

REF_CHAVE_LOCAL_DEV = "local-fernet-v1"


class ChaveInvalidaError(ValueError):
    """cert_master_key não é uma chave Fernet válida (32 bytes urlsafe-base64)."""


class DescriptografiaFalhouError(ValueError):
    """Dados corrompidos, chave errada, ou cifrados com uma chave/versão que
    não é a configurada agora (ver chave_kms_ref)."""


def gerar_chave_local() -> str:
    """Gera uma nova chave Fernet válida — usar pra popular
    CERT_MASTER_KEY em dev/homologação. Cada geração invalida o que foi
    cifrado com a chave anterior (guardar com cuidado, é segredo)."""
    return Fernet.generate_key().decode("ascii")


def _fernet(chave_b64: str) -> Fernet:
    try:
        return Fernet(chave_b64.encode("ascii"))
    except Exception as exc:  # cryptography levanta ValueError genérico
        raise ChaveInvalidaError(
            "cert_master_key não é uma chave Fernet válida — gere uma nova com "
            "app.crypto.gerar_chave_local() e configure via env var/.env."
        ) from exc


def criptografar(dados: bytes, chave_b64: str) -> bytes:
    return _fernet(chave_b64).encrypt(dados)


def descriptografar(dados_cifrados: bytes, chave_b64: str) -> bytes:
    try:
        return _fernet(chave_b64).decrypt(dados_cifrados)
    except InvalidToken as exc:
        raise DescriptografiaFalhouError(
            "Falha ao descriptografar — chave errada/rotacionada, ou dados corrompidos."
        ) from exc
