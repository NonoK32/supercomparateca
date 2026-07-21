"""EPIC 10 / FR9: matching automático por similitud (§5bis punto 3).

Los tests afirman *comportamiento* (qué producto sale, en qué orden), nunca
scores concretos: así siguen valiendo si se cambia el motor de similitud.
"""

from app.matching import normalizar

TICKET_LARGO = "LECHE DESNATADA 0,89\n"
TICKET_ABREVIADO = "LECHE DESNATAD 0,89\n"
TICKET_DISTINTO = "ATUN CLARO ACEITE 2,10\n"


def _supermercado(client, nombre="Mercadona"):
    return client.post("/supermercados", json={"nombre": nombre}).json()


def _subir_ticket(client, sm_id):
    return client.post(
        "/tickets",
        data={"supermercado_id": sm_id},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()


def _enseñar_alias(client, fake_ocr, sm_id, texto, nombre_producto):
    """Sube un ticket y confirma su primera línea: deja el alias aprendido."""
    fake_ocr.texto = texto
    ticket = _subir_ticket(client, sm_id)
    return client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": nombre_producto}},
    ).json()


# ---- normalización ----
def test_normalizar_ignora_tildes_mayusculas_y_espacios():
    assert normalizar("  Atún  CLARO ") == normalizar("atun claro")


def test_normalizar_ignora_el_orden_de_las_palabras():
    assert normalizar("LECHE SEMI 1L") == normalizar("1L SEMI LECHE")


# ---- auto-asignación en la ingesta ----
def test_texto_casi_igual_se_autoasigna(client, fake_ocr):
    """'LECHE DESNATAD' debe resolver al producto de 'LECHE DESNATADA' sin
    preguntar: supera el umbral automático."""
    sm = _supermercado(client)
    linea = _enseñar_alias(
        client, fake_ocr, sm["id"], TICKET_LARGO, "Leche desnatada 1L"
    )

    fake_ocr.texto = TICKET_ABREVIADO
    ticket2 = _subir_ticket(client, sm["id"])
    assert ticket2["lineas"][0]["producto_id"] == linea["producto_id"]
    assert ticket2["estado"] == "procesado"


def test_texto_distinto_no_se_autoasigna(client, fake_ocr):
    sm = _supermercado(client)
    _enseñar_alias(client, fake_ocr, sm["id"], TICKET_LARGO, "Leche desnatada 1L")

    fake_ocr.texto = TICKET_DISTINTO
    ticket2 = _subir_ticket(client, sm["id"])
    assert ticket2["lineas"][0]["producto_id"] is None
    assert ticket2["estado"] == "pendiente"


def test_similitud_no_cruza_supermercados(client, fake_ocr):
    """El alias es por supermercado, también en el fuzzy (§5bis)."""
    merca = _supermercado(client, "Mercadona")
    lidl = _supermercado(client, "Lidl")
    _enseñar_alias(client, fake_ocr, merca["id"], TICKET_LARGO, "Leche desnatada 1L")

    fake_ocr.texto = TICKET_ABREVIADO
    ticket_lidl = _subir_ticket(client, lidl["id"])
    assert ticket_lidl["lineas"][0]["producto_id"] is None


# ---- sugerencias (zona dudosa) ----
def test_sugerencias_proponen_el_producto_mas_parecido(client, fake_ocr):
    sm = _supermercado(client)
    leche = _enseñar_alias(
        client, fake_ocr, sm["id"], TICKET_LARGO, "Leche desnatada 1L"
    )
    _enseñar_alias(client, fake_ocr, sm["id"], TICKET_DISTINTO, "Atún claro en aceite")

    # Parecido pero no lo bastante como para asignarlo solo.
    fake_ocr.texto = "LECHE DESNAT 0,89\n"
    ticket = _subir_ticket(client, sm["id"])
    linea = ticket["lineas"][0]
    assert linea["producto_id"] is None

    sugerencias = client.get(f"/lineas/{linea['id']}/sugerencias").json()
    assert sugerencias, "debería sugerir al menos un candidato"
    assert sugerencias[0]["producto_id"] == leche["producto_id"]
    assert sugerencias[0]["nombre_normalizado"] == "Leche desnatada 1L"
    # El atún no se parece: no debe colarse.
    assert all(s["nombre_normalizado"] != "Atún claro en aceite" for s in sugerencias)


def test_sin_alias_no_hay_sugerencias(client, fake_ocr):
    sm = _supermercado(client)
    fake_ocr.texto = TICKET_LARGO
    ticket = _subir_ticket(client, sm["id"])

    resp = client.get(f"/lineas/{ticket['lineas'][0]['id']}/sugerencias")
    assert resp.status_code == 200
    assert resp.json() == []


def test_aceptar_una_sugerencia_guarda_el_alias_nuevo(client, fake_ocr):
    """§5bis punto 4: confirmar la sugerencia aprende el texto abreviado, que a
    partir de entonces es coincidencia exacta."""
    sm = _supermercado(client)
    leche = _enseñar_alias(
        client, fake_ocr, sm["id"], TICKET_LARGO, "Leche desnatada 1L"
    )

    fake_ocr.texto = "LECHE DESNAT 0,89\n"
    ticket = _subir_ticket(client, sm["id"])
    client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar",
        json={"producto_id": leche["producto_id"]},
    )

    ticket3 = _subir_ticket(client, sm["id"])
    assert ticket3["lineas"][0]["producto_id"] == leche["producto_id"]


def test_sugerencias_de_otro_usuario_dan_404(api_client, fake_ocr):
    from .conftest import registrar_y_login

    token_a = registrar_y_login(api_client, email="a@example.com")
    api_client.headers["Authorization"] = f"Bearer {token_a}"
    sm = _supermercado(api_client)
    fake_ocr.texto = TICKET_LARGO
    ticket = _subir_ticket(api_client, sm["id"])
    linea_id = ticket["lineas"][0]["id"]

    token_b = registrar_y_login(api_client, email="b@example.com")
    api_client.headers["Authorization"] = f"Bearer {token_b}"
    assert api_client.get(f"/lineas/{linea_id}/sugerencias").status_code == 404


def test_sugerencias_requieren_auth(api_client):
    assert api_client.get("/lineas/1/sugerencias").status_code == 401
