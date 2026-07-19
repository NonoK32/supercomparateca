import httpx

from .config import settings


class OCRClient:
    """Cliente HTTP del ocr-service. La imagen se envía, se extrae el texto y
    no se almacena en ningún sitio."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def extraer_texto(self, contenido: bytes, filename: str, content_type: str) -> str:
        resp = httpx.post(
            f"{self._base_url}/ocr",
            files={"imagen": (filename, contenido, content_type)},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["texto"]


def get_ocr_client() -> OCRClient:
    return OCRClient(settings.ocr_service_url)
