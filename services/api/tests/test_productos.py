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
