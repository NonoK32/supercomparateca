TICKET_MERCADONA = """MERCADONA S.A.
LECHE DESNATADA 0,89
12 HUEVOS M 1,95
PAN DE MOLDE 1,25
TOTAL 4,09
"""


def _crear_supermercado(client, nombre="Mercadona"):
    return client.post("/supermercados", json={"nombre": nombre}).json()


def test_subir_ticket_extrae_lineas(client, fake_ocr):
    sm = _crear_supermercado(client)
    fake_ocr.texto = TICKET_MERCADONA

    resp = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("ticket.jpg", b"bytes-de-imagen", "image/jpeg")},
    )
    assert resp.status_code == 201
    ticket = resp.json()

    # Escenario de aceptación (§8): al menos una línea con precio y estado pendiente.
    assert ticket["estado"] == "pendiente"
    assert len(ticket["lineas"]) >= 1

    textos = [linea["texto_original"] for linea in ticket["lineas"]]
    assert any("LECHE" in t for t in textos)
    # La línea TOTAL no debe colarse como producto.
    assert all("TOTAL" not in t.upper() for t in textos)
    # Aún sin asociar a producto (eso es EPIC 3).
    assert all(linea["producto_id"] is None for linea in ticket["lineas"])
    assert float(ticket["lineas"][0]["precio_total"]) == 0.89


def test_supermercado_inexistente_da_404(client, fake_ocr):
    fake_ocr.texto = "LECHE 0,89"
    resp = client.post(
        "/tickets",
        data={"supermercado_id": 999},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    )
    assert resp.status_code == 404


def test_imagen_vacia_da_400(client):
    sm = _crear_supermercado(client)
    resp = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"", "image/jpeg")},
    )
    assert resp.status_code == 400


def test_listar_y_obtener(client, fake_ocr):
    sm = _crear_supermercado(client)
    fake_ocr.texto = "LECHE 0,89"
    creado = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()

    assert len(client.get("/tickets").json()) == 1
    resp = client.get(f"/tickets/{creado['id']}")
    assert resp.status_code == 200
    assert resp.json()["texto_ocr_bruto"] == "LECHE 0,89"


def test_eliminar(client, fake_ocr):
    sm = _crear_supermercado(client)
    fake_ocr.texto = "LECHE 0,89"
    creado = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()

    assert client.delete(f"/tickets/{creado['id']}").status_code == 204
    assert client.get(f"/tickets/{creado['id']}").status_code == 404
