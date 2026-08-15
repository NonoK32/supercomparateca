"""Borrado de cuentas.

Vive aparte porque lo hacen dos sitios —el propio usuario (`DELETE /auth/me`,
art. 17 RGPD) y un admin desde el panel— y lo que se conserva y lo que se
destruye es una decisión de diseño, no un detalle de cada endpoint. Duplicarla
es la forma segura de que las dos copias acaben divergiendo.
"""

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from . import models


def borrar(db: Session, usuario: models.Usuario) -> None:
    """Borra la cuenta conservando el histórico de precios.

    Los **tickets no se borran, se desvinculan** (`usuario_id = NULL`). Los
    precios son un bien compartido: eliminarlos degradaría la comparativa de
    todos los demás, y una vez sin dueño dejan de ser datos personales. Nadie
    vuelve a tener acceso a ellos, porque `_ticket_propio` exige coincidencia de
    usuario y NULL no coincide con nadie.

    Los **alias sí se borran**: son aprendizaje personal, no histórico de
    precios, y no hay nada que dependa de ellos (las líneas apuntan al producto,
    no al alias).

    No hace commit: lo hace quien llama, para que la comprobación previa y el
    borrado entren en la misma transacción.
    """
    db.execute(
        update(models.Ticket)
        .where(models.Ticket.usuario_id == usuario.id)
        .values(usuario_id=None)
    )
    db.execute(
        delete(models.AliasProducto).where(models.AliasProducto.usuario_id == usuario.id)
    )
    db.delete(usuario)
