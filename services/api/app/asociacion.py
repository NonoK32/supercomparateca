"""Lógica de asociación línea↔producto y aprendizaje de alias (§5bis de la spec).

Compartido entre la ingesta de tickets (auto-asignación por alias exacto) y el
endpoint de asociación manual.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def buscar_alias(
    db: Session, supermercado_id: int, texto: str
) -> models.AliasProducto | None:
    """Alias exacto conocido para un texto en un supermercado (§5bis punto 1)."""
    return db.scalar(
        select(models.AliasProducto).where(
            models.AliasProducto.supermercado_id == supermercado_id,
            models.AliasProducto.texto_alias == texto,
        )
    )


def upsert_alias(
    db: Session, supermercado_id: int, texto: str, producto_id: int
) -> None:
    """Guarda o actualiza la asociación texto↔producto. La última confirmación
    del usuario gana (§5bis punto 4: corrección siempre disponible)."""
    alias = buscar_alias(db, supermercado_id, texto)
    if alias is None:
        db.add(
            models.AliasProducto(
                supermercado_id=supermercado_id,
                texto_alias=texto,
                producto_id=producto_id,
            )
        )
    else:
        alias.producto_id = producto_id


def recalcular_estado(ticket: models.Ticket) -> None:
    """Un ticket está `procesado` cuando todas sus líneas tienen producto."""
    if ticket.lineas and all(linea.producto_id is not None for linea in ticket.lineas):
        ticket.estado = "procesado"
    else:
        ticket.estado = "pendiente"
