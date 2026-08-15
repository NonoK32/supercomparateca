import io
import os

import pdf2image
import pypdf
import pytesseract
from PIL import Image

# Tope de paginas de un PDF. Un ticket ocupa una o dos; de ahi en adelante o no
# es un ticket o es un PDF con el que no merece la pena quemar CPU, porque cada
# pagina rasterizada es una pasada entera de Tesseract.
MAX_PAGINAS = 5

# Por debajo de esto se da por hecho que el PDF no trae capa de texto util: un
# escaneo suele devolver cero caracteres, o cuatro sueltos de algun membrete.
MIN_CARACTERES = 30

# Tesseract quiere unos 300 ppp para leer letra pequeña, y la de un ticket lo
# es. Los 200 por defecto de pdf2image se comen decimales de los precios.
PPP = 300


def extraer_texto(contenido: bytes, lang: str | None = None) -> str:
    """Extrae el texto de un ticket, sea imagen o PDF.

    El idioma se toma de `lang` o de la variable de entorno `OCR_LANG`
    (por defecto `spa`). Requiere el binario `tesseract` y los datos del
    idioma instalados, y `poppler` para los PDF escaneados (en macOS:
    `brew install tesseract tesseract-lang poppler`).
    """
    lang = lang or os.getenv("OCR_LANG", "spa")
    if contenido.startswith(b"%PDF-"):
        return _texto_de_pdf(contenido, lang)
    imagen = Image.open(io.BytesIO(contenido))
    return pytesseract.image_to_string(imagen, lang=lang)


def _texto_de_pdf(contenido: bytes, lang: str) -> str:
    """Primero la capa de texto del PDF; si no la trae, se rasteriza y va al OCR.

    Un e-ticket (el de la app del super, el de la compra online) lo genera un
    ordenador y lleva el texto exacto dentro: pasarle OCR seria cambiar algo
    perfecto por algo con erratas. Uno escaneado, en cambio, no es mas que una
    imagen por pagina metida en un PDF, y ahi no hay otra que el OCR.
    """
    lector = pypdf.PdfReader(io.BytesIO(contenido))
    texto = "\n".join(
        pagina.extract_text() or "" for pagina in lector.pages[:MAX_PAGINAS]
    )
    if len(texto.strip()) >= MIN_CARACTERES:
        return texto

    paginas = pdf2image.convert_from_bytes(contenido, dpi=PPP, last_page=MAX_PAGINAS)
    return "\n".join(pytesseract.image_to_string(p, lang=lang) for p in paginas)
