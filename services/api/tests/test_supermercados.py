def test_crear_y_obtener(client):
    resp = client.post("/supermercados", json={"nombre": "Mercadona"})
    assert resp.status_code == 201
    creado = resp.json()
    assert creado["nombre"] == "Mercadona"
    assert isinstance(creado["id"], int)

    resp = client.get(f"/supermercados/{creado['id']}")
    assert resp.status_code == 200
    assert resp.json() == creado


def test_listar(client):
    client.post("/supermercados", json={"nombre": "Mercadona"})
    client.post("/supermercados", json={"nombre": "Lidl"})
    resp = client.get("/supermercados")
    assert resp.status_code == 200
    nombres = {s["nombre"] for s in resp.json()}
    assert nombres == {"Mercadona", "Lidl"}


def test_nombre_duplicado_da_409(client):
    client.post("/supermercados", json={"nombre": "Dia"})
    resp = client.post("/supermercados", json={"nombre": "Dia"})
    assert resp.status_code == 409


def test_nombre_vacio_da_422(client):
    resp = client.post("/supermercados", json={"nombre": ""})
    assert resp.status_code == 422


def test_actualizar(client):
    creado = client.post("/supermercados", json={"nombre": "Aldi"}).json()
    resp = client.patch(f"/supermercados/{creado['id']}", json={"nombre": "ALDI"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "ALDI"


def test_eliminar(client):
    creado = client.post("/supermercados", json={"nombre": "Lidl"}).json()
    assert client.delete(f"/supermercados/{creado['id']}").status_code == 204
    assert client.get(f"/supermercados/{creado['id']}").status_code == 404


def test_obtener_inexistente_da_404(client):
    assert client.get("/supermercados/999").status_code == 404
