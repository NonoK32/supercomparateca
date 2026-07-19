def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ocr_devuelve_texto(client, monkeypatch):
    # Se mockea Tesseract para no depender del binario en los tests.
    monkeypatch.setattr("app.ocr.extraer_texto", lambda contenido, lang="spa": "LECHE 0,89")
    resp = client.post("/ocr", files={"imagen": ("t.png", b"bytes", "image/png")})
    assert resp.status_code == 200
    assert resp.json() == {"texto": "LECHE 0,89"}


def test_ocr_imagen_vacia_da_400(client):
    resp = client.post("/ocr", files={"imagen": ("t.png", b"", "image/png")})
    assert resp.status_code == 400


def test_ocr_archivo_no_imagen_da_400(client):
    # Bytes que no son una imagen: PIL lanza UnidentifiedImageError -> 400.
    resp = client.post("/ocr", files={"imagen": ("t.png", b"esto-no-es-imagen", "image/png")})
    assert resp.status_code == 400
