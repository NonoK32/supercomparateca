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


@router.post("/lista", response_model=schemas.ComparativaLista)
def comparar_lista(
    payload: schemas.ListaCompra,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    """La lista de la compra de hoy: precios de cada producto y dónde sale mejor
    comprarlo todo.

    Es un POST aunque no cree nada: la lista es la entrada del cálculo y puede
    traer decenas de ids, que en la URL quedarían incómodos de leer y de
    registrar. **No se guarda**.

    Los ids que no existan se ignoran en vez de dar 404: la lista vive en el
    navegador y un producto puede haber desaparecido del catálogo desde que se
    añadió; tirar la petición entera por eso obligaría al usuario a adivinar
    cuál sobra.
    """
    return consultas.comparativa_lista(db, payload.producto_ids)
