"""Derecho de supresión (art. 17 RGPD): DELETE /auth/me.

La regla que se comprueba una y otra vez aquí: **los tickets no se borran, se
desvinculan**. Los precios son un bien compartido y eliminarlos degradaría la
comparativa de todos los usuarios; sin dueño dejan de ser datos personales.
"""

from tests.conftest import registrar_y_login

PASSWORD = "password123"


def _crear_ticket(cliente, fake_ocr, texto="LECHE 0,89"):
    # El catálogo es global: si otro usuario ya creó el supermercado, se reusa.
    resp = cliente.post("/supermercados", json={"nombre": "Mercadona"})
    sm = resp.json() if resp.status_code == 201 else cliente.get("/supermercados").json()[0]
    fake_ocr.texto = texto
    return cliente.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()


def _autenticar(api_client, email):
    token = registrar_y_login(api_client, email=email)
    api_client.headers["Authorization"] = f"Bearer {token}"
    return token


def test_borrar_cuenta_devuelve_204_y_el_token_deja_de_valer(client):
    assert client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 204
    # El usuario ya no existe: su token queda inservible.
    assert client.get("/tickets").status_code == 401


def test_no_se_puede_borrar_con_la_password_equivocada(client):
    resp = client.request("DELETE", "/auth/me", json={"password": "otra-cosa"})
    assert resp.status_code == 403
    # Y la cuenta sigue funcionando.
    assert client.get("/tickets").status_code == 200


def test_borrar_cuenta_exige_estar_autenticado(api_client):
    assert api_client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 401


def test_los_precios_del_borrado_siguen_en_la_comparativa(api_client, fake_ocr):
    """El caso que justifica desvincular en vez de borrar."""
    # Ana sube un ticket y asocia su línea a un producto.
    _autenticar(api_client, "ana@example.com")
    ticket = _crear_ticket(api_client, fake_ocr)
    linea = ticket["lineas"][0]
    api_client.post(
        f"/lineas/{linea['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche entera"}},
    )
    producto_id = api_client.get("/productos").json()[0]["id"]
    antes = api_client.get(f"/productos/{producto_id}/precios").json()
    assert len(antes["supermercados"]) == 1

    # Ana se borra.
    assert api_client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 204

    # Bruno, que no tiene nada que ver, sigue viendo ese precio.
    _autenticar(api_client, "bruno@example.com")
    despues = api_client.get(f"/productos/{producto_id}/precios").json()
    assert despues["supermercados"] == antes["supermercados"]


def test_los_tickets_del_borrado_no_son_accesibles_para_nadie(api_client, fake_ocr):
    _autenticar(api_client, "ana@example.com")
    ticket = _crear_ticket(api_client, fake_ocr)
    api_client.request("DELETE", "/auth/me", json={"password": PASSWORD})

    # Sin dueño, el ticket no aparece en ningún listado ni se puede abrir.
    _autenticar(api_client, "bruno@example.com")
    assert api_client.get("/tickets").json() == []
    assert api_client.get(f"/tickets/{ticket['id']}").status_code == 404


def test_el_unico_admin_no_puede_borrarse_si_quedan_otros(api_client):
    """Sin admin, el catálogo global se queda sin nadie que pueda corregirlo."""
    _autenticar(api_client, "admin@example.com")  # el primero es admin
    _autenticar(api_client, "otro@example.com")  # alguien a quien proteger
    _autenticar(api_client, "admin@example.com")

    resp = api_client.request("DELETE", "/auth/me", json={"password": PASSWORD})
    assert resp.status_code == 409
    assert "administrador" in resp.json()["detail"]


def test_el_ultimo_usuario_si_puede_borrarse_aunque_sea_admin(api_client):
    """No hay a quien proteger: bloquearlo sería una traba al art. 17."""
    _autenticar(api_client, "solo@example.com")
    assert api_client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 204


def test_un_usuario_normal_si_puede_borrarse_habiendo_admin(api_client):
    _autenticar(api_client, "admin@example.com")  # este es el admin
    _autenticar(api_client, "normal@example.com")  # este no
    assert api_client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 204


def test_los_alias_propios_se_borran(api_client, fake_ocr):
    """Los alias son aprendizaje personal, no histórico de precios: sí se van."""
    _autenticar(api_client, "ana@example.com")
    ticket = _crear_ticket(api_client, fake_ocr)
    api_client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche entera"}},
    )
    api_client.request("DELETE", "/auth/me", json={"password": PASSWORD})

    # Bruno sube el mismo texto: sin el alias de Ana, queda sin asociar.
    _autenticar(api_client, "bruno@example.com")
    nuevo = _crear_ticket(api_client, fake_ocr)
    assert nuevo["lineas"][0]["producto_id"] is None
