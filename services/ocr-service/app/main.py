from fastapi import FastAPI, File, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError
from pypdf.errors import PyPdfError

from . import ocr

app = FastAPI(title="SuperComparateca OCR", version="0.1.0")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# El campo se sigue llamando `imagen` aunque ya acepte PDF: es el nombre con el
# que lo envía el api, y renombrarlo obligaría a un despliegue coordinado de los
# dos servicios a cambio de nada.
@app.post("/ocr", tags=["ocr"])
def extraer(imagen: UploadFile = File(...)):
    contenido = imagen.file.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío")
    try:
        texto = ocr.extraer_texto(contenido)
    except (UnidentifiedImageError, PyPdfError):
        # PyPdfError cubre además el PDF con contraseña, que no se puede abrir
        # aunque esté perfectamente bien formado.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El archivo no es una imagen ni un PDF legible"
        )
    return {"texto": texto}
