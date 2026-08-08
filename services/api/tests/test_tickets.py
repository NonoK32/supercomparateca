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
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-08-01"},
        files={"imagen": ("ticket.jpg", b"bytes-de-imagen", "image/jpeg")},
    )
    assert resp.status_code == 201
    ticket = resp.json()

    # Escenario de aceptación (§8): al menos una línea con precio y estado pendiente.
    assert ticket["estado"] == "pendiente"
    assert isinstance(ticket["usuario_id"], int)  # queda asociado al usuario del token
    assert len(ticket["lineas"]) >= 1

    textos = [linea["texto_original"] for linea in ticket["lineas"]]
    assert any("LECHE" in t for t in textos)
    # La línea TOTAL no debe colarse como producto.
    assert all("TOTAL" not in t.upper() for t in textos)
    # Aún sin asociar a producto (eso es EPIC 3).
    assert all(linea["producto_id"] is None for linea in ticket["lineas"])
    assert float(ticket["lineas"][0]["precio_total"]) == 0.89


def test_deduce_supermercado_y_fecha_del_propio_ticket(client, fake_ocr):
    # Los dos datos van impresos en el papel: subir la foto debe bastar.
    _crear_supermercado(client)
    fake_ocr.texto = "MERCADONA S.A.\n05/08/2026 13:42\n" + TICKET_MERCADONA

    resp = client.post("/tickets", files={"imagen": ("t.jpg", b"x", "image/jpeg")})

    assert resp.status_code == 201
    assert resp.json()["fecha_compra"] == "2026-08-05"
    assert resp.json()["supermercado_id"] == 1


def test_si_no_se_deducen_se_piden_y_no_se_crea_nada(client, fake_ocr):
    _crear_supermercado(client)
    fake_ocr.texto = "LECHE DESNATADA 0,89\nPAN 1,25"

    resp = client.post("/tickets", files={"imagen": ("t.jpg", b"x", "image/jpeg")})

    assert resp.status_code == 422
    assert set(resp.json()["detail"]["faltan"]) == {"supermercado_id", "fecha_compra"}
    # Un ticket a medias no se puede comparar con nada: no debe quedar rastro.
    assert client.get("/tickets").json() == []


def test_solo_se_pide_lo_que_falta(client, fake_ocr):
    _crear_supermercado(client)
    fake_ocr.texto = "MERCADONA S.A.\nLECHE DESNATADA 0,89"

    resp = client.post("/tickets", files={"imagen": ("t.jpg", b"x", "image/jpeg")})

    assert resp.status_code == 422
    assert resp.json()["detail"]["faltan"] == ["fecha_compra"]


def test_lo_que_indica_el_usuario_gana_a_lo_detectado(client, fake_ocr):
    # Al reenviar tras preguntar, la respuesta del usuario manda.
    sm = _crear_supermercado(client)
    fake_ocr.texto = "MERCADONA S.A.\n05/08/2026\nLECHE 0,89"

    resp = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-07-01"},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    )

    assert resp.json()["fecha_compra"] == "2026-07-01"


def test_supermercado_inexistente_da_404(client, fake_ocr):
    fake_ocr.texto = "LECHE 0,89"
    resp = client.post(
        "/tickets",
        data={"supermercado_id": 999, "fecha_compra": "2026-08-01"},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    )
    assert resp.status_code == 404


def test_imagen_vacia_da_400(client):
    sm = _crear_supermercado(client)
    resp = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-08-01"},
        files={"imagen": ("t.jpg", b"", "image/jpeg")},
    )
    assert resp.status_code == 400


def test_listar_y_obtener(client, fake_ocr):
    sm = _crear_supermercado(client)
    fake_ocr.texto = "LECHE 0,89"
    creado = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-08-01"},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()

    assert len(client.get("/tickets").json()) == 1
    resp = client.get(f"/tickets/{creado['id']}")
    assert resp.status_code == 200
    # El texto OCR completo NO se persiste (minimización): del ticket solo
    # sobrevive lo parseado. Ver la migración 01233e7e156c.
    assert "texto_ocr_bruto" not in resp.json()
    assert [linea["texto_original"] for linea in resp.json()["lineas"]] == ["LECHE"]


def test_eliminar(client, fake_ocr):
    sm = _crear_supermercado(client)
    fake_ocr.texto = "LECHE 0,89"
    creado = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-08-01"},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()

    assert client.delete(f"/tickets/{creado['id']}").status_code == 204
    assert client.get(f"/tickets/{creado['id']}").status_code == 404
