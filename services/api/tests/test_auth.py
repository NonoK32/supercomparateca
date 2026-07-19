from tests.conftest import registrar_y_login

CREDS = {"nombre": "Ana", "email": "ana@example.com", "password": "password123"}


def test_registro_devuelve_usuario_sin_password(api_client):
    resp = api_client.post("/auth/registro", json=CREDS)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "ana@example.com"
    assert "id" in data
    # El hash de la contraseña nunca se expone.
    assert "password" not in data
    assert "password_hash" not in data


def test_registro_email_duplicado_da_409(api_client):
    api_client.post("/auth/registro", json=CREDS)
    assert api_client.post("/auth/registro", json=CREDS).status_code == 409


def test_registro_email_invalido_da_422(api_client):
    malo = {**CREDS, "email": "no-es-email"}
    assert api_client.post("/auth/registro", json=malo).status_code == 422


def test_registro_password_corta_da_422(api_client):
    malo = {**CREDS, "password": "corta"}
    assert api_client.post("/auth/registro", json=malo).status_code == 422


def test_login_correcto_devuelve_token(api_client):
    api_client.post("/auth/registro", json=CREDS)
    resp = api_client.post(
        "/auth/login", data={"username": CREDS["email"], "password": CREDS["password"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_password_incorrecta_da_401(api_client):
    api_client.post("/auth/registro", json=CREDS)
    resp = api_client.post(
        "/auth/login", data={"username": CREDS["email"], "password": "mala-mala-mala"}
    )
    assert resp.status_code == 401


def test_endpoint_protegido_sin_token_da_401(api_client):
    assert api_client.get("/supermercados").status_code == 401
    assert api_client.get("/tickets").status_code == 401


def test_token_invalido_da_401(api_client):
    api_client.headers["Authorization"] = "Bearer token-falso"
    assert api_client.get("/supermercados").status_code == 401


def test_usuario_no_ve_tickets_de_otro(api_client, fake_ocr):
    # Usuario A crea un supermercado y un ticket.
    token_a = registrar_y_login(api_client, email="a@example.com")
    api_client.headers["Authorization"] = f"Bearer {token_a}"
    sm = api_client.post("/supermercados", json={"nombre": "Mercadona"}).json()
    fake_ocr.texto = "LECHE 0,89\n"
    ticket_a = api_client.post(
        "/tickets",
        data={"supermercado_id": sm["id"]},
        files={"imagen": ("t.jpg", b"x", "image/jpeg")},
    ).json()

    # Usuario B no ve el ticket de A.
    token_b = registrar_y_login(api_client, email="b@example.com")
    api_client.headers["Authorization"] = f"Bearer {token_b}"
    assert api_client.get("/tickets").json() == []
    assert api_client.get(f"/tickets/{ticket_a['id']}").status_code == 404
    # Ni puede asociar sus líneas.
    linea_id = ticket_a["lineas"][0]["id"]
    resp = api_client.post(
        f"/lineas/{linea_id}/asociar",
        json={"nuevo_producto": {"nombre_normalizado": "Leche"}},
    )
    assert resp.status_code == 404
