"""
Configuração do backend, lida de variáveis de ambiente.

Nada de segredo com valor-padrão hardcoded aqui: em produção, DATABASE_URL e
CERT_MASTER_KEY vêm do provedor de hospedagem/KMS (ver Marco 4 do plano). Os
defaults abaixo só existem pra rodar local, contra o Postgres de desenvolvimento
que a gente acabou de subir nesta sessão.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://nfse_dev:nfse_dev_local@localhost:5432/nfse_saas"
    )

    # Chave simétrica (Fernet, 32 bytes urlsafe-base64) usada para
    # criptografar certificado/senha em repouso ENQUANTO não escolhemos
    # provedor de hospedagem e trocamos isso por envelope encryption via KMS
    # de verdade (AWS Secrets Manager / GCP Secret Manager — Marco 4 do
    # plano). O esquema da tabela `certificado` já foi desenhado pra essa
    # troca não exigir migração: `chave_kms_ref` guarda qual chave/versão
    # cifrou aquele registro.
    #
    # O valor abaixo É uma chave Fernet válida, mas É DE DESENVOLVIMENTO —
    # gerada nesta sessão (app.crypto.gerar_chave_local()), só serve pro
    # Postgres local desta máquina. Em produção, sempre via env var/.env
    # real (nunca este default) — e nunca versionada em git.
    cert_master_key: str = "VMQ063EE7ooDE2PpkdzF0zezlh7RcbR6sXlAKW4W9mY="

    # Histórico (Marco 5, Fase 1 sem login): o painel operava sempre como
    # este prestador fixo, sem sessão de usuário nenhuma. Substituído no
    # Marco 10 por login de verdade (ver Usuario em app/models.py e
    # prestador_atual_id em app/main.py) — nada mais lê este valor, mas ele
    # fica registrado aqui porque scripts/criar_usuario.py usa o MESMO id
    # como default pra vincular o primeiro usuário (Raiana) ao prestador
    # que já existe no banco (migrado por scripts/migrar_fornecedores.py).
    prestador_ativo_id: str = "036768a4-722f-4bb2-9601-c22bfe905398"

    # Assina o cookie de sessão (Marco 10 — login). MESMA ressalva do
    # cert_master_key: este default É válido mas É de desenvolvimento,
    # gerado nesta sessão só pra rodar local; em produção sempre via env
    # var/.env real, nunca este valor, nunca versionado em git. Trocar essa
    # chave em produção invalida sessões já abertas (todo mundo precisa
    # logar de novo) — não é destrutivo pra dado nenhum, só desloga geral.
    session_secret_key: str = "9f1c9f6b6a7e4b6c8d3a1e2f5c7b9a0d4e6f8b1c3a5d7e9f0b2c4a6e8d0f2b4c"

    # Marco 15 — cadastro público self-service (ver app/services/cadastro.py
    # e app/services/email.py). `resend_api_key` vazio (default) é o estado
    # "ainda não tenho conta no provedor" que o Marcos pediu pra já deixar
    # pronto: nesse caso o envio de e-mail cai pro EmailSenderConsole (só
    # imprime/loga o e-mail, nunca falha o cadastro) em vez de tentar falar
    # com a API de verdade — troca por uma chave real quando a conta Resend
    # existir, sem mudar nenhuma linha de código.
    resend_api_key: str = ""
    email_remetente: str = "NotaFácil <onboarding@resend.dev>"

    # Base da URL do painel usada pra montar o link de confirmação de e-mail
    # (ex.: f"{app_base_url}/confirmar-email?token=..."). Default é o Vite
    # dev server local — TROCAR via env var em produção pro domínio de
    # verdade assim que ele existir (ver Marco 15, item 4: página de
    # marketing + rota pública de cadastro).
    app_base_url: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
