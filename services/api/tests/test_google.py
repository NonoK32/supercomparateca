"""Acceso con Google. El verificador es falso (conftest): sin red ni credenciales."""

import os

import jwt

from app.google_auth import IdentidadGoogle

CREDENCIAL = {"credential": "id-token-de-google"}


def _entrar(cliente):
    return cliente.post("/auth/google", json=CREDENCIAL)


def _usuario_de(token):
    """Id del usuario dueño del token de sesión (no hay endpoint que lo diga)."""
    return jwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])["sub"]


def _cabecera(token):
    return {"Authorization": f"Bearer {token}"}


def test_la_primera_vez_crea_la_cuenta_y_devuelve_sesion(api_client):
    resp = _entrar(api_client)

    assert resp.status_code == 200
    assert resp.json()["access_token"]
    # Sin correo de confirmación: Google ya acredita la dirección, y mandar uno
    # dejaría la cuenta esperando por algo que sobra.
    assert api_client.correo.enviados == []


def test_la_cuenta_creada_entra_sin_confirmar_nada(api_client):
    token = _entrar(api_client).json()["access_token"]

    assert api_client.get("/tickets", headers=_cabecera(token)).status_code == 200


def test_la_segunda_vez_entra_en_la_misma_cuenta(api_client):
    primero = _entrar(api_client).json()["access_token"]
    segundo = _entrar(api_client).json()["access_token"]

    assert _usuario_de(primero) == _usuario_de(segundo)


def test_entra_en_la_cuenta_que_ya_existia_con_ese_email(api_client):
    # Quien se registró con contraseña y luego pulsa el botón de Google tiene
    # que acabar en SU cuenta, no en una segunda con el mismo correo.
    api_client.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": "ana@gmail.com", "password": "password123"},
    )
    con_password = api_client.post(
        "/auth/verificar", json={"token": api_client.correo.token("verificar")}
    ).json()["access_token"]

    con_google = _entrar(api_client).json()["access_token"]

    assert _usuario_de(con_password) == _usuario_de(con_google)


def test_google_confirma_el_email_de_una_cuenta_pendiente(api_client):
    # Se registró, no llegó a confirmar (y por eso no puede entrar) y ahora usa
    # Google: la dirección queda acreditada igual.
    api_client.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": "ana@gmail.com", "password": "password123"},
    )
    credenciales = {"username": "ana@gmail.com", "password": "password123"}
    assert api_client.post("/auth/login", data=credenciales).status_code == 403

    assert _entrar(api_client).status_code == 200

    # Y a partir de ahí también puede entrar con su contraseña de siempre.
    assert api_client.post("/auth/login", data=credenciales).status_code == 200


def test_un_token_que_google_no_valida_no_deja_entrar_ni_crea_nada(api_client):
    api_client.google.fallar = True

    assert _entrar(api_client).status_code == 401

    # Si hubiera creado la cuenta igualmente, este registro daría 409.
    alta = api_client.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": "ana@gmail.com", "password": "password123"},
    )
    assert alta.status_code == 201


def test_sin_configurar_el_endpoint_no_finge_que_funciona(api_client):
    api_client.google.activo = False

    assert _entrar(api_client).status_code == 503


def test_el_primero_que_llega_por_google_es_admin(api_client):
    # Misma regla que el registro normal: alguien tiene que poder administrar
    # el catálogo compartido.
    cabecera = _cabecera(_entrar(api_client).json()["access_token"])
    sm = api_client.post("/supermercados", json={"nombre": "Lidl"}, headers=cabecera)

    borrado = api_client.delete(f"/supermercados/{sm.json()['id']}", headers=cabecera)
    assert borrado.status_code == 204


def test_el_segundo_no_es_admin(api_client):
    _entrar(api_client)
    api_client.google.identidad = IdentidadGoogle(email="luis@gmail.com", nombre="Luis")

    cabecera = _cabecera(_entrar(api_client).json()["access_token"])
    sm = api_client.post("/supermercados", json={"nombre": "Lidl"}, headers=cabecera)

    borrado = api_client.delete(f"/supermercados/{sm.json()['id']}", headers=cabecera)
    assert borrado.status_code == 403


def test_la_config_publica_dice_si_hay_acceso_con_google(api_client):
    # El frontend es estático: sin esto no puede saber si pintar el botón.
    assert "google_client_id" in api_client.get("/auth/config").json()
