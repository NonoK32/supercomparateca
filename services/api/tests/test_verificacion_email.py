"""Verificación de correo y recuperación de contraseña."""

CREDS = {"nombre": "Ana", "email": "ana@example.com", "password": "password123"}


def _registrar(cliente, **cambios):
    return cliente.post("/auth/registro", json={**CREDS, **cambios})


def _login(cliente, password=CREDS["password"], email=CREDS["email"]):
    return cliente.post("/auth/login", data={"username": email, "password": password})


# ---- Verificación ----


def test_al_registrarse_se_envia_un_correo_con_enlace(api_client):
    _registrar(api_client)
    assert len(api_client.correo.enviados) == 1
    mensaje = api_client.correo.enviados[0]
    assert mensaje["para"] == CREDS["email"]
    assert api_client.correo.token("verificar")


def test_el_correo_lleva_las_dos_versiones(api_client):
    # Solo-HTML puntúa peor en los filtros antispam, y el enlace tiene que estar
    # en las dos versiones o el que lea el texto plano se queda sin poder entrar.
    _registrar(api_client)
    mensaje = api_client.correo.enviados[0]
    assert "<a href=" in mensaje["html"]
    assert "<" not in mensaje["texto"]
    assert "verificar=" in mensaje["texto"]


def test_sin_verificar_no_se_puede_entrar(api_client):
    _registrar(api_client)
    resp = _login(api_client)
    assert resp.status_code == 403
    assert "confirmado" in resp.json()["detail"]


def test_verificar_permite_entrar(api_client):
    _registrar(api_client)
    resp = api_client.post(
        "/auth/verificar", json={"token": api_client.correo.token("verificar")}
    )
    assert resp.status_code == 200
    # Verificar ya deja la sesión iniciada: no tiene sentido pedir la
    # contraseña otra vez justo después.
    assert resp.json()["access_token"]
    assert _login(api_client).status_code == 200


def test_un_token_invalido_no_verifica(api_client):
    _registrar(api_client)
    assert api_client.post("/auth/verificar", json={"token": "inventado"}).status_code == 400
    assert _login(api_client).status_code == 403


def test_reenviar_verificacion_manda_otro_correo(api_client):
    _registrar(api_client)
    api_client.post("/auth/reenviar-verificacion", json={"email": CREDS["email"]})
    assert len(api_client.correo.enviados) == 2


def test_reenviar_a_un_email_desconocido_no_delata_nada(api_client):
    resp = api_client.post(
        "/auth/reenviar-verificacion", json={"email": "nadie@example.com"}
    )
    # Misma respuesta que si existiera: si no, esto sería un comprobador de
    # qué direcciones tienen cuenta.
    assert resp.status_code == 202
    assert api_client.correo.enviados == []


def test_si_el_correo_no_sale_el_registro_se_deshace(api_client):
    """Una cuenta sin correo enviado es inservible: no se puede verificar."""
    api_client.correo.fallar = True
    assert _registrar(api_client).status_code == 502

    # Y el email queda libre para volver a intentarlo, en vez de dar 409.
    api_client.correo.fallar = False
    assert _registrar(api_client).status_code == 201


# ---- Recuperación de contraseña ----


def _preparar_verificado(api_client):
    _registrar(api_client)
    api_client.post(
        "/auth/verificar", json={"token": api_client.correo.token("verificar")}
    )


def test_recuperar_envia_enlace_y_permite_cambiar_la_password(api_client):
    _preparar_verificado(api_client)
    api_client.post("/auth/recuperar", json={"email": CREDS["email"]})
    token = api_client.correo.token("restablecer")
    assert token

    resp = api_client.post(
        "/auth/restablecer", json={"token": token, "password": "nueva-password-1"}
    )
    assert resp.status_code == 200

    assert _login(api_client, password="nueva-password-1").status_code == 200
    assert _login(api_client, password=CREDS["password"]).status_code == 401


def test_el_enlace_de_recuperacion_es_de_un_solo_uso(api_client):
    """Al cambiar la contraseña cambia su hash, y el token deja de casar."""
    _preparar_verificado(api_client)
    api_client.post("/auth/recuperar", json={"email": CREDS["email"]})
    token = api_client.correo.token("restablecer")

    api_client.post("/auth/restablecer", json={"token": token, "password": "nueva-password-1"})
    segunda = api_client.post(
        "/auth/restablecer", json={"token": token, "password": "otra-password-2"}
    )
    assert segunda.status_code == 400
    # La segunda no ha cambiado nada.
    assert _login(api_client, password="nueva-password-1").status_code == 200


def test_recuperar_un_email_desconocido_no_delata_nada(api_client):
    resp = api_client.post("/auth/recuperar", json={"email": "nadie@example.com"})
    assert resp.status_code == 202
    assert api_client.correo.enviados == []


def test_recuperar_verifica_de_paso(api_client):
    """Quien recupera por correo ha demostrado que controla la dirección."""
    _registrar(api_client)  # sin verificar
    api_client.post("/auth/recuperar", json={"email": CREDS["email"]})
    api_client.post(
        "/auth/restablecer",
        json={"token": api_client.correo.token("restablecer"), "password": "nueva-password-1"},
    )
    # Si no quedara verificado, seguiria sin poder entrar tras recuperarla.
    assert _login(api_client, password="nueva-password-1").status_code == 200


def test_la_password_nueva_tambien_tiene_minimo(api_client):
    _preparar_verificado(api_client)
    api_client.post("/auth/recuperar", json={"email": CREDS["email"]})
    resp = api_client.post(
        "/auth/restablecer",
        json={"token": api_client.correo.token("restablecer"), "password": "corta"},
    )
    assert resp.status_code == 422


# ---- Separación entre tipos de token ----


def test_un_token_de_correo_no_vale_como_sesion(api_client):
    """Un enlace de verificación dura 24 h y viaja por correo: si valiera como
    credencial de acceso, sería una sesión larga por un canal que no
    controlamos."""
    _registrar(api_client)
    token_correo = api_client.correo.token("verificar")
    resp = api_client.get("/tickets", headers={"Authorization": f"Bearer {token_correo}"})
    assert resp.status_code == 401


def test_un_token_de_verificacion_no_sirve_para_restablecer(api_client):
    _registrar(api_client)
    resp = api_client.post(
        "/auth/restablecer",
        json={"token": api_client.correo.token("verificar"), "password": "nueva-password-1"},
    )
    assert resp.status_code == 400


def test_un_token_de_sesion_no_sirve_para_verificar(api_client):
    _preparar_verificado(api_client)
    sesion = _login(api_client).json()["access_token"]
    assert api_client.post("/auth/verificar", json={"token": sesion}).status_code == 400
