"""Lógica de asociación línea↔producto y aprendizaje de alias (§5bis de la spec).

Compartido entre la ingesta de tickets (auto-asignación por alias exacto) y el
endpoint de asociación manual.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import matching, models


def buscar_alias(
    db: Session, supermercado_id: int, texto: str, usuario_id: int
) -> models.AliasProducto | None:
    """Alias exacto para un texto en un supermercado (§5bis punto 1).

    El alias propio del usuario gana; si no tiene ninguno, se usa el de la
    comunidad (Fase 3: el aprendizaje se comparte, pero cada uno puede
    discrepar). Entre alias ajenos gana el más reciente.
    """
    base = select(models.AliasProducto).where(
        models.AliasProducto.supermercado_id == supermercado_id,
        models.AliasProducto.texto_alias == texto,
    )
    propio = db.scalar(base.where(models.AliasProducto.usuario_id == usuario_id))
    if propio is not None:
        return propio
    return db.scalar(base.order_by(models.AliasProducto.id.desc()))


def resolver_producto(
    db: Session, supermercado_id: int, texto: str, usuario_id: int
) -> int | None:
    """Producto que corresponde a un texto de ticket, sin intervención del usuario.

    Aplica §5bis en orden: alias exacto (punto 1) y, si no lo hay, el alias más
    parecido si supera el umbral automático (punto 3). Si ninguno convence,
    devuelve `None` y la línea queda pendiente de confirmación (punto 2); las
    sugerencias de la zona dudosa se consultan aparte, vía
    `GET /lineas/{id}/sugerencias`.
    """
    alias = buscar_alias(db, supermercado_id, texto, usuario_id)
    if alias is not None:
        return alias.producto_id

    candidato = matching.mejor_candidato_automatico(
        db, supermercado_id, texto, usuario_id
    )
    return candidato.producto_id if candidato is not None else None


def upsert_alias(
    db: Session, supermercado_id: int, texto: str, producto_id: int, usuario_id: int
) -> None:
    """Guarda o actualiza la asociación texto↔producto **del usuario**.

    La última confirmación gana (§5bis punto 4), pero solo sobre su propio
    alias: corregir nunca le cambia el producto a otro usuario.
    """
    propio = db.scalar(
        select(models.AliasProducto).where(
            models.AliasProducto.supermercado_id == supermercado_id,
            models.AliasProducto.texto_alias == texto,
            models.AliasProducto.usuario_id == usuario_id,
        )
    )
    if propio is None:
        db.add(
            models.AliasProducto(
                supermercado_id=supermercado_id,
                texto_alias=texto,
                producto_id=producto_id,
                usuario_id=usuario_id,
            )
        )
    else:
        propio.producto_id = producto_id


def recalcular_estado(ticket: models.Ticket) -> None:
    """Un ticket está `procesado` cuando todas sus líneas tienen producto."""
    if ticket.lineas and all(linea.producto_id is not None for linea in ticket.lineas):
        ticket.estado = "procesado"
    else:
        ticket.estado = "pendiente"
