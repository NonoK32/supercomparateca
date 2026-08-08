from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import asociacion, deteccion, models, parsing, schemas
from ..database import get_db
from ..ocr import OCRClient, get_ocr_client
from ..seguridad import get_current_user

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=schemas.TicketRead, status_code=status.HTTP_201_CREATED)
def subir(
    imagen: UploadFile = File(...),
    supermercado_id: int | None = Form(default=None),
    fecha_compra: date | None = Form(default=None),
    db: Session = Depends(get_db),
    ocr: OCRClient = Depends(get_ocr_client),
    usuario: models.Usuario = Depends(get_current_user),
):
    """Sube la foto de un ticket y devuelve sus líneas.

    El supermercado y la fecha se deducen del propio ticket (`deteccion.py`);
    van en el papel, así que pedírselos al usuario es hacerle transcribir. Solo
    si alguno no sale se contesta **422 con la lista de lo que falta**, para que
    el cliente lo pregunte y reenvíe. En ese caso **no se crea nada**: un ticket
    a medias no se puede comparar con nada y ensuciaría el histórico.
    """
    if supermercado_id is not None:
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
    # Ni la imagen ni el texto completo se persisten. El texto solo vive en
    # memoria el tiempo de parsearlo: un ticket real lleva los 4 últimos
    # dígitos de la tarjeta, el número de fidelización, la hora exacta y la
    # caja, y nada de eso hace falta para comparar precios (minimización,
    # art. 5.1.c RGPD). De aquí solo sobreviven las líneas parseadas.

    if supermercado_id is None:
        supermercado_id = deteccion.detectar_supermercado(
            texto,
            [(sm.id, sm.nombre) for sm in db.scalars(select(models.Supermercado))],
        )
    if fecha_compra is None:
        # `hoy` en UTC y explícito: date.today() depende de la zona del
        # servidor, y el contenedor va en UTC.
        fecha_compra = deteccion.detectar_fecha(
            texto, datetime.now(timezone.utc).date()
        )

    faltan = [
        campo
        for campo, valor in (
            ("supermercado_id", supermercado_id),
            ("fecha_compra", fecha_compra),
        )
        if valor is None
    ]
    if faltan:
        # Antes se daba por buena la fecha de hoy cuando no venía. Era cómodo y
        # casi siempre falso: los tickets se suben días después de la compra, y
        # una fecha inventada no se distingue luego de una real.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "mensaje": "No he podido leer todos los datos del ticket.",
                "faltan": faltan,
            },
        )

    ticket = models.Ticket(
        usuario_id=usuario.id,
        supermercado_id=supermercado_id,
        fecha_compra=fecha_compra,
        estado="pendiente",
    )
    for linea in parsing.parsear_lineas(texto):
        nueva = models.LineaTicket(
            texto_original=linea.texto_original,
            precio_total=linea.precio_total,
        )
        nueva.producto_id = asociacion.resolver_producto(
            db, supermercado_id, linea.texto_original, usuario.id
        )
        ticket.lineas.append(nueva)

    asociacion.recalcular_estado(ticket)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=list[schemas.TicketRead])
def listar(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    return list(
        db.scalars(
            select(models.Ticket).where(models.Ticket.usuario_id == usuario.id)
        ).all()
    )


def _ticket_propio(ticket_id: int, usuario: models.Usuario, db: Session) -> models.Ticket:
    """Devuelve el ticket si pertenece al usuario; si no, 404 (no filtra existencia)."""
    ticket = db.get(models.Ticket, ticket_id)
    if ticket is None or ticket.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket no encontrado")
    return ticket


@router.get("/{ticket_id}", response_model=schemas.TicketRead)
def obtener(
    ticket_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    return _ticket_propio(ticket_id, usuario, db)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    ticket_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    ticket = _ticket_propio(ticket_id, usuario, db)
    db.delete(ticket)
    db.commit()
