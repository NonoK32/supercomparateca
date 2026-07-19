from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..seguridad import get_current_user

router = APIRouter(
    prefix="/supermercados",
    tags=["supermercados"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=schemas.SupermercadoRead, status_code=status.HTTP_201_CREATED)
def crear(payload: schemas.SupermercadoCreate, db: Session = Depends(get_db)):
    sm = models.Supermercado(**payload.model_dump())
    db.add(sm)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un supermercado con ese nombre"
        )
    db.refresh(sm)
    return sm


@router.get("", response_model=list[schemas.SupermercadoRead])
def listar(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Supermercado)).all())


@router.get("/{sm_id}", response_model=schemas.SupermercadoRead)
def obtener(sm_id: int, db: Session = Depends(get_db)):
    sm = db.get(models.Supermercado, sm_id)
    if sm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supermercado no encontrado")
    return sm


@router.patch("/{sm_id}", response_model=schemas.SupermercadoRead)
def actualizar(
    sm_id: int, payload: schemas.SupermercadoUpdate, db: Session = Depends(get_db)
):
    sm = db.get(models.Supermercado, sm_id)
    if sm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supermercado no encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(sm, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un supermercado con ese nombre"
        )
    db.refresh(sm)
    return sm


@router.delete("/{sm_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(sm_id: int, db: Session = Depends(get_db)):
    sm = db.get(models.Supermercado, sm_id)
    if sm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supermercado no encontrado")
    db.delete(sm)
    db.commit()
