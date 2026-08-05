"""Filtro anti-bot en el registro (Turnstile).

Los tests afirman el comportamiento —se verifica o no, se acepta o se rechaza—
nunca el detalle de la llamada a Cloudflare: el cliente se sustituye por uno
falso, igual que el OCR, para que la suite no dependa de la red.
"""

from app.main import app
from app.turnstile import get_turnstile_client

CREDS = {"nombre": "Ana", "email": "ana@example.com", "password": "password123"}


class TurnstileFalso:
    """Cliente falso: activo o no, y aceptando o rechazando lo que se le diga."""

    def __init__(self, activo=True, acepta=True):
        self.activo = activo
        self._acepta = acepta
        self.tokens_recibidos = []

    def verificar(self, token, ip=None):
        self.tokens_recibidos.append(token)
        return self._acepta


def _usar(cliente):
    app.dependency_overrides[get_turnstile_client] = lambda: cliente


def test_sin_clave_configurada_no_se_verifica(api_client):
    """Comportamiento por defecto en desarrollo: el registro funciona sin token."""
    falso = TurnstileFalso(activo=False)
    _usar(falso)
    assert api_client.post("/auth/registro", json=CREDS).status_code == 201
    assert falso.tokens_recibidos == []


def test_con_turnstile_activo_y_token_valido_registra(api_client):
    falso = TurnstileFalso(acepta=True)
    _usar(falso)
    resp = api_client.post(
        "/auth/registro", json={**CREDS, "turnstile_token": "token-bueno"}
    )
    assert resp.status_code == 201
    assert falso.tokens_recibidos == ["token-bueno"]


def test_con_turnstile_activo_y_token_invalido_da_400(api_client):
    _usar(TurnstileFalso(acepta=False))
    resp = api_client.post(
        "/auth/registro", json={**CREDS, "turnstile_token": "token-malo"}
    )
    assert resp.status_code == 400


def test_con_turnstile_activo_sin_token_da_400(api_client):
    """Un bot que llama a la API directamente, sin pasar por el widget."""
    falso = TurnstileFalso(acepta=True)
    _usar(falso)
    assert api_client.post("/auth/registro", json=CREDS).status_code == 400
    # Ni siquiera se llama a Cloudflare si no hay token que verificar.
    assert falso.tokens_recibidos == []


def test_registro_rechazado_no_crea_usuario(api_client):
    """El filtro va antes de tocar la base de datos: el email queda libre."""
    _usar(TurnstileFalso(acepta=False))
    api_client.post("/auth/registro", json={**CREDS, "turnstile_token": "malo"})

    # Con el filtro desactivado, el mismo email se puede registrar: prueba de
    # que el intento anterior no dejó nada a medias.
    _usar(TurnstileFalso(activo=False))
    assert api_client.post("/auth/registro", json=CREDS).status_code == 201


def test_config_publica_expone_la_clave_de_sitio_sin_autenticar(api_client):
    resp = api_client.get("/auth/config")
    assert resp.status_code == 200
    assert "turnstile_site_key" in resp.json()
    # La secreta no se expone jamás.
    assert "secret" not in resp.text.lower()
