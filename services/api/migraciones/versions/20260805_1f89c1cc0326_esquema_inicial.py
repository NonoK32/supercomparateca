"""Esquema inicial: el que ya existía cuando se adoptó Alembic.

Esta revisión es la línea base. Refleja `app/models.py` tal y como quedó tras la
EPIC 11 (`usuarios.rol` y `alias_producto.usuario_id` incluidos), que es lo que
hasta ahora creaba `Base.metadata.create_all` al arrancar la app.

En una base de datos que YA tiene estas tablas (producción) no hay que aplicarla:
hay que marcarla como aplicada sin ejecutarla, con `alembic stamp head`. Ver el
runbook de producción.

Revision ID: 1f89c1cc0326
Revises:
Create Date: 2026-08-05 13:05:28.144604
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f89c1cc0326"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_normalizado", sa.String(length=200), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=True),
        sa.Column("unidad_medida", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_productos_nombre_normalizado", "productos", ["nombre_normalizado"], unique=True
    )

    op.create_table(
        "supermercados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supermercados_nombre", "supermercados", ["nombre"], unique=True)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("rol", sa.String(length=20), nullable=False),
        # sa.func.now() y no un literal: se traduce a now() en PostgreSQL y a
        # CURRENT_TIMESTAMP en SQLite, así la migración vale en ambos.
        sa.Column(
            "fecha_registro",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "alias_producto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("supermercado_id", sa.Integer(), nullable=False),
        sa.Column("texto_alias", sa.String(length=300), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["supermercado_id"], ["supermercados.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "usuario_id", "supermercado_id", "texto_alias", name="uq_alias_sm_texto"
        ),
    )
    op.create_index(
        "ix_alias_producto_texto_alias", "alias_producto", ["texto_alias"], unique=False
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("supermercado_id", sa.Integer(), nullable=False),
        sa.Column("fecha_compra", sa.Date(), nullable=False),
        sa.Column("texto_ocr_bruto", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["supermercado_id"], ["supermercados.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "lineas_ticket",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("texto_original", sa.String(length=300), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("precio_total", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("lineas_ticket")
    op.drop_table("tickets")
    op.drop_index("ix_alias_producto_texto_alias", table_name="alias_producto")
    op.drop_table("alias_producto")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_index("ix_supermercados_nombre", table_name="supermercados")
    op.drop_table("supermercados")
    op.drop_index("ix_productos_nombre_normalizado", table_name="productos")
    op.drop_table("productos")
