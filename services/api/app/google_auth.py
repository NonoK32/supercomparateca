"""Acceso con Google (Google Identity Services).

El navegador consigue de Google un **ID token** firmado y lo manda aquí; este
módulo comprueba la firma contra las claves públicas de Google y se queda con
la dirección de correo. Es la mitad de flujo que hace falta: no pedimos acceso
a ningún dato de Google más allá de quién eres, así que el flujo de código de
autorización —con secreto de cliente, redirección y estado— sobraría entero.

Aislado tras una dependencia, como el OCR, Turnstile y el correo, para poder
sustituirlo en los tests: la suite no toca la red ni necesita credenciales.

Sin `GOOGLE_CLIENT_ID` queda desactivado. A diferencia del correo, aquí eso no
es grave: siempre queda entrar con email y contraseña.
"""

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from .config import settings

# Claves públicas con las que Google firma sus ID token. PyJWKClient las cachea
# y las renueva solo cuando aparece una `kid` que no conoce.
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Google emite con una de las dos formas, según la antigüedad del token.
EMISORES = {"accounts.google.com", "https://accounts.google.com"}


class ErrorGoogle(ValueError):
    """El token no vale: firma, caducidad, destinatario o correo sin confirmar."""


@dataclass(frozen=True)
class IdentidadGoogle:
    email: str
    nombre: str


class VerificadorGoogle:
    def __init__(self, client_id: str):
        self._client_id = client_id
        self._claves = PyJWKClient(JWKS_URL) if client_id else None

    @property
    def activo(self) -> bool:
        return bool(self._client_id)

    def verificar(self, credencial: str) -> IdentidadGoogle:
        try:
            clave = self._claves.get_signing_key_from_jwt(credencial)
            datos = jwt.decode(
                credencial,
                clave.key,
                algorithms=["RS256"],
                # `audience` es la comprobación que impide reutilizar aquí un
                # token que Google emitió para OTRA aplicación: sin ella,
                # cualquiera con un cliente de Google podría entrar como quien
                # quisiera.
                audience=self._client_id,
                options={"require": ["exp", "aud", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            # Cae aquí también si no se pueden traer las claves de Google. Se
            # trata igual que un token inválido: no podemos acreditar quién es,
            # y no hay nada que el usuario pueda arreglar salvo reintentar.
            raise ErrorGoogle("No hemos podido validar tu cuenta de Google") from exc

        if datos.get("iss") not in EMISORES:
            raise ErrorGoogle("Ese token no lo ha emitido Google")

        email = datos.get("email")
        if not email:
            raise ErrorGoogle("Tu cuenta de Google no comparte ninguna dirección")
        # Google puede firmar un token con una dirección que él mismo no da por
        # confirmada. Aceptarla sería tomar por buena una identidad que ni
        # siquiera su emisor sostiene, y aquí el email ES la cuenta.
        if not datos.get("email_verified"):
            raise ErrorGoogle("Google no da por confirmada esa dirección")

        return IdentidadGoogle(
            email=email,
            # `name` es opcional: si no viene, el usuario podrá cambiarlo, pero
            # la cuenta necesita algo con lo que saludarle.
            nombre=datos.get("name") or email.split("@")[0],
        )


def get_verificador_google() -> VerificadorGoogle:
    return VerificadorGoogle(settings.google_client_id)
