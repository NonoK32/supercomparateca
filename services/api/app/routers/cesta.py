from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import consultas, models, schemas
from ..database import get_db
from ..seguridad import get_current_user

router = APIRouter(prefix="/cesta", tags=["cesta"])


@router.get("/comparativa", response_model=schemas.ComparativaCesta)
def comparativa(
    limite: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    """FR10: cuánto costaría tu cesta habitual en cada supermercado.

    La cesta sale de tus propios tickets; los precios, del histórico compartido
    por todos los usuarios.
    """
    return consultas.comparativa_cesta(db, usuario.id, limite)
