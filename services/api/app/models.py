from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # "usuario" | "admin". Solo admin puede modificar/borrar los datos globales
    # (productos, supermercados) de los que dependen todos los demás.
    rol: Mapped[str] = mapped_column(String(20), default="usuario")
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Supermercado(Base):
    __tablename__ = "supermercados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_normalizado: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    categoria: Mapped[str | None] = mapped_column(String(100), default=None)
    unidad_medida: Mapped[str | None] = mapped_column(String(50), default=None)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    supermercado_id: Mapped[int] = mapped_column(ForeignKey("supermercados.id"))
    fecha_compra: Mapped[date] = mapped_column(Date)
    # Solo se guarda el texto extraído; la imagen se descarta tras el OCR.
    texto_ocr_bruto: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")

    lineas: Mapped[list["LineaTicket"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class LineaTicket(Base):
    __tablename__ = "lineas_ticket"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    texto_original: Mapped[str] = mapped_column(String(300))
    cantidad: Mapped[int] = mapped_column(default=1)
    precio_unitario: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    precio_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id"), default=None
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="lineas")


class AliasProducto(Base):
    """Aprendizaje: qué producto corresponde a un texto de ticket, por supermercado.

    El aprendizaje es compartido entre usuarios (Fase 3), pero cada uno puede
    discrepar: un alias pertenece a quien lo confirmó (`usuario_id`) y, al
    resolver un texto, el alias propio gana sobre el de la comunidad. Así la
    corrección de un usuario no le pisa el producto a los demás.

    `usuario_id` es nullable para admitir alias sin dueño (datos heredados o
    sembrados). La unicidad es por usuario: dos personas pueden mapear el mismo
    texto a productos distintos.
    """

    __tablename__ = "alias_producto"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "supermercado_id", "texto_alias", name="uq_alias_sm_texto"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    supermercado_id: Mapped[int] = mapped_column(ForeignKey("supermercados.id"))
    texto_alias: Mapped[str] = mapped_column(String(300), index=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), default=None
    )
