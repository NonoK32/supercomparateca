from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cuentas, models, schemas
from ..database import get_db
from ..seguridad import get_admin_user

# Todo el router es de admin: aquí se ven correos de terceros, que son datos
# personales y no tienen por qué estar a la vista de cualquiera con cuenta.
router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[schemas.UsuarioAdminRead])
def listar(
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_admin_user),
):
    """Las cuentas que hay, de más antigua a más nueva."""
    return list(db.scalars(select(models.Usuario).order_by(models.Usuario.id)).all())


def _otro_usuario(usuario_id: int, admin: models.Usuario, db: Session) -> models.Usuario:
    """El usuario indicado, siempre que no sea el propio admin.

    Cambiarse el rol a uno mismo es la forma más fácil de dejar la instalación
    sin ningún administrador, y borrarse desde aquí se saltaría la contraseña
    que sí pide `DELETE /auth/me`. En los dos casos el camino es el de la propia
    cuenta, no este.
    """
    if usuario_id == admin.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tu propia cuenta se gestiona desde tu perfil, no desde el panel.",
        )
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return usuario


@router.patch("/{usuario_id}", response_model=schemas.UsuarioAdminRead)
def actualizar(
    usuario_id: int,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_admin_user),
):
    """Nombra o retira administradores.

    Es lo que hace practicable el aviso de `DELETE /auth/me` («eres el único
    administrador: nombra a otro antes de borrar tu cuenta»), que hasta ahora no
    tenía forma de cumplirse.
    """
    usuario = _otro_usuario(usuario_id, admin, db)
    usuario.rol = payload.rol
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_admin_user),
):
    """Borra la cuenta de otro usuario.

    Con las mismas reglas que el borrado propio (`cuentas.borrar`): sus tickets
    se **desvinculan** en vez de borrarse, porque los precios son de todos y
    tirarlos degradaría la comparativa de los demás.
    """
    usuario = _otro_usuario(usuario_id, admin, db)
    cuentas.borrar(db, usuario)
    db.commit()
