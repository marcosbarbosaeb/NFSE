#!/usr/bin/env python3
"""
Marco 10: cria (ou atualiza a senha de) um usuário de login, vinculado a um
prestador que já existe no banco. Cadastro é administrativo nesta fase —
não há self-service signup no painel de propósito (ver docstring de
app.main:api_login).

Idempotente por e-mail: se o e-mail já existe, ATUALIZA a senha (e o
prestador_id, se `--prestador-id` foi passado) em vez de falhar — útil pra
resetar senha sem precisar de outro script.

`--prestador-id` é OPCIONAL: se omitido, o script procura o único
Prestador cadastrado no banco (é o caso normal — MVP é um prestador por
banco, ver docstring de Prestador em app/models.py) e usa ele. Se não
achar nenhum ou achar mais de um, pede pra você especificar explicitamente
— não existe um id "certo" fixo entre bancos diferentes (cada deploy tem o
seu, gerado na hora do scripts/migrar_fornecedores.py).

A senha NUNCA é aceita como argumento de linha de comando em texto puro por
padrão (ficaria no histórico do shell e em `ps`/`/proc` enquanto roda) — o
script pede com `getpass` (não ecoa na tela). `--senha` existe só pra uso
não-interativo (CI, provisionamento automatizado); quem usar isso é
responsável por não deixar a senha em histórico de shell/logs.

Mesma lógica de conexão do scripts/migrar_fornecedores.py: superusuário
`postgres` (bypassa RLS), porque `prestador` TEM RLS e este script precisa
ler/validar aquele prestador antes de qualquer sessão de usuário existir.

Uso:
    python3 scripts/criar_usuario.py --email raiana@exemplo.com [--prestador-id ...] --database-url postgresql://...
    (pede a senha interativamente; --database-url deve apontar pro usuário
    ADMINISTRADOR do Postgres — em produção, o do provedor, não o
    nfse_app/nfse_dev de runtime, que não tem acesso RLS-livre a prestador)
"""
import argparse
import sys
import uuid
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import hash_senha
from app.models import Prestador, Usuario

DEFAULT_ADMIN_DATABASE_URL = "postgresql+psycopg://postgres:postgres_dev_local@localhost:5432/nfse_saas"


def _resolver_prestador(db: Session, prestador_id: uuid.UUID | None) -> Prestador:
    if prestador_id is not None:
        prestador = db.get(Prestador, prestador_id)
        if prestador is None:
            raise SystemExit(f"Prestador {prestador_id} não encontrado — rode scripts/migrar_fornecedores.py antes, ou confira o id.")
        return prestador

    prestadores = db.query(Prestador).all()
    if len(prestadores) == 0:
        raise SystemExit("Nenhum prestador cadastrado — rode scripts/migrar_fornecedores.py antes.")
    if len(prestadores) > 1:
        listagem = "\n".join(f"  {p.id}  {p.razao_social}" for p in prestadores)
        raise SystemExit(f"Mais de um prestador no banco — especifique --prestador-id:\n{listagem}")
    return prestadores[0]


def criar_ou_atualizar(db: Session, *, email: str, senha: str, prestador_id: uuid.UUID | None) -> Usuario:
    prestador = _resolver_prestador(db, prestador_id)
    prestador_id = prestador.id

    email_norm = email.strip().lower()
    usuario = db.query(Usuario).filter_by(email=email_norm).one_or_none()
    if usuario is None:
        usuario = Usuario(
            id=uuid.uuid4(), email=email_norm, prestador_id=prestador_id, senha_hash=hash_senha(senha),
            email_confirmado=True,  # caminho administrativo — ver docstring de criar_usuario em app/services/usuarios.py
        )
        db.add(usuario)
        acao = "criado"
    else:
        usuario.senha_hash = hash_senha(senha)
        usuario.prestador_id = prestador_id
        usuario.ativo = True
        usuario.email_confirmado = True  # reset administrativo também confirma, mesmo se o cadastro original era self-service pendente
        acao = "atualizado"
    db.flush()
    print(f"Usuário {acao}: {usuario.email} -> prestador {prestador.razao_social} ({prestador_id})")
    return usuario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--senha", help="Se omitido, pede interativamente (recomendado).")
    parser.add_argument("--prestador-id", default=None, help="Omitir usa o único prestador do banco, se houver só um.")
    parser.add_argument("--database-url", default=DEFAULT_ADMIN_DATABASE_URL)
    args = parser.parse_args()

    senha = args.senha or getpass("Senha para a nova conta: ")
    if len(senha) < 8:
        raise SystemExit("Senha precisa ter pelo menos 8 caracteres.")

    prestador_id = uuid.UUID(args.prestador_id) if args.prestador_id else None
    engine = create_engine(args.database_url)
    with Session(engine) as db:
        criar_ou_atualizar(db, email=args.email, senha=senha, prestador_id=prestador_id)
        db.commit()


if __name__ == "__main__":
    main()
