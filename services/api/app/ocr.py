import httpx

from .config import settings


class ArchivoNoLegible(Exception):
    """El ocr-service no ha sabido abrir el archivo (ni imagen ni PDF legible).

    Es culpa de lo que sube el usuario, no del servidor: un PDF con contraseña,
    uno a medio descargar, o cualquier otra cosa con extensión de imagen. Se
    distingue del resto de fallos del OCR para poder contestar 400 y no 500."""


class OCRClient:
    """Cliente HTTP del ocr-service. El archivo se envía, se extrae el texto y
    no se almacena en ningún sitio."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def extraer_texto(self, contenido: bytes, filename: str, content_type: str) -> str:
        resp = httpx.post(
            f"{self._base_url}/ocr",
            files={"imagen": (filename, contenido, content_type)},
            # Una foto se resuelve en segundos, pero un PDF escaneado son varias
            # páginas y cada una es una pasada entera de Tesseract. Con los 60 s
            # de antes, el ticket largo se caía por timeout justo al final.
            timeout=120.0,
        )
        if resp.status_code == httpx.codes.BAD_REQUEST:
            raise ArchivoNoLegible(resp.json().get("detail", ""))
        resp.raise_for_status()
        return resp.json()["texto"]


def get_ocr_client() -> OCRClient:
    return OCRClient(settings.ocr_service_url)
