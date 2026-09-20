"""Registro de despesas — Marco 8. Ao contrário de emissão/pagamento, não é
por fornecedor: é por categoria (Pro Labore, INSS, Simples Nacional, ...),
igual à seção "Despesas" da planilha real do Marcos."""
import uuid

from sqlalchemy.orm import Session

from app.models import Despesa


def registrar_despesa(db: Session, prestador_id: uuid.UUID, *, categoria: str, competencia: str, valor: float) -> Despesa:
    despesa = Despesa(id=uuid.uuid4(), prestador_id=prestador_id, categoria=categoria, competencia=competencia, valor=valor)
    db.add(despesa)
    db.flush()
    return despesa
