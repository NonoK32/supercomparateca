import httpx

from .config import settings

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileClient:
    """Verifica ante Cloudflare el token que el widget genera en el navegador.

    Aislado tras una dependencia (como el OCR) para poder sustituirlo en los
    tests: así la suite no depende de la red ni de tener credenciales.
    """

    def __init__(self, secret: str):
        self._secret = secret

    @property
    def activo(self) -> bool:
        """Sin clave secreta no se verifica nada (desarrollo y tests)."""
        return bool(self._secret)

    def verificar(self, token: str, ip: str | None = None) -> bool:
        datos = {"secret": self._secret, "response": token}
        if ip:
            # Opcional, pero permite a Cloudflare afinar su valoración.
            datos["remoteip"] = ip
        try:
            resp = httpx.post(VERIFY_URL, data=datos, timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            # Si Cloudflare no responde, se rechaza el registro. Preferimos que
            # falle un alta legítima (se puede reintentar) a abrir la puerta a
            # los bots justo cuando el filtro está caído.
            return False
        return bool(resp.json().get("success"))


def get_turnstile_client() -> TurnstileClient:
    return TurnstileClient(settings.turnstile_secret_key)
