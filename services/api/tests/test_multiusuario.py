"""EPIC 11 / Fase 3: multiusuario, datos compartidos y autorización.

Reglas que se comprueban aquí:
- Los precios son comunes: el ticket de uno alimenta la comparativa de todos.
- El catálogo global (productos, supermercados) solo lo modifica un admin.
- Los alias son propios con respaldo de la comunidad: heredas lo que otros han
  enseñado, pero tu corrección no le cambia el producto a nadie.
"""

from .conftest import registrar_y_login

TICKET = "LECHE DESNATADA 0,89\n"


def _como(client, email):
    """Cambia el cliente al usuario indicado (lo registra la primera vez)."""
    token = registrar_y_login(client, email=email)
    client.headers["Authorization"] = f"Bearer {token}"


def _subir_ticket(client, sm_id, fecha=None):
    datos = {"supermercado_id": sm_id}
    if fecha:
        datos["fecha_compra"] = fecha
    return client.post(
        "/tickets", data=datos, files={"imagen": ("t.jpg", b"x", "image/jpeg")}
    ).json()


def _asociar_nuevo(client, linea_id, nombre):
    return client.post(
        f"/lineas/{linea_id}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": nombre}},
    ).json()


# ---- Roles ----
def test_el_primer_usuario_es_admin_y_el_segundo_no(api_client):
    _como(api_client, "primero@example.com")
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    # El admin puede renombrar el catálogo global.
    assert api_client.patch(
        f"/supermercados/{sm['id']}", json={"nombre": "Mercadona Centro"}
    ).status_code == 200

    _como(api_client, "segundo@example.com")
    assert api_client.patch(
        f"/supermercados/{sm['id']}", json={"nombre": "Mío"}
    ).status_code == 403
    assert api_client.delete(f"/supermercados/{sm['id']}").status_code == 403


def test_usuario_normal_crea_pero_no_borra_productos(api_client):
    _como(api_client, "admin@example.com")
    _como(api_client, "normal@example.com")

    # Crear sí: es el flujo normal al confirmar una línea de ticket.
    producto = api_client.post(
        "/productos", json={"nombre_normalizado": "Leche desnatada 1L"}
    ).json()
    assert "id" in producto

    assert api_client.delete(f"/productos/{producto['id']}").status_code == 403
    assert api_client.patch(
        f"/productos/{producto['id']}", json={"categoria": "lácteos"}
    ).status_code == 403


# ---- Datos compartidos ----
def test_los_precios_de_otros_usuarios_cuentan_en_la_comparativa(api_client, fake_ocr):
    """Fase 3: más gente subiendo tickets = comparativa más fiable."""
    _como(api_client, "ana@example.com")
    merca = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    lidl = api_client.post("/supermercados", json={"nombre": "Lidl"}).json()
    fake_ocr.texto = TICKET
    ticket_ana = _subir_ticket(api_client, merca["id"])
    producto = _asociar_nuevo(
        api_client, ticket_ana["lineas"][0]["id"], "Leche desnatada 1L"
    )

    # Otro usuario aporta el precio del mismo producto en otro supermercado.
    _como(api_client, "bea@example.com")
    fake_ocr.texto = "LECHE DESNATADA 0,75\n"
    ticket_bea = _subir_ticket(api_client, lidl["id"])
    api_client.post(
        f"/lineas/{ticket_bea['lineas'][0]['id']}/asociar",
        json={"producto_id": producto["producto_id"]},
    )

    # Ana ve los dos precios, incluido el que ella nunca subió.
    _como(api_client, "ana@example.com")
    precios = api_client.get(f"/productos/{producto['producto_id']}/precios").json()
    nombres = [s["supermercado"] for s in precios["supermercados"]]
    assert set(nombres) == {"Mercadona", "Lidl"}
    # El más barato va primero.
    assert nombres[0] == "Lidl"


# ---- Alias propios con respaldo de la comunidad ----
def test_hereda_el_alias_de_la_comunidad(api_client, fake_ocr):
    _como(api_client, "ana@example.com")
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    fake_ocr.texto = TICKET
    ticket_ana = _subir_ticket(api_client, sm["id"])
    producto = _asociar_nuevo(
        api_client, ticket_ana["lineas"][0]["id"], "Leche desnatada 1L"
    )

    # Bea nunca ha confirmado ese texto: se aprovecha de lo que enseñó Ana.
    _como(api_client, "bea@example.com")
    ticket_bea = _subir_ticket(api_client, sm["id"])
    assert ticket_bea["lineas"][0]["producto_id"] == producto["producto_id"]


def test_mi_correccion_no_afecta_a_los_demas(api_client, fake_ocr):
    """El punto clave del modelo de alias: discrepar es local."""
    _como(api_client, "ana@example.com")
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    fake_ocr.texto = TICKET
    ticket_ana = _subir_ticket(api_client, sm["id"])
    leche_ana = _asociar_nuevo(
        api_client, ticket_ana["lineas"][0]["id"], "Leche desnatada Hacendado 1L"
    )

    # Bea compra otra marca aunque el ticket ponga lo mismo: corrige.
    _como(api_client, "bea@example.com")
    ticket_bea = _subir_ticket(api_client, sm["id"])
    leche_bea = _asociar_nuevo(
        api_client, ticket_bea["lineas"][0]["id"], "Leche desnatada Pascual 1L"
    )
    assert leche_bea["producto_id"] != leche_ana["producto_id"]

    # Bea mantiene su corrección en los siguientes tickets...
    ticket_bea2 = _subir_ticket(api_client, sm["id"])
    assert ticket_bea2["lineas"][0]["producto_id"] == leche_bea["producto_id"]

    # ...y a Ana no le ha cambiado nada.
    _como(api_client, "ana@example.com")
    ticket_ana2 = _subir_ticket(api_client, sm["id"])
    assert ticket_ana2["lineas"][0]["producto_id"] == leche_ana["producto_id"]


def test_el_fuzzy_respeta_el_alias_propio(api_client, fake_ocr):
    """Un texto parecido debe resolver al producto que YO confirmé, no al de otro."""
    _como(api_client, "ana@example.com")
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    fake_ocr.texto = TICKET
    ticket_ana = _subir_ticket(api_client, sm["id"])
    _asociar_nuevo(api_client, ticket_ana["lineas"][0]["id"], "Leche Hacendado 1L")

    _como(api_client, "bea@example.com")
    ticket_bea = _subir_ticket(api_client, sm["id"])
    leche_bea = _asociar_nuevo(
        api_client, ticket_bea["lineas"][0]["id"], "Leche Pascual 1L"
    )

    # Texto casi igual: entra por similitud, no por coincidencia exacta.
    fake_ocr.texto = "LECHE DESNATAD 0,89\n"
    ticket_bea2 = _subir_ticket(api_client, sm["id"])
    assert ticket_bea2["lineas"][0]["producto_id"] == leche_bea["producto_id"]
