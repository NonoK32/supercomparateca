"""minimiza datos personales del ticket

Dos cambios, los dos por proteccion de datos:

1. Se ELIMINA `tickets.texto_ocr_bruto`. Guardaba el texto integro del ticket,
   que en uno real incluye los 4 ultimos digitos de la tarjeta, el numero de
   fidelizacion, la hora exacta, la tienda y la caja. La spec decia que no
   guardar la imagen protegia la privacidad, pero el texto conservaba lo mismo
   en otro formato. Ninguna funcionalidad lo leia: solo se escribia y se
   devolvia en la respuesta. Minimizacion (art. 5.1.c RGPD).

   OJO: este upgrade DESTRUYE ese texto y no hay vuelta atras. Es
   intencionado. Si hiciera falta conservarlo, sacarlo del backup ANTES.

2. `tickets.usuario_id` pasa a ser NULLABLE, para el borrado de cuenta
   (art. 17). Al borrarse, los tickets se desvinculan en vez de eliminarse:
   los precios son un bien compartido y borrarlos degradaria la comparativa de
   todos, mientras que sin dueño dejan de ser datos personales.

Revision ID: 01233e7e156c
Revises: 1f89c1cc0326
Create Date: 2026-08-06 17:06:28.657470

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '01233e7e156c'
down_revision: str | Sequence[str] | None = '1f89c1cc0326'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table para que el ALTER funcione tambien en SQLite (dev),
    # donde se recrea la tabla; en PostgreSQL son ALTER normales.
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.alter_column('usuario_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_column('texto_ocr_bruto')


def downgrade() -> None:
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        # Nullable, al reves que en el esquema original: el texto se borro y no
        # se puede recuperar, asi que no hay ningun valor con el que rellenar
        # las filas existentes. Con nullable=False esto fallaria en cualquier
        # tabla que ya tenga tickets.
        batch_op.add_column(sa.Column('texto_ocr_bruto', sa.TEXT(), nullable=True))
        # usuario_id NO se devuelve a NOT NULL: si ya hay tickets desvinculados
        # por un borrado de cuenta, restaurar la restriccion fallaria. Volver
        # atras de verdad exigiria decidir que hacer con esos tickets huerfanos,
        # y esa decision no puede tomarla una migracion.
