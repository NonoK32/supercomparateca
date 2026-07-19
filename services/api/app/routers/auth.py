from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, seguridad
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/registro", response_model=schemas.UsuarioRead, status_code=status.HTTP_201_CREATED
)
def registro(payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.scalar(
        select(models.Usuario).where(models.Usuario.email == payload.email)
    )
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email")

    usuario = models.Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=seguridad.hash_password(payload.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=schemas.Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # OAuth2 usa el campo `username`; aquí es el email.
    usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == form.username)
    )
    if usuario is None or not seguridad.verificar_password(
        form.password, usuario.password_hash
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return schemas.Token(access_token=seguridad.crear_token(usuario.id))
