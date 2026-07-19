def test_crear_con_campos_opcionales(client):
    payload = {
        "nombre_normalizado": "Leche desnatada 1L",
        "categoria": "Lácteos",
        "unidad_medida": "L",
    }
    resp = client.post("/productos", json=payload)
    assert resp.status_code == 201
    creado = resp.json()
    assert creado["nombre_normalizado"] == "Leche desnatada 1L"
    assert creado["categoria"] == "Lácteos"
    assert creado["unidad_medida"] == "L"


def test_crear_solo_nombre(client):
    resp = client.post("/productos", json={"nombre_normalizado": "Huevos M x12"})
    assert resp.status_code == 201
    creado = resp.json()
    assert creado["categoria"] is None
    assert creado["unidad_medida"] is None


def test_nombre_duplicado_da_409(client):
    client.post("/productos", json={"nombre_normalizado": "Pan de molde"})
    resp = client.post("/productos", json={"nombre_normalizado": "Pan de molde"})
    assert resp.status_code == 409


def test_actualizar_parcial(client):
    creado = client.post(
        "/productos", json={"nombre_normalizado": "Aceite oliva 1L", "categoria": "Aceites"}
    ).json()
    resp = client.patch(f"/productos/{creado['id']}", json={"unidad_medida": "L"})
    assert resp.status_code == 200
    actualizado = resp.json()
    assert actualizado["unidad_medida"] == "L"
    assert actualizado["categoria"] == "Aceites"  # no se pierde lo previo


def test_eliminar(client):
    creado = client.post("/productos", json={"nombre_normalizado": "Yogur natural x4"}).json()
    assert client.delete(f"/productos/{creado['id']}").status_code == 204
    assert client.get(f"/productos/{creado['id']}").status_code == 404


def test_no_se_puede_eliminar_producto_en_uso(client, fake_ocr):
    # Producto asociado a una línea de ticket -> borrarlo debe dar 409, no 500.
    sm = client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    fake_ocr.texto = "LECHE 0,89\n"
    ticket = client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()
    asoc = client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche desnatada 1L"}},
    ).json()
    assert client.delete(f"/productos/{asoc['producto_id']}").status_code == 409
