import io
import os

import pytesseract
from PIL import Image


def extraer_texto(contenido: bytes, lang: str | None = None) -> str:
    """Extrae el texto de una imagen con Tesseract.

    El idioma se toma de `lang` o de la variable de entorno `OCR_LANG`
    (por defecto `spa`). Requiere el binario `tesseract` y los datos del
    idioma instalados (en macOS: `brew install tesseract tesseract-lang`).
    """
    lang = lang or os.getenv("OCR_LANG", "spa")
    imagen = Image.open(io.BytesIO(contenido))
    return pytesseract.image_to_string(imagen, lang=lang)
