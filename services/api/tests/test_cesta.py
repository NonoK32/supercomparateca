"""FR10: comparar el coste total de la cesta habitual entre supermercados."""

from .conftest import registrar_y_login


def _sm(client, nombre):
    return client.post("/supermercados", json={"nombre": nombre}).json()["id"]


def _compra(client, fake_ocr, sm_id, texto, fecha):
    """Sube un ticket con ese texto y devuelve sus líneas ya creadas."""
    fake_ocr.texto = texto
    return client.post(
        "/tickets",
        data={"supermercado_id": sm_id, "fecha_compra": fecha},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()


def _asociar(client, linea_id, nombre):
    return client.post(
        f"/lineas/{linea_id}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": nombre}},
    ).json()["producto_id"]


def test_cesta_vacia_sin_compras(client):
    data = client.get("/cesta/comparativa").json()
    assert data["productos"] == []
    assert data["supermercados"] == []


def test_la_cesta_ordena_por_veces_comprado(client, fake_ocr):
    sm = _sm(client, "Mercadona")
    # La leche se compra dos veces; el pan, una.
    t1 = _compra(client, fake_ocr, sm, "LECHE 1,00\nPAN 2,00\n", "2026-01-05")
    leche = _asociar(client, t1["lineas"][0]["id"], "Leche 1L")
    _asociar(client, t1["lineas"][1]["id"], "Pan de molde")
    _compra(client, fake_ocr, sm, "LECHE 1,10\n", "2026-01-12")

    productos = client.get("/cesta/comparativa").json()["productos"]
    assert productos[0]["producto_id"] == leche
    assert productos[0]["veces_comprado"] == 2
    assert productos[1]["veces_comprado"] == 1


def test_compara_el_total_entre_supermercados(client, fake_ocr):
    merca = _sm(client, "Mercadona")
    lidl = _sm(client, "Lidl")

    t1 = _compra(client, fake_ocr, merca, "LECHE 1,00\nPAN 2,00\n", "2026-01-05")
    leche = _asociar(client, t1["lineas"][0]["id"], "Leche 1L")
    pan = _asociar(client, t1["lineas"][1]["id"], "Pan de molde")

    # Los mismos dos productos en Lidl, más baratos.
    t2 = _compra(client, fake_ocr, lidl, "LECHE 0,80\nPAN 1,50\n", "2026-01-06")
    client.post(
        f"/lineas/{t2['lineas'][0]['id']}/asociar", json={"producto_id": leche}
    )
    client.post(f"/lineas/{t2['lineas'][1]['id']}/asociar", json={"producto_id": pan})

    sms = client.get("/cesta/comparativa").json()["supermercados"]
    totales = {s["supermercado"]: float(s["total"]) for s in sms}
    assert totales == {"Mercadona": 3.00, "Lidl": 2.30}
    # Misma cobertura: gana el más barato.
    assert sms[0]["supermercado"] == "Lidl"
    assert all(s["productos_cubiertos"] == 2 for s in sms)


def test_cobertura_parcial_no_finge_ser_el_mas_barato(client, fake_ocr):
    """Un supermercado con solo 1 de los 2 productos tiene un total menor, pero
    no debe presentarse como la opción ganadora."""
    merca = _sm(client, "Mercadona")
    lidl = _sm(client, "Lidl")

    t1 = _compra(client, fake_ocr, merca, "LECHE 1,00\nPAN 2,00\n", "2026-01-05")
    leche = _asociar(client, t1["lineas"][0]["id"], "Leche 1L")
    _asociar(client, t1["lineas"][1]["id"], "Pan de molde")

    # En Lidl solo hay precio de la leche.
    t2 = _compra(client, fake_ocr, lidl, "LECHE 0,10\n", "2026-01-06")
    client.post(
        f"/lineas/{t2['lineas'][0]['id']}/asociar", json={"producto_id": leche}
    )

    sms = client.get("/cesta/comparativa").json()["supermercados"]
    assert sms[0]["supermercado"] == "Mercadona"
    assert sms[0]["productos_cubiertos"] == 2
    lidl_fila = next(s for s in sms if s["supermercado"] == "Lidl")
    assert lidl_fila["productos_cubiertos"] == 1
    assert float(lidl_fila["total"]) < float(sms[0]["total"])


def test_usa_el_precio_mas_reciente(client, fake_ocr):
    sm = _sm(client, "Mercadona")
    t1 = _compra(client, fake_ocr, sm, "LECHE 1,00\n", "2026-01-05")
    leche = _asociar(client, t1["lineas"][0]["id"], "Leche 1L")
    t2 = _compra(client, fake_ocr, sm, "LECHE 1,50\n", "2026-02-05")
    client.post(
        f"/lineas/{t2['lineas'][0]['id']}/asociar", json={"producto_id": leche}
    )

    sms = client.get("/cesta/comparativa").json()["supermercados"]
    assert float(sms[0]["total"]) == 1.50


def test_la_cesta_es_de_cada_usuario(api_client, fake_ocr):
    """La cesta sale de MIS tickets, aunque los precios sean compartidos."""
    token = registrar_y_login(api_client, email="ana@example.com")
    api_client.headers["Authorization"] = f"Bearer {token}"
    sm = _sm(api_client, "Mercadona")
    t1 = _compra(api_client, fake_ocr, sm, "LECHE 1,00\n", "2026-01-05")
    _asociar(api_client, t1["lineas"][0]["id"], "Leche 1L")

    token_bea = registrar_y_login(api_client, email="bea@example.com")
    api_client.headers["Authorization"] = f"Bearer {token_bea}"
    assert api_client.get("/cesta/comparativa").json()["productos"] == []


def test_cesta_requiere_auth(api_client):
    assert api_client.get("/cesta/comparativa").status_code == 401
