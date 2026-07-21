"""Consultas de precios sobre el histórico (FR7 comparativa, FR8 evolución).

El histórico son las `LineaTicket` asociadas a un producto, unidas a su `Ticket`
(fecha y supermercado). El volumen es pequeño (app personal), así que la
agregación se hace en Python sobre una única query.
"""

from decimal import Decimal

from sqlalchemy import func, select
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


def cesta_habitual(db: Session, usuario_id: int, limite: int = 10) -> list[dict]:
    """Los productos que este usuario compra más a menudo (FR10).

    "Habitual" = número de veces que aparece en sus tickets. Se deriva del
    histórico, así que no hay ninguna cesta que mantener a mano.
    """
    filas = db.execute(
        select(
            models.LineaTicket.producto_id,
            models.Producto.nombre_normalizado,
            func.count(models.LineaTicket.id).label("veces"),
        )
        .join(models.Ticket, models.LineaTicket.ticket_id == models.Ticket.id)
        .join(models.Producto, models.LineaTicket.producto_id == models.Producto.id)
        .where(models.Ticket.usuario_id == usuario_id)
        .group_by(models.LineaTicket.producto_id, models.Producto.nombre_normalizado)
        .order_by(func.count(models.LineaTicket.id).desc(), models.Producto.nombre_normalizado)
        .limit(limite)
    ).all()
    return [
        {
            "producto_id": fila.producto_id,
            "nombre_normalizado": fila.nombre_normalizado,
            "veces_comprado": fila.veces,
        }
        for fila in filas
    ]


def comparativa_cesta(db: Session, usuario_id: int, limite: int = 10) -> dict:
    """Coste total de la cesta habitual en cada supermercado (FR10).

    Los precios son los del histórico **compartido** (Fase 3): se usa el más
    reciente de cada producto en cada supermercado, venga del ticket de quien
    venga. Un supermercado rara vez tiene precio de todos los productos, así
    que se informa de `productos_cubiertos`: sin eso, el que solo tiene dos
    productos parecería el más barato. Por eso el orden es cobertura primero,
    y a igual cobertura el total más bajo.
    """
    cesta = cesta_habitual(db, usuario_id, limite)

    totales: dict[int, dict] = {}
    for item in cesta:
        for precio in precios_por_supermercado(db, item["producto_id"]):
            entrada = totales.setdefault(
                precio["supermercado_id"],
                {
                    "supermercado_id": precio["supermercado_id"],
                    "supermercado": precio["supermercado"],
                    "total": Decimal("0"),
                    "productos_cubiertos": 0,
                },
            )
            entrada["total"] += precio["precio_actual"]
            entrada["productos_cubiertos"] += 1

    supermercados = sorted(
        totales.values(),
        key=lambda e: (-e["productos_cubiertos"], e["total"]),
    )
    return {"productos": cesta, "supermercados": supermercados}


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
