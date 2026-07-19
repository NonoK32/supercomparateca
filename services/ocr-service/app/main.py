from fastapi import FastAPI, File, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError

from . import ocr

app = FastAPI(title="SuperComparateca OCR", version="0.1.0")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.post("/ocr", tags=["ocr"])
def extraer(imagen: UploadFile = File(...)):
    contenido = imagen.file.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La imagen está vacía")
    try:
        texto = ocr.extraer_texto(contenido)
    except UnidentifiedImageError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El archivo no es una imagen válida"
        )
    return {"texto": texto}
