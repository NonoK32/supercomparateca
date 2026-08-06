"""Seguridad: hashing de contraseñas (bcrypt), JWT y usuario autenticado."""

import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def crear_token(usuario_id: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(usuario_id), "exp": expira}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---- Tokens enviados por correo ----
# Van firmados con el mismo secreto que los de sesión, así que llevan un
# `prop` que dice para qué sirven. Sin eso, un enlace de verificación (que dura
# 24 h y viaja por correo) valdría como token de sesión: get_current_user
# rechaza cualquier token que traiga `prop`, y estas funciones rechazan los que
# no traen el suyo. Las dos comprobaciones son necesarias.
PROPOSITO_VERIFICACION = "verificacion"
PROPOSITO_RESET = "reset"


def _huella_password(password_hash: str) -> str:
    """Marca del hash actual de la contraseña.

    Va dentro de los tokens de restablecimiento: al cambiar la contraseña
    cambia el hash, cambia la huella y los enlaces que quedaran pendientes
    dejan de valer. Es lo que hace que un enlace de recuperación sea de un solo
    uso sin necesidad de guardar estado en la base de datos.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def crear_token_correo(usuario: models.Usuario, proposito: str, minutos: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    payload = {"sub": str(usuario.id), "prop": proposito, "exp": expira}
    if proposito == PROPOSITO_RESET:
        payload["hp"] = _huella_password(usuario.password_hash)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def leer_token_correo(
    token: str, proposito: str, db: Session
) -> models.Usuario | None:
    """Devuelve el usuario del token, o None si no vale para este propósito."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("prop") != proposito:
            return None
        usuario = db.get(models.Usuario, int(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None

    if usuario is None:
        return None
    if proposito == PROPOSITO_RESET and payload.get("hp") != _huella_password(
        usuario.password_hash
    ):
        # La contraseña ya se cambió: este enlace ya se usó o quedó obsoleto.
        return None
    return usuario


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.Usuario:
    cred_exc = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        # Los tokens que se mandan por correo llevan `prop` y NO son de sesión:
        # uno de verificación dura 24 h y viaja por un canal que no controlamos.
        # Sin esta comprobación valdría como credencial de acceso.
        if "prop" in payload:
            raise cred_exc
        usuario_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise cred_exc

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise cred_exc
    return usuario


def get_admin_user(
    usuario: models.Usuario = Depends(get_current_user),
) -> models.Usuario:
    """Exige rol admin. Protege lo que es global y compartido por todos los
    usuarios: modificar o borrar productos y supermercados."""
    if usuario.rol != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Requiere permisos de administrador"
        )
    return usuario
