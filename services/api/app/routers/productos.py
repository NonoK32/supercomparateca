from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import consultas, models, schemas
from ..database import get_db
from ..seguridad import get_current_user

router = APIRouter(
    prefix="/productos",
    tags=["productos"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=schemas.ProductoRead, status_code=status.HTTP_201_CREATED)
def crear(payload: schemas.ProductoCreate, db: Session = Depends(get_db)):
    producto = models.Producto(**payload.model_dump())
    db.add(producto)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un producto con ese nombre normalizado"
        )
    db.refresh(producto)
    return producto


@router.get("", response_model=list[schemas.ProductoRead])
def listar(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Producto)).all())


@router.get("/{producto_id}", response_model=schemas.ProductoRead)
def obtener(producto_id: int, db: Session = Depends(get_db)):
    producto = db.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return producto


@router.patch("/{producto_id}", response_model=schemas.ProductoRead)
def actualizar(
    producto_id: int, payload: schemas.ProductoUpdate, db: Session = Depends(get_db)
):
    producto = db.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un producto con ese nombre normalizado"
        )
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(producto_id: int, db: Session = Depends(get_db)):
    producto = db.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    db.delete(producto)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede eliminar: el producto está en uso",
        )


@router.get("/{producto_id}/precios", response_model=schemas.ComparativaPrecios)
def precios(producto_id: int, db: Session = Depends(get_db)):
    """FR7: precio más reciente del producto en cada supermercado."""
    producto = db.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return schemas.ComparativaPrecios(
        producto_id=producto.id,
        nombre_normalizado=producto.nombre_normalizado,
        supermercados=consultas.precios_por_supermercado(db, producto_id),
    )


@router.get("/{producto_id}/historico", response_model=schemas.HistoricoPrecios)
def historico(
    producto_id: int,
    supermercado_id: int | None = None,
    db: Session = Depends(get_db),
):
    """FR8: evolución del precio del producto en el tiempo."""
    producto = db.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return schemas.HistoricoPrecios(
        producto_id=producto.id,
        historico=consultas.historico(db, producto_id, supermercado_id),
    )
