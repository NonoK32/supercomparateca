"""Tests de FR7 (comparativa entre supermercados) y FR8 (evolución temporal)."""


def _crear_entorno(client):
    merca = client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    lidl = client.post("/supermercados", json={"nombre": "Lidl"}).json()
    prod = client.post(
        "/productos", json={"nombre_normalizado": "Leche desnatada 1L"}
    ).json()
    return merca, lidl, prod


def _registrar_precio(client, fake_ocr, sm_id, prod_id, precio, fecha):
    """Sube un ticket con una línea a `precio` en `fecha` y la asocia al producto."""
    fake_ocr.texto = f"LECHE DESNATADA {precio}\n"
    ticket = client.post(
        "/tickets",
        data={"supermercado_id": sm_id, "fecha_compra": fecha},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()
    linea = ticket["lineas"][0]
    client.post(f"/lineas/{linea['id']}/asociar", json={"producto_id": prod_id})


def test_comparativa_precio_actual_por_supermercado(client, fake_ocr):
    merca, lidl, prod = _crear_entorno(client)
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,95", "2026-07-01")
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,89", "2026-07-10")
    _registrar_precio(client, fake_ocr, lidl["id"], prod["id"], "0,92", "2026-07-05")

    resp = client.get(f"/productos/{prod['id']}/precios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["producto_id"] == prod["id"]

    sms = data["supermercados"]
    # Ordenado por precio ascendente: Mercadona (0.89) antes que Lidl (0.92).
    assert [s["supermercado"] for s in sms] == ["Mercadona", "Lidl"]
    # Precio actual = el más reciente por fecha.
    assert float(sms[0]["precio_actual"]) == 0.89
    assert sms[0]["fecha"] == "2026-07-10"
    assert sms[0]["num_observaciones"] == 2
    assert float(sms[1]["precio_actual"]) == 0.92
    assert sms[1]["num_observaciones"] == 1


def test_historico_ordenado_por_fecha(client, fake_ocr):
    merca, lidl, prod = _crear_entorno(client)
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,95", "2026-07-01")
    _registrar_precio(client, fake_ocr, lidl["id"], prod["id"], "0,92", "2026-07-05")
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,89", "2026-07-10")

    resp = client.get(f"/productos/{prod['id']}/historico")
    assert resp.status_code == 200
    puntos = resp.json()["historico"]
    assert [p["fecha"] for p in puntos] == ["2026-07-01", "2026-07-05", "2026-07-10"]
    assert [float(p["precio"]) for p in puntos] == [0.95, 0.92, 0.89]


def test_historico_filtrado_por_supermercado(client, fake_ocr):
    merca, lidl, prod = _crear_entorno(client)
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,95", "2026-07-01")
    _registrar_precio(client, fake_ocr, lidl["id"], prod["id"], "0,92", "2026-07-05")
    _registrar_precio(client, fake_ocr, merca["id"], prod["id"], "0,89", "2026-07-10")

    resp = client.get(
        f"/productos/{prod['id']}/historico", params={"supermercado_id": merca["id"]}
    )
    puntos = resp.json()["historico"]
    assert len(puntos) == 2
    assert all(p["supermercado"] == "Mercadona" for p in puntos)


def test_producto_sin_historico_devuelve_listas_vacias(client):
    prod = client.post("/productos", json={"nombre_normalizado": "Sin datos"}).json()
    assert client.get(f"/productos/{prod['id']}/precios").json()["supermercados"] == []
    assert client.get(f"/productos/{prod['id']}/historico").json()["historico"] == []


def test_producto_inexistente_da_404(client):
    assert client.get("/productos/999/precios").status_code == 404
    assert client.get("/productos/999/historico").status_code == 404
