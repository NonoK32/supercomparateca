from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


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
    # Se asocia en EPIC 3 (asociación manual línea↔producto).
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id"), default=None
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="lineas")
