from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas, seguridad
from ..config import settings
from ..database import get_db
from ..turnstile import TurnstileClient, get_turnstile_client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=schemas.AuthConfig)
def config_publica():
    """Datos públicos que el frontend necesita para pintar el formulario.

    La clave de sitio de Turnstile se sirve desde aquí en vez de incrustarla en
    el HTML: el frontend es estático y así cambiarla no obliga a reconstruir la
    imagen. Si viene vacía, el frontend no monta el widget.
    """
    return schemas.AuthConfig(turnstile_site_key=settings.turnstile_site_key)


@router.post(
    "/registro", response_model=schemas.UsuarioRead, status_code=status.HTTP_201_CREATED
)
def registro(
    payload: schemas.UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    turnstile: TurnstileClient = Depends(get_turnstile_client),
):
    # Filtro anti-bot antes de tocar la base de datos: si no hay clave secreta
    # configurada no se verifica nada (desarrollo y tests).
    if turnstile.activo:
        ip = request.client.host if request.client else None
        if not payload.turnstile_token or not turnstile.verificar(
            payload.turnstile_token, ip
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No se ha podido verificar que no eres un bot. Recarga e inténtalo de nuevo.",
            )

    existe = db.scalar(
        select(models.Usuario).where(models.Usuario.email == payload.email)
    )
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email")

    # El primero que se registra administra el catálogo global; el resto son
    # usuarios normales (pueden crear productos, pero no editar ni borrar los
    # que ya usan los demás).
    primero = db.scalar(select(models.Usuario.id).limit(1)) is None

    usuario = models.Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=seguridad.hash_password(payload.password),
        rol="admin" if primero else "usuario",
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # Red de seguridad ante registros concurrentes con el mismo email.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email")
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
