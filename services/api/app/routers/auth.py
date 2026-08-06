from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, func, select, update
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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def borrar_mi_cuenta(
    payload: schemas.BorrarCuenta,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(seguridad.get_current_user),
):
    """Derecho de supresión (art. 17 RGPD): el usuario borra su propia cuenta.

    Los **tickets no se borran, se desvinculan** (`usuario_id = NULL`). Los
    precios son un bien compartido: eliminarlos degradaría la comparativa de
    todos los demás, y una vez sin dueño dejan de ser datos personales. Nadie
    vuelve a tener acceso a ellos, porque `_ticket_propio` exige coincidencia
    de usuario y NULL no coincide con nadie.

    Los **alias sí se borran**: son aprendizaje personal, no histórico de
    precios, y no hay nada que dependa de ellos (las líneas apuntan al
    producto, no al alias).

    Se pide la contraseña porque la acción es irreversible y no debería
    bastar con un token robado.
    """
    if not seguridad.verificar_password(payload.password, usuario.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Contraseña incorrecta")

    # Sin ningún admin, el catálogo global (productos, supermercados) se queda
    # sin nadie que pueda corregirlo ni borrarlo. Pero eso solo perjudica a
    # QUIEN SE QUEDE: si no queda nadie más, no hay a quien proteger y el
    # borrado no se bloquea. Poner una traba al último usuario que se va sería
    # convertir un problema operativo en un obstáculo al derecho de supresión.
    if usuario.rol == "admin":
        otros_admins = db.scalar(
            select(func.count())
            .select_from(models.Usuario)
            .where(models.Usuario.rol == "admin", models.Usuario.id != usuario.id)
        )
        quedan_otros = db.scalar(
            select(func.count())
            .select_from(models.Usuario)
            .where(models.Usuario.id != usuario.id)
        )
        if not otros_admins and quedan_otros:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Eres el único administrador: nombra a otro antes de borrar tu cuenta.",
            )

    db.execute(
        update(models.Ticket)
        .where(models.Ticket.usuario_id == usuario.id)
        .values(usuario_id=None)
    )
    db.execute(
        delete(models.AliasProducto).where(
            models.AliasProducto.usuario_id == usuario.id
        )
    )
    db.delete(usuario)
    db.commit()
