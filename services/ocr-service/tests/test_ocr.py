import pytest

from app import ocr

from .conftest import pdf


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


def test_pdf_con_texto_no_pasa_por_el_ocr(monkeypatch):
    """Un e-ticket lleva el texto exacto dentro; el OCR solo lo empeoraria."""
    monkeypatch.setattr(
        "app.ocr.pytesseract.image_to_string",
        lambda *a, **kw: pytest.fail("no deberia llamarse al OCR"),
    )
    texto = ocr.extraer_texto(pdf(["MERCADONA S.A.", "LECHE DESNATADA 0,89", "TOTAL 0,89"]))
    assert "LECHE DESNATADA 0,89" in texto


def test_pdf_escaneado_se_rasteriza_y_pasa_por_el_ocr(monkeypatch):
    """Sin capa de texto no hay nada que extraer: hay que mirar los pixeles."""
    monkeypatch.setattr("app.ocr.pdf2image.convert_from_bytes", lambda *a, **kw: ["pagina"])
    monkeypatch.setattr("app.ocr.pytesseract.image_to_string", lambda *a, **kw: "LECHE 0,89")
    assert ocr.extraer_texto(pdf([])) == "LECHE 0,89"


def test_pdf_solo_con_membrete_cuenta_como_escaneado(monkeypatch):
    """Un escaneo puede traer cuatro caracteres sueltos de la capa de texto. No
    son un ticket, asi que tampoco valen para saltarse el OCR."""
    monkeypatch.setattr("app.ocr.pdf2image.convert_from_bytes", lambda *a, **kw: ["pagina"])
    monkeypatch.setattr("app.ocr.pytesseract.image_to_string", lambda *a, **kw: "LECHE 0,89")
    assert ocr.extraer_texto(pdf(["Dia"])) == "LECHE 0,89"


def test_pdf_largo_se_corta_por_las_dos_vias(monkeypatch):
    """Cada pagina de mas es una pasada entera de Tesseract; un ticket no tiene
    diez. El tope se aplica lea el texto o rasterice."""
    paginas = [[f"PAGINA {n} CON TEXTO DE SOBRA PARA CONTAR"] for n in range(9)]
    texto = ocr.extraer_texto(pdf(*paginas))
    assert "PAGINA 4" in texto and "PAGINA 5" not in texto

    vistas = {}
    monkeypatch.setattr(
        "app.ocr.pdf2image.convert_from_bytes",
        lambda contenido, **kw: vistas.update(kw) or ["pagina"],
    )
    monkeypatch.setattr("app.ocr.pytesseract.image_to_string", lambda *a, **kw: "")
    ocr.extraer_texto(pdf(*[[] for _ in range(9)]))
    assert vistas["last_page"] == ocr.MAX_PAGINAS


def test_pdf_ilegible_da_400(client):
    # Empieza por %PDF- pero no lo es: pypdf lanza PyPdfError -> 400, no un 500.
    resp = client.post("/ocr", files={"imagen": ("t.pdf", b"%PDF-1.4 basura", "application/pdf")})
    assert resp.status_code == 400
