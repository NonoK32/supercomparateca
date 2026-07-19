from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import asociacion, models, schemas
from ..database import get_db
from ..seguridad import get_current_user

router = APIRouter(prefix="/lineas", tags=["lineas"])


@router.post("/{linea_id}/asociar", response_model=schemas.LineaTicketRead)
def asociar(
    linea_id: int,
    payload: schemas.AsociarRequest,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    linea = db.get(models.LineaTicket, linea_id)
    # 404 también si la línea es de un ticket de otro usuario (no filtra existencia).
    if linea is None or linea.ticket.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")

    if payload.producto_id is not None:
        producto = db.get(models.Producto, payload.producto_id)
        if producto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    else:
        # Crear o reutilizar por nombre_normalizado (FR5: "o crear uno nuevo").
        datos = payload.nuevo_producto
        producto = db.scalar(
            select(models.Producto).where(
                models.Producto.nombre_normalizado == datos.nombre_normalizado
            )
        )
        if producto is None:
            producto = models.Producto(**datos.model_dump())
            db.add(producto)
            db.flush()  # asigna producto.id

    linea.producto_id = producto.id
    ticket = linea.ticket
    asociacion.upsert_alias(
        db, ticket.supermercado_id, linea.texto_original, producto.id
    )
    asociacion.recalcular_estado(ticket)

    db.commit()
    db.refresh(linea)
    return linea
