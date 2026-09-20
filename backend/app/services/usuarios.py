"""Login multiusuário — Marco 10. Serviço fino: autenticação (login) e
criação de conta (usada pelo scripts/criar_usuario.py, não exposta como
endpoint público — cadastro de usuário é administrativo nesta fase, não
self-service)."""
import uuid

from sqlalchemy.orm import Session

from app.auth import hash_senha, verificar_senha
from app.models import Usuario


class EmailJaCadastradoError(Exception):
    pass


def autenticar(db: Session, email: str, senha: str) -> Usuario | None:
    """Devolve o Usuario se e-mail+senha baterem e a conta estiver ativa,
    senão None — nunca diz QUAL dos dois (e-mail ou senha) errou, pra não
    ajudar quem está tentando adivinhar contas válidas."""
    usuario = db.query(Usuario).filter_by(email=email.strip().lower(), ativo=True).one_or_none()
    if usuario is None:
        return None
    if not verificar_senha(senha, usuario.senha_hash):
        return None
    return usuario


def criar_usuario(db: Session, prestador_id: uuid.UUID, email: str, senha: str) -> Usuario:
    email_norm = email.strip().lower()
    if db.query(Usuario).filter_by(email=email_norm).one_or_none() is not None:
        raise EmailJaCadastradoError(f"Já existe um usuário com o e-mail '{email_norm}'.")
    usuario = Usuario(id=uuid.uuid4(), prestador_id=prestador_id, email=email_norm, senha_hash=hash_senha(senha))
    db.add(usuario)
    db.flush()
    return usuario
