"""Envío de correo transaccional (Resend).

Aislado tras una dependencia, igual que el OCR y Turnstile, para poder
sustituirlo en los tests y para que el desarrollo no necesite credenciales.

Sin `RESEND_API_KEY` se usa `CorreoLog`, que **no envía nada** y escribe el
mensaje en el log del servicio. En desarrollo eso es justo lo que hace falta:
el enlace de verificación aparece en `docker compose logs api` y el flujo
entero se puede probar sin cuenta de correo.

En producción, en cambio, quedarse sin proveedor es grave: como la
verificación es obligatoria para entrar, nadie podría registrarse de verdad.
Por eso `GET /auth/config` publica `correo_activo` y el smoke test lo
comprueba tras cada despliegue; no repetimos el fallo silencioso de Turnstile.
"""

import logging

import httpx

from .config import settings

log = logging.getLogger("uvicorn.error")

API_URL = "https://api.resend.com/emails"


class ErrorCorreo(RuntimeError):
    """No se ha podido entregar el mensaje al proveedor."""


class CorreoResend:
    def __init__(self, api_key: str, remitente: str):
        self._api_key = api_key
        self._remitente = remitente

    @property
    def activo(self) -> bool:
        return True

    def enviar(self, destinatario: str, asunto: str, html: str, texto: str) -> None:
        try:
            resp = httpx.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    # Identificarse en vez de ir como "python-httpx/…". La API
                    # de Resend está tras Cloudflare, que bloquea por firma de
                    # cliente: comprobado el 2026-08-06 que `Python-urllib/3.10`
                    # se lleva un 403 con "error code: 1010" mientras que httpx
                    # pasa. Hoy no hace falta, pero esa regla no la controlamos
                    # y un nombre propio también ayuda si hay que rastrear
                    # nuestras peticiones en el panel de Resend.
                    "User-Agent": "SuperComparateca/1.0 (+https://supercomparateca.com)",
                },
                json={
                    "from": self._remitente,
                    "to": [destinatario],
                    "subject": asunto,
                    "html": html,
                    # Las dos versiones, no solo la HTML: un mensaje corto, con
                    # un unico enlace y sin alternativa en texto plano es un
                    # patron que los filtros penalizan, y con un dominio recien
                    # estrenado (reputacion cero) eso basta para acabar en spam.
                    "text": texto,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise ErrorCorreo(f"no se pudo contactar con Resend: {exc}") from exc

        if resp.status_code >= 400:
            # El cuerpo de Resend explica por qué (dominio sin verificar, clave
            # inválida, destinatario rechazado). Sin él, depurar esto a
            # distancia es adivinar.
            raise ErrorCorreo(f"Resend respondió {resp.status_code}: {resp.text[:300]}")


class CorreoLog:
    """Desarrollo y tests: no envía nada, deja el mensaje en el log."""

    @property
    def activo(self) -> bool:
        return False

    def enviar(self, destinatario: str, asunto: str, html: str, texto: str) -> None:
        # Se registra la version en texto: en el log el HTML solo estorba, y lo
        # que se busca aqui es el enlace.
        log.warning(
            "CORREO NO ENVIADO (sin RESEND_API_KEY). Para: %s | Asunto: %s\n%s",
            destinatario,
            asunto,
            texto,
        )


def get_cliente_correo() -> CorreoResend | CorreoLog:
    if settings.resend_api_key:
        return CorreoResend(settings.resend_api_key, settings.correo_remitente)
    return CorreoLog()
