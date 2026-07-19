"""Consultas de precios sobre el histórico (FR7 comparativa, FR8 evolución).

El histórico son las `LineaTicket` asociadas a un producto, unidas a su `Ticket`
(fecha y supermercado). El volumen es pequeño (app personal), así que la
agregación se hace en Python sobre una única query.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def _filas(db: Session, producto_id: int):
    """(supermercado_id, nombre, fecha_compra, precio_total) de un producto,
    ordenadas por fecha ascendente."""
    return db.execute(
        select(
            models.Ticket.supermercado_id,
            models.Supermercado.nombre,
            models.Ticket.fecha_compra,
            models.LineaTicket.precio_total,
        )
        .join(models.Ticket, models.LineaTicket.ticket_id == models.Ticket.id)
        .join(
            models.Supermercado,
            models.Ticket.supermercado_id == models.Supermercado.id,
        )
        .where(models.LineaTicket.producto_id == producto_id)
        .order_by(models.Ticket.fecha_compra, models.LineaTicket.id)
    ).all()


def precios_por_supermercado(db: Session, producto_id: int) -> list[dict]:
    """Precio más reciente por supermercado (FR7). Ordenado por precio ascendente."""
    por_sm: dict[int, dict] = {}
    for fila in _filas(db, producto_id):
        entrada = por_sm.setdefault(
            fila.supermercado_id,
            {
                "supermercado_id": fila.supermercado_id,
                "supermercado": fila.nombre,
                "precio_actual": fila.precio_total,
                "fecha": fila.fecha_compra,
                "num_observaciones": 0,
            },
        )
        entrada["num_observaciones"] += 1
        # Las filas vienen ordenadas por fecha ascendente: la última gana.
        entrada["precio_actual"] = fila.precio_total
        entrada["fecha"] = fila.fecha_compra
    return sorted(por_sm.values(), key=lambda e: e["precio_actual"])


def historico(
    db: Session, producto_id: int, supermercado_id: int | None = None
) -> list[dict]:
    """Serie temporal de precios (FR8), opcionalmente filtrada por supermercado."""
    puntos = []
    for fila in _filas(db, producto_id):
        if supermercado_id is not None and fila.supermercado_id != supermercado_id:
            continue
        puntos.append(
            {
                "fecha": fila.fecha_compra,
                "precio": fila.precio_total,
                "supermercado_id": fila.supermercado_id,
                "supermercado": fila.nombre,
            }
        )
    return puntos
