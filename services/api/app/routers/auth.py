from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import correo, models, schemas, seguridad
from ..config import settings
from ..database import get_db
from ..turnstile import TurnstileClient, get_turnstile_client

router = APIRouter(prefix="/auth", tags=["auth"])


def _enlace(ruta: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/?{ruta}={token}"


def _enviar_verificacion(cliente, usuario: models.Usuario) -> None:
    token = seguridad.crear_token_correo(
        usuario,
        seguridad.PROPOSITO_VERIFICACION,
        settings.verificacion_expira_horas * 60,
    )
    url = _enlace("verificar", token)
    cliente.enviar(
        usuario.email,
        "Confirma tu correo en SuperComparateca",
        f"""<p>Hola {usuario.nombre}:</p>
<p>Confirma esta dirección para poder entrar en SuperComparateca.</p>
<p><a href="{url}">Confirmar mi correo</a></p>
<p>El enlace caduca en {settings.verificacion_expira_horas} horas.
Si no has creado ninguna cuenta, ignora este mensaje.</p>""",
    )


@router.get("/config", response_model=schemas.AuthConfig)
def config_publica():
    """Datos públicos que el frontend necesita para pintar el formulario.

    La clave de sitio de Turnstile se sirve desde aquí en vez de incrustarla en
    el HTML: el frontend es estático y así cambiarla no obliga a reconstruir la
    imagen. Si viene vacía, el frontend no monta el widget.
    """
    return schemas.AuthConfig(
        turnstile_site_key=settings.turnstile_site_key,
        correo_activo=bool(settings.resend_api_key),
    )


@router.post(
    "/registro", response_model=schemas.UsuarioRead, status_code=status.HTTP_201_CREATED
)
def registro(
    payload: schemas.UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    turnstile: TurnstileClient = Depends(get_turnstile_client),
    cliente_correo=Depends(correo.get_cliente_correo),
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

    # Si el correo no sale, la cuenta queda inservible: sin verificar no se
    # puede entrar, y sin mensaje no hay forma de verificar. Se deshace el alta
    # para que la persona pueda reintentarlo con el mismo email en vez de
    # quedarse con una cuenta muerta y un 409 cada vez que lo intente.
    try:
        _enviar_verificacion(cliente_correo, usuario)
    except correo.ErrorCorreo as exc:
        db.delete(usuario)
        db.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No hemos podido enviarte el correo de confirmación. Inténtalo dentro de un rato.",
        ) from exc

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
    # La comprobación va DESPUÉS de la contraseña: si fuera antes, cualquiera
    # podría averiguar qué emails están registrados probando a entrar.
    if not usuario.email_verificado:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Todavía no has confirmado tu correo. Revisa tu bandeja de entrada.",
        )
    return schemas.Token(access_token=seguridad.crear_token(usuario.id))


@router.post("/verificar", response_model=schemas.Token)
def verificar_email(
    payload: schemas.VerificarEmail, db: Session = Depends(get_db)
):
    """Confirma el correo desde el enlace del mensaje.

    Devuelve un token de sesión: quien acaba de demostrar que controla la
    dirección ya puede entrar, y obligarle a teclear la contraseña otra vez
    justo después no aporta seguridad, solo fricción.
    """
    usuario = seguridad.leer_token_correo(
        payload.token, seguridad.PROPOSITO_VERIFICACION, db
    )
    if usuario is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El enlace no es válido o ha caducado. Pide uno nuevo.",
        )
    if not usuario.email_verificado:
        usuario.email_verificado = True
        db.commit()
    return schemas.Token(access_token=seguridad.crear_token(usuario.id))


@router.post("/reenviar-verificacion", status_code=status.HTTP_202_ACCEPTED)
def reenviar_verificacion(
    payload: schemas.SolicitarCorreo,
    db: Session = Depends(get_db),
    cliente_correo=Depends(correo.get_cliente_correo),
):
    """Reenvía el correo de confirmación.

    Responde 202 pase lo que pase. Distinguir "no existe" de "ya verificado"
    convertiría esto en un comprobador de qué direcciones tienen cuenta.
    """
    usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == payload.email)
    )
    if usuario is not None and not usuario.email_verificado:
        try:
            _enviar_verificacion(cliente_correo, usuario)
        except correo.ErrorCorreo:
            # No se filtra al cliente por lo mismo de arriba; queda en el log
            # del servicio, que es donde se mira cuando alguien se queja.
            pass
    return {"detail": "Si esa dirección tiene una cuenta sin confirmar, te hemos escrito."}


@router.post("/recuperar", status_code=status.HTTP_202_ACCEPTED)
def recuperar_password(
    payload: schemas.SolicitarCorreo,
    db: Session = Depends(get_db),
    cliente_correo=Depends(correo.get_cliente_correo),
):
    """Envía el enlace para restablecer la contraseña. Siempre responde 202."""
    usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == payload.email)
    )
    if usuario is not None:
        token = seguridad.crear_token_correo(
            usuario, seguridad.PROPOSITO_RESET, settings.reset_expira_minutos
        )
        url = _enlace("restablecer", token)
        try:
            cliente_correo.enviar(
                usuario.email,
                "Restablece tu contraseña de SuperComparateca",
                f"""<p>Hola {usuario.nombre}:</p>
<p>Has pedido cambiar tu contraseña. Si no has sido tú, ignora este mensaje:
tu contraseña actual sigue siendo válida.</p>
<p><a href="{url}">Elegir una contraseña nueva</a></p>
<p>El enlace caduca en {settings.reset_expira_minutos} minutos y solo se puede
usar una vez.</p>""",
            )
        except correo.ErrorCorreo:
            pass
    return {"detail": "Si esa dirección tiene una cuenta, te hemos enviado un enlace."}


@router.post("/restablecer", response_model=schemas.Token)
def restablecer_password(
    payload: schemas.RestablecerPassword, db: Session = Depends(get_db)
):
    """Fija la contraseña nueva a partir del enlace del correo."""
    usuario = seguridad.leer_token_correo(
        payload.token, seguridad.PROPOSITO_RESET, db
    )
    if usuario is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El enlace no es válido, ya se ha usado o ha caducado. Pide uno nuevo.",
        )
    usuario.password_hash = seguridad.hash_password(payload.password)
    # Quien recupera la contraseña por correo ha demostrado que controla la
    # dirección, así que de paso queda verificado: si no, una cuenta sin
    # confirmar seguiría sin poder entrar después de recuperarla.
    usuario.email_verificado = True
    db.commit()
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
