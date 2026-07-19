# ocr-service

Servicio de OCR en **Python + Tesseract**.

Recibe la imagen de un ticket (`POST /ocr`, multipart) y devuelve el texto
extraído: `{"texto": "..."}`. Está aislado en su propio contenedor para poder
sustituir el motor de OCR más adelante sin tocar el resto del sistema.

La imagen **no se almacena**: se procesa y se descarta; solo se devuelve el texto.
El parseo del texto en líneas/precios lo hace el servicio `api` (lógica de negocio).

## Requisito de sistema

Necesita el binario de Tesseract y los datos del idioma español:

```bash
brew install tesseract tesseract-lang    # macOS
```

El idioma se configura con la variable `OCR_LANG` (por defecto `spa`).

## Desarrollo

```bash
cd services/ocr-service
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/ruff check .                          # lint
.venv/bin/pytest -q                             # tests (Tesseract mockeado)
.venv/bin/uvicorn app.main:app --port 8001      # servidor en :8001
```

Los tests mockean Tesseract, así que **no** requieren el binario instalado.
