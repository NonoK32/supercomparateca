# ocr-service

Servicio de OCR en **Python + Tesseract**.

Recibe un ticket (`POST /ocr`, multipart, campo `imagen`) y devuelve el texto
extraído: `{"texto": "..."}`. Está aislado en su propio contenedor para poder
sustituir el motor de OCR más adelante sin tocar el resto del sistema.

El archivo **no se almacena**: se procesa y se descarta; solo se devuelve el texto.
El parseo del texto en líneas/precios lo hace el servicio `api` (lógica de negocio).

## Qué acepta

Una **imagen** (la foto del ticket) o un **PDF**. El campo se llama `imagen` por
compatibilidad con lo que ya envía el `api`; el tipo se deduce del contenido, no
del nombre ni del `Content-Type`.

Con un PDF se intenta primero su **capa de texto** (`pypdf`): un e-ticket —el de
la app del súper o el de la compra online— lo genera un ordenador y lleva el
texto exacto dentro, así que pasarle OCR sería cambiar algo perfecto por algo con
erratas. Solo si no trae texto (un **escaneo**, que no es más que una imagen por
página) se rasteriza a 300 ppp y va a Tesseract. En ambos casos se leen como
mucho `MAX_PAGINAS` (5): un ticket no tiene diez, y cada página rasterizada es
una pasada entera de OCR.

Si el archivo no se puede abrir —no es imagen ni PDF, está a medias, o el PDF
lleva contraseña— responde **400**, y el `api` lo traduce a un 400 para el
usuario en vez de a un 500.

## Requisito de sistema

Necesita el binario de Tesseract con los datos del idioma español, y **poppler**
(lo que usa `pdf2image` para rasterizar los PDF escaneados):

```bash
brew install tesseract tesseract-lang poppler    # macOS
```

Sin poppler, las imágenes y los PDF con capa de texto siguen funcionando; solo
falla el PDF escaneado. El idioma se configura con la variable `OCR_LANG` (por
defecto `spa`).

## Desarrollo

```bash
cd services/ocr-service
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/ruff check .                          # lint
.venv/bin/pytest -q                             # tests (Tesseract mockeado)
.venv/bin/uvicorn app.main:app --port 8001      # servidor en :8001
```

Los tests mockean Tesseract y poppler, así que **no** requieren los binarios
instalados. Los PDF de prueba se construyen a mano en `tests/conftest.py` (`pdf()`)
para que el camino de la capa de texto pase por `pypdf` de verdad.
