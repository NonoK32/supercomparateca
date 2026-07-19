from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/productos", tags=["productos"])


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
    db.commit()
