"""Lista de la compra: elegir productos a mano y ver dónde sale mejor comprarlos.

Se distingue de la cesta habitual (FR10) en de dónde salen los productos —allí
del histórico del usuario, aquí los pone él—, pero el reparto de precios es el
mismo, así que aquí se comprueba sobre todo lo propio: que cada producto trae
sus precios ordenados y que la recomendación no engaña cuando falta cobertura.
"""

import pytest


@pytest.fixture
def catalogo(client, fake_ocr):
    """Dos supermercados con precios distintos para los mismos productos.

    Mercadona: leche 0,89 y pan 1,25. Lidl: solo leche, a 0,79.
    Así Lidl es más barato por producto pero no lo tiene todo, que es
    justamente el caso en el que un total sin cobertura engaña.
    """
    merca = client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    lidl = client.post("/supermercados", json={"nombre": "Lidl"}).json()

    def ticket(sm_id, texto, fecha="2026-08-01"):
        fake_ocr.texto = texto
        return client.post(
            "/tickets",
            data={"supermercado_id": sm_id, "fecha_compra": fecha},
            files={"imagen": ("t.jpg", b"x", "image/jpeg")},
        ).json()

    def asociar(linea_id, nombre=None, producto_id=None):
        cuerpo = (
            {"producto_id": producto_id}
            if producto_id
            else {"nuevo_producto": {"nombre_normalizado": nombre}}
        )
        return client.post(f"/lineas/{linea_id}/asociar", json=cuerpo).json()["producto_id"]

    t = ticket(merca["id"], "LECHE DESNATADA 0,89\nPAN DE MOLDE 1,25")
    leche = asociar(t["lineas"][0]["id"], "Leche desnatada 1L")
    pan = asociar(t["lineas"][1]["id"], "Pan de molde")

    t2 = ticket(lidl["id"], "LECHE DESNATADA 0,79")
    asociar(t2["lineas"][0]["id"], producto_id=leche)

    return {"leche": leche, "pan": pan}


def test_cada_producto_trae_sus_precios_de_menor_a_mayor(client, catalogo):
    resp = client.post("/cesta/lista", json={"producto_ids": [catalogo["leche"]]})

    assert resp.status_code == 200
    producto = resp.json()["productos"][0]
    assert producto["nombre_normalizado"] == "Leche desnatada 1L"
    precios = [(s["supermercado"], float(s["precio_actual"])) for s in producto["supermercados"]]
    # Ascendente: lo primero que se mira es dónde está más barato.
    assert precios == [("Lidl", 0.79), ("Mercadona", 0.89)]


def test_recomienda_donde_comprarlo_todo(client, catalogo):
    resp = client.post(
        "/cesta/lista", json={"producto_ids": [catalogo["leche"], catalogo["pan"]]}
    )

    supers = resp.json()["supermercados"]
    # Mercadona primero aunque su leche sea más cara: es el único que tiene los
    # dos productos. Un total de un solo producto no es comparable con uno de dos.
    assert supers[0]["supermercado"] == "Mercadona"
    assert supers[0]["productos_cubiertos"] == 2
    assert float(supers[0]["total"]) == 2.14
    assert supers[1]["supermercado"] == "Lidl"
    assert supers[1]["productos_cubiertos"] == 1


def test_un_producto_sin_precios_aparece_igual(client, catalogo):
    # Se calla y parecería que la recomendación lo tiene en cuenta.
    huerfano = client.post(
        "/productos", json={"nombre_normalizado": "Cafe molido 250g"}
    ).json()["id"]

    resp = client.post(
        "/cesta/lista", json={"producto_ids": [catalogo["leche"], huerfano]}
    )

    productos = resp.json()["productos"]
    assert len(productos) == 2
    sin_precio = next(p for p in productos if p["producto_id"] == huerfano)
    assert sin_precio["supermercados"] == []
    # Y ningún supermercado dice cubrir más de lo que cubre.
    assert all(s["productos_cubiertos"] <= 1 for s in resp.json()["supermercados"])


def test_se_respeta_el_orden_en_que_se_puso_la_lista(client, catalogo):
    ids = [catalogo["pan"], catalogo["leche"]]
    devueltos = [
        p["producto_id"]
        for p in client.post("/cesta/lista", json={"producto_ids": ids}).json()["productos"]
    ]
    assert devueltos == ids


def test_un_producto_borrado_no_tira_la_peticion(client, catalogo):
    # La lista vive en el navegador y el catálogo puede haber cambiado.
    resp = client.post("/cesta/lista", json={"producto_ids": [catalogo["leche"], 9999]})

    assert resp.status_code == 200
    assert len(resp.json()["productos"]) == 1


def test_lista_vacia_se_rechaza(client):
    assert client.post("/cesta/lista", json={"producto_ids": []}).status_code == 422


def test_requiere_sesion(api_client):
    assert api_client.post("/cesta/lista", json={"producto_ids": [1]}).status_code == 401
