from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import asociacion, matching, models, schemas
from ..database import get_db
from ..seguridad import get_current_user

router = APIRouter(prefix="/lineas", tags=["lineas"])


def _linea_propia(
    linea_id: int, usuario: models.Usuario, db: Session
) -> models.LineaTicket:
    """Devuelve la línea si es de un ticket del usuario; si no, 404 (no filtra
    existencia)."""
    linea = db.get(models.LineaTicket, linea_id)
    if linea is None or linea.ticket.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    return linea


@router.get("/{linea_id}/sugerencias", response_model=list[schemas.SugerenciaProducto])
def sugerencias(
    linea_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    """Productos parecidos al texto de la línea, de más a menos probable (§5bis
    punto 3). Se calculan al vuelo: así reflejan siempre los alias actuales."""
    linea = _linea_propia(linea_id, usuario, db)
    candidatos = matching.buscar_similares(
        db, linea.ticket.supermercado_id, linea.texto_original
    )
    return [
        schemas.SugerenciaProducto(
            producto_id=c.producto_id,
            nombre_normalizado=db.get(models.Producto, c.producto_id).nombre_normalizado,
            texto_alias=c.texto_alias,
            score=round(c.score, 3),
        )
        for c in candidatos
    ]


@router.post("/{linea_id}/asociar", response_model=schemas.LineaTicketRead)
def asociar(
    linea_id: int,
    payload: schemas.AsociarRequest,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    linea = _linea_propia(linea_id, usuario, db)

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
