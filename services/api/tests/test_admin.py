"""Panel de administración: ver las cuentas, cambiar roles y borrar usuarios.

Lo que se comprueba aquí:
- Solo un admin llega; para el resto no existe (403).
- Borrar una cuenta **conserva sus precios**: los tickets se desvinculan, no se
  borran, igual que en el borrado propio. Es la regla del proyecto y es la que
  más fácil sería romper sin darse cuenta.
- La propia cuenta no se gestiona desde aquí.
"""

from .conftest import registrar_y_login


def _como(client, email):
    """Cambia el cliente al usuario indicado (lo registra la primera vez)."""
    token = registrar_y_login(client, email=email)
    client.headers["Authorization"] = f"Bearer {token}"


def test_quien_soy_dice_el_rol(api_client):
    # El frontend lo usa para saber si pinta el panel. El primero es admin.
    _como(api_client, "jefa@example.com")
    yo = api_client.get("/auth/me").json()
    assert yo["email"] == "jefa@example.com"
    assert yo["rol"] == "admin"

    _como(api_client, "otro@example.com")
    assert api_client.get("/auth/me").json()["rol"] == "usuario"


def test_solo_el_admin_ve_y_toca_las_cuentas(api_client):
    _como(api_client, "jefa@example.com")
    _como(api_client, "curioso@example.com")

    # Los correos de terceros no están a la vista de cualquiera con cuenta.
    assert api_client.get("/usuarios").status_code == 403
    assert api_client.delete("/usuarios/1").status_code == 403
    assert api_client.patch("/usuarios/1", json={"rol": "admin"}).status_code == 403


def test_listar_usuarios(api_client):
    _como(api_client, "jefa@example.com")
    _como(api_client, "pepa@example.com")
    _como(api_client, "jefa@example.com")

    usuarios = api_client.get("/usuarios").json()

    assert [u["email"] for u in usuarios] == ["jefa@example.com", "pepa@example.com"]
    assert [u["rol"] for u in usuarios] == ["admin", "usuario"]
    # Sin confirmar no se puede entrar: saber cuáles son cuentas muertas es
    # justo lo que se mira antes de limpiar.
    assert all(u["email_verificado"] for u in usuarios)
    assert "password_hash" not in usuarios[0]


def test_borrar_usuario_conserva_sus_precios(api_client, fake_ocr):
    # La regla del proyecto: los precios son de todos. Borrar a quien subió un
    # ticket no puede empeorar la comparativa de los demás.
    fake_ocr.texto = "LECHE DESNATADA 0,89\n"
    _como(api_client, "jefa@example.com")
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()

    _como(api_client, "pepa@example.com")
    ticket = api_client.post(
        "/tickets",
        data={"supermercado_id": sm["id"], "fecha_compra": "2026-08-01"},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()
    producto = api_client.post(
        f"/lineas/{ticket['lineas'][0]['id']}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche desnatada 1L"}},
    ).json()["producto_id"]
    pepa = 2

    _como(api_client, "jefa@example.com")
    assert api_client.delete(f"/usuarios/{pepa}").status_code == 204

    # La cuenta se ha ido...
    assert [u["email"] for u in api_client.get("/usuarios").json()] == [
        "jefa@example.com"
    ]
    # ...pero su precio sigue alimentando la comparativa de todos.
    precios = api_client.get(f"/productos/{producto}/precios").json()
    assert len(precios["supermercados"]) == 1
    assert float(precios["supermercados"][0]["precio_actual"]) == 0.89


def test_el_admin_no_se_gestiona_a_si_mismo_desde_el_panel(api_client):
    # Borrarse desde aquí se saltaría la contraseña que sí pide DELETE /auth/me,
    # y bajarse el rol es la forma más fácil de quedarse sin ningún admin.
    _como(api_client, "jefa@example.com")
    yo = api_client.get("/auth/me").json()["id"]

    assert api_client.delete(f"/usuarios/{yo}").status_code == 409
    assert api_client.patch(f"/usuarios/{yo}", json={"rol": "usuario"}).status_code == 409
    assert api_client.get("/auth/me").json()["rol"] == "admin"


def test_nombrar_y_retirar_administradores(api_client):
    # Es lo que hace cumplible el aviso de DELETE /auth/me ("nombra a otro
    # antes de borrar tu cuenta"), que hasta ahora no tenía forma de cumplirse.
    _como(api_client, "jefa@example.com")
    _como(api_client, "pepa@example.com")
    _como(api_client, "jefa@example.com")

    assert api_client.patch("/usuarios/2", json={"rol": "admin"}).json()["rol"] == "admin"

    # Y Pepa ya puede administrar de verdad, no solo en el papel.
    _como(api_client, "pepa@example.com")
    assert api_client.get("/usuarios").status_code == 200

    # Retirar el rol también funciona.
    assert api_client.patch("/usuarios/1", json={"rol": "usuario"}).json()["rol"] == "usuario"
    _como(api_client, "jefa@example.com")
    assert api_client.get("/usuarios").status_code == 403


def test_rol_invalido_se_rechaza(api_client):
    _como(api_client, "jefa@example.com")
    _como(api_client, "pepa@example.com")
    _como(api_client, "jefa@example.com")

    assert api_client.patch("/usuarios/2", json={"rol": "superadmin"}).status_code == 422


def test_usuario_inexistente_da_404(api_client):
    _como(api_client, "jefa@example.com")
    assert api_client.delete("/usuarios/999").status_code == 404
    assert api_client.patch("/usuarios/999", json={"rol": "admin"}).status_code == 404
