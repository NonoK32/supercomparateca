from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import asociacion, models, parsing, schemas
from ..database import get_db
from ..ocr import OCRClient, get_ocr_client

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=schemas.TicketRead, status_code=status.HTTP_201_CREATED)
def subir(
    supermercado_id: int = Form(...),
    imagen: UploadFile = File(...),
    fecha_compra: date | None = Form(default=None),
    db: Session = Depends(get_db),
    ocr: OCRClient = Depends(get_ocr_client),
):
    supermercado = db.get(models.Supermercado, supermercado_id)
    if supermercado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supermercado no encontrado")

    contenido = imagen.file.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La imagen está vacía")

    texto = ocr.extraer_texto(
        contenido,
        imagen.filename or "ticket",
        imagen.content_type or "application/octet-stream",
    )
    # La imagen ya no se necesita: solo persiste el texto extraído.

    ticket = models.Ticket(
        supermercado_id=supermercado_id,
        fecha_compra=fecha_compra or date.today(),
        texto_ocr_bruto=texto,
        estado="pendiente",
    )
    for linea in parsing.parsear_lineas(texto):
        nueva = models.LineaTicket(
            texto_original=linea.texto_original,
            precio_total=linea.precio_total,
        )
        # §5bis punto 1: si ya hay alias exacto para este supermercado, se
        # asigna el producto automáticamente (sin preguntar).
        alias = asociacion.buscar_alias(db, supermercado_id, linea.texto_original)
        if alias is not None:
            nueva.producto_id = alias.producto_id
        ticket.lineas.append(nueva)

    asociacion.recalcular_estado(ticket)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=list[schemas.TicketRead])
def listar(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Ticket)).all())


@router.get("/{ticket_id}", response_model=schemas.TicketRead)
def obtener(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(models.Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket no encontrado")
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(models.Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket no encontrado")
    db.delete(ticket)
    db.commit()
