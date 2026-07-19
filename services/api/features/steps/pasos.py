from behave import given, then, when


def _autenticar(context, email="usuario@example.com", password="password123"):
    context.client.post(
        "/auth/registro",
        json={"nombre": "Usuario", "email": email, "password": password},
    )
    token = context.client.post(
        "/auth/login", data={"username": email, "password": password}
    ).json()["access_token"]
    context.client.headers["Authorization"] = f"Bearer {token}"


# ---- Autenticación ----
@given("que soy un usuario autenticado")
def paso_usuario_autenticado(context):
    _autenticar(context)


@given('que me registro con email "{email}" y contraseña "{password}"')
def paso_registro(context, email, password):
    context.response = context.client.post(
        "/auth/registro",
        json={"nombre": "Usuario", "email": email, "password": password},
    )
    assert context.response.status_code == 201, context.response.text


@when('inicio sesión con email "{email}" y contraseña "{password}"')
def paso_login(context, email, password):
    context.response = context.client.post(
        "/auth/login", data={"username": email, "password": password}
    )


@then("recibo un token de acceso")
def paso_recibo_token(context):
    assert context.response.status_code == 200, context.response.text
    assert context.response.json().get("access_token")


@when("pido la lista de supermercados sin autenticarme")
def paso_lista_sin_auth(context):
    context.response = context.client.get("/supermercados")


@then("la respuesta es {codigo:d}")
def paso_respuesta_codigo(context, codigo):
    assert context.response.status_code == codigo, context.response.text


# ---- Supermercados / tickets ----
@given('existe el supermercado "{nombre}"')
def paso_existe_supermercado(context, nombre):
    resp = context.client.post("/supermercados", json={"nombre": nombre})
    assert resp.status_code == 201, resp.text
    context.supermercados[nombre] = resp.json()["id"]


@when('subo la foto de un ticket de "{nombre}" con el texto:')
def paso_subo_ticket(context, nombre):
    context.fake_ocr.texto = context.text
    resp = context.client.post(
        "/tickets",
        data={"supermercado_id": context.supermercados[nombre]},
        files={"imagen": ("ticket.jpg", b"bytes", "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text
    context.response = resp
    context.ticket = resp.json()


@then("el sistema extrae al menos {n:d} línea de producto con precio")
def paso_extrae_lineas(context, n):
    lineas = context.ticket["lineas"]
    assert len(lineas) >= n, f"esperadas >= {n}, obtenidas {len(lineas)}"
    assert all(float(linea["precio_total"]) > 0 for linea in lineas)


@then('el ticket queda en estado "{estado}"')
def paso_estado_ticket(context, estado):
    assert context.ticket["estado"] == estado, context.ticket["estado"]


@when('asocio la primera línea al producto nuevo "{nombre}"')
def paso_asocio_linea(context, nombre):
    linea_id = context.ticket["lineas"][0]["id"]
    resp = context.client.post(
        f"/lineas/{linea_id}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": nombre}},
    )
    assert resp.status_code == 200, resp.text


@then("la primera línea del último ticket queda asociada a un producto")
def paso_linea_asociada(context):
    assert context.ticket["lineas"][0]["producto_id"] is not None


# ---- Precios ----
@then('el producto "{nombre}" cuesta menos en "{barato}" que en "{caro}"')
def paso_comparativa(context, nombre, barato, caro):
    # Busca el producto por nombre para obtener su id.
    productos = context.client.get("/productos").json()
    producto_id = next(p["id"] for p in productos if p["nombre_normalizado"] == nombre)
    sms = context.client.get(f"/productos/{producto_id}/precios").json()["supermercados"]
    precios = {s["supermercado"]: float(s["precio_actual"]) for s in sms}
    assert precios[barato] < precios[caro], precios
