TICKET = "LECHE DESNATADA 0,89\nPAN DE MOLDE 1,25\n"


def _supermercado(client, nombre="Mercadona"):
    return client.post("/supermercados", json={"nombre": nombre}).json()


def _subir_ticket(client, sm_id, texto=TICKET):
    return client.post(
        "/tickets",
        data={"supermercado_id": sm_id},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()


def test_asociar_a_producto_existente(client, fake_ocr):
    sm = _supermercado(client)
    producto = client.post(
        "/productos", json={"nombre_normalizado": "Leche desnatada 1L"}
    ).json()
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    linea = ticket["lineas"][0]

    resp = client.post(
        f"/lineas/{linea['id']}/asociar", json={"producto_id": producto["id"]}
    )
    assert resp.status_code == 200
    assert resp.json()["producto_id"] == producto["id"]


def test_asociar_creando_producto_nuevo(client, fake_ocr):
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    linea = ticket["lineas"][0]

    resp = client.post(
        f"/lineas/{linea['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche desnatada 1L"}},
    )
    assert resp.status_code == 200
    assert resp.json()["producto_id"] is not None
    # El producto se ha creado.
    assert len(client.get("/productos").json()) == 1


def test_estado_pasa_a_procesado_cuando_todas_asociadas(client, fake_ocr):
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    assert ticket["estado"] == "pendiente"

    for linea in ticket["lineas"]:
        client.post(
            f"/lineas/{linea['id']}/asociar",
            json={"nuevo_producto": {"nombre_normalizado": f"P-{linea['id']}"}},
        )

    assert client.get(f"/tickets/{ticket['id']}").json()["estado"] == "procesado"


def test_alias_autoasigna_en_siguiente_ticket(client, fake_ocr):
    """§5bis punto 1: tras confirmar una vez, el siguiente ticket del mismo
    supermercado asigna el producto solo, sin preguntar."""
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket1 = _subir_ticket(client, sm["id"])
    linea_leche = ticket1["lineas"][0]
    producto = client.post(
        f"/lineas/{linea_leche['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche desnatada 1L"}},
    ).json()

    # Segundo ticket del mismo supermercado con el mismo texto.
    ticket2 = _subir_ticket(client, sm["id"])
    linea2 = next(
        line for line in ticket2["lineas"] if line["texto_original"] == "LECHE DESNATADA"
    )
    assert linea2["producto_id"] == producto["producto_id"]


def test_alias_es_por_supermercado(client, fake_ocr):
    merca = _supermercado(client, "Mercadona")
    lidl = _supermercado(client, "Lidl")
    fake_ocr.texto = TICKET

    t_merca = _subir_ticket(client, merca["id"])
    client.post(
        f"/lineas/{t_merca['lineas'][0]['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche desnatada 1L"}},
    )

    # Mismo texto en otro supermercado: NO debe auto-asignarse.
    t_lidl = _subir_ticket(client, lidl["id"])
    assert all(line["producto_id"] is None for line in t_lidl["lineas"])


def test_correccion_actualiza_alias(client, fake_ocr):
    """§5bis punto 4: re-asociar cambia el alias; el siguiente ticket usa el nuevo."""
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    linea = ticket["lineas"][0]

    p1 = client.post(
        f"/lineas/{linea['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche marca A"}},
    ).json()
    p2 = client.post(
        f"/lineas/{linea['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche marca B"}},
    ).json()
    assert p1["producto_id"] != p2["producto_id"]

    ticket2 = _subir_ticket(client, sm["id"])
    linea2 = next(
        line for line in ticket2["lineas"] if line["texto_original"] == "LECHE DESNATADA"
    )
    assert linea2["producto_id"] == p2["producto_id"]


def test_linea_inexistente_da_404(client):
    resp = client.post("/lineas/999/asociar", json={"producto_id": 1})
    assert resp.status_code == 404


def test_producto_inexistente_da_404(client, fake_ocr):
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    resp = client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar", json={"producto_id": 999}
    )
    assert resp.status_code == 404


def test_payload_invalido_da_422(client, fake_ocr):
    sm = _supermercado(client)
    fake_ocr.texto = TICKET
    ticket = _subir_ticket(client, sm["id"])
    linea_id = ticket["lineas"][0]["id"]

    # Ninguno de los dos.
    assert client.post(f"/lineas/{linea_id}/asociar", json={}).status_code == 422
    # Los dos a la vez.
    resp = client.post(
        f"/lineas/{linea_id}/asociar",
        json={"producto_id": 1, "nuevo_producto": {"nombre_normalizado": "X"}},
    )
    assert resp.status_code == 422
